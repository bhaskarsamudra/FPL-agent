import os
import json
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from google import genai
from google.genai import types

# -------------------------------------------------------------
# 1. SETUP & CONFIGURATION
# -------------------------------------------------------------
st.set_page_config(page_title="FPL AI Strategist", page_icon="⚽", layout="wide")
st.title("⚽ FPL AI Strategist")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
MY_TEAM_ID = 3325156
MY_FAVORITE_CLUB = "Manchester United"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
STORAGE_FILE = "chat_store.json"

# All configured leagues
LEAGUES_DICT = {
    "CRAZY FOOT (Primary)": 987870,
    "Explosive": 140555,
    "The Road To": 684844,
    "India": 120,
    "Man Utd": 16,
    "Overall": 314,
    "Jio Star League": 1234984
}

# -------------------------------------------------------------
# 2. PERSISTENT THREAD STORAGE
# -------------------------------------------------------------
def load_all_threads():
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_all_threads(threads):
    try:
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(threads, f, indent=2)
    except Exception as e:
        st.error(f"Error saving chat: {e}")

# -------------------------------------------------------------
# 3. FPL LIVE DATA FETCHER
# -------------------------------------------------------------
@st.cache_data(ttl=600)
def fetch_base_fpl_data():
    boot = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", headers=HEADERS).json()
    elements = {p["id"]: p["web_name"] for p in boot["elements"]}
    teams_map = {t["id"]: t["name"] for t in boot["teams"]}
    teams_short = {t["id"]: t["short_name"] for t in boot["teams"]}

    # Identify Active Gameweek
    curr_gw = 1
    for event in boot["events"]:
        if event.get("is_current"):
            curr_gw = event["id"]
            break
        if event.get("is_next"):
            curr_gw = max(1, event["id"] - 1)
            break

    # 1. User Profile & Latest Points
    my_picks = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/event/{curr_gw}/picks/", headers=HEADERS).json()
    my_entry = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/", headers=HEADERS).json()
    my_squad = [
        {"player": elements.get(p["element"], f"ID {p['element']}"), "starter": p["position"] <= 11, "captain": p["is_captain"]}
        for p in my_picks.get("picks", [])
    ]
    my_bank = my_picks.get("entry_history", {}).get("bank", 0) / 10
    my_latest_gw_points = my_picks.get("entry_history", {}).get("points", 0)

    # 2. Overall World #1 Leader
    wl_standings = requests.get("https://fantasy.premierleague.com/api/leagues-classic/314/standings/", headers=HEADERS).json()
    world_leader = wl_standings["standings"]["results"][0]

    # 3. Premier League Standings
    pl_standings = []
    for t in boot["teams"]:
        pl_standings.append({
            "Pos": t["position"],
            "Club": t["name"],
            "P": t.get("played", 0),
            "W": t.get("win", 0),
            "D": t.get("draw", 0),
            "L": t.get("loss", 0),
            "Pts": t.get("points", 0)
        })
    pl_standings = sorted(pl_standings, key=lambda x: x["Pos"])

    # 4. Upcoming Fixtures for all clubs (Next 6 GWs)
    fixtures_raw = requests.get("https://fantasy.premierleague.com/api/fixtures/?future=1", headers=HEADERS).json()
    team_fixtures = {t["name"]: [] for t in boot["teams"]}
    target_gws = list(range(curr_gw + 1, curr_gw + 7))

    for f in fixtures_raw:
        if f.get("event") in target_gws:
            h_team = teams_map[f["team_h"]]
            a_team = teams_map[f["team_a"]]
            team_fixtures[h_team].append(f"GW{f['event']}: {teams_short[f['team_a']]} (H) [FDR {f['team_h_difficulty']}]")
            team_fixtures[a_team].append(f"GW{f['event']}: {teams_short[f['team_h']]} (A) [FDR {f['team_a_difficulty']}]")

    return {
        "gw": curr_gw,
        "team_name": my_entry.get("name"),
        "total_points": my_entry.get("summary_overall_points"),
        "latest_gw_points": my_latest_gw_points,
        "overall_rank": my_entry.get("summary_overall_rank"),
        "bank": my_bank,
        "squad": my_squad,
        "world_leader": {
            "name": world_leader["player_name"],
            "team": world_leader["entry_name"],
            "points": world_leader["total"],
            "gw_points": world_leader["event_total"]
        },
        "pl_table": pl_standings,
        "team_fixtures_next_6": team_fixtures
    }

@st.cache_data(ttl=300)
def fetch_mini_league_table(league_id: int):
    """Fetches Top 5 and appends the user's team if outside Top 5."""
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

    return league_name, table_rows

# Load initial data
data = fetch_base_fpl_data()
curr_gw = data["gw"]

# -------------------------------------------------------------
# 4. SIDEBAR: DASHBOARD & THREAD MANAGER
# -------------------------------------------------------------
saved_threads = load_all_threads()
if not saved_threads:
    default_thread = f"GW {curr_gw} Strategy"
    saved_threads[default_thread] = []
    save_all_threads(saved_threads)

with st.sidebar:
    st.header(f"📊 Gameweek {curr_gw}")
    st.caption(f"**Team:** {data['team_name']}")

    # 1. User Summary Metrics
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total Points", data['total_points'])
        st.metric("Overall Rank", f"{data['overall_rank']:,}")
    with c2:
        st.metric("Latest GW", data['latest_gw_points'])
        st.metric("Bank", f"£{data['bank']}m")

    st.divider()

    # 2. World #1 Leader
    st.subheader("🌍 World #1 Leader")
    st.write(f"**{data['world_leader']['name']}** — *{data['world_leader']['team']}*")
    w1, w2 = st.columns(2)
    with w1: st.metric("Total Pts", data['world_leader']['points'])
    with w2: st.metric("GW Pts", data['world_leader']['gw_points'])

    st.divider()

    # 3. Dynamic Mini-League Selector & Leaderboard
    st.subheader("🏆 Mini-League Leaderboards")
    selected_league_label = st.selectbox("Select League:", list(LEAGUES_DICT.keys()), index=0)
    selected_league_id = LEAGUES_DICT[selected_league_label]

    league_name, league_table = fetch_mini_league_table(selected_league_id)
    st.caption(f"Displaying: **{league_name}** (ID: {selected_league_id})")
    st.dataframe(pd.DataFrame(league_table), hide_index=True, use_container_width=True)

    st.divider()

    # 4. Conversation Threads
    st.subheader("💬 Conversation Threads")
    thread_names = list(saved_threads.keys())
    selected_thread = st.selectbox("Switch Thread:", thread_names, index=len(thread_names) - 1)

    new_thread_input = st.text_input("New Thread Name:", placeholder=f"e.g., GW {curr_gw} Differentials")
    if st.button("➕ Create Thread", use_container_width=True) and new_thread_input.strip():
        new_name = new_thread_input.strip()
        if new_name not in saved_threads:
            saved_threads[new_name] = []
            save_all_threads(saved_threads)
            st.rerun()

# -------------------------------------------------------------
# 5. CHAT DISPLAY & GEMINI REASONING
# -------------------------------------------------------------
active_messages = saved_threads.get(selected_thread, [])

st.markdown(f"### 🧵 {selected_thread}")
st.caption(f"Active League Context: **{selected_league_label}** | Primary Money League: **CRAZY FOOT**")

for msg in active_messages:
    with st.chat_message(msg["role"]):
        st.caption(f"🗓️ {msg.get('timestamp', '')} | ⚽ {msg.get('gw_tag', f'GW {curr_gw}')}")
        st.markdown(msg["content"])

if prompt := st.chat_input(f"Ask in '{selected_thread}'... (transfers, captaincy, rivals, fixtures)"):
    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")
    gw_tag = f"Gameweek {curr_gw}"

    user_entry = {"role": "user", "content": prompt, "timestamp": now_str, "gw_tag": gw_tag}
    active_messages.append(user_entry)
    with st.chat_message("user"):
        st.caption(f"🗓️ {now_str} | ⚽ {gw_tag}")
        st.markdown(prompt)

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
        f"You are the elite FPL Chief Strategist for Team ID {MY_TEAM_ID}.\n"
        f"Primary Target League: CRAZY FOOT (ID: 987870) - This is the user's only paid money league. "
        f"All transfer suggestions, risk assessments, and chip plans should primarily optimize winning CRAZY FOOT.\n"
        f"Other Participating Leagues: {LEAGUES_DICT}.\n"
        f"Currently Viewed League in UI: {selected_league_label} (ID: {selected_league_id}).\n"
        f"Favorite Club: {MY_FAVORITE_CLUB}. ANTI-FAN-BIAS MANDATE: Never recommend {MY_FAVORITE_CLUB} players out of loyalty. "
        f"Only recommend them if their form, expected data (xG/xA), and fixture runs warrant it. Warn the user if bias is detected.\n\n"
        f"Available Data:\n"
        f"- Live Gameweek: {curr_gw}\n"
        f"- User Squad: {data['squad']}\n"
        f"- User Bank Balance: £{data['bank']}m\n"
        f"- World #1 Leader: {data['world_leader']}\n"
        f"- Current League Table: {league_table}\n"
        f"- Full Premier League Table: {data['pl_table']}\n"
        f"- Next 6 Fixtures with FDR for all 20 clubs: {data['team_fixtures_next_6']}\n\n"
        "Format responses cleanly with bold headings and concise bullet points."
    )

    with st.chat_message("assistant"):
        with st.spinner("Analyzing FPL & League data..."):
            chat = client.chats.create(
                model="gemini-3.5-flash-lite",
                history=history_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            response = chat.send_message(prompt)
            st.caption(f"🗓️ {now_str} | ⚽ {gw_tag}")
            st.markdown(response.text)

    assistant_entry = {
        "role": "assistant",
        "content": response.text,
        "timestamp": now_str,
        "gw_tag": gw_tag
    }
    active_messages.append(assistant_entry)

    saved_threads[selected_thread] = active_messages
    save_all_threads(saved_threads)