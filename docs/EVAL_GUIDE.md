# BoardPilot Eval Guide

Eval exists to measure whether correct source chunks enter the reranked Top 5 and whether answers stay grounded in saved Evidence records.

## Seed Cases

Each EvalCase should include:

- question text
- product id
- expected source ids
- expected chunk ids
- expected answer points
- tags
- difficulty

## Metrics

The MVP API records:

- Recall@20
- Rerank@5
- Citation Support Rate
- Unsupported Claim Rate
- Need Review Rate
- Evidence Sufficiency Rate
- Failure Category distribution
- Latency

## Failure Categories

Use the categories from `BOARDPILOT_REQUIREMENTS.md` so review decisions can feed source repair, parser fixes, retrieval tuning, and regression tests.

