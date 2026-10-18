"""
Matchday Recap Crew - four cooperating agents built with Microsoft Agent Framework
and a model deployed in Microsoft Foundry (Azure OpenAI).

  Stats agent   -> pulls the facts from the match data using tools
  Analyst agent -> explains WHY the match went the way it did
  Writer agent  -> writes the recap and social posts
  Fact-checker  -> verifies every claim with tools; sends the draft back if wrong

run_crew() returns all outputs and calls on_event(...) at each step so a UI can
show the agents working live.
"""
import json
import os
import re
from urllib.parse import urlparse

from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient

from .tools import make_tools

MAX_REVISIONS = 2


def make_client() -> OpenAIChatCompletionClient:
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    # Foundry's "Target URI" includes a long path; the client only needs https://<resource>.<domain>/
    u = urlparse(endpoint)
    base = f"{u.scheme}://{u.netloc}/"
    return OpenAIChatCompletionClient(
        model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
        azure_endpoint=base,
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )


def build_agents(client, match: dict) -> dict:
    t = make_tools(match)

    stats = Agent(
        client,
        name="StatsAgent",
        instructions=(
            "You are a football data analyst. Use your tools to gather the facts of the match: "
            "final score, goals (scorer, minute, assist), possession, shots, xG, cards and big chances. "
            "Also compare the two halves with get_period_stats (1-45 and 46-end). "
            "Return a concise fact sheet as bullet points. Only state numbers you got from a tool."
        ),
        tools=[t["overview"], t["goals"], t["moments"], t["period"]],
    )

    analyst = Agent(
        client,
        name="AnalystAgent",
        instructions=(
            "You are a tactical football analyst. Given a fact sheet, explain in 4-6 bullet points WHY "
            "the result happened: momentum swings, xG vs goals (clinical or wasteful finishing), impact of "
            "cards and substitutions, and how each team's playing style showed. You may call "
            "get_period_stats to check a momentum theory. Be specific, cite minutes and numbers."
        ),
        tools=[t["period"], t["moments"]],
    )

    writer = Agent(
        client,
        name="WriterAgent",
        instructions=(
            "You are a sports journalist for a fictional synthetic league. Using ONLY the fact sheet and "
            "analysis provided, write:\n"
            "## Match Recap\nA headline and a 200-250 word recap.\n"
            "## Social Posts\nThree short posts (under 280 characters each): one for each club's fans and "
            "one neutral. No real clubs, leagues or trademarks.\n"
            "If you receive fact-check corrections, rewrite the content fixing every issue."
        ),
    )

    checker = Agent(
        client,
        name="FactCheckerAgent",
        instructions=(
            "You are a strict fact-checker. Check EVERY factual claim in the draft (scores, scorers, minutes, "
            "assists, stats, cards, substitutions) using your tools. Do not trust the draft.\n"
            "Reply with ONLY a JSON object, no other text:\n"
            '{"approved": true|false, "claims_checked": <int>, '
            '"issues": [{"claim": "...", "problem": "...", "correct_fact": "..."}]}\n'
            "List ONLY claims that are wrong. Never put a correct claim in issues. "
            "Every issue must include correct_fact.\n"
            "approved is true only if issues is empty. Opinions and adjectives are not issues."
        ),
        tools=[t["overview"], t["goals"], t["minute"], t["player"], t["period"]],
    )

    return {"stats": stats, "analyst": analyst, "writer": writer, "checker": checker}


def parse_verdict(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"approved": False, "claims_checked": 0,
                "issues": [{"claim": "-", "problem": "Fact-checker returned no JSON", "correct_fact": "-"}]}
    try:
        v = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"approved": False, "claims_checked": 0,
                "issues": [{"claim": "-", "problem": "Fact-checker returned invalid JSON", "correct_fact": "-"}]}
    # Drop "issues" that are really confirmations: a genuine issue always comes with a correct fact.
    v["issues"] = [i for i in v.get("issues") or []
                   if isinstance(i, dict)
                   and str(i.get("correct_fact") or "").strip().lower() not in ("", "none", "null", "n/a", "-")]
    v["approved"] = not v["issues"]
    return v


DEMO_ERROR_NOTE = (
    "\n\nDEMO MODE: to demonstrate the fact-checker, deliberately get exactly ONE fact wrong in "
    "the recap (for example, change the minute of a goal or the name of a scorer). Do not mention it."
)


async def run_crew(match: dict, on_event=None, client=None, plant_error: bool = False) -> dict:
    """Run the four agents on one match. on_event(agent_name, status, text) is optional.
    plant_error=True makes the first draft contain one deliberate mistake (labelled demo mode)."""
    emit = on_event or (lambda *a: None)
    client = client or make_client()
    a = build_agents(client, match)
    title = f"{match['home_team']} {match['final_score']} {match['away_team']}"

    emit("StatsAgent", "working", f"Pulling facts for {title}...")
    facts = (await a["stats"].run(f"Build the fact sheet for match {match['match_id']}: {title}.")).text
    emit("StatsAgent", "done", facts)

    emit("AnalystAgent", "working", "Analysing why the match unfolded this way...")
    analysis = (await a["analyst"].run(f"Fact sheet:\n{facts}\n\nExplain why the result happened.")).text
    emit("AnalystAgent", "done", analysis)

    emit("WriterAgent", "working", "Writing recap and social posts...")
    draft = (await a["writer"].run(
        f"Fact sheet:\n{facts}\n\nAnalysis:\n{analysis}" + (DEMO_ERROR_NOTE if plant_error else ""))).text
    emit("WriterAgent", "done", draft)

    history = []
    for attempt in range(MAX_REVISIONS + 1):
        emit("FactCheckerAgent", "working", f"Verifying claims (round {attempt + 1})...")
        verdict = parse_verdict((await a["checker"].run(f"Fact-check this draft:\n\n{draft}")).text)
        history.append(verdict)
        if verdict["approved"]:
            emit("FactCheckerAgent", "approved",
                 f"All {verdict.get('claims_checked', '?')} claims verified.")
            break
        emit("FactCheckerAgent", "rejected", json.dumps(verdict["issues"], indent=2))
        if attempt == MAX_REVISIONS:
            break
        emit("WriterAgent", "working", "Fixing the issues the fact-checker found...")
        fixes = "\n".join(f"- {i.get('claim', '')}: {i.get('problem', '')} -> {i.get('correct_fact', '')}"
                          for i in verdict["issues"])
        draft = (await a["writer"].run(
            f"Fact sheet:\n{facts}\n\nYour previous draft:\n{draft}\n\n"
            f"Fact-check corrections to apply:\n{fixes}\n\nRewrite the full content.")).text
        emit("WriterAgent", "done", draft)

    return {"match": title, "facts": facts, "analysis": analysis, "final": draft,
            "approved": history[-1]["approved"], "fact_checks": history}
