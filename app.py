import os
import json
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st
from google import genai
from google.genai import types

# -------------------------------------------------------------
# 1. SETUP & CREDENTIALS
# -------------------------------------------------------------
st.set_page_config(page_title="FPL AI Strategist", page_icon="⚽", layout="wide")
st.title("⚽ FPL AI Strategist")

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
MY_TEAM_ID = 3325156
MY_FAVORITE_CLUB = "Manchester United"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
LOCAL_BACKUP_FILE = "chat_store.json"

LEAGUES_DICT = {
    "Crazy Football Fans (Primary)": 987870,
    "Explosive": 140555,
    "The Road To": 684844,
    "India": 120,
    "Man Utd": 16,
    "Overall": 314,
    "Jio Star League": 1234984
}

# -------------------------------------------------------------
# 2. PERSISTENT GIST STORAGE
# -------------------------------------------------------------
def get_gist_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FPL-Agent"
    }

def find_or_create_gist():
    if not GITHUB_TOKEN:
        return None
    url = "https://api.github.com/gists"
    try:
        r = requests.get(url, headers=get_gist_headers())
        if r.status_code == 200:
            for g in r.json():
                if "fpl_chat_store.json" in g.get("files", {}):
                    return g["id"]
            create_payload = {
                "description": "FPL Agent Persistent Chat Memory",
                "public": False,
                "files": {"fpl_chat_store.json": {"content": "{}"}}
            }
            res = requests.post(url, headers=get_gist_headers(), json=create_payload)
            if res.status_code == 201:
                return res.json()["id"]
    except Exception:
        pass
    return None

GIST_ID = find_or_create_gist()

def load_all_threads():
    if GIST_ID and GITHUB_TOKEN:
        try:
            url = f"https://api.github.com/gists/{GIST_ID}"
            r = requests.get(url, headers=get_gist_headers())
            if r.status_code == 200:
                raw_content = r.json()["files"]["fpl_chat_store.json"]["content"]
                return json.loads(raw_content)
        except Exception:
            pass
    if os.path.exists(LOCAL_BACKUP_FILE):
        try:
            with open(LOCAL_BACKUP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_all_threads(threads):
    payload_str = json.dumps(threads, indent=2)
    if GIST_ID and GITHUB_TOKEN:
        try:
            url = f"https://api.github.com/gists/{GIST_ID}"
            patch_data = {"files": {"fpl_chat_store.json": {"content": payload_str}}}
            requests.patch(url, headers=get_gist_headers(), json=patch_data)
        except Exception:
            pass
    try:
        with open(LOCAL_BACKUP_FILE, "w", encoding="utf-8") as f:
            f.write(payload_str)
    except Exception:
        pass

# -------------------------------------------------------------
# 3. ADVANCED STATS, DEADLINES & SCOUTING ENGINE
# -------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_base_fpl_data():
    boot = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", headers=HEADERS).json()
    teams_map = {t["id"]: t["name"] for t in boot["teams"]}
    teams_short = {t["id"]: t["short_name"] for t in boot["teams"]}

    # Deadline Logic
    now_utc = datetime.now(timezone.utc)
    target_gw = 38
    is_live_matchday = False

    for event in boot["events"]:
        deadline_dt = datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))
        if now_utc < deadline_dt:
            target_gw = event["id"]
            break

    active_or_last_gw = max(1, target_gw - 1)
    for event in boot["events"]:
        if event["id"] == active_or_last_gw and event.get("is_current") and not event.get("finished"):
            is_live_matchday = True
            break

    # Fixtures & FDR
    fixtures_raw = requests.get("https://fantasy.premierleague.com/api/fixtures/?future=1", headers=HEADERS).json()
    team_fixtures = {t["name"]: [] for t in boot["teams"]}
    lookahead_gws = list(range(target_gw, target_gw + 4))

    for f in fixtures_raw:
        if f.get("event") in lookahead_gws:
            h_team = teams_map[f["team_h"]]
            a_team = teams_map[f["team_a"]]
            team_fixtures[h_team].append({"gw": f["event"], "opp": teams_short[f["team_a"]], "home": True, "fdr": f["team_h_difficulty"]})
            team_fixtures[a_team].append({"gw": f["event"], "opp": teams_short[f["team_h"]], "home": False, "fdr": f["team_a_difficulty"]})

    # Player Registry & 3GW xP Projections
    all_players_pool = []
    elements_detail = {}
    price_risers = []
    price_fallers = []

    for p in boot["elements"]:
        pos_str = ["GK", "DEF", "MID", "FWD"][p["element_type"] - 1]
        cost = p["now_cost"] / 10
        cost_change = p.get("cost_change_event", 0) / 10
        price_symbol = f"▲ +£{cost_change:.1f}m" if cost_change > 0 else (f"▼ -£{abs(cost_change):.1f}m" if cost_change < 0 else "—")
        
        if cost_change > 0: price_risers.append(f"{p['web_name']} ({price_symbol})")
        if cost_change < 0: price_fallers.append(f"{p['web_name']} ({price_symbol})")

        form_val = float(p.get("form", 0.0) or 0.0)
        xgi_val = float(p.get("expected_goal_involvements", 0.0) or 0.0)
        club_name = teams_map.get(p["team"], "Unknown")

        # 3GW xP Calculation
        upcoming = team_fixtures.get(club_name, [])[:3]
        fdr_weights = {1: 1.3, 2: 1.15, 3: 1.0, 4: 0.85, 5: 0.7}
        projected_3gw_xp = 0.0
        for fix in upcoming:
            mult = fdr_weights.get(fix.get("fdr", 3), 1.0)
            base_xp = form_val * 0.6 + (xgi_val * 1.5)
            projected_3gw_xp += max(1.5, base_xp * mult)

        player_dict = {
            "id": p["id"],
            "name": p["web_name"],
            "club": club_name,
            "club_short": teams_short.get(p["team"], "UNK"),
            "pos": pos_str,
            "cost": cost,
            "price_delta": price_symbol,
            "form": form_val,
            "points": p.get("total_points", 0),
            "event_points": p.get("event_points", 0),
            "xGI": xgi_val,
            "selected_by": p.get("selected_by_percent", "0.0"),
            "xp_3gw": round(projected_3gw_xp, 1)
        }
        elements_detail[p["id"]] = player_dict
        all_players_pool.append(player_dict)

    # User Squad Detail & History
    my_picks = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/event/{active_or_last_gw}/picks/", headers=HEADERS).json()
    my_entry = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/", headers=HEADERS).json()
    my_history = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/history/", headers=HEADERS).json()

    # Free Transfers Calc
    free_transfers_available = 1
    recent_history = my_history.get("current", [])
    if recent_history:
        last_gw_stat = recent_history[-1]
        free_transfers_available = min(5, max(1, 1 if last_gw_stat.get("event_transfers", 0) > 0 else 2))

    # Active Chips Tracking
    chips_used = [c["name"] for c in my_history.get("chips", [])]

    my_squad = []
    pitch_data = {"GK": [], "DEF": [], "MID": [], "FWD": [], "BENCH": []}

    for p in my_picks.get("picks", []):
        info = elements_detail.get(p["element"], {})
        is_starter = p["position"] <= 11
        badge = "(C)" if p["is_captain"] else ("(V)" if p["is_vice_captain"] else "")
        
        card = {
            "name": info.get("name", "Unknown"),
            "club": info.get("club_short", "UNK"),
            "pos": info.get("pos"),
            "points": info.get("event_points", 0),
            "badge": badge,
            "cost": f"£{info.get('cost', 0.0)}m",
            "price_delta": info.get("price_delta", "—"),
            "form": info.get("form"),
            "xGI": info.get("xGI"),
            "3GW_xP": info.get("xp_3gw"),
            "starter": is_starter
        }
        my_squad.append(card)
        if is_starter:
            pitch_data[info.get("pos", "MID")].append(card)
        else:
            pitch_data["BENCH"].append(card)

    formation = f"{len(pitch_data['DEF'])}-{len(pitch_data['MID'])}-{len(pitch_data['FWD'])}"

    # Premier League Standings
    pl_standings = []
    for t in boot["teams"]:
        pl_standings.append({
            "Pos": t["position"], "Club": t["name"], "P": t.get("played", 0),
            "W": t.get("win", 0), "D": t.get("draw", 0), "L": t.get("loss", 0),
            "GD": t.get("strength_overall_home", 0) - t.get("strength_overall_away", 0),
            "Pts": t.get("points", 0)
        })
    pl_standings = sorted(pl_standings, key=lambda x: x["Pos"])

    # World Leader
    wl_standings = requests.get("https://fantasy.premierleague.com/api/leagues-classic/314/standings/", headers=HEADERS).json()
    world_leader = wl_standings["standings"]["results"][0]

    return {
        "target_gw": target_gw,
        "active_or_last_gw": active_or_last_gw,
        "is_live_matchday": is_live_matchday,
        "team_name": my_entry.get("name"),
        "manager_name": f"{my_entry.get('player_first_name')} {my_entry.get('player_last_name')}",
        "total_points": my_entry.get("summary_overall_points"),
        "latest_gw_points": my_picks.get("entry_history", {}).get("points", 0),
        "overall_rank": my_entry.get("summary_overall_rank"),
        "bank": my_picks.get("entry_history", {}).get("bank", 0) / 10,
        "free_transfers": free_transfers_available,
        "chips_used": chips_used,
        "formation": formation,
        "pitch_data": pitch_data,
        "squad": my_squad,
        "price_risers": price_risers[:6],
        "price_fallers": price_fallers[:6],
        "world_leader": {
            "name": world_leader["player_name"],
            "team": world_leader["entry_name"],
            "points": world_leader["total"],
            "gw_points": world_leader["event_total"]
        },
        "pl_table": pl_standings,
        "scouting_radar": {
            "top_xp_forwards": sorted([p for p in all_players_pool if p["pos"] == "FWD"], key=lambda x: x["xp_3gw"], reverse=True)[:6],
            "top_xp_midfielders": sorted([p for p in all_players_pool if p["pos"] == "MID"], key=lambda x: x["xp_3gw"], reverse=True)[:8],
            "top_xp_defenders": sorted([p for p in all_players_pool if p["pos"] == "DEF"], key=lambda x: x["xp_3gw"], reverse=True)[:6],
            "differentials": [p for p in all_players_pool if p["xGI"] >= 1.5 and float(p["selected_by"]) < 10.0][:6]
        }
    }

@st.cache_data(ttl=300)
def fetch_mini_league_table(league_id: int):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    res = requests.get(url, headers=HEADERS).json()
    league_name = res.get("league", {}).get("name", "Mini-League")
    results = res.get("standings", {}).get("results", [])

    table_rows = []
    user_in_top5 = False

    for m in results[:5]:
        is_user = (m["entry"] == MY_TEAM_ID)
        if is_user:
            user_in_top5 = True
        table_rows.append({
            "Rank": f"#{m['rank']}",
            "Team": m["entry_name"] + (" (You)" if is_user else ""),
            "Manager": m["player_name"],
            "GW": m["event_total"],
            "Total": m["total"],
            "entry_id": m["entry"]
        })

    if not user_in_top5 and results:
        user_entry = next((m for m in results if m["entry"] == MY_TEAM_ID), None)
        if user_entry:
            table_rows.append({"Rank": "---", "Team": "---------", "Manager": "---------", "GW": "-", "Total": "-", "entry_id": None})
            table_rows.append({
                "Rank": f"#{user_entry['rank']}",
                "Team": f"{user_entry['entry_name']} (You)",
                "Manager": user_entry["player_name"],
                "GW": user_entry["event_total"],
                "Total": user_entry["total"],
                "entry_id": user_entry["entry"]
            })

    leader_entry = results[0]["entry"] if results else None
    return league_name, table_rows, leader_entry

data = fetch_base_fpl_data()
target_gw = data["target_gw"]
last_gw = data["active_or_last_gw"]

# -------------------------------------------------------------
# 4. SIDEBAR DASHBOARD
# -------------------------------------------------------------
saved_threads = load_all_threads()
if not saved_threads:
    default_thread = f"GW {target_gw} Strategy"
    saved_threads[default_thread] = []
    save_all_threads(saved_threads)

with st.sidebar:
    if data["is_live_matchday"]:
        st.header(f"⚽ Live: GW {last_gw}")
        st.caption(f"Targeting: **Gameweek {target_gw}**")
    else:
        st.header(f"🎯 Gameweek {target_gw}")
        st.caption(f"Manager: **{data['manager_name']}** | Team: **{data['team_name']}**")

    # Manager Metrics Grid
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total Points", data['total_points'])
        st.metric("Overall Rank", f"{data['overall_rank']:,}")
    with c2:
        st.metric("Free Transfers", f"{data['free_transfers']} FT")
        st.metric("Bank Balance", f"£{data['bank']}m")

    # Compact World #1 Bar
    st.info(f"🌍 **World #1 Leader:** {data['world_leader']['name']} ({data['world_leader']['team']}) — **{data['world_leader']['points']} pts** (GW: {data['world_leader']['gw_points']})")

    # Mini-League Selector & Leaderboard
    st.subheader("🏆 Mini-League Leaderboard")
    selected_league_label = st.selectbox("Select Mini-League:", list(LEAGUES_DICT.keys()), index=0)
    selected_league_id = LEAGUES_DICT[selected_league_label]

    league_name, league_table, leader_entry_id = fetch_mini_league_table(selected_league_id)
    st.caption(f"Standings for **{league_name}**")
    
    clean_df = pd.DataFrame(league_table)
    if "entry_id" in clean_df.columns:
        clean_df = clean_df.drop(columns=["entry_id"])
    st.dataframe(clean_df, hide_index=True, use_container_width=True)

    st.divider()

    # Price Movement Radar
    st.subheader("📈 Price Movement Radar")
    if data["price_risers"]:
        st.caption("🔥 Recent Risers: " + ", ".join(data["price_risers"]))
    if data["price_fallers"]:
        st.caption("❄️ Recent Fallers: " + ", ".join(data["price_fallers"]))

    st.divider()

    # Conversation Threads
    st.subheader("💬 Conversation Threads")
    thread_names = list(saved_threads.keys())
    selected_thread = st.selectbox("Switch Thread:", thread_names, index=len(thread_names) - 1)

    new_thread_input = st.text_input("New Thread Name:", placeholder=f"e.g., GW {target_gw} Wildcard")
    if st.button("➕ Create Thread", use_container_width=True) and new_thread_input.strip():
        new_name = new_thread_input.strip()
        if new_name not in saved_threads:
            saved_threads[new_name] = []
            save_all_threads(saved_threads)
            st.rerun()

# -------------------------------------------------------------
# 5. VISUAL PITCH FORMATION COMPONENT (EXPANDABLE)
# -------------------------------------------------------------
def render_player_badge(card):
    badge_html = f"<span style='color: #00ff87; font-weight: bold;'>{card['badge']}</span>" if card['badge'] else ""
    return f"""
    <div style="background: rgba(255,255,255,0.92); border-radius: 6px; padding: 4px 6px; margin: 2px auto; text-align: center; max-width: 110px; box-shadow: 0 2px 4px rgba(0,0,0,0.25);">
        <div style="font-size: 11px; font-weight: 700; color: #111; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{card['name']} {badge_html}</div>
        <div style="font-size: 9px; color: #555;">{card['club']} • {card['cost']}</div>
        <div style="background: #37003c; color: #00ff87; font-size: 10px; font-weight: 800; border-radius: 3px; margin-top: 2px;">{card['points']} pts</div>
    </div>
    """

with st.expander("🏟️ View Active Lineup Pitch (FPL Formation: " + data["formation"] + ")", expanded=False):
    st.markdown("""
    <style>
    .pitch-container {
        background: linear-gradient(180deg, #1f8a4c 0%, #15733d 50%, #0d5c2e 100%);
        border: 2px solid #ffffff;
        border-radius: 12px;
        padding: 16px 8px;
        margin-bottom: 12px;
    }
    .pitch-row {
        display: flex;
        justify-content: space-around;
        align-items: center;
        margin: 10px 0;
    }
    .bench-dugout {
        background: rgba(15, 30, 20, 0.85);
        border: 1px dashed #00ff87;
        border-radius: 8px;
        padding: 8px;
        margin-top: 12px;
        display: flex;
        justify-content: space-around;
    }
    </style>
    """, unsafe_allow_html=True)

    pitch_html = '<div class="pitch-container">'
    # Goalkeeper row
    pitch_html += '<div class="pitch-row">'
    for p in data["pitch_data"]["GK"]: pitch_html += render_player_badge(p)
    pitch_html += '</div>'

    # Defender row
    pitch_html += '<div class="pitch-row">'
    for p in data["pitch_data"]["DEF"]: pitch_html += render_player_badge(p)
    pitch_html += '</div>'

    # Midfielder row
    pitch_html += '<div class="pitch-row">'
    for p in data["pitch_data"]["MID"]: pitch_html += render_player_badge(p)
    pitch_html += '</div>'

    # Forward row
    pitch_html += '<div class="pitch-row">'
    for p in data["pitch_data"]["FWD"]: pitch_html += render_player_badge(p)
    pitch_html += '</div>'

    # Bench dugout
    pitch_html += '<div style="color: #ffffff; font-size: 11px; font-weight: bold; margin-top: 8px; text-align: center;">🪑 BENCH DUGOUT</div>'
    pitch_html += '<div class="bench-dugout">'
    for p in data["pitch_data"]["BENCH"]: pitch_html += render_player_badge(p)
    pitch_html += '</div></div>'

    st.markdown(pitch_html, unsafe_allow_html=True)

# -------------------------------------------------------------
# 6. CHAT DISPLAY & FILE ATTACHMENTS
# -------------------------------------------------------------
active_messages = saved_threads.get(selected_thread, [])

st.markdown(f"### 🧵 {selected_thread}")
st.caption(f"Targeting: **Gameweek {target_gw}** | Active Mini-League: **Crazy Football Fans**")

for msg in active_messages:
    with st.chat_message(msg["role"]):
        st.caption(f"🗓️ {msg.get('timestamp', '')} | {msg.get('gw_tag', f'Target: GW {target_gw}')}")
        st.markdown(msg["content"])

# Multimodal File Uploader (Retained for screenshots and CSVs)
uploaded_file = st.file_uploader(
    "📎 Attach screenshot, rival squad, or fixture sheet (Optional)",
    type=["png", "jpg", "jpeg", "webp", "csv", "txt"],
    key="file_uploader"
)

if prompt := st.chat_input(f"Ask strategist in '{selected_thread}'..."):
    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")
    gw_badge = f"⚽ Target: GW {target_gw}" if not data["is_live_matchday"] else f"⚽ Live: GW {last_gw} (Target: GW {target_gw})"

    user_entry = {"role": "user", "content": prompt, "timestamp": now_str, "gw_tag": gw_badge}
    active_messages.append(user_entry)
    with st.chat_message("user"):
        st.caption(f"🗓️ {now_str} | {gw_badge}")
        st.markdown(prompt)
        if uploaded_file:
            st.caption(f"📎 Attached: {uploaded_file.name}")

    client = genai.Client(api_key=GEMINI_API_KEY)
    history_contents = []
    for m in active_messages[:-1]:
        history_contents.append(
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])]
            )
        )

    system_instruction = (
        f"You are the elite FPL Chief Strategist managing {data['manager_name']}'s squad '{data['team_name']}'.\n"
        f"Primary League: Crazy Football Fans (ID: 987870). All decisions must optimize winning this paid money league.\n"
        f"Target Gameweek: GW {target_gw}. Bank: £{data['bank']}m. Free Transfers: {data['free_transfers']} FT.\n"
        f"Chips Used: {data['chips_used'] if data['chips_used'] else 'None'}.\n"
        f"Favorite Club: {MY_FAVORITE_CLUB}. ANTI-FAN-BIAS: Never recommend {MY_FAVORITE_CLUB} players out of sentiment; justify purely with stats.\n\n"
        "DIRECTIVES & STRATEGIC CAPABILITIES:\n"
        "1. Identify Squad Weak Links: Pinpoint underperforming players based on form, low xGI, or difficult FDR runs.\n"
        "2. Transfer Moves: Deliver a Primary SELL -> BUY plan using 3GW xP projections, plus an immediate Plan B alternative.\n"
        "3. Chip Strategy: Advise when to hold or trigger chips (Wildcard, Free Hit, Bench Boost, Triple Captain) considering blanks and doubles.\n"
        "4. Price Rise/Fall Awareness: Warn the user if players are due for an overnight price rise or drop.\n"
        "5. Visual Tables: Output fixtures and league standings in Markdown tables with Pos, Team, Manager, GD, and Pts.\n"
        "6. Tone: Decisive and numbers-backed. Never deflect with 'What do you want to do?'.\n\n"
        f"LIVE DATA ENGINE:\n"
        f"- Active Lineup Formation: {data['formation']}\n"
        f"- Squad Details: {data['squad']}\n"
        f"- Scouting Shortlists: {data['scouting_radar']}\n"
        f"- Mini-League Table: {league_table}\n"
        f"- Premier League Table: {data['pl_table']}\n"
    )

    current_prompt_parts = []
    if uploaded_file:
        file_bytes = uploaded_file.read()
        mime_type = uploaded_file.type
        current_prompt_parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
        current_prompt_parts.append(types.Part.from_text(text=f"Attached file: {uploaded_file.name}."))
    current_prompt_parts.append(types.Part.from_text(text=prompt))

    with st.chat_message("assistant"):
        with st.spinner("Analyzing 3GW xP projections, price movements, and league standings..."):
            chat = client.chats.create(
                model="gemini-2.5-flash",
                history=history_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            response = chat.send_message(current_prompt_parts)
            st.caption(f"🗓️ {now_str} | {gw_badge}")
            st.markdown(response.text)

    assistant_entry = {
        "role": "assistant",
        "content": response.text,
        "timestamp": now_str,
        "gw_tag": gw_badge
    }
    active_messages.append(assistant_entry)

    saved_threads[selected_thread] = active_messages
    save_all_threads(saved_threads)
