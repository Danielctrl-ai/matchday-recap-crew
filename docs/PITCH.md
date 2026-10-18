# Submission text

## Elevator pitch (short)
Four AI agents turn raw football match data into a fact-checked match report and social posts in under a minute, and catch their own mistakes before anything is published.

## Project description
**What it is:** Matchday Recap Crew is a multi-agent system that turns football match event data into a publish-ready match recap and three social posts.

**The problem it solves:** Media teams need instant post-match content, but a single AI prompt makes up scorers, minutes and stats. One wrong fact damages trust.

**What it does:** A Stats Agent pulls facts from the match data with tools. An Analyst Agent explains why the result happened. A Writer Agent drafts the recap and posts. A Fact-Checker Agent verifies every claim against the data, sends wrong claims back to the Writer, and approves the content only when it is correct. The web app shows each agent working live, with an xG timeline and a full fact-check log.

**Microsoft technologies:** Microsoft Foundry (Azure OpenAI gpt-4.1-mini), Microsoft Agent Framework (Python) for agents, tool calling and orchestration, Azure Container Apps with Azure Container Registry for hosting, Container Apps secrets, and GitHub.

**Data:** 100% synthetic. Invented teams, players and events from our own realistic match generator. No real footage, Premier League data or trademarks.

**Category:** Best Multi-Agent System

**Live demo:** https://matchday-recap-crew.jollypebble-71ea79f7.eastus2.azurecontainerapps.io
**Repository:** https://github.com/Danielctrl-ai/matchday-recap-crew
