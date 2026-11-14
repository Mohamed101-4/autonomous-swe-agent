"""Minimal SWE-bench Verified adapter.

Uses the official dataset (princeton-nlp/SWE-bench_Verified on Hugging Face) and
its fields: instance_id, repo, base_commit, problem_statement, patch (gold fix),
test_patch, FAIL_TO_PASS, PASS_TO_PASS, version.

It does NOT use the official x86 evaluation images (large and slow on an 8 GB
ARM Mac). Instead it builds small ARM images from hand-written environment specs
below and supports only `pytest-dev/pytest` instances whose versions are listed.
An instance counts as compatible only if, in this environment, its FAIL_TO_PASS
tests fail before the gold patch and FAIL_TO_PASS + PASS_TO_PASS all pass after it.

Setting (differs from the official leaderboard, so numbers are not comparable):
- The agent's repo has the test_patch applied (the new failing tests are visible).
- The agent's verifier runs FAIL_TO_PASS only.
- Grading runs FAIL_TO_PASS + PASS_TO_PASS on the patched repo (official criteria).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from swe_agent.test_runner import DockerPytestRunner, TestRun

ROOT = Path(__file__).resolve().parents[1]
DATASET = "princeton-nlp/SWE-bench_Verified"
CACHE = ROOT / ".cache" / "swebench"
DOCKERFILE = ROOT / "docker" / "swebench.Dockerfile"

_PYTEST_TESTING = "argcomplete==2.1.2 hypothesis==6.56.4 mock==5.0.1 nose==1.3.7 "
_PYTEST_TESTING += "pygments==2.14.0 requests==2.28.2 xmlschema==2.5.1"

# Hand-written environments, based on each version's setup.cfg (install + testing deps).
ENVS = {
    "pytest7": {
        "python": "3.9",
        "packages": "attrs==22.2.0 iniconfig==2.0.0 packaging==23.0 pluggy==1.0.0 "
        "exceptiongroup==1.1.0 tomli==2.0.1 py==1.11.0 " + _PYTEST_TESTING,
    },
    "pytest5_6": {
        "python": "3.9",
        "packages": "attrs==21.4.0 iniconfig==1.1.1 packaging==21.3 pluggy==0.13.1 "
        "py==1.11.0 toml==0.10.2 more-itertools==8.14.0 wcwidth==0.2.6 " + _PYTEST_TESTING,
    },
}
SUPPORTED = {
    "pytest-dev/pytest": {
        "7.2": "pytest7",
        "6.3": "pytest5_6",
        "6.2": "pytest5_6",
        "6.0": "pytest5_6",
        "5.4": "pytest5_6",
    }
}


@dataclass(frozen=True)
class Instance:
    instance_id: str
    repo: str
    version: str
    base_commit: str
    problem_statement: str
    patch: str
    test_patch: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]

    @property
    def env(self) -> str:
        return SUPPORTED[self.repo][self.version]

    @classmethod
    def from_row(cls, row: dict) -> Instance:
        def as_list(v):
            return json.loads(v) if isinstance(v, str) else list(v)

        return cls(
            instance_id=row["instance_id"],
            repo=row["repo"],
            version=row["version"],
            base_commit=row["base_commit"],
            problem_statement=row["problem_statement"],
            patch=row["patch"],
            test_patch=row["test_patch"],
            fail_to_pass=as_list(row["FAIL_TO_PASS"]),
            pass_to_pass=as_list(row["PASS_TO_PASS"]),
        )


def is_supported(row: dict) -> bool:
    return row["version"] in SUPPORTED.get(row["repo"], {})


def load_instances(ids: list[str] | None = None) -> list[Instance]:
    """Load supported instances from the official dataset (downloads it once)."""
    from datasets import load_dataset

    rows = load_dataset(DATASET, split="test")
    out = [Instance.from_row(r) for r in rows if is_supported(r)]
    if ids:
        out = [i for i in out if i.instance_id in ids]
        missing = set(ids) - {i.instance_id for i in out}
        if missing:
            raise ValueError(f"unknown or unsupported instance ids: {sorted(missing)}")
    return out


def repo_cache(repo: str) -> Path:
    """A local clone of the upstream repo (cloned once)."""
    path = CACHE / repo.replace("/", "__")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", f"https://github.com/{repo}", str(path)], check=True)
    return path


def apply_diff(repo_dir: Path, diff: str) -> None:
    # Stop git from finding an enclosing repo (e.g. this project); otherwise
    # `git apply` resolves paths against that repo and silently skips files.
    env = os.environ | {"GIT_CEILING_DIRECTORIES": str(Path(repo_dir).resolve().parent)}
    proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        input=diff, text=True, cwd=repo_dir, capture_output=True, env=env,
    )  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"git apply failed: {proc.stderr.strip()}")


def prepare_repo(inst: Instance, dest: Path, with_test_patch: bool = True) -> Path:
    """Export the repo at base_commit (no .git), add the version file, apply test_patch."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tempfile.TemporaryFile() as tar_file:
        subprocess.run(
            ["git", "archive", inst.base_commit], cwd=repo_cache(inst.repo),
            stdout=tar_file, check=True,
        )  # fmt: skip
        tar_file.seek(0)
        with tarfile.open(fileobj=tar_file) as tar:
            tar.extractall(dest, filter="data")
    # setuptools-scm normally generates this file at install time.
    (dest / "src" / "_pytest" / "_version.py").write_text(
        f'version = __version__ = "{inst.version}.0"\n'
        f"version_tuple = {tuple(int(x) for x in inst.version.split('.')) + (0,)}\n"
    )
    if with_test_patch:
        apply_diff(dest, inst.test_patch)
    return dest


def image_tag(env_name: str) -> str:
    """Tag includes a hash of the spec, so changing the spec builds a new image."""
    spec = json.dumps(ENVS[env_name], sort_keys=True) + DOCKERFILE.read_text()
    return f"swe-agent-swebench:{env_name}-{hashlib.sha256(spec.encode()).hexdigest()[:8]}"


def runner_for(inst: Instance, timeout_s: int = 300) -> DockerPytestRunner:
    env = ENVS[inst.env]
    return DockerPytestRunner(
        image=image_tag(inst.env),
        timeout_s=timeout_s,
        memory="1g",
        cpus=2.0,
        env={"PYTHONPATH": "/work/src"},
        tmp_size="256m",
        dockerfile=DOCKERFILE,
        build_args={"PYTHON": env["python"], "PACKAGES": env["packages"]},
    )


def selectable_ids(test_ids: list[str], repo_dir: Path) -> list[str]:
    """Turn dataset test ids into pytest selectors.

    SWE-bench ids containing spaces are cut off at the first space (e.g.
    "test_x[True,"), so those select the whole parametrized test instead. Ids
    whose file does not exist in the repo (e.g. inner pytester tests) are dropped.
    """
    out: list[str] = []
    for tid in test_ids:
        if "[" in tid and not tid.endswith("]"):
            tid = tid.split("[", 1)[0]
        if not (Path(repo_dir) / tid.split("::", 1)[0]).is_file():
            continue
        if tid not in out:
            out.append(tid)
    return out


def grade(workspace: Path, inst: Instance, runner: DockerPytestRunner) -> TestRun:
    """Official success criteria: all FAIL_TO_PASS and PASS_TO_PASS tests pass."""
    return runner.run(workspace, selectable_ids(inst.fail_to_pass + inst.pass_to_pass, workspace))


def validate(inst: Instance, work: Path) -> dict:
    """Check the instance works in our environment (bug reproduces, gold patch fixes it)."""
    runner = runner_for(inst)
    repo = prepare_repo(inst, work / inst.instance_id)
    before = runner.run(repo, selectable_ids(inst.fail_to_pass, repo))
    if before.ok:
        return {"compatible": False, "reason": "FAIL_TO_PASS already passes before the fix"}
    apply_diff(repo, inst.patch)
    after = grade(repo, inst, runner)
    if not after.ok:
        failing = after.failing_tests[:5] or [after.output.strip().splitlines()[-1:]]
        return {"compatible": False, "reason": f"gold patch does not pass here: {failing}"}
    return {"compatible": True, "reason": "ok", "grade_seconds": after.duration_s}
