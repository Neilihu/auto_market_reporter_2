# skill-stock-daily-report

`skill-stock-daily-report` is the end-to-end orchestration skill for this repository.

It runs the full pipeline:

1. Step 1: collecting specifc stock news into JSON
2. Step 2: generate per-ticker TXT summaries
3. Step 3: export TXT to PDF

## What It Does

- Resolves project root by walking up to `config.txt`
- Ensures shared Python environment at `<root>/.venv`
- Supports two startup modes through `AUTO` in `config.txt`:
  - `AUTO=0`: interactive config flow
  - `AUTO=1`: skip config Q&A and run directly
- Applies config updates by overwrite (not merge)
- Runs the pipeline in strict order: `step_1 -> step_2 -> step_3`
- On success, returns:
  1. `finished`
  2. Final PDF path

## AUTO Mode

`config.txt` includes:

```text
AUTO:
0
```

Behavior:

- If `AUTO` is missing or invalid, it is treated as `0` and written back as `0`
- If `AUTO=1`, the skill starts execution directly after environment checks
- If `AUTO=0`, the skill enters the interactive config process

After every run (success or failure), the skill asks:

`Enable auto-run next time (AUTO=1)?`

It then overwrites `AUTO`:

- yes -> `1`
- no -> `0`

## Interactive Config Flow (AUTO=0)

During each config turn, the skill displays:

1. `Report related content` (in user language)
2. `COMPANY`
3. `TOPIC CORE`

Then it asks whether anything else should be changed.

### Company Updates

- Accepts add/remove intent in natural language
- Validates newly added symbols (via `scripts/resolve_us_ticker.py`)
- Does not auto-recommend symbols
- Overwrites `COMPANY` in normalized format

Each `COMPANY` line keeps:

- ticker
- formal company name
- common stock-market aliases

Example:

```text
XOM: XOM, Exxon Mobil, ExxonMobil, Exxon Mobil Corporation
```

### Topic Updates

- `TOPIC CORE` is the anchor
- After confirming `TOPIC CORE`, the skill asks for directions of interest
- If no direction is given, topic terms are auto-generated from `TOPIC CORE`
- If direction is given, topic terms prioritize that direction
- Generated `TOPIC` is written to `config.txt` immediately in the same turn

## Additional Tunables

The skill can also update:

- `DAY RANGE`
- `TOP_K`
- `SUMMARY LENGTH`
- `MODEL`
- `PDF OUTPUT DIR`
- `PDF FONT SIZE`

All updates are overwrite-based.

## Execution Commands

The orchestrator runs these scripts with `<root>/.venv/bin/python`:

- `step_1/news-collector/scripts/collect_news.py`
- `step_2/stock-report-writer` flow (`prepare_inputs.py` + summary generation + `write_output.py`)
- `step_3/txt-to-pdf-exporter/scripts/txt_to_pdf.py`

## Failure Contract

On failure, the skill returns structured fields:

- `failed_step`
- `command`
- `stderr_summary`

No downstream step runs after a failure.

## Skill-based model

OPENAI

## Author

Neili Hu
