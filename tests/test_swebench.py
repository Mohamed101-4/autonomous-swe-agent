"""SWE-bench adapter tests.

Pure tests always run. The end-to-end harness test needs Docker, the cloned
repo cache and the Hugging Face dataset, so it is skipped when those are missing.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

from swe_agent.swebench import CACHE, Instance, is_supported, selectable_ids
from swe_agent.test_runner import docker_available

ROOT = Path(__file__).resolve().parents[1]


def test_selectable_ids(tmp_path):
    (tmp_path / "testing").mkdir()
    (tmp_path / "testing" / "test_a.py").write_text("")
    ids = [
        "testing/test_a.py::test_ok",
        "testing/test_a.py::test_p[True,",  # truncated at a space in the dataset
        "testing/test_a.py::test_p[False,",
        "testing/test_a.py::test_q[x]",
        "test_inner.py::test_hello",  # inner pytester test, not a repo file
    ]
    assert selectable_ids(ids, tmp_path) == [
        "testing/test_a.py::test_ok",
        "testing/test_a.py::test_p",
        "testing/test_a.py::test_q[x]",
    ]


def test_instance_from_row_and_support():
    row = {
        "instance_id": "pytest-dev__pytest-1", "repo": "pytest-dev/pytest", "version": "7.2",
        "base_commit": "abc", "problem_statement": "bug", "patch": "", "test_patch": "",
        "FAIL_TO_PASS": '["a::b"]', "PASS_TO_PASS": "[]",
    }  # fmt: skip
    inst = Instance.from_row(row)
    assert inst.fail_to_pass == ["a::b"] and inst.env == "pytest7"
    assert is_supported(row)
    assert not is_supported(row | {"repo": "django/django"})


def test_compatible_list_is_recorded():
    data = json.loads((ROOT / "eval" / "swebench" / "compatible.json").read_text())
    assert data["dataset"] == "princeton-nlp/SWE-bench_Verified"
    assert len(data["compatible"]) == sum(r["compatible"] for r in data["results"].values())


def diff_to_edits(diff: str) -> list[dict]:
    """Turn a unified diff into search/replace edits (used by the oracle LLM)."""
    edits, path = [], None
    for block in re.split(r"(?m)^(?=diff --git )", diff):
        m = re.search(r"(?m)^\+\+\+ b/(\S+)", block)
        if not m:
            continue
        path = m.group(1)
        for hunk in re.split(r"(?m)^@@[^\n]*\n", block)[1:]:
            old, new = [], []
            for line in hunk.splitlines():
                tag, text = line[:1], line[1:]
                if tag in (" ", "-"):
                    old.append(text)
                if tag in (" ", "+"):
                    new.append(text)
            edits.append({"path": path, "search": "\n".join(old), "replace": "\n".join(new)})
    return edits


HAVE_DATA = (CACHE / "pytest-dev__pytest").exists() and importlib.util.find_spec("datasets")


@pytest.mark.skipif(not (docker_available() and HAVE_DATA), reason="needs Docker + SWE-bench data")
def test_harness_end_to_end_with_oracle(tmp_path):
    spec = importlib.util.spec_from_file_location("run_swebench", ROOT / "eval/run_swebench.py")
    import sys

    sys.path.insert(0, str(ROOT / "eval"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from swe_agent.swebench import load_instances

    inst = load_instances(["pytest-dev__pytest-10051"])[0]

    class Oracle:
        def complete(self, system, prompt):
            if "planning agent" in system:
                return json.dumps({"summary": "x"})
            return json.dumps({"edits": diff_to_edits(inst.patch)})

    class Useless:
        def complete(self, system, prompt):
            return json.dumps({"summary": "x"} if "planning agent" in system else {"edits": []})

    for llm_cls, expect in ((Oracle, 1), (Useless, 0)):
        out = tmp_path / llm_cls.__name__
        code = mod.main(
            ["--instances", inst.instance_id, "--configs", "multi_agent", "baseline",
             "--out", str(out)],
            llm_factory=lambda i, c, cls=llm_cls: cls(), embedder=None,
        )  # fmt: skip
        assert code == 0
        (run_dir,) = out.iterdir()
        summary = json.loads((run_dir / "results.json").read_text())["summary"]
        assert summary["multi_agent"]["resolved"] == expect
        assert summary["baseline"]["resolved"] == expect
