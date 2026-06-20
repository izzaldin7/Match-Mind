import streamlit as st
import requests
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="MatchMind",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Styling ────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    .stApp { background-color: #0a0e1a; color: #e8eaf0; }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding: 2rem 3rem;}

    .mm-header {
        text-align: center;
        margin-bottom: 0.25rem;
    }
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
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        cursor: pointer;
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

    .ai-output {
        background: #0f1525;
        border: 1px solid #1a2035;
        border-radius: 4px;
        padding: 2rem;
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        line-height: 1.8;
        color: #c8cad4;
    }
    .ai-output-header {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 1.6rem;
        letter-spacing: 3px;
        color: #FFD700;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #1a2035;
    }

    .fixture-header {
        background: linear-gradient(135deg, #0f1525 0%, #111827 100%);
        border: 1px solid #1a2035;
        border-radius: 4px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .fixture-teams-big {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 2.5rem;
        letter-spacing: 3px;
        color: #ffffff;
    }
    .fixture-vs {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        color: #5a6070;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin: 0 1rem;
    }
    .fixture-score-big {
        font-family: 'JetBrains Mono', monospace;
        font-size: 3rem;
        font-weight: 500;
        color: #FFD700;
        margin: 0.5rem 0;
    }
    .fixture-sub {
        font-family: 'Inter', sans-serif;
        font-size: 0.7rem;
        color: #5a6070;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 0.5rem;
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
    .stSelectbox [data-baseweb="select"] {
        background: #0f1525;
        border-color: #1a2035;
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

    .standings-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        margin-bottom: 1.5rem;
    }
    .standings-table th {
        font-size: 0.65rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #5a6070;
        padding: 0.5rem 0.75rem;
        border-bottom: 1px solid #1a2035;
        text-align: center;
    }
    .standings-table th:first-child { text-align: left; }
    .standings-table td {
        padding: 0.6rem 0.75rem;
        color: #c8cad4;
        border-bottom: 1px solid #0f1525;
        text-align: center;
    }
    .standings-table td:first-child {
        text-align: left;
        font-weight: 600;
        color: #e8eaf0;
    }
    .standings-table tr:last-child td { border-bottom: none; }
    .standings-pts {
        font-family: 'JetBrains Mono', monospace;
        color: #FFD700 !important;
        font-weight: 600;
    }

    .report-card {
        background: #0f1525;
        border: 1px solid #1a2035;
        border-left: 3px solid #FF8C00;
        border-radius: 4px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
        transition: border-color 0.2s;
    }
    .report-card:hover { border-color: #FFD700; }
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


def render_match_card(m, key_prefix=""):
    card_class, status_cls, status_label = status_class(m["status"])
    score = format_score(m.get("home_score"), m.get("away_score"), m["status"])
    group_badge = f'<span class="group-badge">{group_display(m.get("group", ""))}</span>' if m.get("group") else ""
    is_finished = m["status"].upper() in ("FINISHED",)
    is_upcoming = m["status"].upper() not in ("FINISHED", "IN_PLAY", "PAUSED", "HALFTIME")

    st.markdown(f"""
    <div class="match-card {card_class}">
        <div style="display:flex;align-items:center;justify-content:center;gap:1.5rem;">
            <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;letter-spacing:2px;color:#ffffff;text-align:right;flex:1;">
                {m['home_team']}
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:500;color:#FFD700;min-width:90px;text-align:center;line-height:1;position:relative;top:-2px;">
                {score}
            </div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;letter-spacing:2px;color:#ffffff;text-align:left;flex:1;">
                {m['away_team']}
            </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:center;gap:0.75rem;margin-top:0.5rem;">
            {group_badge}
            <span class="{status_cls}" style="font-family:'Inter',sans-serif;font-size:0.65rem;letter-spacing:1px;text-transform:uppercase;">{status_label}</span>
            {f'<span style="color:#5a6070;font-family:Inter,sans-serif;font-size:0.65rem;">{m.get("date","")}</span>' if m.get("date") else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    if is_upcoming:
        with col1:
            if st.button("Generate Briefing", key=f"{key_prefix}_brief_{m['match_id']}"):
                with st.spinner("Analysing fixture..."):
                    result = api_get(f"/matches/{m['match_id']}/briefing")
                if result and "error" not in result:
                    st.session_state[f"ai_result_{m['match_id']}"] = ("briefing", result)
                elif result:
                    st.error(result["error"])
    elif is_finished:
        with col1:
            if st.button("Generate Report", key=f"{key_prefix}_report_{m['match_id']}"):
                with st.spinner("Compiling match report..."):
                    result = api_get(f"/matches/{m['match_id']}/report")
                if result and "error" not in result:
                    st.session_state[f"ai_result_{m['match_id']}"] = ("report", result)
                elif result:
                    st.error(result["error"])

    # Display AI result inline below this card
    key = f"ai_result_{m['match_id']}"
    if key in st.session_state:
        result_type, r = st.session_state[key]
        if result_type == "briefing":
            st.markdown(f"""
            <div class="fixture-header">
                <div>
                    <span class="fixture-teams-big">{r['home_team']}</span>
                    <span class="fixture-vs">vs</span>
                    <span class="fixture-teams-big">{r['away_team']}</span>
                </div>
                <div class="fixture-sub">
                    <span class="group-badge">{group_display(r.get('group', ''))}</span>
                    &nbsp;{r.get('date', '')} · Pre-Match Briefing
                </div>
            </div>
            <div class="ai-output">
                <div class="ai-output-header">Match Intelligence</div>
                {format_ai_text(r['briefing'])}
            </div>
            """, unsafe_allow_html=True)
        else:
            home_s = r.get("home_score", "?")
            away_s = r.get("away_score", "?")
            st.markdown(f"""
            <div class="fixture-header">
                <div>
                    <span class="fixture-teams-big">{r['home_team']}</span>
                    <span class="fixture-vs">vs</span>
                    <span class="fixture-teams-big">{r['away_team']}</span>
                </div>
                <div class="fixture-score-big">{home_s} — {away_s}</div>
                <div class="fixture-sub">
                    <span class="group-badge">{group_display(r.get('group', ''))}</span>
                    &nbsp;Full Time · Post-Match Report
                </div>
            </div>
            <div class="ai-output">
                <div class="ai-output-header">Match Report</div>
                {format_ai_text(r['report'])}
            </div>
            """, unsafe_allow_html=True)


def render_standings_table(standings):
    if not standings:
        return
    rows_html = ""
    for i, row in enumerate(standings):
        qual_color = "#FFD700" if i < 2 else "#c8cad4"
        rows_html += f"""
        <tr>
            <td style="color:{qual_color};font-weight:600;">{row['team']}</td>
            <td>{row['played']}</td>
            <td>{row['won']}</td>
            <td>{row['drawn']}</td>
            <td>{row['lost']}</td>
            <td>{row['gf']}</td>
            <td>{row['ga']}</td>
            <td>{row['gd']}</td>
            <td class="standings-pts">{row['points']}</td>
        </tr>
        """
    st.markdown(f"""
    <table class="standings-table">
        <thead>
            <tr>
                <th>Team</th>
                <th>P</th><th>W</th><th>D</th><th>L</th>
                <th>GF</th><th>GA</th><th>GD</th><th>Pts</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────

st.markdown("""
<div class="mm-header">
    <div class="mm-logo">Match<span>Mind</span></div>
    <div class="mm-tagline">AI-Powered FIFA World Cup 2026 Companion</div>
</div>
<div class="mm-divider"></div>
""", unsafe_allow_html=True)


# ── Navigation ─────────────────────────────────────────────────────

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
        st.markdown("""
        <div class="match-card">
            <div style="text-align:center;font-family:'Inter',sans-serif;font-size:0.85rem;color:#5a6070;padding:0.5rem;">
                No matches scheduled today.
            </div>
        </div>
        """, unsafe_allow_html=True)
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

        col1, col2 = st.columns([2, 1])
        with col1:
            group_options = ["All Groups"] + sorted(groups.keys())
            selected_group = st.selectbox("Filter by group", group_options, label_visibility="collapsed")
        with col2:
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

            left_col, right_col = st.columns([3, 2])

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
                if standings:
                    render_standings_table(standings)
                else:
                    st.markdown('<div style="color:#5a6070;font-size:0.8rem;padding:0.5rem 0;">No matches played yet.</div>', unsafe_allow_html=True)

            st.markdown("<hr style='border:none;border-top:1px solid #1a2035;margin:1.5rem 0;'>", unsafe_allow_html=True)

        if selected_group == "All Groups":
            for g in sorted(groups.keys()):
                render_group_section(g, groups[g])
            if knockout:
                render_group_section("Knockout Stage", knockout)
        else:
            render_group_section(selected_group, groups.get(selected_group, []))


# ══════════════════════════════════════════════════════════════════
# TAB 3 — REPORTS
# ══════════════════════════════════════════════════════════════════

with tab3:
    st.markdown('<div class="section-label">Finished Matches — Click to Generate Report</div>', unsafe_allow_html=True)

    all_matches = api_get("/matches")

    if all_matches and "error" not in all_matches:
        finished_matches = [
            m for m in all_matches
            if m["status"].upper() in ("FINISHED",)
        ]

        if not finished_matches:
            st.markdown('<div style="color:#5a6070;font-size:0.85rem;padding:1rem 0;">No finished matches yet.</div>', unsafe_allow_html=True)
        else:
            finished_matches.sort(key=lambda x: x.get("date", ""), reverse=True)

            # Group by date
            by_date = {}
            for m in finished_matches:
                d = m.get("date", "Unknown")
                by_date.setdefault(d, []).append(m)

            for date_key in sorted(by_date.keys(), reverse=True):
                st.markdown(f'<div class="section-label">{date_key}</div>', unsafe_allow_html=True)
                for m in by_date[date_key]:
                    render_match_card(m, key_prefix="reports")