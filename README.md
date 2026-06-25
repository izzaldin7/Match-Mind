# MatchMind

A football analytics API built for the 2026 FIFA World Cup. MatchMind pulls live match data, enriches it with player and team statistics from Highlightly, and uses Groq (Llama 3.3 70B) to generate pre-match briefings, post-match reports, and data-driven player/team debate breakdowns.

---

## What it does

- **Pre-match briefings** — group standings, qualification scenarios, head-to-head history, team form, discipline watch, and standout performers, all synthesised into a written analyst briefing
- **Post-match reports** — result summary, player box scores, qualification impact, and a full match report generated from live data
- **Lineup data** — confirmed starting XI and substitutes for any match, available ~30 minutes before kickoff
- **Player debates** — statistical comparison of 2–4 players based solely on their 2026 World Cup performances, with position-aware analysis
- **Team debates** — head-to-head comparison of two teams across attacking, defensive, and possession metrics
- **Scheduled data refresh** — match statuses and scores sync from football-data.org every 30 minutes automatically

---

## Tech stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| AI / LLM | Groq API (Llama 3.3 70B) |
| Match data | football-data.org |
| Player & team stats | Highlightly (RapidAPI) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Scheduling | APScheduler |
| Server | Uvicorn |

---

## Project structure

```
matchmind/
├── api.py           # FastAPI routes and endpoint logic
├── ai.py            # Context builders and Groq prompt generation
├── utils.py         # Data fetching, caching, and formatting helpers
├── database.py      # SQLAlchemy models and DB setup
├── scheduler.py     # Match data refresh job (runs every 30 min)
├── main.py          # Manual trigger for a one-off data refresh
├── clear.py         # Dev utility to clear cached content from the DB
├── requirements.txt
└── Procfile         # For Railway / production deployment
```

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/matches` | All World Cup matches |
| GET | `/matches/today` | Today's matches |
| GET | `/matches/{id}/briefing` | Pre-match briefing (today's matches only) |
| GET | `/matches/{id}/report` | Post-match report (finished matches only) |
| GET | `/matches/{id}/lineup` | Starting XI and substitutes |
| POST | `/debate/players` | Compare 2–4 players |
| POST | `/debate/teams` | Compare 2 teams |

### Player debate request body
```json
{
  "players": ["Kylian Mbappe", "Erling Haaland"]
}
```

### Team debate request body
```json
{
  "teams": ["France", "Germany"]
}
```

---

## Local setup

### 1. Clone the repo and install dependencies

```bash
git clone https://github.com/your-username/matchmind.git
cd matchmind
pip install -r requirements.txt
```

### 2. Create a `.env` file

```
FOOTBALL_API_KEY=your_football_data_api_key
HIGHLIGHTLY_API_KEY=your_rapidapi_key
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=sqlite:///matchmind.db
```

### 3. Seed the database

```bash
python main.py
```

This fetches all current World Cup match data from football-data.org and builds the local tournament cache.

### 4. Start the API

```bash
uvicorn api:app --reload
```

The API will be available at `http://localhost:8000`.

---

## Deployment (Railway)

The `Procfile` is already configured:

```
web: uvicorn api:app --host 0.0.0.0 --port $PORT
```

Set the following environment variables in your Railway project dashboard:

```
FOOTBALL_API_KEY=
HIGHLIGHTLY_API_KEY=
GROQ_API_KEY=
DATABASE_URL=        # Railway PostgreSQL URL (auto-set if you add a Postgres plugin)
```

For production, add a PostgreSQL database via Railway's dashboard. The `DATABASE_URL` variable is picked up automatically — no code changes required.

---

## Caching

MatchMind caches generated content in the database to avoid redundant API and LLM calls:

- **Briefings** have a TTL and expire after a set period
- **Reports and lineups** are cached permanently once generated
- **Box scores** are cached per match

To clear cached content during development:

```bash
python clear.py reports       # clear post-match reports
python clear.py briefings     # clear pre-match briefings
python clear.py box-scores    # clear player box scores
python clear.py all           # clear everything
```

---

## Notes

- Briefings are only generated for matches scheduled on the current date. Requesting a briefing for a past or future match returns a 400 error.
- Reports are only available once a match status is `FINISHED`.
- Lineups are sourced from Highlightly and are typically available 30 minutes before kickoff.
- Player debate comparisons enforce position rules: goalkeepers can only be compared with goalkeepers, defenders with defenders, and midfielders/attackers can be mixed.
- All AI-generated content is grounded strictly in tournament data. The prompts explicitly prohibit the model from drawing on club form, career history, or anything outside the 2026 World Cup.
