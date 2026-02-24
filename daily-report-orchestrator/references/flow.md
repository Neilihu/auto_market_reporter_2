# Daily Report Orchestrator Reference

## Input/Output Contract
- Input root: resolve by walking up from current directory to nearest `config.txt`.
- Runtime Python: `<root>/.venv/bin/python`.
- AUTO mode:
  - read `AUTO` from config before config interaction
  - `AUTO=1` skip config Q&A and run pipeline directly
  - `AUTO=0` run interactive config flow
  - missing/invalid defaults to `0`
- Pipeline order: `step_1 -> step_2 -> step_3`.
- Outputs:
  - `collect_info/<timestamp>.json`
  - `collect_info/<json_stem>.txt`
  - `<PDF OUTPUT DIR>/<json_stem>.pdf`

## Operating Principle
- Conservative by default, not aggressive.
- Ask for confirmation before high-impact changes.
- Apply minimal required config overwrites to satisfy intent.

## Config Confirmation Rules
- In interactive mode (`AUTO=0`), config edits are iterative across turns and pipeline start requires explicit final confirmation.
- In every config turn, print `Report related content` before company/topic display.
- `Report related content` should be shown in the user's language.
- In every config turn, always show current `COMPANY` and `TOPIC CORE`.
- If user asks for more adjustable parameters, explain remaining config fields and allow edits in the same interaction.
- If user asks to change outcome/behavior, first evaluate whether config changes can achieve it; if yes, update config first.
- Must show current `COMPANY` tickers before asking company edits.
- Must ask before execution:
  - company change intent (add/remove/replace)
  - `TOPIC CORE`
- Must ask and apply:
  - after `TOPIC CORE` confirmation, ask whether user has specific directions of interest
  - if no specific direction is provided, automatically generate related topic terms from `TOPIC CORE`
  - if specific direction is provided, prioritize that direction in generated `TOPIC`
  - once direction input is available (or explicitly absent), write generated `TOPIC` to config in the same turn
  - user intent/guidance for topic directions (angle / examples / must include / must exclude / time horizon / preferred metrics)
- Must read and use:
  - `TOPIC CORE` as final execution theme shown to user
- Must overwrite after confirmation:
  - `COMPANY`
  - `TOPIC CORE`
  - generated `TOPIC`
  - any other user-confirmed configurable field
- `COMPANY` overwrite format requirement:
  - each ticker line must include ticker + formal company name + common stock-market aliases
  - example: `XOM: XOM, Exxon Mobil, ExxonMobil, Exxon Mobil Corporation`
- Ask `PDF OUTPUT DIR` only when missing or empty.
- If user gives no changes, echo:
  - used company tickers
  - used TOPIC CORE
- Do not echo alias strings or full expanded keyword lists.
- For newly added company items:
  - validate US ticker directly when possible
  - otherwise lookup with `scripts/resolve_us_ticker.py`
  - do not proactively recommend ticker codes
  - if lookup not found, do not modify config and ask for more detail
  - script status meanings:
    - `resolved_exact`: input itself is a valid US-listed ticker
    - `resolved_from_lookup`: lookup found US-listed mappings; require explicit user confirmation before adding
    - `not_found`: no reliable mapping; keep config unchanged
- Additional configurable fields and purpose:
  - `DAY RANGE`: how many recent days step_1 scans
  - `TOP_K`: per-ticker cap in step_1 results
  - `SUMMARY LENGTH`: target min-max words per ticker summary
  - `MODEL`: generation model used by step_2
  - `AUTO`: auto-run switch (`0` interactive, `1` auto-run)
  - `PDF OUTPUT DIR`: destination folder for generated PDF
  - `PDF FONT SIZE`: PDF typography base size in step_3

## Prompt Templates
- `Report related content`
- `COMPANY: <tickers>`
- `TOPIC CORE: <core>`
- `Anything else you want to change?`
- `No more changes noted. I will start execution now.`
- `Enable auto-run next time (AUTO=1)?`
- `Current COMPANY tickers are: <tickers>. Tell me what to remove or add.`
- `For this TOPIC CORE, what directions are you interested in? We can discuss angles first, then finalize keywords.`
- `Do you have specific directions for this topic? If not, I will generate related keywords automatically from TOPIC CORE.`
- `Which directions matter most, and are there terms you want included or avoided?`
- `Using COMPANY: <tickers>. TOPIC core: <core>.`
- `Lookup result found: <symbol> / <name>. Do you want to add it to COMPANY?`
- `No reliable US ticker mapping found, so config was not changed. Please provide more details (full company name/exchange).`
- `PDF OUTPUT DIR is empty. Please confirm the PDF output directory.`
- `You can also adjust: DAY RANGE, TOP_K, SUMMARY LENGTH, MODEL, PDF OUTPUT DIR, and PDF FONT SIZE. Which one do you want to change?`
- `This request can be achieved through config updates first, so I will apply config overwrite before execution.`
- `Configuration updates are ready. Start pipeline now?`

## Error Response Shape
Return concise structured text with:
- `failed_step`
- `command`
- `stderr_summary`

Example:

```text
failed_step: step_3
command: <root>/.venv/bin/python <root>/step_3/txt-to-pdf-exporter/scripts/txt_to_pdf.py --cwd <root>
stderr_summary: No TXT files found in collect_info
```

## Acceptance Checklist
- Root resolution works from root, `step_2`, and `step_3/txt-to-pdf-exporter`.
- Existing `.venv` is reused without recreation.
- Missing `.venv` triggers creation + requirements install.
- `AUTO` missing/invalid falls back to `0`.
- `AUTO=1` skips config Q&A and starts execution directly.
- `AUTO=0` follows full config Q&A flow.
- Current `COMPANY` is shown before company questions.
- `COMPANY` updates use confirmed additions/removals only.
- New non-ticker inputs are looked up and require explicit confirmation before adding.
- Lookup failure does not modify `COMPANY`.
- Success response first shows `完成了`, then returns the final PDF path.
- Generated `TOPIC` follows latest user intent; hard constraints apply only if user explicitly sets them.
- When user asks for further tunables, remaining config fields are explained and can be overwritten in the same run.
- User-initiated behavior changes are mapped to config updates first when feasible.
- `PDF OUTPUT DIR` is confirmed when missing/blank.
- In interactive mode (`AUTO=0`), without final execution confirmation step_1 is not triggered.
- Config-phase messages always include `COMPANY` and `TOPIC CORE`.
- `Report related content` and `Anything else you want to change?` follow the user's language.
- After TOPIC CORE confirmation, direction question is always asked before generating TOPIC.
- On success, first show `完成了`, then return the final PDF path.
- After every run (success or failure), user is asked whether to enable auto-run, and `AUTO` is overwritten accordingly.
- Steps run in strict order and stop on first failure.
