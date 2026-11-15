# Resume claims vs. evidence

The resume text below was written as a **target** before the project was built.
This table maps each claim to the code, the tests, and what has actually been
measured. Status as of 2026-11-14 (Apple M3 MacBook Pro, 8 GB RAM).

Legend: **Built** = implemented and tested. **Not measured** = needs real-model
runs (needs an Anthropic API key). **Unsupported** = no evidence; do not use as written.

| Resume claim | Code | Tests | Measured result | Status |
|---|---|---|---|---|
| Tech: Python, LangGraph, PyTorch, Docker, PostgreSQL | `swe_agent/graph.py` (LangGraph), `swe_agent/retrieval.py` (sentence-transformers on PyTorch), `swe_agent/test_runner.py` + `docker/` (Docker), `swe_agent/db.py` + `docker-compose.yml` (PostgreSQL) | `test_pipeline.py`, `test_retrieval.py`, `test_sandbox.py`, `test_db.py` | All used and exercised by tests | Built |
| Hierarchical multi-agent system (planner, localizer, patcher, verifier) | `swe_agent/agents/`, `swe_agent/graph.py` | `test_agents.py`, `test_pipeline.py` (checks node order and retry loop) | Agents run in order planner → localizer → patcher → verifier → report (scripted LLM) | Built. Note: it's a fixed pipeline with a retry loop, not a deep hierarchy |
| AST analysis and RAG | `swe_agent/code_index.py`, `swe_agent/retrieval.py`, `swe_agent/agents/localizer.py` | `test_code_index.py`, `test_retrieval.py` | On the sample bug, the buggy `login` function ranks #1 with keyword, embedding and hybrid search | Built |
| Autonomously diagnoses and patches **100+** software defects | `eval/bugs/` (10 bugs), SWE-bench subset (11 instances) | `test_eval_bugs.py`, `test_swebench.py` | **No real-model runs.** At most 21 defects are available to attempt | **Unsupported**: replace with the measured number fixed, out of 21 |
| Sandboxed Docker pipeline | `swe_agent/test_runner.py` (`DockerPytestRunner`), `docker/sandbox.Dockerfile` | `test_sandbox.py` (non-root, no network, no host secrets, read-only, memory limit, timeout kill) | All sandbox checks pass | Built |
| Test-driven self-correction | `swe_agent/graph.py` (retry edge), `swe_agent/agents/verifier.py` (feedback), `patcher.py` (retry prompt) | `test_pipeline.py::test_retry_after_failed_patch`, `test_gives_up_after_max_retries` | Retry loop verified with a scripted LLM; real benefit not measured (`no_retries` ablation exists) | Built; benefit **not measured** |
| **85%** patch validation accuracy | `summarize()` in `swe_agent/evaluation.py` (verifier verdict vs. hidden-test grade) | `test_evaluation.py::test_summary_validation_metrics` | **Not measured** (only oracle harness checks, which are 100% by design) | **Not measured**: use the eval's `validation_accuracy` |
| **40%** faster debugging | CLI/eval record run time (`duration_s`) | — | **No comparison exists.** There is no human or prior-tool timing to compare against | **Unsupported**: drop it, or report measured mean time per bug vs. baseline |
| Evaluated on SWE-bench Verified | `swe_agent/swebench.py`, `eval/run_swebench.py`, `eval/swebench/compatible.json` | `test_swebench.py` (oracle end-to-end on `pytest-dev__pytest-10051`) | 11/12 pytest instances compatible; **no agent runs yet**. Setting not leaderboard-comparable | Adapter built; **not evaluated** |
| Ablations across retrieval strategy, planning depth and verifier ranking | `CONFIGS` in `swe_agent/evaluation.py`: `no_embeddings`, `reduced_planning`, `minimal_feedback` (+ `no_retries`) | `test_evaluation.py` | **Not run** with a real model | Built; **not measured**. "Verifier ranking" is implemented as verifier *feedback* (full vs. minimal); there's no candidate-patch ranking |
| **+12 points** resolve rate over a single-agent baseline | `swe_agent/baseline.py`, `eval/run_eval.py` | `test_baseline.py`, `test_evaluation.py` | **Not measured** | **Unsupported** until the eval runs; then report the measured difference (it may be smaller, zero or negative) |

## Honest version you can use today

> **Autonomous AI Software Engineering Agent** | Python, LangGraph, PyTorch, Docker, PostgreSQL
> - Built a four-agent bug-fixing pipeline (planner, localizer, patcher, verifier) in LangGraph, with Python AST indexing and hybrid BM25 + sentence-embedding retrieval to pick code context for an LLM patcher.
> - Ran patch verification in a locked-down Docker sandbox (no network, non-root, read-only, resource limits) with test-driven retries, and logged every run to PostgreSQL.
> - Built an evaluation harness with a 10-bug set graded by hidden tests, a single-agent baseline, three ablations, and a minimal SWE-bench Verified adapter (11 compatible instances on ARM).

## To turn "not measured" into numbers

1. Put `ANTHROPIC_API_KEY` in `.env`.
2. `uv run python eval/run_eval.py --bugs cart_discount` (pilot; check the cost in `summary.md`).
3. `uv run python eval/run_eval.py` and `uv run python eval/run_swebench.py`.
4. Copy the numbers from `eval/results/<timestamp>/summary.md` into this table and the README, with the date, model and machine.
