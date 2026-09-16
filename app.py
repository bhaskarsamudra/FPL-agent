import os
import json
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
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
# 3. ADVANCED STATS & SCOUTING ENGINE
# -------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_base_fpl_data():
    boot = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", headers=HEADERS).json()
    teams_map = {t["id"]: t["name"] for t in boot["teams"]}
    teams_short = {t["id"]: t["short_name"] for t in boot["teams"]}
    teams_code = {t["id"]: t["code"] for t in boot["teams"]}

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

    fixtures_raw = requests.get("https://fantasy.premierleague.com/api/fixtures/?future=1", headers=HEADERS).json()
    team_fixtures = {t["name"]: [] for t in boot["teams"]}
    lookahead_gws = list(range(target_gw, target_gw + 4))

    for f in fixtures_raw:
        if f.get("event") in lookahead_gws:
            h_team = teams_map[f["team_h"]]
            a_team = teams_map[f["team_a"]]
            team_fixtures[h_team].append({"gw": f["event"], "opp": teams_short[f["team_a"]], "home": True, "fdr": f["team_h_difficulty"]})
            team_fixtures[a_team].append({"gw": f["event"], "opp": teams_short[f["team_h"]], "home": False, "fdr": f["team_a_difficulty"]})

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
        club_code = teams_code.get(p["team"], 0)

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
            "club_code": club_code,
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

    my_picks = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/event/{active_or_last_gw}/picks/", headers=HEADERS).json()
    my_entry = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/", headers=HEADERS).json()
    my_history = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/history/", headers=HEADERS).json()

    free_transfers_available = 1
    recent_history = my_history.get("current", [])
    if recent_history:
        last_gw_stat = recent_history[-1]
        free_transfers_available = min(5, max(1, 1 if last_gw_stat.get("event_transfers", 0) > 0 else 2))

    chips_used = [c["name"] for c in my_history.get("chips", [])]

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
        "elements_detail": elements_detail,
        "price_risers": price_risers[:6],
        "price_fallers": price_fallers[:6],
        "world_leader": {
            "name": world_leader["player_name"],
            "team": world_leader["entry_name"],
            "points": world_leader["total"],
            "gw_points": world_leader["event_total"]
        },
        "scouting_radar": {
            "top_xp_forwards": sorted([p for p in all_players_pool if p["pos"] == "FWD"], key=lambda x: x["xp_3gw"], reverse=True)[:6],
            "top_xp_midfielders": sorted([p for p in all_players_pool if p["pos"] == "MID"], key=lambda x: x["xp_3gw"], reverse=True)[:8],
            "top_xp_defenders": sorted([p for p in all_players_pool if p["pos"] == "DEF"], key=lambda x: x["xp_3gw"], reverse=True)[:6],
            "differentials": [p for p in all_players_pool if p["xGI"] >= 1.5 and float(p["selected_by"]) < 10.0][:6]
        }
    }

@st.cache_data(ttl=300)
def fetch_mini_league_full(league_id: int):
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
            "Total": m["total"]
        })

    if not user_in_top5 and results:
        user_entry = next((m for m in results if m["entry"] == MY_TEAM_ID), None)
        if user_entry:
            table_rows.append({"Rank": "---", "Team": "---------", "Manager": "---------", "GW": "-", "Total": "-"})
            table_rows.append({
                "Rank": f"#{user_entry['rank']}",
                "Team": f"{user_entry['entry_name']} (You)",
                "Manager": user_entry["player_name"],
                "GW": user_entry["event_total"],
                "Total": user_entry["total"]
            })

    all_managers = {}
    for m in results:
        label = f"#{m['rank']} {m['entry_name']} ({m['player_name']})"
        all_managers[label] = m["entry"]

    return league_name, table_rows, all_managers

@st.cache_data(ttl=300)
def fetch_team_pitch_data(entry_id: int, gw: int, elements_detail: dict):
    try:
        picks_res = requests.get(f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/", headers=HEADERS).json()
        entry_res = requests.get(f"https://fantasy.premierleague.com/api/entry/{entry_id}/", headers=HEADERS).json()
        
        pitch_data = {"GK": [], "DEF": [], "MID": [], "FWD": [], "BENCH": []}
        all_squad = []

        for p in picks_res.get("picks", []):
            info = elements_detail.get(p["element"], {})
            pos = info.get("pos", "MID")
            club_code = info.get("club_code", 0)
            
            jersey_suffix = "_1-66.png" if pos == "GK" else "-66.png"
            jersey_url = f"https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_{club_code}{jersey_suffix}"

            badge = " (C)" if p["is_captain"] else (" (V)" if p["is_vice_captain"] else "")
            card = {
                "name": info.get("name", "Unknown"),
                "club": info.get("club_short", "UNK"),
                "pos": pos,
                "badge": badge,
                "points": info.get("event_points", 0),
                "cost": f"£{info.get('cost', 0.0)}m",
                "jersey_url": jersey_url,
                "is_captain": p["is_captain"],
                "is_vice": p["is_vice_captain"]
            }
            all_squad.append(card)
            if p["position"] <= 11:
                pitch_data[pos].append(card)
            else:
                card["bench_order"] = p["position"] - 11
                pitch_data["BENCH"].append(card)

        formation = f"{len(pitch_data['DEF'])}-{len(pitch_data['MID'])}-{len(pitch_data['FWD'])}"
        team_name = entry_res.get("name", f"Team {entry_id}")
        manager_name = f"{entry_res.get('player_first_name', '')} {entry_res.get('player_last_name', '')}"
        
        return {
            "team_name": team_name,
            "manager_name": manager_name,
            "formation": formation,
            "pitch_data": pitch_data,
            "all_squad": all_squad
        }
    except Exception:
        return None

# Load Core Data
data = fetch_base_fpl_data()
target_gw = data["target_gw"]
last_gw = data["active_or_last_gw"]

# -------------------------------------------------------------
# 4. ROBUST HTML PITCH COMPONENT (ST.COMPONENTS.V1.HTML)
# -------------------------------------------------------------
def build_card_html(p, is_bench=False):
    cap = ""
    if p.get("is_captain"):
        cap = '<span style="background:#111;color:#fff;border-radius:50%;font-size:8px;padding:1px 4px;margin-left:2px;font-weight:bold;">C</span>'
    elif p.get("is_vice"):
        cap = '<span style="background:#555;color:#fff;border-radius:50%;font-size:8px;padding:1px 4px;margin-left:2px;font-weight:bold;">V</span>'

    top_badge = f'<div style="font-size:9px;color:#2c3e50;font-weight:700;margin-bottom:2px;">{p.get("bench_order", "")}. {p["pos"]}</div>' if is_bench else ""

    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;width:72px;margin:2px 4px;">'
        f'{top_badge}'
        f'<img src="{p["jersey_url"]}" style="height:38px;width:38px;object-fit:contain;filter:drop-shadow(0 2px 3px rgba(0,0,0,0.3));margin-bottom:1px;" />'
        f'<div style="background:#fff;color:#111;font-size:10px;font-weight:800;border-radius:3px 3px 0 0;width:100%;text-align:center;padding:2px 1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 1px 2px rgba(0,0,0,0.2);">'
        f'{p["name"]}{cap}</div>'
        f'<div style="background:#37003c;color:#00ff87;font-size:9px;font-weight:900;border-radius:0 0 3px 3px;width:100%;text-align:center;padding:1px 0;">'
        f'{p["points"]} pts</div>'
        f'</div>'
    )

def build_full_pitch_html(pitch_data):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; }
      body { background: transparent; overflow-x: hidden; }
      .field {
        background: linear-gradient(180deg, #028940 0%, #027336 25%, #028940 50%, #027336 75%, #028940 100%);
        border: 2px solid #ffffff;
        border-radius: 12px 12px 0 0;
        padding: 10px 4px;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
      }
      .line {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin-bottom: 6px;
      }
      .dugout {
        background: linear-gradient(180deg, #d8f3dc 0%, #b7e4c7 100%);
        border-left: 2px solid #ffffff;
        border-right: 2px solid #ffffff;
        border-bottom: 2px solid #ffffff;
        border-radius: 0 0 12px 12px;
        padding: 8px 4px 6px 4px;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
      }
      .dugout-title {
        font-size: 9px;
        font-weight: 800;
        color: #1b4332;
        letter-spacing: 1px;
        margin-bottom: 4px;
      }
      .dugout-row {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
      }
    </style>
    </head>
    <body>
      <div class="field">
    """

    # Goalkeepers
    html += '<div class="line">'
    for p in pitch_data["GK"]: html += build_card_html(p)
    html += '</div>'

    # Defenders
    html += '<div class="line">'
    for p in pitch_data["DEF"]: html += build_card_html(p)
    html += '</div>'

    # Midfielders
    html += '<div class="line">'
    for p in pitch_data["MID"]: html += build_card_html(p)
    html += '</div>'

    # Forwards
    html += '<div class="line" style="margin-bottom: 2px;">'
    for p in pitch_data["FWD"]: html += build_card_html(p)
    html += '</div></div>'

    # Bench Dugout
    html += """
      <div class="dugout">
        <div class="dugout-title">🪑 BENCH DUGOUT</div>
        <div class="dugout-row">
    """
    for p in pitch_data["BENCH"]: html += build_card_html(p, is_bench=True)
    html += '</div></div></body></html>'
    return html

@st.dialog("⚽ Squad Inspection", width="large")
def show_squad_popup(team_id: int):
    tdata = fetch_team_pitch_data(team_id, last_gw, data["elements_detail"])
    if not tdata:
        st.error("Squad lineup could not be retrieved.")
        return

    st.markdown(f"### **{tdata['team_name']}** ({tdata['formation']})")
    st.caption(f"Manager: **{tdata['manager_name']}** | Gameweek {last_gw}")

    html_code = build_full_pitch_html(tdata["pitch_data"])
    components.html(html_code, height=480, scrolling=False)

# -------------------------------------------------------------
# 5. SIDEBAR DASHBOARD
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
    st.info(f"🌍 **World #1:** {data['world_leader']['name']} ({data['world_leader']['team']}) — **{data['world_leader']['points']} pts**")

    # Mini-League Selector & Leaderboard
    st.subheader("🏆 Mini-League Leaderboard")
    selected_league_label = st.selectbox("Select Mini-League:", list(LEAGUES_DICT.keys()), index=0)
    selected_league_id = LEAGUES_DICT[selected_league_label]

    league_name, league_table, all_league_managers = fetch_mini_league_full(selected_league_id)
    st.caption(f"Standings for **{league_name}**")
    st.dataframe(pd.DataFrame(league_table), hide_index=True, use_container_width=True)

    # Inspect Squad with Pop-up Trigger
    st.subheader("🔍 Inspect Squad")
    manager_options = list(all_league_managers.keys())
    default_idx = 0
    for idx, opt in enumerate(manager_options):
        if "(You)" in opt:
            default_idx = idx
            break

    sub_col1, sub_col2 = st.columns([3, 1])
    with sub_col1:
        chosen_manager_label = st.selectbox("Select Manager:", manager_options, index=default_idx, label_visibility="collapsed")
    with sub_col2:
        if st.button("🔍 View", use_container_width=True):
            show_squad_popup(all_league_managers[chosen_manager_label])

    st.divider()

    # Price Movement Radar
    st.subheader("📈 Price Movement Radar")
    if data["price_risers"]:
        st.caption("🔥 Risers: " + ", ".join(data["price_risers"]))
    if data["price_fallers"]:
        st.caption("❄️ Fallers: " + ", ".join(data["price_fallers"]))

    st.divider()

    # Conversation Threads
    st.subheader("💬 Conversation Threads")
    thread_names = list(saved_threads.keys())
    selected_thread = st.selectbox("Switch Thread:", thread_names, index=len(thread_names) - 1)

    new_thread_input = st.text_input("New Thread Name:", placeholder=f"e.g., GW {target_gw} Transfers")
    if st.button("➕ Create Thread", use_container_width=True) and new_thread_input.strip():
        new_name = new_thread_input.strip()
        if new_name not in saved_threads:
            saved_threads[new_name] = []
            save_all_threads(saved_threads)
            st.rerun()

# -------------------------------------------------------------
# 6. CHAT DISPLAY & COMPACT ATTACHMENT TOGGLE
# -------------------------------------------------------------
active_messages = saved_threads.get(selected_thread, [])

st.markdown(f"### 🧵 {selected_thread}")
st.caption(f"Targeting: **Gameweek {target_gw}** | Active Mini-League: **Crazy Football Fans**")

for msg in active_messages:
    with st.chat_message(msg["role"]):
        st.caption(f"🗓️ {msg.get('timestamp', '')} | {msg.get('gw_tag', f'Target: GW {target_gw}')}")
        st.markdown(msg["content"])

with st.expander("📎 Attach Screenshot / Data File (Optional)", expanded=False):
    uploaded_file = st.file_uploader(
        "Upload image or CSV (Rival team screenshots, LiveFPL tables, injury reports):",
        type=["png", "jpg", "jpeg", "webp", "csv", "txt"],
        label_visibility="collapsed",
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

    user_pitch_info = fetch_team_pitch_data(MY_TEAM_ID, last_gw, data["elements_detail"])

    system_instruction = (
        f"You are the elite FPL Chief Strategist managing {data['manager_name']}'s squad '{data['team_name']}'.\n"
        f"Primary League: Crazy Football Fans (ID: 987870). All decisions must optimize winning this paid money league.\n"
        f"Target Gameweek: GW {target_gw}. Bank: £{data['bank']}m. Free Transfers: {data['free_transfers']} FT.\n"
        f"Chips Used: {data['chips_used'] if data['chips_used'] else 'None'}.\n"
        f"Favorite Club: {MY_FAVORITE_CLUB}. ANTI-FAN-BIAS: Never recommend {MY_FAVORITE_CLUB} players out of emotion; justify purely with stats.\n\n"
        "DIRECTIVES:\n"
        "1. Identify Squad Weak Links based on form, low xGI, or bad FDR runs.\n"
        "2. Deliver a Primary SELL -> BUY plan using 3GW xP projections, plus an immediate Plan B alternative.\n"
        "3. Chip Strategy: Advise when to hold or trigger chips (Wildcard, Free Hit, Bench Boost, Triple Captain).\n"
        "4. Price Rise/Fall Awareness: Warn user if targets are due to change price overnight.\n"
        "5. Output fixtures and league standings in Markdown tables with Pos, Team, Manager, GD, and Pts.\n"
        "6. Never deflect with 'What do you want to do?'. Give clear, math-backed tactical answers.\n\n"
        f"LIVE DATA ENGINE:\n"
        f"- User Squad & Formation: {user_pitch_info['formation'] if user_pitch_info else 'N/A'}\n"
        f"- Full Squad Details: {user_pitch_info['all_squad'] if user_pitch_info else []}\n"
        f"- Scouting Radar (Market): {data['scouting_radar']}\n"
        f"- Mini-League Table: {league_table}\n"
    )

    current_prompt_parts = []
    if uploaded_file:
        file_bytes = uploaded_file.read()
        mime_type = uploaded_file.type
        current_prompt_parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
        current_prompt_parts.append(types.Part.from_text(text=f"Attached file: {uploaded_file.name}."))
    current_prompt_parts.append(types.Part.from_text(text=prompt))

    with st.chat_message("assistant"):
        with st.spinner("Analyzing 3GW xP projections, formation, and rival differentials..."):
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
