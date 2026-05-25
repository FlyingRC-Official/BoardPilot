# FlyingRC BoardPilot Operations Guide

This guide turns the generic BoardPilot MVP into a FlyingRC internal support workbench.

## 1. Deploy Privately

Start with a local or office-LAN Docker Compose deployment. Do not expose the stack directly to the public internet for the first validation pass.

```bash
cd /Users/lyhenry/Desktop/Projects/BoardPilot
cp config/flyingrc.env.example .env
# Edit BOARDPILOT_API_KEY and NEXT_PUBLIC_BOARDPILOT_API_KEY to the same long secret.
docker compose up --build
```

Open:

- Web workbench: `http://127.0.0.1:3001`
- API health: `http://127.0.0.1:8000/health`

For remote internal access, put the host behind Tailscale, ZeroTier, VPN, or Cloudflare Access. Keep direct port forwarding off until auth and audit retention are hardened. When other computers open the workbench, set `NEXT_PUBLIC_API_BASE_URL` and `BOARDPILOT_CORS_ORIGINS` to the LAN/VPN host name instead of `localhost`, because browser requests are made from the user's computer.

## 2. Seed FlyingRC Starter Knowledge

After the API is healthy, import the starter FlyingRC products, aliases, source material, and eval cases:

```bash
python3 scripts/seed_flyingrc.py \
  --api-base http://127.0.0.1:8000 \
  --api-key "replace-with-a-long-random-secret"
```

The seed is intentionally small. It creates three controlled product areas:

- FlyingRC F4 Flight Controller
- FlyingRC AM32 ESC
- FlyingRC CAN Node

Then add real documents in `/sources`: product manuals, wiring diagrams, pinout tables, firmware release notes, historical support tickets, text logs, and reviewed FAQ entries.

## 3. Test Like FlyingRC Support

Run the normal regression checks before changing code:

```bash
cd /Users/lyhenry/Desktop/Projects/BoardPilot/api
source .venv/bin/activate
pytest
alembic upgrade head

cd /Users/lyhenry/Desktop/Projects/BoardPilot/web
npm install
npm run build
```

Run the operational smoke test:

1. Open `/sources` and confirm FlyingRC products, aliases, source versions, and chunks exist.
2. Open `/ask` and ask the acceptance questions printed by the seed script.
3. Confirm answers show saved Evidence and citation markers.
4. Use feedback buttons when an answer is incomplete or missing a source.
5. Open `/review` and confirm low-confidence or feedback items are visible.
6. Open `/eval`, run an EvalRun, and inspect Recall@20, Rerank@5, Citation Support Rate, and Need Review Rate.

Initial FlyingRC pass criteria:

- At least 80% of representative questions retrieve the correct source in reranked Top 5.
- Evidence-backed answers show visible citations.
- Missing or partial evidence goes to Review instead of being treated as authoritative.
- Each failed case is categorized as missing source, stale source, bad parse, bad chunk, bad recall, bad rerank, unsupported claim, generation error, product alias missing, or human policy required.

## 4. Daily Workflow

- Knowledge maintainers upload each new manual, pinout, firmware note, wiring diagram, and reviewed FAQ as a new source version.
- Support engineers ask customer questions in `/ask`, inspect the evidence pack, and adapt the answer for the customer.
- Reviewers handle incomplete, risky, or user-reported answers in `/review`.
- Good reviewed answers become ApprovedFAQ sources.
- Useful failures become EvalCases so they stay covered after future retrieval or model changes.
- Evaluators run `/eval` weekly and compare the latest run to the previous run.

## 5. Real Data Rules

Before importing QQ, WeChat, email, order, or support-ticket history, remove customer names, phone numbers, addresses, order IDs, QQ/WeChat IDs, and payment details.

Keep fake/local providers during the first pass. Enable OpenAI-compatible LLM, embedding, OCR, or Cohere rerank providers only after FlyingRC approves which source material is allowed to leave the private deployment.
