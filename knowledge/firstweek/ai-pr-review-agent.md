# AI PR Review Agent

Repository-grounded pull request reviews.

## About
AI PR Review Agent is a GitHub pull-request review system organized around security, quality, test and documentation specialists. The README describes repository-grounded findings, aggregation, a confidence gate and a human review queue. The graph implementation confirms a LangGraph fan-out to specialist nodes followed by an aggregate node.

## Technology stack

Python, FastAPI, LangGraph, Redis, Next.js.

## Architecture and request flow
GitHub webhook ingress validates signatures and delivery identity. Redis and ARQ separate request acceptance from review execution. A worker fetches the diff, then the LangGraph workflow dispatches review work. The documented retrieval stack combines PostgreSQL full-text search with vector retrieval and reciprocal rank fusion. Findings are merged and evaluated before a GitHub review may be posted. The Next.js frontend presents repositories, pull requests and review details.

## Operating model
The README documents an append-only event trail with agent activity, cost and latency. It also describes a budget guard that refuses work when spend cannot be read and an approval gate for uncertain or critical findings. These are documented behaviors; this corpus does not claim to have exercised the live service.

## Where to start
Read `backend/orchestrator/graph.py`, then `nodes.py`, to trace specialist execution. Read `backend/data/ingestion.py` for repository indexing. The README explains the separate ingress, worker and dashboard processes. Real LLM and embedding calls are explicitly opt-in in the documented configuration.

## Current limitations
Live GitHub posting, cloud storage and model behavior were not verified during this inspection. The project must be configured with an indexed repository whose identifier matches webhook payloads. A running ingress without its worker is not a working review pipeline.

## Ownership
Individual implementation contributions and current component owners have not been independently verified. Ask a project maintainer to assign them.

## Architecture flow
A documented workflow: validate ingress, queue work, run specialists, then aggregate and apply approval/confidence gates.

- GitHub webhook → FastAPI ingress: event.
- FastAPI ingress → Redis / ARQ: enqueue.
- Redis / ARQ → Review worker: job.
- Review worker → LangGraph specialists: diff + context.
- LangGraph specialists → Aggregation + gate: findings.

## Evidence
- `ai-pr-review-agent/README.md`
- `ai-pr-review-agent/backend/orchestrator/graph.py`
- `ai-pr-review-agent/backend/orchestrator/nodes.py`
- `ai-pr-review-agent/backend/data/ingestion.py`
