---
name: skill-stock-daily-report
description: Alias entry skill for this project. Use when users mention skill_stock_daily_report or ask to run the full daily report pipeline. This skill delegates directly to daily-report-orchestrator unless users explicitly request a single step skill.
---

# skill_stock_daily_report

Use this as the default entrypoint for end-to-end execution.

## Routing Rule
- If user asks for full run / daily pipeline / skill_stock_daily_report:
  - immediately use `daily-report-orchestrator`.
- If user explicitly asks for a single stage only, route to:
  - `step_1/news-collector` for data collection only
  - `step_2/stock-report-writer` for JSON-to-TXT summary only
  - `step_3/txt-to-pdf-exporter` for TXT-to-PDF only

## Delegation Contract
- Do not duplicate orchestration logic here.
- Keep `daily-report-orchestrator` as the single source of truth for:
  - root/config resolution
  - environment checks
  - config confirmation dialogue
  - step_1 -> step_2 -> step_3 execution
  - final artifact reporting
