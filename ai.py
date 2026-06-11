from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_match_briefing(home_team, away_team, match_date, stage, group=None):
    group_info = f"Group {group}"if group else stage

    prompt = f"""
    You are MatchMind, an AI football analyst for the 2026 FIFA World Cup.

    Generate an exciting pre-match intelligence briefing for:
    {home_team} vs {away_team}
    Date: {match_date}
    Stage: {group_info}

    Include:
    - A punchy opening line
    - Key storylines to watch
    - What's at stake for each team
    - One bold prediction

    Keep it under 200 words. Be engaging and use football terminology.
    """

    response = client.chat.completions.create(
        model = "llama-3.3-70b-versatile",
        messages = [{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def generate_post_match_report(home_team, away_team, home_score, away_score, stage, group=None):
    group_info = f"Group {group}"if group else stage
    result = f"{home_team} {home_score}-{away_score} {away_team}"

    if home_score > away_score:
        outcome = f"{home_team} won"
    elif away_score > home_score:
        outcome = f"{away_team} won"
    else:
        outcome = "The match ended in a draw."

    prompt = f"""
    You are MatchMind, an AI football analyst for the 2026 FIFA World Cup.
    Generate an engaging post-match report for:

    {result}
    Stage: {group_info}
    Outcome: {outcome}

    Include:
    - A punchy headline and opening line
    - How the match likely unfolded (tempo, momentum shifts)
    - Key moments that decided the game
    - A standout performer for the winning, losing or drawing sides
    - What this result means for each team going forward in context of group standings or knockout phase

    Keep it under 300 words. Be vivid and use football terminology. Fans should feel like they can rely upon you for an accurate post match analysis.
    """

    response = client.chat.completions.create(
        model = "llama-3.3-70b-versatile",
        messages = [{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    result = generate_match_briefing("Mexico", "South Africa", "2026-06-11", "GROUP_STAGE", "GROUP_A")
    print(result)

    report = generate_post_match_report("Mexico", "South Africa", 0, 0, "GROUP_STAGE", "GROUP_A")
    print("\nREPORT:\n", report)