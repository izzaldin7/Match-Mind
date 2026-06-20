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

    /* Base */
    .stApp {
        background-color: #0a0e1a;
        color: #e8eaf0;
    }

    /* Hide default streamlit chrome */
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding: 2rem 3rem;}

    /* Header */
    .mm-header {
        display: flex;
        align-items: baseline;
        gap: 12px;
        margin-bottom: 0.25rem;
    }
    .mm-logo {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 3rem;
        color: #ffffff;
        letter-spacing: 2px;
        line-height: 1;
    }
    .mm-logo span {
        color: #00d4ff;
    }
    .mm-tagline {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        color: #5a6070;
        letter-spacing: 3px;
        text-transform: uppercase;
        font-weight: 500;
    }
    .mm-divider {
        height: 1px;
        background: linear-gradient(90deg, #00d4ff 0%, #0040ff 50%, transparent 100%);
        margin: 1rem 0 2rem 0;
        opacity: 0.4;
    }

    /* Nav tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent;
        gap: 0;
        border-bottom: 1px solid #1a2035;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        font-weight: 500;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #5a6070;
        padding: 0.75rem 1.5rem;
        border-bottom: 2px solid transparent;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #00d4ff !important;
        border-bottom: 2px solid #00d4ff !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 2rem;
    }

    /* Match cards */
    .match-card {
        background: #0f1525;
        border: 1px solid #1a2035;
        border-radius: 4px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        position: relative;
        transition: border-color 0.2s;
    }
    .match-card:hover {
        border-color: #00d4ff30;
    }
    .match-card-live {
        border-left: 3px solid #ff3b5c;
    }
    .match-card-finished {
        border-left: 3px solid #2a3045;
    }
    .match-card-upcoming {
        border-left: 3px solid #00d4ff;
    }
    .match-teams {
        font-family: 'Inter', sans-serif;
        font-size: 1rem;
        font-weight: 600;
        color: #e8eaf0;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .match-score {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.1rem;
        font-weight: 500;
        color: #ffffff;
        background: #1a2035;
        padding: 0.2rem 0.6rem;
        border-radius: 3px;
        min-width: 60px;
        text-align: center;
    }
    .match-meta {
        font-family: 'Inter', sans-serif;
        font-size: 0.7rem;
        color: #5a6070;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 0.4rem;
    }
    .status-live {
        color: #ff3b5c;
        font-weight: 600;
        animation: pulse 2s infinite;
    }
    .status-finished {color: #5a6070;}
    .status-upcoming {color: #00d4ff;}

    @keyframes pulse {
        0%, 100% {opacity: 1;}
        50% {opacity: 0.5;}
    }

    /* Group badge */
    .group-badge {
        display: inline-block;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        color: #00d4ff;
        background: #00d4ff15;
        border: 1px solid #00d4ff30;
        padding: 0.15rem 0.5rem;
        border-radius: 2px;
        letter-spacing: 1px;
        margin-right: 0.5rem;
    }

    /* AI output */
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
        color: #00d4ff;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #1a2035;
    }

    /* Fixture header */
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
        color: #00d4ff;
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

    /* Buttons */
    .stButton button {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        background: transparent;
        color: #00d4ff;
        border: 1px solid #00d4ff40;
        border-radius: 3px;
        padding: 0.5rem 1.25rem;
        transition: all 0.2s;
        width: 100%;
    }
    .stButton button:hover {
        background: #00d4ff10;
        border-color: #00d4ff;
    }

    /* Selectbox */
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

    /* Error/info */
    .stAlert {
        background: #0f1525;
        border-color: #1a2035;
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
    }

    /* Spinner */
    .stSpinner {color: #00d4ff;}

    /* Section label */
    .section-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.65rem;
        letter-spacing: 3px;
        text-transform: uppercase;
        color: #5a6070;
        margin-bottom: 1rem;
    }

    /* Stats grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
        margin-top: 1rem;
    }
    .stat-box {
        background: #0f1525;
        border: 1px solid #1a2035;
        border-radius: 3px;
        padding: 0.75rem 1rem;
        text-align: center;
    }
    .stat-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.3rem;
        color: #ffffff;
        font-weight: 500;
    }
    .stat-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.65rem;
        color: #5a6070;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 0.25rem;
    }
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
    elif s in ("FINISHED", "FINISHED"):
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


# ── Header ─────────────────────────────────────────────────────────

st.markdown("""
<div class="mm-header">
    <div class="mm-logo">Match<span>Mind</span></div>
</div>
<div class="mm-tagline">AI-Powered FIFA World Cup 2026 Companion</div>
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
            <div class="match-meta">No matches scheduled today.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for m in data:
            card_class, status_cls, status_label = status_class(m["status"])
            score = format_score(m["home_score"], m["away_score"], m["status"])

            st.markdown(f"""
            <div class="match-card {card_class}">
                <div class="match-teams">
                    {m['home_team']}
                    <span class="match-score">{score}</span>
                    {m['away_team']}
                </div>
                <div class="match-meta">
                    <span class="{status_cls}">{status_label}</span>
                    &nbsp;·&nbsp; ID {m['match_id']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Briefing / Report selector ──────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)

        upcoming = [m for m in data if m["status"].upper() not in ("FINISHED",)]
        finished = [m for m in data if m["status"].upper() in ("FINISHED",)]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="section-label">Pre-Match Briefing</div>', unsafe_allow_html=True)
            if upcoming:
                briefing_options = {
                    f"{m['home_team']} vs {m['away_team']}": m['match_id']
                    for m in upcoming
                }
                selected_briefing = st.selectbox(
                    "Select match",
                    options=list(briefing_options.keys()),
                    key="briefing_select",
                    label_visibility="collapsed"
                )
                if st.button("Generate Briefing", key="gen_briefing"):
                    match_id = briefing_options[selected_briefing]
                    with st.spinner("Analysing fixture..."):
                        result = api_get(f"/matches/{match_id}/briefing")
                    if result and "error" not in result:
                        st.session_state["briefing_result"] = result
                    elif result:
                        st.error(result["error"])
            else:
                st.markdown('<div class="match-card"><div class="match-meta">No upcoming matches today.</div></div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="section-label">Post-Match Report</div>', unsafe_allow_html=True)
            if finished:
                report_options = {
                    f"{m['home_team']} vs {m['away_team']}": m['match_id']
                    for m in finished
                }
                selected_report = st.selectbox(
                    "Select match",
                    options=list(report_options.keys()),
                    key="report_select",
                    label_visibility="collapsed"
                )
                if st.button("Generate Report", key="gen_report"):
                    match_id = report_options[selected_report]
                    with st.spinner("Compiling match report..."):
                        result = api_get(f"/matches/{match_id}/report")
                    if result and "error" not in result:
                        st.session_state["report_result"] = result
                    elif result:
                        st.error(result["error"])
            else:
                st.markdown('<div class="match-card"><div class="match-meta">No finished matches today yet.</div></div>', unsafe_allow_html=True)

        # ── Display briefing result ─────────────────────────────
        if "briefing_result" in st.session_state:
            r = st.session_state["briefing_result"]
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="fixture-header">
                <div>
                    <span class="fixture-teams-big">{r['home_team']}</span>
                    <span class="fixture-vs">vs</span>
                    <span class="fixture-teams-big">{r['away_team']}</span>
                </div>
                <div class="fixture-sub">
                    <span class="group-badge">{group_display(r.get('group', ''))}</span>
                    {r.get('date', '')} · Pre-Match Briefing
                </div>
            </div>
            <div class="ai-output">
                <div class="ai-output-header">Match Intelligence</div>
                {format_ai_text(r['briefing'])}
            </div>
            """, unsafe_allow_html=True)

        # ── Display report result ───────────────────────────────
        if "report_result" in st.session_state:
            r = st.session_state["report_result"]
            home_s = r.get("home_score", "?")
            away_s = r.get("away_score", "?")
            st.markdown("<br>", unsafe_allow_html=True)
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
                    Full Time · Post-Match Report
                </div>
            </div>
            <div class="ai-output">
                <div class="ai-output-header">Match Report</div>
                {format_ai_text(r['report'])}
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# TAB 2 — ALL FIXTURES
# ══════════════════════════════════════════════════════════════════

with tab2:
    all_data = api_get("/matches")

    if all_data and "error" not in all_data:
        # Group by group_name
        groups = {}
        knockout = []
        for m in all_data:
            g = m.get("group")
            if g:
                groups.setdefault(g, []).append(m)
            else:
                knockout.append(m)

        # Filter controls
        col1, col2 = st.columns([2, 1])
        with col1:
            group_options = ["All Groups"] + sorted(groups.keys())
            selected_group = st.selectbox(
                "Filter by group",
                group_options,
                label_visibility="collapsed"
            )
        with col2:
            status_filter = st.selectbox(
                "Filter by status",
                ["All", "Upcoming", "Finished"],
                label_visibility="collapsed"
            )

        st.markdown("<br>", unsafe_allow_html=True)

        def filter_matches(matches):
            if status_filter == "Upcoming":
                return [m for m in matches if m["status"].upper() not in ("FINISHED",)]
            elif status_filter == "Finished":
                return [m for m in matches if m["status"].upper() in ("FINISHED",)]
            return matches

        def render_group(group_name, matches):
            filtered = filter_matches(matches)
            if not filtered:
                return
            st.markdown(f'<div class="section-label">{group_display(group_name)}</div>', unsafe_allow_html=True)
            for m in filtered:
                card_class, status_cls, status_label = status_class(m["status"])
                score = format_score(m["home_score"], m["away_score"], m["status"])
                st.markdown(f"""
                <div class="match-card {card_class}">
                    <div class="match-teams">
                        {m['home_team']}
                        <span class="match-score">{score}</span>
                        {m['away_team']}
                    </div>
                    <div class="match-meta">
                        <span class="{status_cls}">{status_label}</span>
                        &nbsp;·&nbsp; {m.get('date', '')}
                        &nbsp;·&nbsp; {m.get('stage', '').replace('_', ' ')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

        if selected_group == "All Groups":
            for g in sorted(groups.keys()):
                render_group(g, groups[g])
            if knockout:
                render_group("Knockout Stage", knockout)
        else:
            render_group(selected_group, groups.get(selected_group, []))


# ══════════════════════════════════════════════════════════════════
# TAB 3 — REPORTS (browse finished matches)
# ══════════════════════════════════════════════════════════════════

with tab3:
    st.markdown('<div class="section-label">Generate a report for any finished match</div>', unsafe_allow_html=True)

    all_matches = api_get("/matches")

    if all_matches and "error" not in all_matches:
        finished_matches = [
            m for m in all_matches
            if m["status"].upper() in ("FINISHED",)
        ]

        if not finished_matches:
            st.markdown('<div class="match-card"><div class="match-meta">No finished matches yet.</div></div>', unsafe_allow_html=True)
        else:
            # Sort by date descending
            finished_matches.sort(key=lambda x: x.get("date", ""), reverse=True)

            report_options = {
                f"{m['home_team']} vs {m['away_team']} ({m.get('date', '')}) — {group_display(m.get('group', 'Knockout'))}": m['match_id']
                for m in finished_matches
            }

            selected = st.selectbox(
                "Select a finished match",
                options=list(report_options.keys()),
                label_visibility="collapsed"
            )

            if st.button("Generate Report", key="gen_report_tab3"):
                match_id = report_options[selected]
                with st.spinner("Compiling match report..."):
                    result = api_get(f"/matches/{match_id}/report")
                if result and "error" not in result:
                    st.session_state["tab3_report"] = result
                elif result:
                    st.error(result["error"])

        if "tab3_report" in st.session_state:
            r = st.session_state["tab3_report"]
            home_s = r.get("home_score", "?")
            away_s = r.get("away_score", "?")
            st.markdown("<br>", unsafe_allow_html=True)
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
                    Full Time · Post-Match Report
                </div>
            </div>
            <div class="ai-output">
                <div class="ai-output-header">Match Report</div>
                {format_ai_text(r['report'])}
            </div>
            """, unsafe_allow_html=True)