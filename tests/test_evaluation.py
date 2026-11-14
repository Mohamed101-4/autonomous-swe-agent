import importlib.util
import json
from pathlib import Path

from swe_agent.evaluation import load_bugs, summarize
from swe_agent.test_runner import LocalPytestRunner

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)

BUGS = {b.issue: b for b in load_bugs()}


class OracleLLM:
    """Plans trivially and answers with each bug's reference fix (tests the harness only)."""

    def complete(self, system: str, prompt: str) -> str:
        if "planning agent" in system:
            return json.dumps({"summary": "x", "search_terms": [], "steps": []})
        bug = next(b for issue, b in BUGS.items() if issue in prompt)
        return json.dumps({"explanation": "reference fix", "edits": bug.reference_edits})


class NoOpLLM:
    def complete(self, system: str, prompt: str) -> str:
        if "planning agent" in system:
            return json.dumps({"summary": "x"})
        return json.dumps({"edits": []})


def run(tmp_path, llm_cls, configs):
    code = run_eval.main(
        ["--configs", *configs, "--bugs", "cart_discount", "shared_tags",
         "--sandbox", "local", "--no-db", "--out", str(tmp_path)],
        llm_factory=lambda bug, config: llm_cls(), runner=LocalPytestRunner(), embedder=None,
    )  # fmt: skip
    assert code == 0
    (out_dir,) = tmp_path.iterdir()
    return json.loads((out_dir / "results.json").read_text()), (out_dir / "summary.md").read_text()


def test_eval_harness_with_oracle(tmp_path):
    data, md = run(tmp_path, OracleLLM, ["multi_agent", "baseline", "no_retries"])
    assert len(data["records"]) == 6
    for config in ("multi_agent", "baseline", "no_retries"):
        s = data["summary"][config]
        assert (s["resolved"], s["runs"], s["validation_accuracy"]) == (2, 2, 1.0)
    assert data["meta"]["n_bugs"] == 2 and "GB RAM" in data["meta"]["machine"]
    assert "| multi_agent | 2/2 | 100% |" in md


def test_eval_harness_with_useless_llm(tmp_path):
    data, _ = run(tmp_path, NoOpLLM, ["multi_agent"])
    s = data["summary"]["multi_agent"]
    assert s["resolved"] == 0 and s["mean_attempts"] == 3  # tried, retried, gave up
    assert s["validation_accuracy"] == 1.0 and s["verifier_pass_precision"] is None


def test_summary_validation_metrics():
    base = {"config": "c", "attempts": 1, "duration_s": 1.0, "llm_calls": 1, "error": None,
            "input_tokens": 1_000_000, "output_tokens": 100_000}  # fmt: skip
    records = [
        base | {"agent_verdict": "resolved", "resolved": True},
        base | {"agent_verdict": "resolved", "resolved": False},  # verifier fooled
        base | {"agent_verdict": "failed", "resolved": False},
        base | {"agent_verdict": "failed", "resolved": False},
    ]
    s = summarize(records, "claude-opus-5-5")["c"]
    assert s["resolve_rate"] == 0.25
    assert s["validation_accuracy"] == 0.75
    assert s["verifier_pass_precision"] == 0.5
    assert s["cost_usd"] == 4 * 4.0 + 4 * 0.1 * 20.0
