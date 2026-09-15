import streamlit as st
import requests
from google import genai
from google.genai import types

# Page setup for mobile & desktop
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
@st.cache_data(ttl=600)  # Caches data for 10 minutes to save API requests
def fetch_fpl_overview():
    boot = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", headers=HEADERS).json()
    elements = {p["id"]: p["web_name"] for p in boot["elements"]}
    
    # Active Gameweek
    curr_gw = 1
    for event in boot["events"]:
        if event.get("is_current"):
            curr_gw = event["id"]
            break
        if event.get("is_next"):
            curr_gw = max(1, event["id"] - 1)
            break

    # User Profile
    my_picks = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/event/{curr_gw}/picks/", headers=HEADERS).json()
    my_entry = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/", headers=HEADERS).json()
    my_squad = [
        {"player": elements.get(p["element"], f"ID {p['element']}"), "starter": p["position"] <= 11, "captain": p["is_captain"]}
        for p in my_picks.get("picks", [])
    ]
    my_bank = my_picks.get("entry_history", {}).get("bank", 0) / 10

    # Overall World #1 Leader
    wl_standings = requests.get("https://fantasy.premierleague.com/api/leagues-classic/314/standings/", headers=HEADERS).json()
    world_leader = wl_standings["standings"]["results"][0]
    
    # Mini-League Leader
    ml_standings = requests.get(f"https://fantasy.premierleague.com/api/leagues-classic/{MY_MINI_LEAGUE_ID}/standings/", headers=HEADERS).json()
    ml_leader = ml_standings["standings"]["results"][0]

    return {
        "gw": curr_gw,
        "team_name": my_entry.get("name"),
        "manager_name": f"{my_entry.get('player_first_name')} {my_entry.get('player_last_name')}",
        "total_points": my_entry.get("summary_overall_points"),
        "overall_rank": my_entry.get("summary_overall_rank"),
        "bank": my_bank,
        "squad": my_squad,
        "world_leader": {"name": world_leader["player_name"], "team": world_leader["entry_name"], "points": world_leader["total"]},
        "mini_league_leader": {"name": ml_leader["player_name"], "team": ml_leader["entry_name"], "points": ml_leader["total"]}
    }

data = fetch_fpl_overview()

# Sidebar: Live Manager Dashboard
with st.sidebar:
    st.header(f"📊 Gameweek {data['gw']}")
    st.metric("Overall Rank", f"{data['overall_rank']:,}")
    st.metric("Total Points", data['total_points'])
    st.metric("Bank Balance", f"£{data['bank']}m")
    st.divider()
    st.markdown(f"**ML Leader:** {data['mini_league_leader']['name']} ({data['mini_league_leader']['points']} pts)")
    st.markdown(f"**World #1:** {data['world_leader']['name']} ({data['world_leader']['points']} pts)")

# -------------------------------------------------------------
# CHAT MEMORY INTERFACE
# -------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Chat Input
if prompt := st.chat_input("Ask for transfer targets, captaincy, or rival comparison..."):
    # Render user message
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
        f"You are the elite FPL Chief Strategist for Team ID {MY_TEAM_ID} in Mini-League {MY_MINI_LEAGUE_ID}. "
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