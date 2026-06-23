import streamlit as st
import requests
from datetime import datetime

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="MatchMind",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    .stApp { background-color: #0a0e1a; color: #e8eaf0; }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding: 2rem 3rem;}

    .mm-header { text-align: center; margin-bottom: 0.25rem; }
    .mm-logo {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 3.5rem;
        color: #ffffff;
        letter-spacing: 4px;
        line-height: 1;
    }
    .mm-logo span { color: #FFD700; }
    .mm-tagline {
        font-family: 'Inter', sans-serif;
        font-size: 0.7rem;
        color: #6a7080;
        letter-spacing: 4px;
        text-transform: uppercase;
        font-weight: 500;
        margin-top: 0.25rem;
    }
    .mm-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, #FFD700 30%, #FF8C00 70%, transparent 100%);
        margin: 1rem auto 2rem auto;
        opacity: 0.5;
        max-width: 600px;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: transparent;
        gap: 0;
        border-bottom: 1px solid #1a2035;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        font-weight: 500;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #5a6070;
        padding: 0.75rem 2rem;
        border-bottom: 2px solid transparent;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #FFD700 !important;
        border-bottom: 2px solid #FFD700 !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab-panel"] { padding-top: 2rem; }

    .match-card {
        background: #0f1525;
        border: 1px solid #1a2035;
        border-radius: 4px 4px 0 0;
        padding: 0.75rem 1.5rem;
        margin-bottom: 0;
        transition: border-color 0.2s;
    }
    .match-card:hover { border-color: #FFD70030; }
    .match-card-live { border-left: 3px solid #ff3b5c; }
    .match-card-finished { border-left: 3px solid #FF8C00; }
    .match-card-upcoming { border-left: 3px solid #FFD700; }

    .status-live { color: #ff3b5c; font-weight: 600; animation: pulse 2s infinite; }
    .status-finished { color: #FF8C00; }
    .status-upcoming { color: #FFD700; }

    @keyframes pulse {
        0%, 100% {opacity: 1;}
        50% {opacity: 0.5;}
    }

    .group-badge {
        display: inline-block;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        color: #FFD700;
        background: #FFD70015;
        border: 1px solid #FFD70030;
        padding: 0.15rem 0.5rem;
        border-radius: 2px;
        letter-spacing: 1px;
    }

    .ai-modal {
        background: #0d1220;
        border: 1px solid #FFD70030;
        border-radius: 6px;
        padding: 2rem;
        margin-top: 0.5rem;
        margin-bottom: 1.5rem;
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        line-height: 1.8;
        color: #c8cad4;
        position: relative;
    }
    .ai-modal-header {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 1.6rem;
        letter-spacing: 3px;
        color: #FFD700;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #1a2035;
    }
    .ai-modal-fixture {
        text-align: center;
        margin-bottom: 1.5rem;
        padding-bottom: 1.5rem;
        border-bottom: 1px solid #1a2035;
    }
    .ai-modal-teams {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 2rem;
        letter-spacing: 3px;
        color: #ffffff;
    }
    .ai-modal-score {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2.5rem;
        font-weight: 500;
        color: #FFD700;
        margin: 0.25rem 0;
    }
    .ai-modal-sub {
        font-family: 'Inter', sans-serif;
        font-size: 0.7rem;
        color: #5a6070;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 0.25rem;
    }

    .stButton button {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        background: transparent;
        color: #FFD700;
        border: 1px solid #FFD70040;
        border-radius: 3px;
        padding: 0.5rem 1.25rem;
        transition: all 0.2s;
        width: 100%;
    }
    .stButton button:hover {
        background: #FFD70010;
        border-color: #FFD700;
    }

    .stSelectbox label {
        font-family: 'Inter', sans-serif;
        font-size: 0.7rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #5a6070;
    }
    .stAlert {
        background: #0f1525;
        border-color: #1a2035;
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
    }
    .stSpinner { color: #FFD700; }
    .section-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.65rem;
        letter-spacing: 3px;
        text-transform: uppercase;
        color: #5a6070;
        margin-bottom: 1rem;
    }

    .standings-wrap {
        background: #0f1525;
        border: 1px solid #1a2035;
        border-radius: 4px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }
    .standings-row {
        display: flex;
        align-items: center;
        padding: 0.4rem 0;
        border-bottom: 1px solid #0a0e1a;
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
    }
    .standings-row:last-child { border-bottom: none; }
    .standings-header {
        font-size: 0.6rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #5a6070;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #1a2035;
        margin-bottom: 0.25rem;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0 !important;
        margin-top: -0.5rem !important;
        margin-bottom: 0.75rem !important;
    }

    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {
        border-top: none !important;
        border-top-left-radius: 0 !important;
        border-top-right-radius: 0 !important;
        width: auto !important;
        padding: 0.3rem 1rem !important;
        font-size: 0.65rem !important;
        color: #5a6070 !important;
        border-color: #1a2035 !important;
        background: #0f1525 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button:hover {
        color: #FFD700 !important;
        border-color: #FFD70040 !important;
        background: #FFD70010 !important;
    }
    div[data-testid="column"] + div[data-testid="column"] {
        padding-left: 1rem !important;
    }
    .s-team { flex: 3; color: #e8eaf0; font-weight: 600; }
    .s-team-gold { flex: 3; color: #FFD700; font-weight: 600; }
    .s-num { flex: 1; text-align: center; color: #c8cad4; }
    .s-pts { flex: 1; text-align: center; color: #FFD700; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────

def api_get(endpoint):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to MatchMind API. Make sure the server is running.")
        return None
    except requests.exceptions.HTTPError as e:
        return {"error": e.response.json().get("detail", str(e))}
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None


def api_post(endpoint, payload):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to MatchMind API. Make sure the server is running.")
        return None
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except (ValueError, requests.exceptions.JSONDecodeError):
            detail = f"Server error ({e.response.status_code}): no response body"
        return {"error": detail}
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None


def status_class(status):
    s = status.upper()
    if s in ("IN_PLAY", "PAUSED", "HALFTIME"):
        return "match-card-live", "status-live", "● LIVE"
    elif s in ("FINISHED",):
        return "match-card-finished", "status-finished", "FINISHED"
    else:
        return "match-card-upcoming", "status-upcoming", "UPCOMING"


def format_score(home_score, away_score, status):
    s = status.upper()
    if s in ("IN_PLAY", "PAUSED", "HALFTIME", "FINISHED"):
        h = home_score if home_score is not None else "?"
        a = away_score if away_score is not None else "?"
        return f"{h} — {a}"
    return "vs"


def group_display(group):
    if not group:
        return ""
    return group.replace("GROUP_", "Group ")


def format_ai_text(text):
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.strip().split('\n\n') if p.strip()]
    lines_html = []
    for i, para in enumerate(paragraphs):
        lines = para.split('\n')
        joined = '<br>'.join(lines)
        if i == 0 and len(para) < 120:
            lines_html.append(
                f'<p style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;'
                f'letter-spacing:2px;color:#ffffff;margin:0 0 1.25rem 0;">{joined}</p>'
            )
        else:
            lines_html.append(f'<p style="margin:0 0 1.2rem 0;">{joined}</p>')
    return ''.join(lines_html)


def render_standings(standings):
    if not standings:
        st.markdown('<div style="color:#5a6070;font-size:0.8rem;padding:0.5rem 0;">No matches played yet.</div>', unsafe_allow_html=True)
        return

    header = '<div class="standings-row standings-header"><div class="s-team">Team</div><div class="s-num">P</div><div class="s-num">W</div><div class="s-num">D</div><div class="s-num">L</div><div class="s-num">GD</div><div class="s-pts">Pts</div></div>'
    rows = ""
    for i, row in enumerate(standings):
        team_cls = "s-team-gold" if i < 2 else "s-team"
        rows += f'<div class="standings-row"><div class="{team_cls}">{row["team"]}</div><div class="s-num">{row["played"]}</div><div class="s-num">{row["won"]}</div><div class="s-num">{row["drawn"]}</div><div class="s-num">{row["lost"]}</div><div class="s-num">{row["gd"]}</div><div class="s-pts">{row["points"]}</div></div>'

    st.markdown(f'<div class="standings-wrap">{header}{rows}</div>', unsafe_allow_html=True)


def _short_name(full_name):
    if not full_name:
        return ""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0][:10]
    last = parts[-1]
    if len(last) <= 9:
        return last
    return last[:9]


def render_lineup_card(lineup_data, home_team, away_team):
    home = lineup_data.get("home") or {}
    away = lineup_data.get("away") or {}

    home_name = home.get("name") or home_team
    away_name = away.get("name") or away_team
    home_formation = home.get("formation", "")
    away_formation = away.get("formation", "")

    def flatten_rows(rows):
        players = []
        for row in rows:
            if isinstance(row, list):
                players.extend(row)
        return players

    home_starters = flatten_rows(home.get("initialLineup", []))
    away_starters = flatten_rows(away.get("initialLineup", []))
    home_subs = home.get("substitutes", [])
    away_subs = away.get("substitutes", [])

    st.markdown(f"""
<div style="text-align:center;margin-bottom:1.5rem;">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:1.8rem;letter-spacing:3px;color:#ffffff;">
        {home_name} <span style="color:#5a6070;font-size:1rem;">vs</span> {away_name}
    </div>
    <div style="font-family:'Inter',sans-serif;font-size:0.65rem;color:#5a6070;letter-spacing:3px;text-transform:uppercase;margin-top:0.25rem;">
        Starting Lineups · 2026 FIFA World Cup
    </div>
</div>
""", unsafe_allow_html=True)

    if not home_starters and not away_starters:
        st.markdown("""
<div style="text-align:center;padding:2rem;color:#5a6070;font-family:'Inter',sans-serif;font-size:0.85rem;letter-spacing:1px;">
    Match lineups not available yet. Check back closer to kickoff.
</div>
""", unsafe_allow_html=True)
        return

    col_home, col_div, col_away = st.columns([5, 0.2, 5])

    def render_team_column(col, team_name, formation, starters, subs):
        with col:
            badge = f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.65rem;color:#5a6070;background:#0a0e1a;border:1px solid #1a2035;border-radius:2px;padding:0.1rem 0.5rem;letter-spacing:2px;">{formation}</span>' if formation else ""
            st.markdown(f"""
<div style="text-align:center;margin-bottom:0.75rem;">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:3px;color:#FFD700;margin-bottom:0.3rem;">{team_name}</div>
    {badge}
</div>
""", unsafe_allow_html=True)

            st.markdown('<div style="font-family:\'Inter\',sans-serif;font-size:0.6rem;letter-spacing:2px;text-transform:uppercase;color:#5a6070;margin-bottom:0.4rem;">Starting XI</div>', unsafe_allow_html=True)

            for p in starters:
                num = p.get("number") or "—"
                name = p.get("name") or ""
                pos = p.get("position") or ""
                pos_color = "#FF8C00" if "goalkeeper" in pos.lower() else "#4a6fa5"
                pos_short = pos[:3].upper() if pos else ""
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.6rem;padding:0.3rem 0.5rem;border-bottom:1px solid #0f1525;">
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:{pos_color};width:20px;text-align:center;flex-shrink:0;">{num}</div>
    <div style="font-family:'Inter',sans-serif;font-size:0.8rem;color:#e8eaf0;flex:1;">{name}</div>
    <div style="font-family:'Inter',sans-serif;font-size:0.58rem;color:#5a6070;letter-spacing:0.5px;">{pos_short}</div>
</div>
""", unsafe_allow_html=True)

            if subs:
                st.markdown('<div style="font-family:\'Inter\',sans-serif;font-size:0.6rem;letter-spacing:2px;text-transform:uppercase;color:#5a6070;margin-top:1rem;margin-bottom:0.4rem;">Substitutes</div>', unsafe_allow_html=True)
                for s in subs:
                    num = s.get("number") or "—"
                    name = s.get("name") or ""
                    pos = s.get("position") or ""
                    pos_short = pos[:3].upper() if pos else ""
                    st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.6rem;padding:0.25rem 0.5rem;border-bottom:1px solid #0a0e1a;">
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#3a4060;width:20px;text-align:center;flex-shrink:0;">{num}</div>
    <div style="font-family:'Inter',sans-serif;font-size:0.78rem;color:#8a8ea8;flex:1;">{name}</div>
    <div style="font-family:'Inter',sans-serif;font-size:0.58rem;color:#5a6070;">{pos_short}</div>
</div>
""", unsafe_allow_html=True)

    render_team_column(col_home, home_name, home_formation, home_starters, home_subs)

    with col_div:
        st.markdown('<div style="width:1px;background:#1a2035;min-height:400px;margin:0 auto;"></div>', unsafe_allow_html=True)

    render_team_column(col_away, away_name, away_formation, away_starters, away_subs)


def render_match_card(m, key_prefix=""):
    card_class, status_cls, status_label = status_class(m["status"])
    score = format_score(m.get("home_score"), m.get("away_score"), m["status"])
    grp = group_display(m.get("group", ""))
    group_badge_html = f'<span class="group-badge">{grp}</span>' if grp else ""
    date_val = m.get("date") or ""
    date_html = f'<span style="color:#5a6070;font-family:Inter,sans-serif;font-size:0.65rem;">{date_val}</span>' if date_val else ""
    kickoff_val = m.get("kick_off_time") or ""
    kickoff_html = f'<span style="color:#5a6070;font-family:Inter,sans-serif;font-size:0.65rem;">⏱ {kickoff_val}</span>' if kickoff_val else ""
    meta_row = f'{group_badge_html}<span class="{status_cls}" style="font-family:\'Inter\',sans-serif;font-size:0.65rem;letter-spacing:1px;text-transform:uppercase;">{status_label}</span>{date_html}{kickoff_html}'
    is_finished = m["status"].upper() in ("FINISHED",)
    is_upcoming = m["status"].upper() not in ("FINISHED", "IN_PLAY", "PAUSED", "HALFTIME")
    mid = m['match_id']
    modal_key = f"ai_result_{mid}"
    lineup_key = f"lineup_result_{mid}"
    active_key = f"active_{key_prefix}_{mid}"
    lineup_active_key = f"lineup_active_{key_prefix}_{mid}"

    st.markdown(f"""
<div class="match-card {card_class}">
    <div style="display:flex;align-items:center;justify-content:center;gap:1.5rem;">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:2px;color:#ffffff;text-align:right;flex:1;">{m['home_team']}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:1.3rem;font-weight:500;color:#FFD700;min-width:90px;text-align:center;line-height:1;position:relative;top:-2px;">{score}</div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:2px;color:#ffffff;text-align:left;flex:1;">{m['away_team']}</div>
    </div>
    <div style="display:flex;align-items:center;justify-content:center;gap:0.75rem;margin-top:0.5rem;">
        {meta_row}
    </div>
</div>
""", unsafe_allow_html=True)

    details_key = f"details_open_{key_prefix}_{mid}"
    is_live = not is_finished and not is_upcoming

    # Single details button, bottom left
    btn_col1, _ = st.columns([2, 10])
    with btn_col1:
        btn_label = "✕ Details" if st.session_state.get(details_key) else "⚡ Details"
        if st.button(btn_label, key=f"{key_prefix}_details_{mid}"):
            st.session_state[details_key] = not st.session_state.get(details_key, False)
            st.rerun()

    # Sub-buttons revealed on click
    if st.session_state.get(details_key):
        if is_live:
            sub1, _ = st.columns([2, 10])
            with sub1:
                if st.button("🗒 Lineup", key=f"{key_prefix}_lineup_{mid}"):
                    st.session_state[active_key] = False
                    with st.spinner("Fetching lineup..."):
                        result = api_get(f"/matches/{mid}/lineup")
                    if result and "error" not in result:
                        st.session_state[lineup_key] = result
                        st.session_state[lineup_active_key] = True
                    elif result:
                        st.error(result["error"])
        else:
            sub1, sub2, _ = st.columns([2, 2, 8])
            with sub1:
                action_label = "⚡ Briefing" if is_upcoming else "📋 Report"
                if st.button(action_label, key=f"{key_prefix}_action_{mid}"):
                    if is_upcoming:
                        st.session_state[lineup_active_key] = False
                        with st.spinner("Analysing fixture..."):
                            result = api_get(f"/matches/{mid}/briefing")
                        if result and "error" not in result:
                            st.session_state[modal_key] = ("briefing", result)
                            st.session_state[active_key] = True
                        elif result:
                            st.error(result["error"])
                    else:
                        st.session_state[lineup_active_key] = False
                        with st.spinner("Compiling match report..."):
                            result = api_get(f"/matches/{mid}/report")
                        if result and "error" not in result:
                            st.session_state[modal_key] = ("report", result)
                            st.session_state[active_key] = True
                        elif result:
                            st.error(result["error"])
            with sub2:
                if st.button("🗒 Lineup", key=f"{key_prefix}_lineup_{mid}"):
                    st.session_state[active_key] = False
                    with st.spinner("Fetching lineup..."):
                        result = api_get(f"/matches/{mid}/lineup")
                    if result and "error" not in result:
                        st.session_state[lineup_key] = result
                        st.session_state[lineup_active_key] = True
                    elif result:
                        st.error(result["error"])

    # ── AI modal (briefing / report) ───────────────────────────────
    if st.session_state.get(active_key) and modal_key in st.session_state:
        result_type, r = st.session_state[modal_key]

        close_col, _ = st.columns([1, 9])
        with close_col:
            if st.button("✕ Close", key=f"close_{key_prefix}_{mid}"):
                st.session_state[active_key] = False
                st.rerun()

        if result_type == "briefing":
            st.markdown(f"""
<div class="ai-modal">
    <div class="ai-modal-fixture">
        <div class="ai-modal-teams">{r['home_team']} <span style="color:#5a6070;font-size:1rem;letter-spacing:2px;">vs</span> {r['away_team']}</div>
        <div class="ai-modal-sub"><span class="group-badge">{group_display(r.get('group',''))}</span>&nbsp; {r.get('date','')} · Pre-Match Briefing</div>
    </div>
    <div class="ai-modal-header">Match Intelligence</div>
    {format_ai_text(r['briefing'])}
</div>
""", unsafe_allow_html=True)
        else:
            home_s = r.get("home_score", "?")
            away_s = r.get("away_score", "?")
            st.markdown(f"""
<div class="ai-modal">
    <div class="ai-modal-fixture">
        <div class="ai-modal-teams">{r['home_team']} <span style="color:#5a6070;font-size:1rem;letter-spacing:2px;">vs</span> {r['away_team']}</div>
        <div class="ai-modal-score">{home_s} — {away_s}</div>
        <div class="ai-modal-sub"><span class="group-badge">{group_display(r.get('group',''))}</span>&nbsp; Full Time · Post-Match Report</div>
    </div>
    <div class="ai-modal-header">Match Report</div>
    {format_ai_text(r['report'])}
</div>
""", unsafe_allow_html=True)

    # ── Lineup modal ───────────────────────────────────────────────
    if st.session_state.get(lineup_active_key) and lineup_key in st.session_state:
        r = st.session_state[lineup_key]

        close_col, _ = st.columns([1, 9])
        with close_col:
            if st.button("✕ Close", key=f"close_lineup_{key_prefix}_{mid}"):
                st.session_state[lineup_active_key] = False
                st.rerun()

        render_lineup_card(
            r["lineup"],
            r.get("home_team", m["home_team"]),
            r.get("away_team", m["away_team"])
        )


# ── Header ─────────────────────────────────────────────────────────

st.markdown("""
<div class="mm-header">
    <div class="mm-logo">Match<span>Mind</span></div>
    <div class="mm-tagline">AI-Powered FIFA World Cup 2026 Companion</div>
</div>
<div class="mm-divider"></div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["Today", "All Fixtures", "Reports", "Fan Debate"])


# ══════════════════════════════════════════════════════════════════
# TAB 1 — TODAY
# ══════════════════════════════════════════════════════════════════

with tab1:
    today_str = datetime.today().strftime("%A, %B %d")
    st.markdown(f'<div class="section-label">{today_str}</div>', unsafe_allow_html=True)

    data = api_get("/matches/today")
    if data is None:
        st.stop()

    if not data:
        st.markdown('<div class="match-card"><div style="text-align:center;color:#5a6070;padding:0.5rem;font-family:Inter,sans-serif;font-size:0.85rem;">No matches scheduled today.</div></div>', unsafe_allow_html=True)
    else:
        for m in data:
            render_match_card(m, key_prefix="today")


# ══════════════════════════════════════════════════════════════════
# TAB 2 — ALL FIXTURES
# ══════════════════════════════════════════════════════════════════

with tab2:
    all_data = api_get("/matches")

    if all_data and "error" not in all_data:
        groups = {}
        knockout = []
        for m in all_data:
            g = m.get("group")
            if g:
                groups.setdefault(g, []).append(m)
            else:
                knockout.append(m)

        filter_col1, filter_col2 = st.columns([3, 1])
        with filter_col1:
            selected_group = st.selectbox("Filter by group", ["All Groups"] + sorted(groups.keys()), label_visibility="collapsed")
        with filter_col2:
            status_filter = st.selectbox("Filter by status", ["All", "Upcoming", "Finished"], label_visibility="collapsed")

        st.markdown("<br>", unsafe_allow_html=True)

        def filter_matches(matches):
            if status_filter == "Upcoming":
                return [m for m in matches if m["status"].upper() not in ("FINISHED",)]
            elif status_filter == "Finished":
                return [m for m in matches if m["status"].upper() in ("FINISHED",)]
            return matches

        def render_group_section(group_name, matches):
            filtered = filter_matches(matches)
            if not filtered and status_filter != "All":
                return

            st.markdown(f'<div class="section-label">{group_display(group_name)}</div>', unsafe_allow_html=True)
            left_col, gap_col, right_col = st.columns([3, 0.2, 2])

            with left_col:
                st.markdown('<div class="section-label">Matches</div>', unsafe_allow_html=True)
                if filtered:
                    for m in filtered:
                        render_match_card(m, key_prefix=f"fix_{group_name}")
                else:
                    st.markdown('<div style="color:#5a6070;font-size:0.8rem;padding:0.5rem 0;">No matches for this filter.</div>', unsafe_allow_html=True)

            with right_col:
                st.markdown('<div class="section-label">Standings</div>', unsafe_allow_html=True)
                from utils import get_group_standings
                standings = get_group_standings(group_name)
                render_standings(standings)

            st.markdown("<hr style='border:none;border-top:1px solid #1a2035;margin:1.5rem 0;'>", unsafe_allow_html=True)

        if selected_group == "All Groups":
            for g in sorted(groups.keys()):
                render_group_section(g, groups[g])
            if knockout:
                real_knockout = [m for m in knockout if m.get("home_team") and m.get("away_team")]
                if real_knockout:
                    render_group_section("Knockout Stage", real_knockout)
        else:
            render_group_section(selected_group, groups.get(selected_group, []))


# ══════════════════════════════════════════════════════════════════
# TAB 3 — REPORTS
# ══════════════════════════════════════════════════════════════════

with tab3:
    st.markdown('<div class="section-label">Finished Matches — Select to Generate Report</div>', unsafe_allow_html=True)

    all_matches = api_get("/matches")

    if all_matches and "error" not in all_matches:
        finished_matches = [m for m in all_matches if m["status"].upper() in ("FINISHED",)]

        if not finished_matches:
            st.markdown('<div style="color:#5a6070;font-size:0.85rem;padding:1rem 0;">No finished matches yet.</div>', unsafe_allow_html=True)
        else:
            finished_matches.sort(key=lambda x: (x.get("date", ""), x.get("kick_off_time", "")), reverse=True)
            by_date = {}
            for m in finished_matches:
                d = m.get("date", "Unknown")
                by_date.setdefault(d, []).append(m)

            for date_key in sorted(by_date.keys(), reverse=True):
                st.markdown(f'<div class="section-label">{date_key}</div>', unsafe_allow_html=True)
                for m in by_date[date_key]:
                    render_match_card(m, key_prefix="reports")


# ══════════════════════════════════════════════════════════════════
# TAB 4 — FAN DEBATE
# ══════════════════════════════════════════════════════════════════

with tab4:
    st.markdown('<div class="section-label">Fan Debate Analyzer — 2026 FIFA World Cup</div>', unsafe_allow_html=True)

    debate_type = st.radio(
        "Compare", ["Players", "Teams"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if debate_type == "Players":
        st.markdown('<div class="section-label">Enter player names as they appear in match data (2–4 players)</div>', unsafe_allow_html=True)

        if "debate_player_count" not in st.session_state:
            st.session_state["debate_player_count"] = 2

        player_inputs = []
        for i in range(st.session_state["debate_player_count"]):
            val = st.text_input(
                f"Player {i + 1}",
                key=f"debate_player_{i}",
                label_visibility="collapsed",
                placeholder=f"Player {i + 1} name"
            )
            player_inputs.append(val)

        add_col, remove_col, _ = st.columns([1, 1, 6])
        with add_col:
            if st.session_state["debate_player_count"] < 4:
                if st.button("+ Add player"):
                    st.session_state["debate_player_count"] += 1
                    st.rerun()
        with remove_col:
            if st.session_state["debate_player_count"] > 2:
                if st.button("– Remove"):
                    st.session_state["debate_player_count"] -= 1
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        players = [p.strip() for p in player_inputs if p.strip()]

        if st.button("⚡ Generate Debate", key="debate_players_btn"):
            if len(players) < 2:
                st.error("Enter at least 2 player names.")
            else:
                with st.spinner("Analyzing tournament data..."):
                    result = api_post("/debate/players", {"players": players})
                if result and "error" not in result:
                    st.session_state["debate_result"] = result
                elif result:
                    st.error(result["error"])

    else:  # Teams
        all_matches = api_get("/matches")
        team_list = []
        if all_matches and "error" not in all_matches:
            teams_seen = set()
            for m in all_matches:
                teams_seen.add(m["home_team"])
                teams_seen.add(m["away_team"])
            team_list = sorted(t for t in teams_seen if t)

        st.markdown('<div class="section-label">Select two teams to compare</div>', unsafe_allow_html=True)
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            team_a = st.selectbox("Team A", team_list, key="debate_team_a", label_visibility="collapsed")
        with t_col2:
            remaining = [t for t in team_list if t != team_a]
            team_b = st.selectbox("Team B", remaining, key="debate_team_b", label_visibility="collapsed")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("⚡ Generate Debate", key="debate_teams_btn"):
            with st.spinner("Analyzing tournament data..."):
                result = api_post("/debate/teams", {"teams": [team_a, team_b]})
            if result and "error" not in result:
                st.session_state["debate_result"] = result
            elif result:
                st.error(result["error"])

    # ── Result display ─────────────────────────────────────────────
    if "debate_result" in st.session_state:
        r = st.session_state["debate_result"]
        subjects = r.get("subjects", [])
        is_players = r.get("type") == "players"

        label = " vs ".join(subjects)
        sub_label = "Player Comparison" if is_players else "Team Comparison"

        close_col, _ = st.columns([1, 9])
        with close_col:
            if st.button("✕ Clear", key="debate_close"):
                del st.session_state["debate_result"]
                st.rerun()

        st.markdown(f"""
<div class="ai-modal">
    <div class="ai-modal-fixture">
        <div class="ai-modal-teams">{label}</div>
        <div class="ai-modal-sub">2026 FIFA World Cup · {sub_label}</div>
    </div>
    <div class="ai-modal-header">Fan Debate Analysis</div>
    {format_ai_text(r['debate'])}
</div>
""", unsafe_allow_html=True)