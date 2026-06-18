from groq import Groq
from dotenv import load_dotenv
import os
from utils import (
    format_standings_for_prompt,
    get_match_context,
    get_head_to_head,
    get_team_tournament_form
)

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_match_briefing(home_team, away_team, match_date, stage, group=None, match_id=None):
    group_info = f"Group {group}" if group else stage

    standings_context = ""
    wiki_context = ""
    scorers_context = ""

    if group:
        standings_context = format_standings_for_prompt(group, exclude_match_id=match_id)

    home_form = get_team_tournament_form(home_team, exclude_match_id=match_id)
    away_form = get_team_tournament_form(away_team, exclude_match_id=match_id)
    scorer_blocks = [s for s in [home_form, away_form] if s]
    if scorer_blocks:
        scorers_context = "\n\n".join(scorer_blocks)

    h2h = get_head_to_head(home_team, away_team)
    if h2h:
        wiki_context = h2h

    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    Write a pre-match briefing for the following fixture:

    {home_team} vs {away_team}
    Date: {match_date}
    Stage: {group_info}

    {standings_context}

    {scorers_context}

    {wiki_context}

    This is the World Cup — write with a sense of occasion and genuine weight.
    Be engaging and vivid where the moment calls for it, but always grounded and
    intelligent. Every sentence should earn its place. No hollow hype or clichés.

    Structure your briefing as follows:
    - An opening line that captures the mood and stakes of this fixture
    - What the current standings mean for both teams — the pressure, the opportunity,
      what a win, draw or loss does to their tournament hopes. Be specific to their
      actual situation in the table, not generic.
    - If players are listed above with goal involvements this tournament, weave
      them in naturally — e.g. a player who has already scored may be looking to
      add to his tally, or a team's goal threat may be concentrated in one player.
      Only reference players listed above.
    - Any relevant historical context between these teams from the head-to-head
      data, if present.
    - A brief tactical outlook — how each side might approach this game given
      what's at stake
    - A considered prediction with a clear reason behind it

    ABSOLUTE RULES — these cannot be broken under any circumstances:
    - Only mention player names that explicitly appear in the data provided above
      (goal involvements section or head-to-head context). Do not recall, assume,
      or invent any player names from your training data.
    - Do not mention, imply, or reference any disciplinary incidents — cards, red
      cards, suspensions, or bans — for either team under any circumstances, unless
      such information explicitly and literally appears in the data provided above.
    - Measure each team's situation purely from the standings and data provided.
      Do not assume form, tactics, or results beyond what the data shows.
    - If the standings show no matches played yet, do not invent any prior context.
    - No exclamation marks. Confident, assured tone throughout.
    - Keep it under 220 words.
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def generate_post_match_report(home_team, away_team, home_score, away_score, stage, group=None, match_id=None, match_date=None):
    group_info = f"Group {group}" if group else stage
    result = f"{home_team} {home_score}-{away_score} {away_team}"

    if home_score > away_score:
        outcome = f"{home_team} won"
    elif away_score > home_score:
        outcome = f"{away_team} won"
    else:
        outcome = "the match ended in a draw"

    standings_context = ""
    match_context = ""
    motm_context = ""

    if group:
        standings_context = format_standings_for_prompt(group, exclude_match_id=match_id)

    if match_id:
        raw_context = get_match_context(home_team, away_team, match_date=match_date, highlightly_match_id=match_id)
        if raw_context:
            match_context = f"Match data:\n{raw_context}"

    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    Write a post-match report for the following result:

    {result}
    Stage: {group_info}
    Outcome: {outcome}

    {standings_context}

    {match_context}

    {motm_context}

    Write this like a match report from a quality sports publication — analytical,
    alive, with a sense of occasion. Be vivid where the moment earns it, precise
    where the data demands it. Never hollow, never over the top.

    Structure your report as follows:
    - A headline and opening paragraph that captures the result and its significance
    - A match narrative built from the goals, their minutes, and any other events
      (cards, substitutions) listed in the match data above. Use the timeline to
      show the shape of the game — when it turned, when it was sealed.
    - If match statistics (possession, shots, big chances, etc.) are present in the
      match data above, use them to support your description of how the game was
      controlled — but only state numbers that appear explicitly in that data.
    - If goal involvements are listed for either team above, you may reference
      players responsible for that team's attacking threat this tournament.
    - The referee's name, if provided, can be mentioned briefly for color — purely
      as a factual note, without any characterization of how the match was
      conducted.
    - What this result means for both teams in the group standings going forward,
      based strictly on the standings table above.

    ABSOLUTE RULES — these cannot be broken under any circumstances:
    - Only mention player names, referees, or venues that explicitly appear in the
      data above. Do not recall, invent, or assume any names from your training data.
    - Do not invent minute-by-minute events, cards, substitutions, or stats that
      are not present in the data above.
    - Do not characterize the disciplinary tone of the match in any way beyond
      what the data explicitly shows.
    - No exclamation marks. Confident, measured tone throughout.
    - Keep it under 280 words.
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    briefing = generate_match_briefing("Mexico", "South Africa", "2026-06-11", "GROUP_STAGE", "GROUP_A", match_id=537327)
    print("BRIEFING:\n", briefing)

    report = generate_post_match_report("Mexico", "South Africa", 2, 0, "GROUP_STAGE", "GROUP_A", match_id=537327, match_date="2026-06-11")
    print("\nREPORT:\n", report)