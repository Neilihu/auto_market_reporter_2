---
name: daily-report-orchestrator
description: Orchestrate the full daily stock report pipeline end-to-end. Use when users want one run that validates runtime/config, confirms and updates COMPANY/TOPIC CORE settings, then executes step_1 news collection, step_2 summary writing, and step_3 TXT-to-PDF export in order.
---

# Daily Report Orchestrator Workflow

Follow this workflow exactly.

## Operating Principle
- Be conservative by default, not aggressive.
- Prefer explicit confirmation over assumptions.
- Prefer minimal changes to achieve the user's goal.
- If ambiguity remains on high-impact config updates, pause and ask before writing.

## 1) Resolve Root From Current Directory
- Start from `$PWD` and walk up until `config.txt` is found.
- Treat that directory as `<root>`.
- If not found, stop and return:
`config.txt not found while walking up from current directory`

## 2) Ensure Runtime Environment
- Preferred interpreter: `<root>/.venv/bin/python`.
- If interpreter exists and is executable, use it directly.
- If missing or not executable, create and prepare it:

```bash
python3 -m venv "<root>/.venv"
"<root>/.venv/bin/python" -m pip install --upgrade pip
"<root>/.venv/bin/python" -m pip install -r "<root>/requirements.txt"
```

- If environment setup fails, stop and return structured error:
  - `failed_step: env_setup`
  - `command: <the failed command>`
  - `stderr_summary: <short stderr>`

## 3) Read AUTO Mode
- Read `AUTO` from `<root>/config.txt`.
- Valid values:
  - `0`: interactive config mode
  - `1`: auto-run mode
- If missing or invalid, treat as `0` and overwrite config to set `AUTO` to `0`.

## 4) Confirm Config With User Before Execution (AUTO=0 only)
- During config conversation, always display this header line before company info:
`Report related content` (or equivalent in user's language)
- During config conversation, always display current `COMPANY` and `TOPIC CORE` in every turn.
- If user asks what else can be adjusted, list remaining configurable fields in `config.txt`, explain each briefly, and offer adjustments in the same run.
- If user proactively asks to change behavior, first check whether it can be achieved by editing `config.txt`; prefer config overwrite over ad-hoc workflow changes.
- Always show current `COMPANY` tickers before asking any company changes.
- Ask for company changes in natural language (add/remove/replace).
- Parse user intent into:
  - tickers to remove
  - new items to add
- For each new item:
  - if it is already a valid US ticker, mark as confirmed
  - otherwise run:

```bash
"<root>/.venv/bin/python" "<root>/daily-report-orchestrator/scripts/resolve_us_ticker.py" --query "<item>"
```

  - if script returns `resolved_from_lookup`, report factual lookup result and ask user whether to add the returned ticker
  - do not proactively recommend any ticker code
  - if script returns `not_found`, report not found, do not modify `config.txt`, and ask user for more details
- After explicit user confirmation, overwrite `COMPANY` section in `config.txt` with the final ticker list.
- When overwriting `COMPANY`, each line must keep:
  - ticker
  - formal company name
  - common stock-market aliases
- Example format:
  - `NEE: NEE, NextEra Energy, NextEra Energy Inc, NextEra`
- Ask whether user wants to change `TOPIC CORE`.
- After `TOPIC CORE` is confirmed, always ask whether user has specific directions of interest for this topic.
- If user provides no specific direction, automatically generate related topic terms from `TOPIC CORE`.
- If user provides specific direction(s), generate `TOPIC` terms primarily according to those user directions.
- As soon as direction input is available (or explicitly absent), immediately write the generated `TOPIC` terms to `config.txt` in the same turn.
- Ask whether user has extra guidance for topic terms (focus, include/exclude terms, tone, horizon, metric preference).
- If user starts brainstorming from the core, switch to collaborative Q&A: ask clarifying questions and answer questions before finalizing topic directions.
- Use `TOPIC CORE` as the primary user-facing execution theme.
- Regenerate `TOPIC` from `TOPIC CORE` with user intent as the primary guidance (hard constraints only when explicitly requested).
- Overwrite old `TOPIC` in `config.txt` with the latest intent-aligned topic term set.
- If `PDF OUTPUT DIR` is missing/blank, also ask for `PDF OUTPUT DIR`.
- Remaining configurable fields to explain on request:
  - `DAY RANGE`: lookback window in days for step_1 news collection
  - `TOP_K`: max kept items per ticker in step_1 output
  - `SUMMARY LENGTH`: min-max words per field summary in step_2
  - `MODEL`: LLM model used in step_2 generation
  - `PDF OUTPUT DIR`: output folder for step_3 PDF
  - `PDF FONT SIZE`: base font size used by step_3 PDF rendering
- Any user-confirmed field update must overwrite the old config value.
- If user does not change settings, explicitly echo what will be used:
  - current `COMPANY` tickers
  - current `TOPIC CORE`
- Do not display alias lists or exploded keyword variants unless user asks.

## 5) Final Execution Gate
- Config edits can happen across multiple chat turns.
- Use user-friendly wording instead of internal terms like "gate".
- Before running any pipeline step, ask:
`Anything else you want to change?` (or equivalent in user's language)
- If user says no more changes, ask:
`No more changes noted. I will start execution now.`
- Only proceed when user gives explicit confirmation (for example: `yes`, `start`, `confirm`, `go ahead`).
- If user does not confirm or requests more edits, stay in config stage and do not execute step_1.
- If `AUTO=1`, skip this gate and proceed directly to execution.

## 6) Execute Step 1 (News Collector)
- Run:

```bash
"<root>/.venv/bin/python" "<root>/step_1/news-collector/scripts/collect_news.py"
```

- If command fails, stop immediately and return structured error:
  - `failed_step: step_1`
  - `command: ...`
  - `stderr_summary: ...`

## 7) Execute Step 2 (Stock Report Writer)
- Trigger the `step_2/stock-report-writer` workflow:
  - run `prepare_inputs.py`
  - generate per-field summaries with LLM using step_2 rules
  - run `write_output.py`
- If any sub-step fails, stop immediately and return:
  - `failed_step: step_2`
  - `command: ...`
  - `stderr_summary: ...`

## 8) Execute Step 3 (TXT To PDF Exporter)
- Run:

```bash
"<root>/.venv/bin/python" "<root>/step_3/txt-to-pdf-exporter/scripts/txt_to_pdf.py" --cwd "<root>"
```

- If command fails, stop immediately and return structured error:
  - `failed_step: step_3`
  - `command: ...`
  - `stderr_summary: ...`

## 9) End-Of-Run AUTO Prompt (Always)
- After every run (success or failure), always ask:
`Enable auto-run next time (AUTO=1)?`
- Overwrite `AUTO` in config based on user response:
  - yes -> `AUTO=1`
  - no -> `AUTO=0`

## 10) Return Final PDF Path Only
- On success, first display: `完成了`
- Then return one line containing the final PDF path.
- Do not include:
  - config-change recap
  - per-step status summary
  - fetch counts
  - JSON/TXT paths
- No hidden retries except one retry for dependency install during environment setup.

## Reference
- See `references/flow.md` for question templates and acceptance checklist.
