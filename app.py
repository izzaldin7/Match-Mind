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
        border-radius: 4px;
        padding: 0.75rem 1.5rem;
        margin-bottom: 0.35rem;
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
    }
    div[data-testid="stHorizontalBlock"] div[data-testeid="stButton"] button:hover {
    color: #FFD700 !important;
    border-color: #FFD70040 !important;
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
    active_key = f"active_{key_prefix}_{mid}"

    # Match card HTML
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

    # Buttons inside the card area
    btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 6])
    if is_upcoming:
        with btn_col1:
            if st.button("⚡ Briefing", key=f"{key_prefix}_brief_{mid}"):
                with st.spinner("Analysing fixture..."):
                    result = api_get(f"/matches/{mid}/briefing")
                if result and "error" not in result:
                    st.session_state[modal_key] = ("briefing", result)
                    st.session_state[active_key] = True
                elif result:
                    st.error(result["error"])
    elif is_finished:
        with btn_col1:
            if st.button("📋 Report", key=f"{key_prefix}_report_{mid}"):
                with st.spinner("Compiling match report..."):
                    result = api_get(f"/matches/{mid}/report")
                if result and "error" not in result:
                    st.session_state[modal_key] = ("report", result)
                    st.session_state[active_key] = True
                elif result:
                    st.error(result["error"])

    # Modal display
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


# ── Header ─────────────────────────────────────────────────────────

st.markdown("""
<div class="mm-header">
    <div class="mm-logo">Match<span>Mind</span></div>
    <div class="mm-tagline">AI-Powered FIFA World Cup 2026 Companion</div>
</div>
<div class="mm-divider"></div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["Today", "All Fixtures", "Reports"])


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