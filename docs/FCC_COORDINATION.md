# FCC / Codex coordination

## Active ownership

- Codex: `RG-01` — complete; production `SECRET_KEY` enforcement and focused
  tests pass.
- Codex: `RG-02` — implementation complete; retryable, atomic, idempotent and
  concurrency-safe scheduled reconciliation. PostgreSQL parallel-worker
  rehearsal remains an environment-level acceptance check.
- Codex: `BE-02` — complete; requesting users receive member-import
  success/failure summaries without exposing internal failure details.
- Codex: local Super Admin browser setup — complete; one-time `/setup/admin`
  flow creates the first account, signs it in, and is unavailable outside
  `DEBUG` mode.
- FCC: Please choose any task except `RG-01`, record it here before editing, and
  avoid modifying the files listed below until Codex marks the task complete.

## Codex-owned files

- `chapelflow-backend/config/settings/base.py`
- `chapelflow-backend/config/settings/production.py`
- `chapelflow-backend/tests/common/test_production_settings.py`
- `chapelflow-backend/apps/finance/tasks.py`
- `chapelflow-backend/tests/finance/test_reconciliation_tasks.py`
- `chapelflow-backend/apps/members/tasks.py`
- Member-import task tests selected after inspection.

## Handoff

- Status: `RG-01` and `BE-02` complete; `RG-02` code complete with its
  production-PostgreSQL parallel-worker rehearsal still open
- Updated: 2026-09-18
