"""
Match-data tools the agents can call.

Each function reads the synthetic match JSON so agents work from real
numbers instead of guessing. make_tools() binds the functions to one match.
"""
import json
from typing import Annotated


def make_tools(match: dict):
    home, away = match["home_team"], match["away_team"]
    events = match["events"]

    def get_match_overview() -> str:
        """Final score, teams, playing styles and full team stats (possession, shots, xG, cards...)."""
        return json.dumps({
            "home_team": home, "away_team": away,
            "final_score": f"{home} {match['final_score']} {away}",
            "home_style": match["home_style"], "away_style": match["away_style"],
            "team_stats": match["team_stats"],
        }, indent=2)

    def get_goals() -> str:
        """Every goal: minute, team, scorer, assist, xG of the chance and score after the goal."""
        goals = [e for e in events if e["type"] == "goal"]
        return json.dumps(goals, indent=2) if goals else "No goals were scored."

    def get_key_moments() -> str:
        """Goals, big chances (xG >= 0.3), red/yellow cards and substitutions, in time order."""
        keep = [e for e in events
                if e["type"] in ("goal", "substitution")
                or (e["type"] == "shot" and e.get("xg", 0) >= 0.3)
                or e.get("card")]
        return json.dumps(keep, indent=2)

    def get_period_stats(
        start_minute: Annotated[int, "First minute of the period, e.g. 1"],
        end_minute: Annotated[int, "Last minute of the period, e.g. 45"],
    ) -> str:
        """Shots, shots on target, xG and goals for each team between two minutes (use to find momentum swings)."""
        out = {t: {"shots": 0, "on_target": 0, "xg": 0.0, "goals": 0} for t in (home, away)}
        for e in events:
            if start_minute <= e["minute"] <= end_minute and e["type"] in ("shot", "goal"):
                s = out[e["team"]]
                s["shots"] += 1
                s["on_target"] += int(e.get("on_target", False))
                s["xg"] = round(s["xg"] + e.get("xg", 0), 2)
                s["goals"] += int(e["type"] == "goal")
        return json.dumps({"period": f"{start_minute}-{end_minute}", **out}, indent=2)

    def get_events_at_minute(
        minute: Annotated[int, "Match minute to look up"],
    ) -> str:
        """All events that happened in a given minute (use to verify a specific claim)."""
        found = [e for e in events if e["minute"] == minute]
        return json.dumps(found, indent=2) if found else f"No recorded events in minute {minute}."

    def get_player_events(
        player_name: Annotated[str, "Player's full name as it appears in the data"],
    ) -> str:
        """Every event involving a player (shots, goals, assists, cards, substitutions)."""
        name = player_name.lower()
        found = [e for e in events if any(
            isinstance(v, str) and v.lower() == name for v in e.values())]
        return json.dumps(found, indent=2) if found else f"No events found for '{player_name}'."

    return {
        "overview": get_match_overview,
        "goals": get_goals,
        "moments": get_key_moments,
        "period": get_period_stats,
        "minute": get_events_at_minute,
        "player": get_player_events,
    }
