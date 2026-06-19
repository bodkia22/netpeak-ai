# Netpeak Request Classifier

Structured classification of internal employee requests (Slack / Telegram / Email) using the Anthropic Claude API. Reads raw requests from a CSV file, classifies each one via Claude's Tool Use, validates the output strictly with Pydantic, and produces a JSON dump plus an aggregated Markdown report.

## What it does

For every row in `input_requests.csv`, the request text is sent to Claude along with a tool definition generated directly from a Pydantic model. The model is forced to call that tool (`tool_choice={"type": "tool", ...}`), so the response is always a JSON object matching the schema — never free text. The response is then re-validated through Pydantic before being trusted.

Output:
- `output.json` — full structured result for every request
- `report.md` — aggregated counts by category, priority, department, confidence, and a list of requests flagged as `needs_clarification`

## Output schema

Each request is classified into a single `RequestClassification` object. The model produces all fields in one tool call, in the order below. Fields marked **➕** were added on top of the assignment's required set — the rationale is in [Why the schema was extended](#why-the-schema-was-extended).

| Field                 | Type            | What it holds                                                                                          |
|-----------------------|-----------------|--------------------------------------------------------------------------------------------------------|
| `reasoning` ➕         | `str`           | Short chain-of-thought written *first*: what in the text points to this category, urgency, and whether there's enough detail to act on. |
| `category`            | enum            | One of six fixed categories (see below).                                                               |
| `target_department`   | `str \| null`   | Requesting department if clear from the text (e.g. `HR`, `продажі`); `null` if not.                    |
| `priority`            | enum            | `low` / `medium` / `high`, derived from tone and content (see below).                                  |
| `short_summary`       | `str`           | The gist of the request in one sentence (Ukrainian).                                                   |
| `requested_actions`   | `list[str]`     | Concrete actions being asked for; empty list if there's no concrete request.                           |
| `needs_clarification` | `bool`          | `true` if the request is too vague to take on as-is.                                                   |
| `confidence` ➕        | enum            | `low` / `medium` / `high` — the model's certainty in *its own* classification, assessed last.          |

`request_id` is also carried on the object to pair output back to input rows, but it's hidden from the LLM (`SkipJsonSchema`) so it can't influence the result.

### Categories (`category`)

- **автоматизація** — a request to automate a manual, repetitive process
- **інтеграція** — connecting or syncing different systems / tools together
- **звіт/аналітика** — reports, dashboards, data analysis
- **баг/підтримка** — something is broken or not working; technical help needed
- **питання/консультація** — a general question or opinion, with no concrete build request
- **поза скоупом** — not the AI unit's job (hardware purchases, thank-you notes, requests aimed at other departments)

### Priority (`priority`)

- **high** — explicit urgency markers ("терміново", "горить"), a tight deadline ("сьогодні до вечора"), or a critical problem blocking work
- **medium** — there's a deadline or moderate importance, but no signs of being critical
- **low** — no urgency signals: a general question, an idea for later, a thank-you

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

## Why the schema was extended

The assignment requires `category`, `target_department`, `priority`, `short_summary`, `requested_actions`, `needs_clarification`. Two more fields were added (`reasoning`, `confidence`), and here's the reasoning for each:

- **`reasoning`** is asked for *first*, before any verdict. It isn't used programmatically — its job is to make the model think through the classification before committing to values (which helps consistency on borderline requests), and to give a human reviewer a one-line "why" without re-reading the raw text.
- **`confidence`** captures a different axis from `needs_clarification`. `needs_clarification` is about the *input* being too vague to act on; `confidence` is about the *model* being unsure of its own judgment even when the input is clear. In the report, low-confidence items form a useful secondary triage list next to the clarification list.

The tool's `input_schema` is generated directly from `RequestClassification.model_json_schema()` rather than hand-written, so the Pydantic model is the single source of truth — field descriptions sent to the LLM and the validation applied to its output can't drift apart.

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
