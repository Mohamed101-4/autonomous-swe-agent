"""Find which supported SWE-bench Verified instances work in our ARM sandbox.

For each candidate: FAIL_TO_PASS must fail at base_commit (+test_patch), and
FAIL_TO_PASS + PASS_TO_PASS must all pass after applying the gold patch.
Writes eval/swebench/compatible.json. No LLM calls.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swe_agent.swebench import DATASET, ENVS, SUPPORTED, load_instances, validate  # noqa: E402


def main() -> int:
    instances = load_instances()
    work = ROOT / ".workspaces" / "swebench-validate"
    results = {}
    for i, inst in enumerate(instances, 1):
        try:
            res = validate(inst, work)
        except Exception as exc:
            res = {"compatible": False, "reason": f"{type(exc).__name__}: {exc}"}
        results[inst.instance_id] = {"version": inst.version, "env": inst.env, **res}
        print(f"[{i}/{len(instances)}] {inst.instance_id} ({inst.version}): {res['reason']}")
    out = {
        "dataset": DATASET,
        "date": time.strftime("%Y-%m-%d"),
        "machine": f"{platform.machine()} {platform.system()}",
        "supported_repos_versions": SUPPORTED,
        "environments": ENVS,
        "candidates": len(instances),
        "compatible": sorted(k for k, v in results.items() if v["compatible"]),
        "results": results,
    }
    path = ROOT / "eval" / "swebench" / "compatible.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\n{len(out['compatible'])}/{len(instances)} compatible -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
