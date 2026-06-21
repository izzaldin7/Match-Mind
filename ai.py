from groq import Groq
from dotenv import load_dotenv
import os
from utils import (
    format_standings_for_prompt,
    format_qualification_scenarios_for_prompt,
    get_match_context,
    get_head_to_head,
    get_team_tournament_form,
    get_group_standings,
    format_discipline_watch_for_prompt,
    format_recent_match_context_for_prompt
)

load_dotenv()

client = None


def get_groq_client():
    global client
    if client:
        return client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY in environment.")
    client = Groq(api_key=api_key)
    return client


def build_match_briefing_context(home_team, away_team, match_date, stage, group=None, match_id=None):
    group_info = group.replace("GROUP_", "Group ") if group else stage
    context = {
        "fixture": f"{home_team} vs {away_team}",
        "date": match_date,
        "stage": group_info,
        "standings": None,
        "qualification_scenarios": None,
        "goal_involvements": None,
        "head_to_head": None,
        "discipline_watch": None,
        "recent_match_context": None
    }

    if group:
        context["standings"] = format_standings_for_prompt(group, exclude_match_id=match_id)
        context["qualification_scenarios"] = format_qualification_scenarios_for_prompt(
            group, home_team, away_team, exclude_match_id=match_id
        )

    home_form = get_team_tournament_form(home_team, exclude_match_id=match_id)
    away_form = get_team_tournament_form(away_team, exclude_match_id=match_id)
    scorer_blocks = [block for block in (home_form, away_form) if block]
    if scorer_blocks:
        context["goal_involvements"] = "\n\n".join(scorer_blocks)

    context["head_to_head"] = get_head_to_head(home_team, away_team)

    context["discipline_watch"] = format_discipline_watch_for_prompt(
        home_team, away_team, match_date,
        group_name=group,
        exclude_match_id=match_id
    )

    context["recent_match_context"] = format_recent_match_context_for_prompt(
        home_team, away_team, match_date,
        group_name=group,
        exclude_match_id=match_id
    )

    return context


def build_post_match_context(home_team, away_team, home_score, away_score, stage, group=None, match_id=None, match_date=None):
    group_info = group.replace("GROUP_", "Group ") if group else stage

    if home_score is None or away_score is None:
        outcome = "the final score is unavailable"
    elif home_score > away_score:
        outcome = f"{home_team} won"
    elif away_score > home_score:
        outcome = f"{away_team} won"
    else:
        outcome = "the match ended in a draw"

    result = f"{home_team} {home_score}-{away_score} {away_team}"

    context = {
        "result": result,
        "stage": group_info,
        "outcome": outcome,
        "standings": None,
        "qualification_notes": None,
        "match_data": None
    }

    if group and match_date:
        # Use up_to_date to show standings as they were on the day of this match
        context["standings"] = format_standings_for_prompt(group, up_to_date=match_date)

        qualification_notes = []
        standings_data = get_group_standings(group, up_to_date=match_date)
        if standings_data:
            for team_row in standings_data:
                team = team_row["team"]
                if team not in (home_team, away_team):
                    continue
                pts = team_row["points"]
                played = team_row["played"]
                remaining = 3 - played
                if pts >= 6:
                    qualification_notes.append(
                        f"{team} have qualified for the Round of 32 with this result."
                    )
                elif pts + (remaining * 3) < 4:
                    qualification_notes.append(
                        f"{team} have been eliminated from the tournament with this result."
                    )
        context["qualification_notes"] = "\n".join(qualification_notes) if qualification_notes else None

    elif group:
        context["standings"] = format_standings_for_prompt(group)

    if match_date:
        context["match_data"] = get_match_context(
            home_team,
            away_team,
            match_date=match_date,
            highlightly_match_id=None
        )

    return context


def _context_block(title, value):
    if value:
        return f"{title}:\n{value}"
    return f"{title}: Not available."


def generate_match_briefing(home_team, away_team, match_date, stage, group=None, match_id=None, context=None):
    if context is None:
        context = build_match_briefing_context(
            home_team, away_team, match_date, stage,
            group=group, match_id=match_id
        )

    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    Write a pre-match briefing for the following fixture:

    Fixture: {context["fixture"]}
    Date: {context["date"]}
    Stage: {context["stage"]}

    AVAILABLE DATA

    {_context_block("Current standings", context["standings"])}

    {_context_block("Qualification scenarios", context["qualification_scenarios"])}

    {_context_block("Recent match context", context["recent_match_context"])}

    {_context_block("Tournament goal involvements", context["goal_involvements"])}

    {_context_block("Discipline watch", context["discipline_watch"])}

    {_context_block("Head-to-head history", context["head_to_head"])}

    This is the World Cup. Write with a sense of occasion and genuine weight,
    but stay grounded in the data. Every sentence should earn its place. No
    hollow hype or clichés.

    Structure your briefing as follows:
    - An opening line that captures the mood and stakes of this fixture.
    - A clear standings and qualification paragraph. Use the qualification
      scenarios directly: if a team is already qualified, say so and explain
      they are playing for group position. If a team is eliminated, say so.
      If still alive, explain exactly what they need from this match.
      Do not state what a win, draw, or loss is worth in points — this is
      obvious to any football fan and adds no value. Focus instead on what
      the result means narratively — pressure, opportunity, must-win situation,
      comfortable position, etc.
    - A recent form paragraph based only on the recent match context provided.
      Reference the most recent result for each team. If tournament goal
      involvements are listed above, YOU MUST name the players involved and
      their tallies — this is mandatory, not optional. Make clear these are
      tournament totals, not match-specific. Never imply a player scored in
      a specific match unless explicitly stated.
    - A discipline paragraph — this is MANDATORY if discipline watch data is
      available above. If it is available, you must name every suspended player
      and every player one yellow card from suspension, for both teams. Do not
      summarise vaguely — name them specifically. If discipline data is not
      available, skip this paragraph entirely without mentioning its absence.
    - Any relevant historical context between these teams from the head-to-head
      data, if present. If head-to-head data is not available, do not say
      "no data is available" or "we cannot assess this". Instead write a single
      natural sentence acknowledging this is a rare or first meeting — e.g.
      "These sides rarely cross paths on the international stage, making this
      a genuinely fresh encounter." Vary the phrasing, keep it brief, and move on.
    - A brief tactical outlook tied to the standings, recent match context, and
      player availability.
    - A considered prediction with a clear reason behind it. The prediction
      must be based on the quality and context of the data — form, discipline,
      goal threat, qualification pressure. Do not predict a draw simply because
      both teams drew their previous match, or because the standings are level.
      That is lazy reasoning. A draw is a valid prediction only if the data
      genuinely supports equal strength and neither team having a clear edge.
      State the reasoning explicitly and make it specific to these two teams.

    ABSOLUTE RULES - these cannot be broken under any circumstances:
    - Your briefing must be driven by the AVAILABLE DATA above. Use all available
      sections directly and specifically.
    - If a category says "Not available", do not invent it. Skip that section
      entirely — do not write a sentence acknowledging its absence either.
    - If goal involvements, discipline watch, and recent match context are all
      "Not available", this is a matchday 1 fixture where neither team has played
      yet. In this case, skip the recent form and discipline paragraphs entirely.
      Do not write phrases like "no prior data is available" or "both teams are
      yet to play" — simply omit those sections and focus on standings, h2h
      history, tactical outlook, and prediction.
    - Only mention player names that explicitly appear in the data provided above.
      Do not recall, assume, or invent any player names from your training data.
    - Do not invent injuries, suspensions, tactical systems, lineups, or
      off-field news not present in the data.
    - Discipline can only be discussed from the discipline watch block. If that
      block is not available, do not mention cards, suspensions, or suspension risk.
    - No exclamation marks. Confident, assured tone throughout.
    - Write between 400-500 words. Use clear paragraph breaks between
      each section — each section must be its own paragraph.
    - Avoid generic filler phrases such as "both teams will look to build
      on their momentum", "this will be a crucial encounter", "every point
      counts", "regroup and reassess", or any variation of these. Every
      sentence must say something specific and grounded in the data provided.
      If you cannot say something specific, say nothing.
    """

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def generate_post_match_report(home_team, away_team, home_score, away_score, stage, group=None, match_id=None, match_date=None, context=None):
    if context is None:
        context = build_post_match_context(
            home_team, away_team, home_score, away_score, stage,
            group=group, match_id=match_id, match_date=match_date
        )

    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    Write a post-match report for the following result:

    Result: {context["result"]}
    Stage: {context["stage"]}
    Outcome: {context["outcome"]}

    AVAILABLE DATA

    {_context_block("Current standings", context["standings"])}

    {_context_block("Qualification updates", context.get("qualification_notes"))}

    {_context_block("Match data", context["match_data"])}

    Write this like a match report from a quality sports publication — analytical,
    alive, with a sense of occasion. Be vivid where the moment earns it, precise
    where the data demands it. Never hollow, never over the top.

    Structure your report as follows:
    - A headline and strong opening paragraph that captures the result, the stakes,
      and why it mattered in the group.
    - A chronological match narrative built from the goals, half-time score, cards,
      substitutions, and other listed events. If red cards are listed, explain how
      they changed the match without inventing details beyond the event timeline.
    - A statistics paragraph using expected goals, shots, shots on target,
      possession, corners, big chances, or saves when those numbers are present.
    - A personnel paragraph using the listed lineups, formations, starters,
      and substitutes where present.
    - A group-standings paragraph explaining what the result means for both teams,
      based strictly on the standings table above. If qualification updates are
      listed above, include them naturally here — e.g. "With this win, Mexico
      have secured their place in the Round of 32."
    - A concise closing paragraph about what each side takes into the next match.

    ABSOLUTE RULES — these cannot be broken under any circumstances:
    - Your report must be driven by the AVAILABLE DATA above. Use all available
      sections directly and specifically.
    - If goals, red cards, half-time score, xG, shots on target, or lineups are
      present in match data, they must appear in the report.
    - If match data says "Not available", write a shorter result-focused report
      and state that detailed event/statistical data is not available. Do not
      create a match narrative from imagination.
    - Only mention player names, referees, or venues that explicitly appear in
      the data above. Do not recall, invent, or assume any names.
    - Do not invent events, cards, substitutions, or stats not present in the data.
    - Do not characterize the disciplinary tone of the match beyond what the
      data explicitly shows.
    - No exclamation marks. Confident, measured tone throughout.
    - If detailed match data is available, write 500-700 words.
      If match data is not available, keep it under 250 words.
    - Avoid generic filler phrases such as "regroup and reassess",
      "build on this momentum", "crucial encounter", "every point counts",
      or any variation of stock sports journalism clichés. Every sentence
      must say something specific and grounded in the data above.
    - In the substitutions data, "SUB ON" means the player entered the pitch,
      "SUB OFF" means the player left the pitch. Never reverse this.
    """

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    briefing = generate_match_briefing("Mexico", "South Africa", "2026-06-11", "GROUP_STAGE", "GROUP_A", match_id=537327)
    print("\nBRIEFING:\n", briefing)

    report = generate_post_match_report("Mexico", "South Africa", 2, 0, "GROUP_STAGE", "GROUP_A", match_id=537327, match_date="2026-06-11")
    print("\nREPORT:\n", report)