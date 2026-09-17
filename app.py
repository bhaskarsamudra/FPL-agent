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
# 3. ADVANCED STATS & CHIP PARSER
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
    risers_list = []
    fallers_list = []

    for p in boot["elements"]:
        pos_str = ["GK", "DEF", "MID", "FWD"][p["element_type"] - 1]
        cost = p["now_cost"] / 10
        cost_change = p.get("cost_change_event", 0) / 10

        if cost_change > 0:
            risers_list.append({"Player": p["web_name"], "Price": f"£{cost:.1f}m", "Rise": f"+£{cost_change:.1f}m"})
        elif cost_change < 0:
            fallers_list.append({"Player": p["web_name"], "Price": f"£{cost:.1f}m", "Fall": f"-£{abs(cost_change):.1f}m"})

        form_val = float(p.get("form", 0.0) or 0.0)
        xgi_val = float(p.get("expected_goal_involvements", 0.0) or 0.0)
        club_name = teams_map.get(p["team"], "Unknown")
        club_code = teams_code.get(p["team"], 0)

        upcoming = team_fixtures.get(club_name, [])[:3]
        fdr_weights = {1: 1.3, 2: 1.15, 3: 1.0, 4: 0.85, 5: 0.7}
        projected_3gw_xp = 0.0
        single_gw_xp = max(1.5, (form_val * 0.6 + (xgi_val * 1.5)) * fdr_weights.get(upcoming[0]["fdr"] if upcoming else 3, 1.0))
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
            "form": form_val,
            "points": p.get("total_points", 0),
            "event_points": p.get("event_points", 0),
            "xGI": xgi_val,
            "selected_by": p.get("selected_by_percent", "0.0"),
            "xp_next_gw": round(single_gw_xp, 1),
            "xp_3gw": round(projected_3gw_xp, 1)
        }
        elements_detail[p["id"]] = player_dict
        all_players_pool.append(player_dict)

    my_picks = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/event/{active_or_last_gw}/picks/", headers=HEADERS).json()
    my_entry = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/", headers=HEADERS).json()
    my_history = requests.get(f"https://fantasy.premierleague.com/api/entry/{MY_TEAM_ID}/history/", headers=HEADERS).json()

    # Exact Multi-GW Free Transfer Accumulator
    calculated_ft = 1
    past_gws = my_history.get("current", [])
    if past_gws:
        ft_acc = 1
        for gw_stat in past_gws:
            transfers = gw_stat.get("event_transfers", 0)
            ft_acc = max(0, ft_acc - transfers)
            ft_acc = min(5, ft_acc + 1)
        calculated_ft = ft_acc

    # Chips data
    chips_played_data = {c["name"]: c.get("event") for c in my_history.get("chips", [])}

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
        "calculated_ft": calculated_ft,
        "chips_played": chips_played_data,
        "elements_detail": elements_detail,
        "risers_list": risers_list[:8],
        "fallers_list": fallers_list[:8],
        "world_leader": {
            "name": world_leader["player_name"],
            "team": world_leader["entry_name"],
            "points": world_leader["total"],
            "gw_points": world_leader["event_total"]
        },
        "scouting_radar": {
            "top_xp_forwards": sorted([p for p in all_players_pool if p["pos"] == "FWD"], key=lambda x: x["xp_3gw"], reverse=True)[:5],
            "top_xp_midfielders": sorted([p for p in all_players_pool if p["pos"] == "MID"], key=lambda x: x["xp_3gw"], reverse=True)[:6],
            "top_xp_defenders": sorted([p for p in all_players_pool if p["pos"] == "DEF"], key=lambda x: x["xp_3gw"], reverse=True)[:5]
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
def fetch_team_pitch_data(team_id: int, gw: int, elements_detail: dict):
    try:
        picks_res = requests.get(f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/", headers=HEADERS).json()
        entry_res = requests.get(f"https://fantasy.premierleague.com/api/entry/{team_id}/", headers=HEADERS).json()

        gw_points = picks_res.get("entry_history", {}).get("points", 0)
        total_points = entry_res.get("summary_overall_points", 0)

        live_res = requests.get(f"https://fantasy.premierleague.com/api/event/{gw}/live/", headers=HEADERS).json()
        live_elements = {el["id"]: el["stats"]["total_points"] for el in live_res.get("elements", [])}

        pitch_data = {"GK": [], "DEF": [], "MID": [], "FWD": [], "BENCH": []}
        all_squad = []

        for p in picks_res.get("picks", []):
            info = elements_detail.get(p["element"], {})
            pos = info.get("pos", "MID")
            club_code = info.get("club_code", 0)

            jersey_suffix = "_1-66.png" if pos == "GK" else "-66.png"
            jersey_url = f"https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_{club_code}{jersey_suffix}"

            is_cap = bool(p.get("is_captain"))
            is_vc = bool(p.get("is_vice_captain"))

            raw_pts = live_elements.get(p["element"], info.get("event_points", 0))
            calc_pts = raw_pts * (p.get("multiplier", 1) or 1)

            card = {
                "name": info.get("name", "Unknown"),
                "club": info.get("club_short", "UNK"),
                "pos": pos,
                "points": calc_pts,
                "cost": f"£{info.get('cost', 0.0)}m",
                "jersey_url": jersey_url,
                "is_captain": is_cap,
                "is_vice": is_vc,
                "xp_next_gw": info.get("xp_next_gw", 3.0),
                "xp_3gw": info.get("xp_3gw", 9.0)
            }
            all_squad.append(card)
            if p["position"] <= 11:
                pitch_data[pos].append(card)
            else:
                card["bench_order"] = p["position"] - 11
                pitch_data["BENCH"].append(card)

        formation = f"{len(pitch_data['DEF'])}-{len(pitch_data['MID'])}-{len(pitch_data['FWD'])}"
        team_name = entry_res.get("name", f"Team {team_id}")
        manager_name = f"{entry_res.get('player_first_name', '')} {entry_res.get('player_last_name', '')}"

        return {
            "team_name": team_name,
            "manager_name": manager_name,
            "gw_points": gw_points,
            "total_points": total_points,
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
# 4. SQUAD INSPECTION POPUP DIALOG
# -------------------------------------------------------------
def build_card_html(p, is_bench=False):
    cap_html = ""
    if p.get("is_captain"):
        cap_html = '<span style="background:#000;color:#fff;border-radius:50%;width:13px;height:13px;display:inline-flex;align-items:center;justify-content:center;font-size:8px;font-weight:900;margin-left:3px;flex-shrink:0;">C</span>'
    elif p.get("is_vice"):
        cap_html = '<span style="background:#555;color:#fff;border-radius:50%;width:13px;height:13px;display:inline-flex;align-items:center;justify-content:center;font-size:8px;font-weight:900;margin-left:3px;flex-shrink:0;">V</span>'

    top_badge = f'<div style="font-size:9px;color:#2c3e50;font-weight:800;margin-bottom:2px;">{p.get("bench_order", "")}. {p["pos"]}</div>' if is_bench else ""

    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;width:80px;margin:2px 4px;">'
        f'{top_badge}'
        f'<img src="{p["jersey_url"]}" style="height:38px;width:38px;object-fit:contain;filter:drop-shadow(0 2px 3px rgba(0,0,0,0.35));margin-bottom:2px;" />'
        f'<div style="background:#fff;color:#111;font-size:10px;font-weight:800;border-radius:3px 3px 0 0;width:100%;display:flex;align-items:center;justify-content:center;padding:2px 2px;box-shadow:0 1px 2px rgba(0,0,0,0.2);">'
        f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{p["name"]}</span>{cap_html}</div>'
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
        padding: 12px 4px;
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
    html += '<div class="line">'
    for p in pitch_data["GK"]: html += build_card_html(p)
    html += '</div><div class="line">'
    for p in pitch_data["DEF"]: html += build_card_html(p)
    html += '</div><div class="line">'
    for p in pitch_data["MID"]: html += build_card_html(p)
    html += '</div><div class="line" style="margin-bottom: 2px;">'
    for p in pitch_data["FWD"]: html += build_card_html(p)
    html += '</div></div>'

    html += """
      <div class="dugout">
        <div class="dugout-title">🪑 BENCH DUGOUT</div>
        <div class="dugout-row">
    """
    for p in pitch_data["BENCH"]: html += build_card_html(p, is_bench=True)
    html += '</div></div></body></html>'
    return html

@st.dialog("⚽ Squad Inspection", width="large")
def render_squad_dialog(team_id: int):
    if "popup_gw" not in st.session_state:
        st.session_state.popup_gw = last_gw

    current_popup_gw = st.session_state.popup_gw
    tdata = fetch_team_pitch_data(team_id, current_popup_gw, data["elements_detail"])
    if not tdata:
        st.error(f"Squad data for Gameweek {current_popup_gw} could not be retrieved.")
        return

    st.markdown(
        f"""
        <div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; margin-bottom: 2px;">
            <div style="display: flex; align-items: baseline; gap: 8px;">
                <h3 style="margin: 0; padding: 0;">{tdata['team_name']} ({tdata['formation']})</h3>
                <span style="color: #666; font-size: 13px; font-weight: 600;">(Total: {tdata['total_points']} pts)</span>
            </div>
            <div>
                <span style="background: #37003c; color: #00ff87; font-size: 14px; font-weight: 800; border-radius: 6px; padding: 3px 10px;">
                    GW{current_popup_gw}: {tdata['gw_points']} pts
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.caption(f"Manager: **{tdata['manager_name']}**")

    nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])
    with nav_col1:
        if current_popup_gw > 1:
            if st.button("‹", key="gw_left_arr", use_container_width=True):
                st.session_state.popup_gw = current_popup_gw - 1
                st.rerun()

    with nav_col2:
        st.markdown(
            f"<div style='text-align:center;font-size:16px;font-weight:800;color:#37003c;padding-top:4px;'>Gameweek {current_popup_gw}</div>",
            unsafe_allow_html=True
        )

    with nav_col3:
        if current_popup_gw < last_gw:
            if st.button("›", key="gw_right_arr", use_container_width=True):
                st.session_state.popup_gw = current_popup_gw + 1
                st.rerun()

    html_code = build_full_pitch_html(tdata["pitch_data"])
    components.html(html_code, height=480, scrolling=False)

# -------------------------------------------------------------
# 5. SIDEBAR DASHBOARD & FPL CHIP CARDS
# -------------------------------------------------------------
if "custom_ft" not in st.session_state:
    st.session_state.custom_ft = data["calculated_ft"]

# Chip SVG Icons
CHIP_SVGS = {
    "wildcard": '''<svg width="32" height="32" viewBox="0 0 40 40" fill="none"><polygon points="20,2 36,11 36,29 20,38 4,29 4,11" fill="#00d4ff" stroke="#0072ff" stroke-width="2"/><polygon points="20,10 23,16 30,17 25,22 26,29 20,25 14,29 15,22 10,17 17,16" fill="#ffffff"/></svg>''',
    "freehit": '''<svg width="32" height="32" viewBox="0 0 40 40" fill="none"><polygon points="20,2 36,11 36,29 20,38 4,29 4,11" fill="#00d4ff" stroke="#0072ff" stroke-width="2"/><rect x="11" y="14" width="18" height="12" rx="2" fill="#ffffff"/><circle cx="11" cy="20" r="2.5" fill="#00d4ff"/><circle cx="29" cy="20" r="2.5" fill="#00d4ff"/><text x="20" y="22" font-size="6" font-weight="900" fill="#0072ff" text-anchor="middle">FREE</text></svg>''',
    "bboost": '''<svg width="32" height="32" viewBox="0 0 40 40" fill="none"><polygon points="20,2 36,11 36,29 20,38 4,29 4,11" fill="#00d4ff" stroke="#0072ff" stroke-width="2"/><rect x="11" y="22" width="18" height="4" rx="1.5" fill="#ffffff"/><path d="M15 26v4M25 26v4" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/><path d="M20 11l-5 6h10l-5-6z" fill="#ffffff"/></svg>''',
    "3xc": '''<svg width="32" height="32" viewBox="0 0 40 40" fill="none"><polygon points="20,2 36,11 36,29 20,38 4,29 4,11" fill="#00d4ff" stroke="#0072ff" stroke-width="2"/><circle cx="20" cy="20" r="9" fill="#ffffff"/><text x="20" y="24" font-size="11" font-weight="900" fill="#0072ff" text-anchor="middle">3C</text></svg>'''
}

CHIP_META = {
    "wildcard": "Wildcard",
    "freehit": "Free Hit",
    "bboost": "Bench Boost",
    "3xc": "Triple Captain"
}

def render_chip_card_html(chip_id):
    label = CHIP_META[chip_id]
    svg_icon = CHIP_SVGS[chip_id]
    is_played = chip_id in data["chips_played"]
    gw_num = data["chips_played"].get(chip_id)

    if is_played:
        return f"""
        <div style="background:#f8f9fa; border:1px solid #e2e8f0; border-radius:10px; padding:8px 4px; text-align:center; margin-bottom:8px; opacity:0.65;">
            <div style="filter: grayscale(100%); display:flex; justify-content:center; margin-bottom:3px;">{svg_icon}</div>
            <div style="font-size:11px; font-weight:800; color:#64748b;">{label}</div>
            <div style="background:#37003c; color:#ffffff; font-size:9px; font-weight:800; border-radius:4px; padding:2px 6px; margin-top:3px; display:inline-block;">
                Played GW {gw_num}
            </div>
        </div>
        """
    else:
        return f"""
        <div style="background:#ffffff; border:1px solid #e0e7ff; border-radius:10px; padding:8px 4px; text-align:center; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
            <div style="display:flex; justify-content:center; margin-bottom:3px;">{svg_icon}</div>
            <div style="font-size:11px; font-weight:800; color:#37003c;">{label}</div>
            <div style="color:#00875a; font-size:9px; font-weight:800; margin-top:3px;">
                Available
            </div>
        </div>
        """

with st.sidebar:
    if data["is_live_matchday"]:
        st.header(f"⚽ Live: GW {last_gw}")
        st.caption(f"Targeting: **Gameweek {target_gw}**")
    else:
        st.header(f"🎯 Gameweek {target_gw}")
        st.caption(f"Manager: **{data['manager_name']}** | Team: **{data['team_name']}**")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total Points", data['total_points'])
        st.metric("Overall Rank", f"{data['overall_rank']:,}")
    with c2:
        st.metric("Bank Balance", f"£{data['bank']}m")
        st.session_state.custom_ft = st.number_input(
            "Free Transfers", min_value=1, max_value=5, value=st.session_state.custom_ft, step=1
        )

    # 2x2 Official FPL Chip Grid
    st.markdown("<div style='font-size:13px; font-weight:800; color:#37003c; margin: 10px 0 6px 0;'>🃏 FPL Chips</div>", unsafe_allow_html=True)
    chip_c1, chip_c2 = st.columns(2)
    with chip_c1:
        st.markdown(render_chip_card_html("wildcard"), unsafe_allow_html=True)
        st.markdown(render_chip_card_html("bboost"), unsafe_allow_html=True)
    with chip_c2:
        st.markdown(render_chip_card_html("freehit"), unsafe_allow_html=True)
        st.markdown(render_chip_card_html("3xc"), unsafe_allow_html=True)

    st.info(f"🌍 **World #1:** {data['world_leader']['name']} ({data['world_leader']['team']}) — **{data['world_leader']['points']} pts**")

    st.subheader("🏆 Mini-League Leaderboard")
    selected_league_label = st.selectbox("Select Mini-League:", list(LEAGUES_DICT.keys()), index=0)
    selected_league_id = LEAGUES_DICT[selected_league_label]

    league_name, league_table, all_league_managers = fetch_mini_league_full(selected_league_id)
    st.caption(f"Standings for **{league_name}**")
    st.dataframe(pd.DataFrame(league_table), hide_index=True, use_container_width=True)

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
            st.session_state.active_dialog_team = all_league_managers[chosen_manager_label]
            st.session_state.popup_gw = last_gw
            st.rerun()

    st.divider()

    st.subheader("📈 Price Movement Radar")
    tab_risers, tab_fallers = st.tabs(["🔥 Risers", "❄️ Fallers"])
    with tab_risers:
        if data["risers_list"]:
            st.dataframe(pd.DataFrame(data["risers_list"]), hide_index=True, use_container_width=True)
        else:
            st.caption("No price rises recorded today.")
    with tab_fallers:
        if data["fallers_list"]:
            st.dataframe(pd.DataFrame(data["fallers_list"]), hide_index=True, use_container_width=True)
        else:
            st.caption("No price falls recorded today.")

if "active_dialog_team" in st.session_state and st.session_state.active_dialog_team is not None:
    render_squad_dialog(st.session_state.active_dialog_team)

# -------------------------------------------------------------
# 6. HEADER & INLINE COMPACT THREAD SELECTOR
# -------------------------------------------------------------
saved_threads = load_all_threads()
if not saved_threads:
    default_thread = f"GW {target_gw} Strategy"
    saved_threads[default_thread] = []
    save_all_threads(saved_threads)

thread_names = list(saved_threads.keys())
if "selected_thread" not in st.session_state or st.session_state.selected_thread not in thread_names:
    st.session_state.selected_thread = thread_names[-1]

if "show_thread_picker" not in st.session_state:
    st.session_state.show_thread_picker = False

st.markdown("<h2 style='margin:0; padding:0; font-size:1.75rem;'>⚽ FPL AI Strategist</h2>", unsafe_allow_html=True)

head_col1, head_col2, _ = st.columns([0.45, 0.08, 0.47])
with head_col1:
    st.markdown(f"<div style='font-size:1.25rem; font-weight:800; color:#37003c; padding-top:2px;'>🧵 {st.session_state.selected_thread}</div>", unsafe_allow_html=True)
with head_col2:
    if st.button("⌵", key="toggle_thread_btn", help="Switch or create thread"):
        st.session_state.show_thread_picker = not st.session_state.show_thread_picker
        st.rerun()

st.markdown(f"<div style='font-size:0.85rem; color:#666; margin-top:-4px; margin-bottom:6px;'>Targeting: <b>Gameweek {target_gw}</b> | Active Mini-League: <b>Crazy Football Fans</b></div>", unsafe_allow_html=True)

if st.session_state.show_thread_picker:
    p_col1, p_col2, p_col3 = st.columns([5, 4, 1])
    with p_col1:
        picked = st.selectbox(
            "Select thread:",
            thread_names,
            index=thread_names.index(st.session_state.selected_thread),
            label_visibility="collapsed"
        )
        if picked != st.session_state.selected_thread:
            st.session_state.selected_thread = picked
            st.session_state.show_thread_picker = False
            st.rerun()
    with p_col2:
        new_title = st.text_input("New Thread Name", placeholder="e.g. GW5 Transfers", label_visibility="collapsed")
    with p_col3:
        if st.button("➕", help="Add thread", use_container_width=True) and new_title.strip():
            c_name = new_title.strip()
            if c_name not in saved_threads:
                saved_threads[c_name] = []
                save_all_threads(saved_threads)
                st.session_state.selected_thread = c_name
                st.session_state.show_thread_picker = False
                st.rerun()

# -------------------------------------------------------------
# 7. CHAT DISPLAY & DYNAMIC INTENT-BASED AI STRATEGIST
# -------------------------------------------------------------
current_thread = st.session_state.selected_thread

clean_active_messages = []
for m in saved_threads.get(current_thread, []):
    content_text = m.get("content", "")
    if "Strategy engine error" not in content_text and "google.genai.errors" not in content_text and "ClientError" not in content_text:
        clean_active_messages.append(m)

for msg in clean_active_messages:
    with st.chat_message(msg["role"]):
        st.caption(f"🗓️ {msg.get('timestamp', '')} | {msg.get('gw_tag', f'Target: GW {target_gw}')}")
        st.markdown(msg["content"])

with st.expander("📎 Attach Screenshot / Data File (Optional)", expanded=False):
    uploaded_file = st.file_uploader(
        "Upload image or CSV:",
        type=["png", "jpg", "jpeg", "webp", "csv", "txt"],
        label_visibility="collapsed",
        key="file_uploader"
    )

if prompt := st.chat_input(f"Ask strategist in '{current_thread}'..."):
    now_str = datetime.now().strftime("%b %d, %Y • %I:%M %p")
    gw_badge = f"⚽ Target: GW {target_gw}" if not data["is_live_matchday"] else f"⚽ Live: GW {last_gw} (Target: GW {target_gw})"

    user_entry = {"role": "user", "content": prompt, "timestamp": now_str, "gw_tag": gw_badge}
    clean_active_messages.append(user_entry)
    with st.chat_message("user"):
        st.caption(f"🗓️ {now_str} | {gw_badge}")
        st.markdown(prompt)
        if uploaded_file:
            st.caption(f"📎 Attached: {uploaded_file.name}")

    user_pitch_info = fetch_team_pitch_data(MY_TEAM_ID, last_gw, data["elements_detail"])

    xp_squad_lines = []
    starter_total_next_gw = 0.0
    starter_total_3gw = 0.0

    if user_pitch_info and user_pitch_info["all_squad"]:
        for p in user_pitch_info["all_squad"]:
            nxt = float(p.get("xp_next_gw", 3.0))
            t3 = float(p.get("xp_3gw", 9.0))
            if not p.get("bench_order"):
                starter_total_next_gw += nxt
                starter_total_3gw += t3
            cap_mark = " (C)" if p.get("is_captain") else ""
            xp_squad_lines.append(f"| {p['name']}{cap_mark} | {p['pos']} | £{p['cost']} | {nxt:.1f} | {t3:.1f} |")

    squad_xp_table = "\n".join(xp_squad_lines)

    system_instruction = (
        f"You are the elite FPL Chief Strategist managing {data['manager_name']}'s squad '{data['team_name']}'.\n"
        f"Primary League: Crazy Football Fans (ID: 987870). Target Gameweek: GW {target_gw}.\n"
        f"Bank: £{data['bank']}m. Free Transfers Available: {st.session_state.custom_ft} FT.\n"
        f"Chips Inventory: Played={data['chips_played']}, Available={[c for c in ['wildcard','freehit','bboost','3xc'] if c not in data['chips_played']]}.\n"
        f"Anti-Fan Bias: Support for {MY_FAVORITE_CLUB} must never dictate decisions.\n\n"
        "COMMUNICATION & INTENT DIRECTIVES:\n"
        "- DYNAMIC ADAPTATION: Answer the user's specific prompt directly. NEVER force a repetitive boilerplate template (such as always generating Weak Link Analysis or Plan A/Plan B) unless the user explicitly asks for a full transfer plan.\n"
        "- Direct Statistical Inquiries: If the user asks about points, projected scores, or specific player comparisons (e.g. Mbeumo vs Szoboszlai), provide the exact data, comparative table, and concise verdict without unprompted transfer pitches.\n"
        "- Rival Inquiries: If the user asks about a rival manager or team, analyze that specific rival using available league data.\n"
        "- Decisive Advice: When advice is requested, be assertive with numbers, stats (xP, xGI, FDR), and tactical reasoning. Never deflect with 'What do you want to do?'."
    )

    prompt_context = (
        f"### LIVE GAMEWEEK {target_gw} CONTEXT\n"
        f"Free Transfers Bank: {st.session_state.custom_ft} FT | Bank Remaining: £{data['bank']}m\n"
        f"User Starting XI Projected Total: Next GW = {starter_total_next_gw:.1f} pts | 3-GW Total = {starter_total_3gw:.1f} pts\n\n"
        f"Current Squad Expected Points Matrix:\n"
        f"| Player | Position | Cost | GW{target_gw} xP | 3-GW xP |\n"
        f"| :--- | :--- | :--- | :--- | :--- |\n"
        f"{squad_xp_table}\n\n"
        f"Market Scouting Targets:\n"
        f"- Top FWDs: {[p['name'] + ' (3GW xP: ' + str(p['xp_3gw']) + ')' for p in data['scouting_radar']['top_xp_forwards']]}\n"
        f"- Top MIDs: {[p['name'] + ' (3GW xP: ' + str(p['xp_3gw']) + ')' for p in data['scouting_radar']['top_xp_midfielders']]}\n"
        f"- Top DEFs: {[p['name'] + ' (3GW xP: ' + str(p['xp_3gw']) + ')' for p in data['scouting_radar']['top_xp_defenders']]}\n\n"
        f"Mini-League Top 5 Overview: {league_table[:5]}\n\n"
        f"User Query: {prompt}"
    )

    contents = []
    for m in clean_active_messages[:-1]:
        contents.append(
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])]
            )
        )

    current_parts = []
    if uploaded_file:
        current_parts.append(types.Part.from_bytes(data=uploaded_file.read(), mime_type=uploaded_file.type))
        current_parts.append(types.Part.from_text(text=f"Attached file: {uploaded_file.name}."))
    current_parts.append(types.Part.from_text(text=prompt_context))
    contents.append(types.Content(role="user", parts=current_parts))

    client = genai.Client(api_key=GEMINI_API_KEY)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing data and formulating response..."):
            try:
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                model_reply = response.text
                st.caption(f"🗓️ {now_str} | {gw_badge}")
                st.markdown(model_reply)

                assistant_entry = {
                    "role": "assistant",
                    "content": model_reply,
                    "timestamp": now_str,
                    "gw_tag": gw_badge
                }
                clean_active_messages.append(assistant_entry)
                saved_threads[current_thread] = clean_active_messages
                save_all_threads(saved_threads)
            except Exception as e:
                st.error(f"Strategy engine error: {str(e)}")
