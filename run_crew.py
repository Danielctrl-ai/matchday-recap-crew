"""
Run the Matchday Recap Crew from the terminal.

    python run_crew.py                         # newest match in data/matches/
    python run_crew.py data/matches/SYN-71224.json
"""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from crew.agents import run_crew

ICONS = {"working": "...", "done": "OK ", "approved": "PASS", "rejected": "FIX"}


def log(agent, status, text):
    print(f"\n[{ICONS.get(status, status)}] {agent} - {status}")
    if status != "working":
        print(text)
    else:
        print(f"    {text}")


def main():
    load_dotenv()
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        files = sorted(Path("data/matches").glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            sys.exit("No matches found. Run: python data/generate_match.py --seed 1 --count 3")
        path = files[-1]
    match = json.loads(path.read_text())
    print(f"Running crew on {path.name}")
    result = asyncio.run(run_crew(match, on_event=log))

    out = Path("outputs")
    out.mkdir(exist_ok=True)
    dest = out / f"{match['match_id']}_recap.json"
    dest.write_text(json.dumps(result, indent=2))
    print("\n" + "=" * 60)
    print("FINAL (fact-check passed)" if result["approved"] else "FINAL (fact-check still has issues)")
    print("=" * 60)
    print(result["final"])
    print(f"\nSaved to {dest}")


if __name__ == "__main__":
    main()
