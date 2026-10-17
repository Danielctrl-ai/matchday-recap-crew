"""
Synthetic football match generator for Matchday Recap Crew.

All teams, players and events are invented (no real clubs, players or
Premier League data), so output is safe to use under the hackathon's
synthetic-data rule.

Usage:
    python data/generate_match.py                 # random match -> data/matches/
    python data/generate_match.py --seed 42       # reproducible match
    python data/generate_match.py --count 5       # five matches
"""
import argparse
import json
import random
from pathlib import Path

TEAMS = {
    "Riverside Rovers": {"style": "possession", "strength": 0.58},
    "Harbour City FC": {"style": "counter", "strength": 0.52},
    "Northgate Athletic": {"style": "pressing", "strength": 0.55},
    "Ashford Wanderers": {"style": "direct", "strength": 0.48},
    "Kingsbridge United": {"style": "possession", "strength": 0.53},
    "Millbrook Town": {"style": "counter", "strength": 0.46},
}

FIRST = ["Leo", "Marcus", "Theo", "Kai", "Elias", "Jonah", "Rafa", "Niko",
         "Sami", "Owen", "Dario", "Felix", "Tomas", "Ade", "Luca", "Mateo"]
LAST = ["Hartley", "Okafor", "Lindqvist", "Moreau", "Brennan", "Castell",
        "Adeyemi", "Kowal", "Fairbairn", "Silva-Reed", "Ashdown", "Varga",
        "Mensah", "Doyle", "Iversen", "Quill"]
POSITIONS = ["GK", "RB", "CB", "CB", "LB", "DM", "CM", "CM", "RW", "ST", "LW"]

# Style tweaks: (possession bias, shot rate, long-shot share)
STYLE = {
    "possession": (0.08, 1.00, 0.25),
    "counter": (-0.08, 0.95, 0.30),
    "pressing": (0.03, 1.10, 0.35),
    "direct": (-0.04, 1.05, 0.45),
}


def make_squad(rng, team):
    used, squad = set(), []
    for i, pos in enumerate(POSITIONS + ["CM", "ST", "RW", "CB"]):
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if name not in used:
                used.add(name)
                break
        squad.append({"id": f"{team[:3].upper()}{i+1:02d}", "name": name,
                      "position": pos, "starter": i < 11})
    return squad


def shot_xg(rng, long_share):
    if rng.random() < long_share:
        return round(rng.uniform(0.02, 0.08), 2), "outside box"
    if rng.random() < 0.12:
        return round(rng.uniform(0.35, 0.76), 2), "close range"
    return round(rng.uniform(0.07, 0.30), 2), "inside box"


def generate(seed=None):
    rng = random.Random(seed)
    home, away = rng.sample(list(TEAMS), 2)
    squads = {home: make_squad(rng, home), away: make_squad(rng, away)}
    on_pitch = {t: [p for p in squads[t] if p["starter"]] for t in squads}
    bench = {t: [p for p in squads[t] if not p["starter"]] for t in squads}

    base = TEAMS[home]["strength"] - TEAMS[away]["strength"] + 0.04  # home edge
    poss_home = 0.5 + base * 0.6 + STYLE[TEAMS[home]["style"]][0] - STYLE[TEAMS[away]["style"]][0]

    events, score = [], {home: 0, away: 0}
    stats = {t: {"possession_ticks": 0, "passes": 0, "shots": 0, "shots_on_target": 0,
                 "xg": 0.0, "corners": 0, "fouls": 0, "yellow_cards": 0, "red_cards": 0}
             for t in squads}

    def outfield(team, attacking=True):
        pool = [p for p in on_pitch[team] if p["position"] != "GK"]
        if attacking:
            pool = [p for p in pool if p["position"] in ("ST", "RW", "LW", "CM")] or pool
        return rng.choice(pool)

    momentum = 0.0
    for minute in range(1, 91 + rng.randint(2, 5)):
        # momentum drifts, creating spells of pressure (good material for the Analyst agent)
        momentum = max(-0.2, min(0.2, momentum + rng.uniform(-0.05, 0.05)))
        p_home = max(0.25, min(0.75, poss_home + momentum))
        team = home if rng.random() < p_home else away
        opp = away if team == home else home
        stats[team]["possession_ticks"] += 1
        stats[team]["passes"] += rng.randint(4, 9)

        style = TEAMS[team]["style"]
        shot_rate = 0.13 * STYLE[style][1] * (1 + (TEAMS[team]["strength"] - 0.5))
        if rng.random() < shot_rate:
            shooter = outfield(team)
            xg, zone = shot_xg(rng, STYLE[style][2])
            on_target = rng.random() < 0.35 + xg
            goal = on_target and rng.random() < min(0.95, xg * 1.6)
            stats[team]["shots"] += 1
            stats[team]["xg"] = round(stats[team]["xg"] + xg, 2)
            if on_target:
                stats[team]["shots_on_target"] += 1
            ev = {"minute": minute, "team": team, "type": "goal" if goal else "shot",
                  "player": shooter["name"], "xg": xg, "zone": zone,
                  "on_target": on_target}
            if goal:
                score[team] += 1
                assister = outfield(team)
                if assister["name"] != shooter["name"] and rng.random() < 0.75:
                    ev["assist"] = assister["name"]
                ev["score_after"] = f"{score[home]}-{score[away]}"
            events.append(ev)
            if not on_target and rng.random() < 0.3:
                stats[team]["corners"] += 1
                events.append({"minute": minute, "team": team, "type": "corner"})

        if rng.random() < 0.12:
            fouler = outfield(opp, attacking=False)
            stats[opp]["fouls"] += 1
            ev = {"minute": minute, "team": opp, "type": "foul", "player": fouler["name"]}
            r = rng.random()
            if r < 0.18:
                ev["card"] = "yellow"
                stats[opp]["yellow_cards"] += 1
            elif r < 0.195:
                ev["card"] = "red"
                stats[opp]["red_cards"] += 1
                on_pitch[opp] = [p for p in on_pitch[opp] if p["name"] != fouler["name"]]
                poss_home += -0.06 if opp == home else 0.06
            events.append(ev)

        if minute in (60, 70, 80) and bench[team]:
            off = outfield(team, attacking=False)
            on = bench[team].pop(0)
            on_pitch[team] = [p for p in on_pitch[team] if p["name"] != off["name"]] + [on]
            events.append({"minute": minute, "team": team, "type": "substitution",
                           "player_off": off["name"], "player_on": on["name"]})

    total = sum(s["possession_ticks"] for s in stats.values())
    for t, s in stats.items():
        s["possession_pct"] = round(100 * s.pop("possession_ticks") / total)

    return {
        "match_id": f"SYN-{rng.randint(10000, 99999)}",
        "synthetic": True,
        "competition": "Synthetic League (fictional)",
        "home_team": home, "away_team": away,
        "home_style": TEAMS[home]["style"], "away_style": TEAMS[away]["style"],
        "final_score": f"{score[home]}-{score[away]}",
        "team_stats": stats,
        "lineups": squads,
        "events": events,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--out", default=str(Path(__file__).parent / "matches"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for i in range(args.count):
        seed = None if args.seed is None else args.seed + i
        m = generate(seed)
        path = out / f"{m['match_id']}.json"
        path.write_text(json.dumps(m, indent=2))
        print(f"{path.name}: {m['home_team']} {m['final_score']} {m['away_team']} "
              f"(xG {m['team_stats'][m['home_team']]['xg']} - {m['team_stats'][m['away_team']]['xg']}, "
              f"{len(m['events'])} events)")


if __name__ == "__main__":
    main()
