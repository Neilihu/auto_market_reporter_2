# Output Format And Checks

Execution contract:
- Script A (`scripts/prepare_inputs.py`) produces normalized run payload JSON.
- LLM generates per-field summaries and creates sections payload JSON.
- Script B (`scripts/write_output.py`) writes final TXT.

Final TXT structure:

```text
=== AMD ===
Summary: <configured English word range, unless no context>

=== AMZN ===
Summary: <configured English word range, unless no context>
```

Rules:
- Starting from `$PWD`, walk up parent directories to find the first `config.txt`; use that directory as `<root>`.
- If `config.txt` is not found during upward search, stop and report:
  `config.txt not found while walking up from current directory`.
- Read `MODEL` from `<root>/config.txt`; use `gpt-5-mini` when missing/blank.
- Create one section for every key in `results`.
- Keep field order identical to the JSON key order.
- Do not add a global intro paragraph at the top of the TXT file.
- Write in English only.
- Read `SUMMARY LENGTH` from `<root>/config.txt` each run and enforce that range for each non-empty field summary.
- Parse `SUMMARY LENGTH` as `<min>-<max>` words, for example `200-300`.
- If `SUMMARY LENGTH` is missing or invalid, use default `200-300`.
- If no usable context exists for a field, output exactly:
  `Summary: No context available.`

Acceptance checklist:
- Latest `*.json` from `<root>/collect_info` is used.
- Output file is `<root>/collect_info/<same_name>.txt`.
- Existing TXT with same name is overwritten.
- Every field appears once with `=== <FIELD> ===`.
- Any script failure stops execution with its error output.
