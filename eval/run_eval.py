"""Run the eval set across configurations and write measured results.

Examples:
    python eval/run_eval.py --dry-run
    python eval/run_eval.py --configs multi_agent baseline --bugs cart_discount
    python eval/run_eval.py                      # all configs x all bugs, once
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swe_agent.config import load_settings  # noqa: E402
from swe_agent.evaluation import (  # noqa: E402
    CONFIGS,
    load_bugs,
    make_record,
    run_one,
    summarize,
    summary_markdown,
)
from swe_agent.pipeline import make_runner  # noqa: E402


def machine_info() -> str:
    try:
        model = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
        mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                 text=True).stdout)  # fmt: skip
        return f"{model or platform.processor()}, {mem // 2**30} GB RAM, {platform.system()}"
    except (OSError, ValueError):
        return f"{platform.machine()} {platform.system()}"


def git_commit() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)  # fmt: skip
    return out.stdout.strip() or "unknown"


def main(argv: list[str] | None = None, llm_factory=None, runner=None, embedder=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--configs", nargs="+", choices=list(CONFIGS), default=list(CONFIGS))
    p.add_argument("--bugs", nargs="+", help="bug ids (default: all)")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--sandbox", choices=["docker", "local"], default="docker")
    p.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    p.add_argument("--no-db", action="store_true", help="do not record runs in Postgres")
    p.add_argument("--dry-run", action="store_true", help="show the plan; make no LLM calls")
    args = p.parse_args(argv)

    settings = load_settings()
    bugs = load_bugs(ids=args.bugs)
    total = len(bugs) * len(args.configs) * args.repeats
    print(f"{len(bugs)} bugs x {len(args.configs)} configs x {args.repeats} repeat(s) "
          f"= {total} runs | model {settings.model}")  # fmt: skip
    if args.dry_run:
        for config in args.configs:
            print(f"  {config}: {CONFIGS[config] or 'full multi-agent system'}")
        return 0

    if llm_factory is None:
        if not settings.has_llm_key:
            print("error: ANTHROPIC_API_KEY is not set (see .env.example)", file=sys.stderr)
            return 2
        from swe_agent.llm import AnthropicLLM

        def llm_factory(bug, config):
            return AnthropicLLM(settings)

    if embedder is None and any(CONFIGS[c].get("use_embeddings", True) for c in args.configs):
        from swe_agent.retrieval import default_embedder

        embedder = default_embedder()
    runner = runner or make_runner(settings, args.sandbox)
    db_url = None if args.no_db else settings.database_url

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = args.out / stamp
    work = ROOT / ".workspaces" / f"eval-{stamp}"
    records = []
    n = 0
    for repeat in range(args.repeats):
        for bug in bugs:
            for config in args.configs:
                n += 1
                result = graded = error = None
                try:
                    result, graded = run_one(
                        bug, config, settings=settings, llm=llm_factory(bug, config),
                        runner=runner, embedder=embedder, workspace_root=work,
                    )  # fmt: skip
                except Exception as exc:  # keep going; the failure is recorded
                    error = f"{type(exc).__name__}: {exc}"
                rec = make_record(bug.id, config, repeat, result, graded, error)
                records.append(rec)
                mark = "RESOLVED" if rec["resolved"] else ("ERROR" if error else "failed")
                print(f"[{n}/{total}] {config:<17} {bug.id:<26} {mark:<8} "
                      f"attempts={rec['attempts']} {rec['duration_s'] or 0:.1f}s"
                      + (f"  {error}" if error else ""))  # fmt: skip
                if db_url and result is not None:
                    try:
                        from swe_agent.db import init_db, record_run

                        init_db(db_url)
                        record_run(
                            db_url, result, repo_id=f"eval:{bug.id}", options=CONFIGS[config]
                        )
                    except Exception as exc:
                        print(f"  warning: not recorded in Postgres: {exc}", file=sys.stderr)

    meta = {
        "date": time.strftime("%Y-%m-%d %H:%M %Z"),
        "git_commit": git_commit(),
        "model": settings.model,
        "effort": settings.effort,
        "sandbox": args.sandbox,
        "machine": machine_info(),
        "n_bugs": len(bugs),
        "repeats": args.repeats,
        "configs": args.configs,
    }
    summary = summarize(records, settings.model)
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
