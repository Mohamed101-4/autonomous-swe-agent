"""Run the agents on the compatible SWE-bench Verified subset (see swe_agent/swebench.py).

Examples:
    python eval/run_swebench.py --dry-run
    python eval/run_swebench.py --instances pytest-dev__pytest-10051
    python eval/run_swebench.py --configs multi_agent baseline
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_eval import git_commit, machine_info  # noqa: E402

from swe_agent.baseline import run_baseline  # noqa: E402
from swe_agent.config import load_settings  # noqa: E402
from swe_agent.evaluation import CONFIGS, make_record, summarize, summary_markdown  # noqa: E402
from swe_agent.pipeline import RunOptions, run_agent  # noqa: E402
from swe_agent.swebench import (  # noqa: E402
    grade,
    load_instances,
    prepare_repo,
    runner_for,
    selectable_ids,
)

COMPATIBLE = ROOT / "eval" / "swebench" / "compatible.json"


def run_instance(inst, config, *, settings, llm, embedder, work):
    repo = prepare_repo(inst, work / "repos" / inst.instance_id)  # base_commit + test_patch
    runner = runner_for(inst)
    targets = selectable_ids(inst.fail_to_pass, repo)
    spec = dict(CONFIGS[config])
    if spec.pop("baseline", False):
        result = run_baseline(
            repo, inst.problem_statement, settings=settings, llm=llm, runner=runner,
            workspace_root=work / "runs", test_targets=targets,
        )  # fmt: skip
    else:
        options = RunOptions(**spec)
        result = run_agent(
            repo, inst.problem_statement, settings=settings, llm=llm, runner=runner,
            embedder=embedder if options.use_embeddings else None, options=options,
            workspace_root=work / "runs", test_targets=targets,
        )  # fmt: skip
    result.mode = config
    return result, grade(Path(result.workspace), inst, runner)


def main(argv: list[str] | None = None, llm_factory=None, embedder=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--configs", nargs="+", choices=list(CONFIGS),
                   default=["multi_agent", "baseline"])  # fmt: skip
    p.add_argument("--instances", nargs="+", help="instance ids (default: all compatible)")
    p.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    compat = json.loads(COMPATIBLE.read_text())
    ids = args.instances or compat["compatible"]
    not_ok = sorted(set(ids) - set(compat["compatible"]))
    if not_ok:
        print(f"error: not in the compatible subset: {not_ok}", file=sys.stderr)
        return 2
    settings = load_settings()
    total = len(ids) * len(args.configs)
    print(f"{len(ids)} SWE-bench Verified instances x {len(args.configs)} configs = {total} runs"
          f" | model {settings.model}")  # fmt: skip
    if args.dry_run:
        print("  " + "\n  ".join(ids))
        return 0
    if llm_factory is None:
        if not settings.has_llm_key:
            print("error: ANTHROPIC_API_KEY is not set (see .env.example)", file=sys.stderr)
            return 2
        from swe_agent.llm import AnthropicLLM

        def llm_factory(inst, config):
            return AnthropicLLM(settings)

    if embedder is None and any(CONFIGS[c].get("use_embeddings", True) for c in args.configs):
        from swe_agent.retrieval import default_embedder

        embedder = default_embedder()

    instances = load_instances(ids)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    work = ROOT / ".workspaces" / f"swebench-{stamp}"
    records, n = [], 0
    for inst in instances:
        for config in args.configs:
            n += 1
            result = graded = error = None
            try:
                result, graded = run_instance(
                    inst, config, settings=settings, llm=llm_factory(inst, config),
                    embedder=embedder, work=work,
                )  # fmt: skip
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            rec = make_record(inst.instance_id, config, 0, result, graded, error)
            records.append(rec)
            mark = "RESOLVED" if rec["resolved"] else ("ERROR" if error else "failed")
            print(f"[{n}/{total}] {config:<17} {inst.instance_id:<26} {mark:<8} "
                  f"attempts={rec['attempts']} {rec['duration_s'] or 0:.1f}s"
                  + (f"  {error}" if error else ""))  # fmt: skip

    meta = {
        "dataset": "SWE-bench Verified (compatible pytest-dev/pytest subset)",
        "date": time.strftime("%Y-%m-%d %H:%M %Z"),
        "git_commit": git_commit(),
        "model": settings.model,
        "effort": settings.effort,
        "sandbox": "docker (per-environment ARM image, --network none)",
        "machine": machine_info(),
        "n_bugs": len(instances),
        "repeats": 1,
        "configs": args.configs,
        "instances": ids,
    }
    summary = summarize(records, settings.model)
    out_dir = args.out / f"swebench-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "records": records}, indent=2) + "\n"
    )
    (out_dir / "summary.md").write_text(summary_markdown(summary, meta))
    print("\n" + summary_markdown(summary, meta))
    print(f"Saved to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
