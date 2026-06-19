# Netpeak Request Classifier

Structured classification of internal employee requests (Slack / Telegram / Email) using the Anthropic Claude API. Reads raw requests from a CSV file, classifies each one via Claude's Tool Use, validates the output strictly with Pydantic, and produces a JSON dump plus an aggregated Markdown report.

## What it does

For every row in `input_requests.csv`, the request text is sent to Claude along with a tool definition generated directly from a Pydantic model. The model is forced to call that tool (`tool_choice={"type": "tool", ...}`), so the response is always a JSON object matching the schema — never free text. The response is then re-validated through Pydantic before being trusted.

Output:
- `output.json` — full structured result for every request
- `report.md` — aggregated counts by category, priority, department, confidence, and a list of requests flagged as `needs_clarification`

### Categories (`category`)

`автоматизація` · `інтеграція` · `звіт/аналітика` · `баг/підтримка` · `питання/консультація` · `поза скоупом`

### Priority (`priority`)

`low` · `medium` · `high`

## Quick start

### Requirements

- Python 3.10+
- An Anthropic API key

### Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

### Environment variables (`.env`)

| Variable             | Description                                          | Default            |
|-----------------------|-------------------------------------------------------|---------------------|
| `ANTHROPIC_API_KEY`   | Your Anthropic API key                                 | — (required)       |
| `ANTHROPIC_MODEL`     | Model used for classification                          | `claude-sonnet-4-6` |
| `MAX_RETRIES`         | Retry attempts per request before falling back         | `3`                 |

### Run

```bash
python main.py
```

Reads `input_requests.csv` from the project root, writes `output.json` and `report.md` next to it.

### Run with Docker

```bash
docker-compose up --build
```

`.env` must exist before this — `docker-compose.yml` loads it via `env_file`.

## Architecture

```
main.py                — thin orchestrator: read CSV → classify (async, concurrency-limited) → write outputs
src/
  config.py             — typed settings from .env (pydantic-settings)
  models.py             — IncomingRequest (input validation) + RequestClassification (LLM output schema)
  prompts.py            — system prompt with category/priority/clarification rules
  csv_reader.py         — CSV → list[IncomingRequest], skips and logs invalid rows
  classifier.py         — Claude Tool Use call, retry/backoff, fallback on failure
  output_writer.py      — output.json + report.md generation
```

Each module has one responsibility; `main.py` contains no business logic of its own.

## Schema design

The fields required by the assignment (`category`, `target_department`, `priority`, `short_summary`, `requested_actions`, `needs_clarification`) are implemented as specified. Two fields were added on top of that:

- **`reasoning`** — a short chain-of-thought string the model fills in *before* the other fields, inside the same tool call. It isn't used programmatically, but it does two things: it nudges the model to think through category/priority before committing to a value (helps consistency on borderline requests), and it gives a human reviewer a one-line "why" without re-reading the raw text.
- **`confidence`** (`low` / `medium` / `high`) — the model's own certainty about *its* classification, asked for last. This is a different axis from `needs_clarification`: `needs_clarification` is about the *input* being too vague to act on; `confidence` is about the *model* being unsure of its own judgment call even when the input is clear. In the report, low-confidence items are a useful secondary triage list alongside the clarification list.

`request_id` also lives on the model but is marked `SkipJsonSchema` — needed to pair output back to input rows, but irrelevant to the LLM and excluded from the tool schema so it can't influence the classification.

The tool's `input_schema` is generated directly from `RequestClassification.model_json_schema()` rather than hand-written, so the Pydantic model is the single source of truth — field descriptions and actual validation can't drift apart.

## Validation & error handling

- Claude is forced to call the tool — it cannot reply with free text.
- If the model somehow doesn't return a tool_use block at all (rare, but possible even with `tool_choice`), this is raised explicitly with the response's `stop_reason` rather than failing with an opaque error.
- The tool's arguments are re-validated through Pydantic before being trusted; a schema violation (wrong enum value, missing field) is caught and logged distinctly from a transient API/network failure, so the two failure modes don't look identical in the logs.
- On any failure, the request is retried up to `MAX_RETRIES` times with exponential backoff (`2^attempt` seconds).
- If all retries fail, the request is **not dropped and the run does not crash** — it gets a fallback `RequestClassification` (`поза скоупом`, `low`, `needs_clarification=True`, error message in `short_summary`), so `output.json` always has one entry per input row.
- `temperature=0` minimizes (not eliminates) run-to-run variance.
- If `.env` is missing or invalid, the app exits with a clear message pointing to `.env.example` instead of a raw stack trace.

## Known limitations

**Invalid LLM output** — handled via validation + retry + fallback (above). The one gap: validation errors and API errors are logged differently but still retried the same number of times the same way — a schema-validation failure isn't necessarily something a retry fixes if the model keeps making the same mistake.

**Large volume** — concurrency is capped with `asyncio.Semaphore` (hardcoded to 20 in `main.py`), which protects against rate limits, but:
- the concurrency limit, input path, and output paths are hardcoded constants, not configurable via `.env` or CLI args;
- there's no checkpointing — if the process crashes mid-run, the whole batch restarts from scratch, including requests that already succeeded.

For the 18-row test file this is a non-issue; it would matter at hundreds or thousands of rows.

**Non-determinism** — `temperature=0` plus a forced tool call (so the model can't change output *shape*) makes results stable in practice, but doesn't guarantee identical output between runs. Borderline requests (ambiguous priority, overlapping categories) can occasionally flip — this is exactly what the `confidence` field is meant to surface.

**Token cost** — not tracked or estimated anywhere. For 18 short requests this is negligible, but there's no cost guardrail and nothing stops a much larger CSV from running an expensive batch unattended. There's also no deduplication of near-identical requests (e.g. two people in the sample data asking about the same report) — each still triggers its own full LLM call.

**Input row validation** — `IncomingRequest` rejects rows with empty `raw_text`, but `id`, `channel`, and `timestamp` aren't validated at all. A row with a blank `id` would still be processed and produce an `output.json` entry that's hard to trace back to its source row.

## What I'd do with more time

- Move hardcoded paths/limits into `.env` or CLI args.
- Replace `print()` with proper `logging` (levels, structured output).
- Estimate token cost before running, plus a `--dry-run` flag.
- Basic unit tests for `csv_reader.py` and `output_writer.py` (no API calls needed there).
- Resume support — skip rows already present in a previous `output.json` on restart.
- A lightweight human-vs-AI validation pass: have a few people manually classify the same requests and compare against the model's output, as a sanity check beyond "it ran without errors."

## A process note

A meaningful chunk of the time on this task went into thinking through hypothetical input problems — malformed rows, weird encodings, empty files, adversarial text — before actually looking closely at what `input_requests.csv` contained. The real data turned out to be clean: 18 well-formed rows, no missing fields, nothing that broke the pipeline. The defensive code that exists (input validation in `IncomingRequest`, retry/fallback in the classifier) earns its place regardless, but some of that early time would have been better spent reading the actual sample data first, and only then deciding which edge cases were actually worth designing for — instead of guessing upfront.