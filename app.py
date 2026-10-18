"""
Matchday Recap Crew - web app.

    streamlit run app.py
"""
import asyncio
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "data"))
from generate_match import generate  # noqa: E402

from crew.agents import run_crew  # noqa: E402

load_dotenv()
MATCH_DIR = ROOT / "data" / "matches"
MATCH_DIR.mkdir(parents=True, exist_ok=True)

AGENTS = {
    "StatsAgent": ("📊", "Stats Agent", "Pulls facts from the match data with tools"),
    "AnalystAgent": ("🧠", "Analyst Agent", "Explains why the result happened"),
    "WriterAgent": ("✍️", "Writer Agent", "Writes the recap and social posts"),
    "FactCheckerAgent": ("🔎", "Fact-Checker Agent", "Verifies every claim against the data"),
}

st.set_page_config(page_title="Matchday Recap Crew", page_icon="⚽", layout="wide")
st.title("⚽ Matchday Recap Crew")
st.caption("Four AI agents turn raw match data into a fact-checked recap. "
           "Built with Microsoft Agent Framework + Microsoft Foundry. All teams, players and data are synthetic.")

# ---------- Sidebar: choose a match ----------
with st.sidebar:
    st.header("1. Pick a match")
    if st.button("🎲 Generate a new synthetic match", use_container_width=True):
        m = generate()
        (MATCH_DIR / f"{m['match_id']}.json").write_text(json.dumps(m, indent=2))
        st.session_state.match_file = f"{m['match_id']}.json"
        st.session_state.pop("result", None)

    uploaded = st.file_uploader("…or upload a match JSON", type="json")
    if uploaded:
        m = json.load(uploaded)
        (MATCH_DIR / f"{m['match_id']}.json").write_text(json.dumps(m, indent=2))
        st.session_state.match_file = f"{m['match_id']}.json"

    files = sorted(p.name for p in MATCH_DIR.glob("*.json"))
    if not files:
        st.info("No matches yet - generate one above.")
        st.stop()
    default = files.index(st.session_state.get("match_file", files[0])) \
        if st.session_state.get("match_file") in files else 0
    choice = st.selectbox("Saved matches", files, index=default)
    if choice != st.session_state.get("match_file"):
        st.session_state.match_file = choice
        st.session_state.pop("result", None)

    st.header("2. Options")
    plant = st.toggle("Demo: plant one mistake for the fact-checker to catch", value=False,
                      help="The Writer deliberately gets one fact wrong in its first draft, "
                           "so you can watch the Fact-Checker catch it and send it back.")

match = json.loads((MATCH_DIR / st.session_state.match_file).read_text())
home, away = match["home_team"], match["away_team"]
hs, as_ = match["team_stats"][home], match["team_stats"][away]

# ---------- Match header ----------
c1, c2, c3 = st.columns([2, 1, 2])
c1.markdown(f"### {home}\n*{match['home_style']} style*")
c2.markdown(f"<h1 style='text-align:center;margin:0'>{match['final_score']}</h1>", unsafe_allow_html=True)
c3.markdown(f"<div style='text-align:right'><h3>{away}</h3><i>{match['away_style']} style</i></div>",
            unsafe_allow_html=True)

left, right = st.columns([1, 1])
with left:
    rows = [("Possession %", "possession_pct"), ("Shots", "shots"), ("On target", "shots_on_target"),
            ("xG", "xg"), ("Corners", "corners"), ("Fouls", "fouls"), ("Yellow cards", "yellow_cards"),
            ("Red cards", "red_cards")]
    st.dataframe(pd.DataFrame({"Stat": [r[0] for r in rows], home: [hs[r[1]] for r in rows],
                               away: [as_[r[1]] for r in rows]}).set_index("Stat"),
                 use_container_width=True)
with right:
    st.markdown("**Cumulative xG**")
    last_min = max(e["minute"] for e in match["events"])
    xg = {home: 0.0, away: 0.0}
    timeline = []
    shots = {e["minute"]: [] for e in match["events"]}
    for e in match["events"]:
        shots[e["minute"]].append(e)
    for minute in range(0, last_min + 1):
        for e in shots.get(minute, []):
            if e["type"] in ("shot", "goal"):
                xg[e["team"]] += e.get("xg", 0)
        timeline.append({"minute": minute, home: round(xg[home], 2), away: round(xg[away], 2)})
    st.line_chart(pd.DataFrame(timeline).set_index("minute"), height=260,
                  color=["#2563eb", "#f97316"])
    goals = [e for e in match["events"] if e["type"] == "goal"]
    st.caption("Goals: " + (", ".join(f"{e['minute']}' {e['player']} ({e['team']})" for e in goals) or "none"))

st.divider()

# ---------- Run the crew ----------
st.header("🤖 The crew at work")
cols = st.columns(4)
for col, (key, (icon, name, desc)) in zip(cols, AGENTS.items()):
    col.markdown(f"**{icon} {name}**  \n<span style='font-size:0.85em;opacity:0.75'>{desc}</span>",
                 unsafe_allow_html=True)

if st.button("▶ Run the Recap Crew", type="primary", use_container_width=True):
    feed = st.container()
    current = {}

    def on_event(agent, status, text):
        icon, name, _ = AGENTS[agent]
        if status == "working":
            current[agent] = feed.status(f"{icon} {name}: {text}", state="running", expanded=False)
            return
        box = current.pop(agent, None) or feed.status(f"{icon} {name}", expanded=False)
        if status == "rejected":
            issues = json.loads(text)
            box.update(label=f"{icon} {name}: found {len(issues)} issue(s), sending back to the Writer",
                       state="error", expanded=True)
            for i in issues:
                box.markdown(f"- ❌ **{i.get('claim')}** - {i.get('problem')}  \n"
                             f"  ✅ Correct: {i.get('correct_fact')}")
        elif status == "approved":
            box.update(label=f"{icon} {name}: {text}", state="complete", expanded=False)
        else:
            box.update(label=f"{icon} {name}: done", state="complete", expanded=False)
            box.markdown(text)

    try:
        st.session_state.result = asyncio.run(run_crew(match, on_event=on_event, plant_error=plant))
    except Exception as e:  # show friendly error in the UI
        for box in current.values():  # stop any spinner left running by the crash
            box.update(state="error", expanded=False)
        if isinstance(e, KeyError) and str(e.args[0]).startswith("AZURE_OPENAI"):
            st.error(f"Missing setting {e}. Add it to your .env file (see .env.example).")
        else:
            st.error(f"The crew hit an error: {type(e).__name__}: {e}")

# ---------- Results ----------
res = st.session_state.get("result")
if res and res["match"].startswith(home):
    st.divider()
    if res["approved"]:
        rounds = len(res["fact_checks"])
        st.success(f"✅ Fact-check passed" + (f" after {rounds - 1} revision(s)" if rounds > 1 else ""))
    else:
        st.warning("⚠️ Fact-checker still found issues after the maximum revisions. Review before publishing.")

    t1, t2, t3, t4 = st.tabs(["📰 Recap & social posts", "🧠 Analysis", "📊 Fact sheet", "🔎 Fact-check log"])
    t1.markdown(res["final"])
    t2.markdown(res["analysis"])
    t3.markdown(res["facts"])
    for n, v in enumerate(res["fact_checks"], 1):
        t4.markdown(f"**Round {n}:** {'✅ approved' if v['approved'] else '❌ rejected'} "
                    f"- {v.get('claims_checked', '?')} claims checked")
        for i in v.get("issues", []):
            t4.markdown(f"- {i.get('claim')} → {i.get('correct_fact')}")
    st.download_button("⬇ Download results (JSON)", json.dumps(res, indent=2),
                       file_name=f"{match['match_id']}_recap.json", mime="application/json")
