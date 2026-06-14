# Deferred Items — Phase 06

## test_pipeline_bedarf.py::test_one_client_per_run (deferred to Plan 06-05)
- **Found during:** Plan 06-04 execution (full-suite run).
- **Status:** FAILING (`assert 0 == 1`) — pipeline.run does not yet call `PageSpeedClient.from_config`.
- **Why out of scope:** This test asserts pipeline-side wiring (exactly one `from_config`
  per run). Plan 06-04 owns ONLY `lead_analyzer/clients/` and is explicitly forbidden from
  modifying `pipeline.py`. The wiring is Plan 06-05's responsibility ("client not yet wired — Plan 05").
- **Action:** None taken. Will go GREEN once Plan 06-05 wires the client into the pipeline.

## test_performance.py (owned by Plan 06-03, concurrent wave)
- ImportError at collection (`performance` not yet in `lead_analyzer.analyzers`) when run
  before 06-03 lands its module. Out of scope for 06-04; ignored via `--ignore` during 06-04 runs.
