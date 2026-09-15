import streamlit as st
import requests
import pandas as pd
from google import genai
from google.genai import types

# Page setup
st.set_page_config(page_title="FPL AI Strategist", page_icon="⚽", layout="wide")
st.title("⚽ FPL AI Strategist")

# Retrieve secrets configured in Streamlit Cloud
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
MY_TEAM_ID = 3325156
MY_MINI_LEAGUE_ID = 987870
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# -------------------------------------------------------------
# FPL LIVE DATA FETCHER
# -------------------------------------------------------------
@st.cache_data(ttl=600)
def fetch_fpl_overview():
    boot = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", headers=HEADERS).json()
    elements = {p["id"]: p["web_name"] for p in boot["elements"]}
    
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

    # 3. Mini-League Details & Table Assembly
    ml_res = requests.get(f"https://fantasy.premierleague.com/api/leagues-classic/{MY_MINI_LEAGUE_ID}/standings/", headers=HEADERS).json()
    ml_name = ml_res["league"]["name"]
    ml_results = ml_res["standings"]["results"]

    # Build Top 5 list
    table_rows = []
    user_in_top5 = False

    for m in ml_results[:5]:
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

    # If user is not in Top 5, append user's team at the bottom
    if not user_in_top5:
        user_entry = next((m for m in ml_results if m["entry"] == MY_TEAM_ID), None)
        if user_entry:
            table_rows.append({
                "Rank": "---",
                "Team": "---------",
                "Manager": "---------",
                "GW": "-",
                "Total": "-"
            })
            table_rows.append({
                "Rank": f"#{user_entry['rank']}",
                "Team": f"{user_entry['entry_name']} (You)",
                "Manager": user_entry["player_name"],
                "GW": user_entry["event_total"],
                "Total": user_entry["total"]
            })

    return {
        "gw": curr_gw,
        "team_name": my_entry.get("name"),
        "manager_name": f"{my_entry.get('player_first_name')} {my_entry.get('player_last_name')}",
        "total_points": my_entry.get("summary_overall_points"),
        "latest_gw_points": my_latest_gw_points,
        "overall_rank": my_entry.get("summary_overall_rank"),
        "bank": my_bank,
        "squad": my_squad,
        "mini_league_name": ml_name,
        "mini_league_table": table_rows,
        "world_leader": {
            "name": world_leader["player_name"],
            "team": world_leader["entry_name"],
            "points": world_leader["total"],
            "gw_points": world_leader["event_total"]
        }
    }

data = fetch_fpl_overview()

# -------------------------------------------------------------
# SIDEBAR: LIVE DASHBOARD
# -------------------------------------------------------------
with st.sidebar:
    st.header(f"📊 Gameweek {data['gw']}")
    st.caption(f"**Team:** {data['team_name']}")

    # 1. User Summary Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Points", data['total_points'])
        st.metric("Overall Rank", f"{data['overall_rank']:,}")
    with col2:
        st.metric("Latest GW Points", data['latest_gw_points'])
        st.metric("Bank Balance", f"£{data['bank']}m")

    st.divider()

    # 2. World #1 Leader First
    st.subheader("🌍 World #1 Leader")
    st.write(f"**{data['world_leader']['name']}** — *{data['world_leader']['team']}*")
    wcol1, wcol2 = st.columns(2)
    with wcol1:
        st.metric("Total Pts", data['world_leader']['points'])
    with wcol2:
        st.metric("GW Pts", data['world_leader']['gw_points'])

    st.divider()

    # 3. Mini-League Leaderboard Second
    st.subheader(f"🏆 {data['mini_league_name']}")
    df_league = pd.DataFrame(data["mini_league_table"])
    # Drop internal entry_id column if present before rendering
    if "entry_id" in df_league.columns:
        df_league = df_league.drop(columns=["entry_id"])

    st.dataframe(
        df_league,
        hide_index=True,
        use_container_width=True
    )

# -------------------------------------------------------------
# CHAT INTERFACE
# -------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Chat Input
if prompt := st.chat_input("Ask for transfer targets, captaincy, or rival comparison..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call Gemini
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Format chat history for Gemini
    history_contents = []
    for m in st.session_state.messages[:-1]:
        history_contents.append(
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])]
            )
        )

    system_instruction = (
        f"You are the elite FPL Chief Strategist for Team ID {MY_TEAM_ID} in Mini-League {MY_MINI_LEAGUE_ID} ({data['mini_league_name']}). "
        f"Current FPL Context: {data}. "
        "Keep responses structured with bold headings and concise bullet points."
    )

    with st.chat_message("assistant"):
        with st.spinner("Analyzing FPL data..."):
            chat = client.chats.create(
                model="gemini-3.5-flash-lite",
                history=history_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            response = chat.send_message(prompt)
            st.markdown(response.text)
            
    st.session_state.messages.append({"role": "assistant", "content": response.text})