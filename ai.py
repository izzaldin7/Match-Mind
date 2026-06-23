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
    format_recent_match_context_for_prompt,
    format_recent_standout_performers_for_prompt,
    format_player_debate_context,
    format_team_debate_context
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
        "recent_match_context": None,
        "recent_standout_performers": None
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

    context["recent_standout_performers"] = format_recent_standout_performers_for_prompt(
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

    context["box_score"] = None
    if match_date:
        from utils import find_highlightly_match_id, fetch_box_score, format_box_score_for_prompt
        highlightly_id = find_highlightly_match_id(home_team, away_team, match_date)
        if highlightly_id:
            box_score_data = fetch_box_score(highlightly_id)
            context["box_score"] = format_box_score_for_prompt(box_score_data, home_team, away_team)

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

    {_context_block("Recent standout performers", context["recent_standout_performers"])}

    {_context_block("Tournament goal involvements", context["goal_involvements"])}

    {_context_block("Discipline watch", context["discipline_watch"])}

    {_context_block("Head-to-head history", context["head_to_head"])}

    Your job is not just to inform the reader — it's to make someone who hasn't
    decided whether to watch this match decide that they should. You do this
    through specificity, not hype: a concrete stake, a live question the match
    will answer, a named player worth watching and the stated reason why. A
    reader should finish this briefing knowing exactly what to watch for and
    why it would matter if it happens. Never reach for inflated words like
    "massive", "huge", "blockbuster", or "epic" to manufacture excitement —
    if the stakes are real, stating them plainly is more compelling than
    decorating them.

    Write like a print broadsheet previewing a World Cup match — The Guardian,
    The Athletic, L'Équipe — not a stats summary with adjectives sprinkled in.
    Stay grounded in the data provided. Every sentence should earn its place.

    Structure your briefing to cover the following, but DO NOT announce your
    own structure. Never open a paragraph by naming the category you're about
    to cover ("Looking at the standings...", "In terms of recent form...",
    "From a disciplinary standpoint..."). A reader should never sense a
    checklist underneath. Move between ideas with natural transitions instead.

    - An opening line that gives the reader a concrete reason to care about
      kickoff — a specific stake, not a mood-setting platitude.
    - A standings and qualification section. Use the qualification scenarios
      directly: if a team is already qualified, say so and frame what they're
      now playing for instead — group position, momentum, a particular
      opponent they'd rather avoid in the next round. If a team is eliminated,
      say so plainly. If still alive, state exactly what result they need and
      let the reader feel the pressure of that requirement rather than being
      told it's pressurized. Do not state what a win, draw, or loss is worth
      in points — any football fan already knows this.
    - A recent form section based only on the recent match context provided.
      Reference the most recent result for each team. If tournament goal
      involvements are listed above, name the players and their tallies — this
      is mandatory. Make clear these are tournament totals, not match-specific.
      Never imply a player scored in a specific match unless explicitly stated.
      If standout performer data from each team's most recent match is listed,
      weave that player and performance in too, making clear it refers to that
      one previous match, not the tournament as a whole. Frame this section
      around a live question: is this team trending toward something, or due
      a correction — and what would the reader actually see on the pitch that
      confirms it either way.
    - A discipline section — MANDATORY if discipline watch data is available.
      Name every suspended player and every player one yellow card from
      suspension, for both teams, specifically. If a suspension or
      one-yellow-from-trouble situation directly affects how a team can play
      (e.g. a key creator unavailable, a defender walking a tightrope), say so
      — this is a real subplot of the match, not a footnote. If discipline data
      is not available, skip this section entirely without mentioning its absence.
    - Historical context between these teams from the head-to-head data, if
      present — use it to add a genuine thread of intrigue (a recurring
      pattern, an unusual history) rather than reciting results. If
      head-to-head data is not available, write a single natural sentence
      acknowledging this is a rare or first meeting and frame that itself as
      a reason for curiosity — uncharted territory is its own hook. Vary the
      phrasing, keep it brief, and move on.
    - A tactical outlook tied to the standings, recent form, and player
      availability — give the reader something specific to watch for once
      the match starts, tied to what's actually in the data.
    - A considered prediction with explicit reasoning specific to these two
      teams. Do not predict a draw simply because both teams drew their
      previous match or because standings are level — that is lazy reasoning.
      A draw is valid only if the data genuinely supports equal strength with
      neither side holding a clear edge. State the reasoning explicitly.

    ABSOLUTE RULES - these cannot be broken under any circumstances:
    - Your briefing must be driven by the AVAILABLE DATA above. Use all available
      sections directly and specifically.
    - If a category says "Not available", do not invent it. Skip that section
      entirely — do not write a sentence acknowledging its absence either.
    - If goal involvements, discipline watch, and recent match context are all
      "Not available", this is a matchday 1 fixture where neither team has played
      yet. In this case, skip the recent form and discipline sections entirely.
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
    - Never describe something as "significant", "dramatic", "pivotal", or
      "a turning point" — describe the situation with enough precision that
      its weight is self-evident.
    - Write between 400-500 words. Use clear paragraph breaks between
      each section — each section must be its own paragraph.
    - Avoid generic filler phrases such as "both teams will look to build
      on their momentum", "this will be a crucial encounter", "every point
      counts", "regroup and reassess", or any variation of these. Every
      sentence must say something specific and grounded in the data provided.
      If you cannot say something specific, say nothing.
    """

    try:
        response = get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Failed to generate content via Groq: {e}")


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

    {_context_block("Player box scores", context.get("box_score"))}

    Write this like a match report from a quality print broadsheet — The Guardian,
    The Athletic, L'Équipe — not a recap bot summarizing a data feed. The best
    sportswriters make a reader who didn't watch the match feel something about
    it. Specific, vivid detail does that. Stating that something was "significant"
    or "dramatic" does not — show the moment precisely enough that the drama is
    self-evident, and let the reader arrive at the feeling themselves.

    Structure your report to cover the following, but DO NOT announce your own
    structure. Never open a paragraph by naming the category you're about to
    discuss ("From a statistical standpoint...", "Personnel-wise...", "In terms
    of group standings..."). A reader should never be able to tell you're working
    from a checklist. Move between sections with narrative transitions instead —
    let one paragraph's ending naturally raise the question the next paragraph answers.

    - A headline and strong opening paragraph that captures the result, the stakes,
      and why it mattered in the group.
    - A chronological match narrative built from the goals, half-time score, cards,
      substitutions, VAR decisions, and other listed events. If red cards, missed penalties,
      or VAR decisions are listed, explain how they changed the match without inventing details
      beyond the event timeline. A missed penalty followed by a goal from the same player later
      is a real narrative thread — let the gap between the two moments do the work, rather than
      labelling the miss as significant. Describe what happened; trust the reader to feel its weight.
    - A statistics paragraph using expected goals, shots, shots on target,
      possession, corners, big chances, or saves when those numbers are present.
      Weave these into the story of how the match was actually controlled or
      lost, rather than listing them as a separate ledger.
    - A personnel paragraph using the listed lineups, formations, starters,
      and substitutes where present.
    - Standout performers paragraph for both teams using the box score data — name the top-rated
      player(s) and explain specifically what they did to earn that rating. Use the supporting
      stats (goals, assists, xG, xA, dribbles completed, duels won, key passes, passing accuracy,
      saves, tackles/interceptions, fouls won) to justify the number, but only cite the stats that
      meaningfully explain it — a 9.0 rating built on a hat-trick does not need its tackle count
      mentioned, while a 9.0 rating with zero goals should be explained through dribbles, defensive
      actions, duels, or passing instead. Do not dump every stat listed for a player. Only reference
      players and stats explicitly present in the box score data above.
    - A group-standings paragraph explaining what the result means for both teams,
      based strictly on the standings table above. If qualification updates are
      listed above, include them naturally here — e.g. "With this win, Mexico
      have secured their place in the Round of 32."
    - A concise closing paragraph about what each side takes into the next match.
      This paragraph must say something specific to THESE two teams and THIS
      result — not a generic sentiment that could be pasted onto any match report.
      Banned closing constructions, in any phrasing or variation: "build on this
      momentum", "regroup and reassess", "bounce back from this defeat", "look
      to maintain", "must improve their performance", "stage is set for". If your
      closing sentence could be copy-pasted into a report about a different match
      and still make sense, rewrite it until it couldn't be.

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
    - Do not describe player movements, build-up play, pressing patterns, or
      passage of play that are not explicitly listed in the match data. Only
      the events listed (goals, cards, substitutions, VAR decisions) happened
      as far as this report is concerned.
    - Do not describe HOW a goal was scored (header, volley, tap-in, driven
      shot, curled finish, slotted past the keeper) unless explicitly stated
      in the match data. Say the player scored, reference the assist if listed,
      and move on. In case of a penalty miss, do not describe how it was missed
      (goalkeeper save, hit the post, out of target).
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
    - Never describe a moment as "significant", "dramatic", "pivotal", or
      "a turning point" — describe what happened with enough precision that
      the reader recognizes its weight without being told.
    - In the substitutions data, "SUB ON" means the player entered the pitch,
      "SUB OFF" means the player left the pitch. Never reverse this.
    """

    try:
        response = get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Failed to generate content via Groq: {e}")
    
def generate_player_debate(player_names, context_str):
    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    A fan wants to compare the following players based purely on their performances
    at this tournament. No club form, no career history, no reputation — only what
    has happened at this World Cup.

    Players: {', '.join(player_names)}

    TOURNAMENT DATA (2026 FIFA World Cup only)

    {context_str}

    Write a sharp, analytical fan debate breakdown. Structure it as follows:

    - An opening line that frames what makes this comparison genuinely interesting or contested.
    - A dedicated paragraph for each player, using their name as the section heading.
      Cover what the numbers say about their tournament impact, their role, their efficiency,
      and what separates them from the others in this comparison.
    - A verdict paragraph that directly answers: who has been the standout player at this
      tournament among those compared, and why. Be specific. Reference the data explicitly.
      Do not hedge unless the numbers are genuinely inseparable — in that case, say so and
      explain exactly why.

    ABSOLUTE RULES:
    - Only use the data provided above. Do not invent stats, reference club form, or
      draw on anything outside this tournament.
    - If a player has limited appearances or missing stats, factor that into the verdict
      rather than ignoring it.
    - No exclamation marks. Analytical, assured tone throughout.
    - Write between 300-450 words. Each player section is its own paragraph.
    - No clichés. Every sentence must say something specific and grounded in the data.
    """
    try:
        response = get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Failed to generate player debate via Groq: {e}")


def generate_team_debate(team_names, context_str):
    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    A fan wants to compare the following teams based purely on their performances
    at this tournament. No squad reputation, no manager history — only what the
    data from this World Cup shows.

    Teams: {', '.join(team_names)}

    TOURNAMENT DATA (2026 FIFA World Cup only)

    {context_str}

    Write a sharp, analytical fan debate breakdown. Structure it as follows:

    - An opening line that frames what makes this comparison interesting.
    - A dedicated paragraph for each team using the team name as the section heading.
      Cover their record, goal threat, defensive solidity, xG, possession, and what
      the numbers say about their style and quality at this tournament.
    - A verdict paragraph that directly answers: which team has looked more convincing
      so far and why. Be specific. Reference the data directly.

    ABSOLUTE RULES:
    - Only use the data provided above. Do not reference past tournaments, squad names
      not present in the data, or anything outside this tournament.
    - No exclamation marks. Analytical, confident tone throughout.
    - Write between 300-450 words. Each team section is its own paragraph.
    - No clichés. Every sentence must say something specific and grounded in the data.
    """
    try:
        response = get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Failed to generate team debate via Groq: {e}")

if __name__ == "__main__":
    briefing = generate_match_briefing("Mexico", "South Africa", "2026-06-11", "GROUP_STAGE", "GROUP_A", match_id=537327)
    print("\nBRIEFING:\n", briefing)

    report = generate_post_match_report("Mexico", "South Africa", 2, 0, "GROUP_STAGE", "GROUP_A", match_id=537327, match_date="2026-06-11")
    print("\nREPORT:\n", report)