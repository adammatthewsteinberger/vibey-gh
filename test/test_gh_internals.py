# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""The paths the happy-path tests do not reach: refusals, re-runs, and drift.

Where the module shells out, these tests give it a real thing to shell out to — a fake
`gh` on PATH, a real bare repository over file:// — rather than a mocked `subprocess.run`.
A mock cannot tell you that the argument order is wrong.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from vibey_gh import fingerprints, install, merge_train, realign, versioning
from vibey_gh.config import GhConfig


def git(cwd: Path, *a: str) -> str:
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)
    return r.stdout


def init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main", ".")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")


# ---------------------------------------------------------------- install


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    init(tmp_path)
    return tmp_path


def outcomes(actions) -> dict[str, str]:
    return {a.hook: a.outcome for a in actions}


def test_installing_twice_reports_everything_unchanged(repo):
    cfg = GhConfig(root=repo)
    install.install(cfg)
    second = outcomes(install.install(cfg))
    assert set(second.values()) == {"unchanged"}
    assert install.installed(cfg) == (True, [])


def test_an_outdated_vibey_hook_is_replaced_not_chained(repo):
    cfg = GhConfig(root=repo)
    install.install(cfg)
    hook = repo / install.HOOKS_DIR / "pre-push"
    hook.write_text(hook.read_text() + "\n# stale vibey-gh copy\n")
    (repo / install.WORKFLOWS_DIR / "provenance.yml").write_text("stale\n")

    ok, problems = install.installed(cfg)
    assert not ok
    assert any("pre-push is out of date" in p for p in problems)
    assert any("provenance.yml is out of date" in p for p in problems)

    assert outcomes(install.install(cfg))["pre-push"] == "updated"
    assert not (repo / install.HOOKS_DIR / "pre-push.local").exists()
    assert install.installed(cfg) == (True, [])


def test_a_foreign_hook_is_preserved_and_chained(repo):
    cfg = GhConfig(root=repo)
    hooks = repo / install.HOOKS_DIR
    hooks.mkdir()
    (hooks / "pre-push").write_text("#!/bin/sh\necho someone elses check\n")

    assert outcomes(install.install(cfg))["pre-push"] == "chained"
    local = hooks / "pre-push.local"
    assert "someone elses check" in local.read_text()
    assert local.stat().st_mode & stat.S_IXUSR


def test_missing_hooks_and_workflows_are_both_reported(repo):
    ok, problems = install.installed(GhConfig(root=repo), local=True)
    assert not ok
    assert any("commit-msg is missing" in p for p in problems)
    assert any("provenance.yml is missing" in p for p in problems)
    assert any("core.hooksPath" in p for p in problems)


def test_install_can_leave_core_hookspath_alone(repo):
    install.install(GhConfig(root=repo), hooks_path=False)
    got = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert got.stdout.strip() == ""


# ---------------------------------------------------------------- fingerprints


def test_an_unreadable_rev_range_is_an_error_not_a_silent_pass(repo):
    with pytest.raises(RuntimeError, match="cannot read no-such-ref"):
        fingerprints.commits_missing_trailer("no-such-ref..HEAD", GhConfig(root=repo))


# ---------------------------------------------------------------- versioning


def cfg_with_versions(root: Path, *files: str) -> GhConfig:
    return GhConfig(
        root=root, version_files=files, content_paths=("content/",), code_paths=("src/",)
    )


def test_read_version_skips_absent_files_and_reads_json_metadata(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"metadata": {"version": "3.4.5"}}))
    cfg = cfg_with_versions(tmp_path, "gone.py", "m.json")
    assert versioning.read_version(cfg) == "3.4.5"


def test_read_version_accepts_a_flat_json_version(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"version": "9.0.1"}))
    assert versioning.read_version(cfg_with_versions(tmp_path, "m.json")) == "9.0.1"


def test_read_version_raises_when_no_file_carries_one(tmp_path):
    (tmp_path / "v.py").write_text("# nothing here\n")
    with pytest.raises(RuntimeError, match="no version found"):
        versioning.read_version(cfg_with_versions(tmp_path, "v.py", "absent.json"))


def test_git_failures_surface_as_runtime_errors(repo):
    with pytest.raises(RuntimeError, match="git diff"):
        versioning._git(GhConfig(root=repo), "diff", "--name-only", "nope", "HEAD")


def test_decide_refuses_to_guess_when_the_ref_has_no_version(repo):
    (repo / "v.py").write_text('__version__ = "1.0.0"\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "no version file tracked yet")
    cfg = cfg_with_versions(repo, "absent.py")
    new, why = versioning.decide(cfg, "HEAD")
    assert new is None and "refusing to guess" in why


def test_read_version_at_walks_past_junk_to_the_file_that_has_one(repo):
    (repo / "broken.json").write_text("{not json")
    (repo / "empty.py").write_text("x = 1\n")
    (repo / "m.json").write_text(json.dumps({"metadata": {"version": "2.0.0"}}))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")

    cfg = cfg_with_versions(repo, "absent.json", "broken.json", "empty.py", "m.json")
    assert versioning.read_version_at(cfg, "HEAD") == "2.0.0"
    assert versioning.read_version_at(cfg_with_versions(repo, "empty.py"), "HEAD") is None


def test_apply_version_skips_absent_files_and_rejects_a_file_without_a_version(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"version": "1.0.0"}))
    assert versioning.apply_version(cfg_with_versions(tmp_path, "gone.py", "m.json"), "1.1.0") == [
        "m.json"
    ]
    assert json.loads((tmp_path / "m.json").read_text())["version"] == "1.1.0"

    (tmp_path / "v.py").write_text("# no version line\n")
    with pytest.raises(RuntimeError, match="expected one __version__ line"):
        versioning.apply_version(cfg_with_versions(tmp_path, "v.py"), "1.1.0")


def test_dev_version_strips_non_digits_and_survives_a_digitless_build(tmp_path):
    (tmp_path / "v.py").write_text('__version__ = "1.2.3"\n')
    cfg = cfg_with_versions(tmp_path, "v.py")
    assert versioning.dev_version(cfg, "run-42") == "1.2.3.dev42"
    assert versioning.dev_version(cfg, "none") == "1.2.3.dev0"


# ---------------------------------------------------------------- merge train


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch) -> Path:
    """A `gh` on PATH that replays scripted answers and records what it was asked.

    Answers live in `answers.json`, keyed by the joined argv; `calls.txt` records every
    invocation, so a test can assert on the command line the module actually built.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
here = pathlib.Path({str(bin_dir)!r})
with (here / "calls.txt").open("a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
answers = json.loads((here / "answers.json").read_text())
entry = answers.get(" ".join(sys.argv[1:]))
if entry is None:
    sys.stderr.write("no scripted answer\\n")
    raise SystemExit(3)
sys.stdout.write(entry.get("out", ""))
sys.stderr.write(entry.get("err", ""))
raise SystemExit(entry.get("code", 0))
""")
    gh.chmod(0o755)
    (bin_dir / "answers.json").write_text("{}")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return bin_dir


def script(bin_dir: Path, answers: dict) -> None:
    (bin_dir / "answers.json").write_text(json.dumps(answers))


def calls(bin_dir: Path) -> list[str]:
    path = bin_dir / "calls.txt"
    return path.read_text().splitlines() if path.exists() else []


def test_open_pull_requests_lists_then_views_each_one(fake_gh):
    cfg = GhConfig(root=Path.cwd(), integration_branch="develop")
    listing = "pr list --base develop --state open --json number --jq sort_by(.number)"
    script(
        fake_gh,
        {
            listing: {"out": json.dumps([{"number": 4}, {"number": 7}])},
            "pr view 4 --json number,title,isDraft,mergeable,reviewDecision,"
            "statusCheckRollup,author": {"out": json.dumps({"number": 4, "title": "four"})},
            "pr view 7 --json number,title,isDraft,mergeable,reviewDecision,"
            "statusCheckRollup,author": {"out": json.dumps({"number": 7, "title": "seven"})},
        },
    )
    assert [pr["title"] for pr in merge_train.open_pull_requests(cfg)] == ["four", "seven"]


def test_an_empty_listing_yields_no_pull_requests(fake_gh):
    cfg = GhConfig(root=Path.cwd(), integration_branch="develop")
    script(
        fake_gh,
        {"pr list --base develop --state open --json number --jq sort_by(.number)": {"out": ""}},
    )
    assert merge_train.open_pull_requests(cfg) == []


def test_a_failing_gh_call_raises_with_its_stderr(fake_gh):
    cfg = GhConfig(root=Path.cwd(), integration_branch="develop")
    script(fake_gh, {})
    with pytest.raises(RuntimeError, match="no scripted answer"):
        merge_train.open_pull_requests(cfg)


def test_merge_prefers_a_plain_merge(fake_gh):
    script(fake_gh, {"pr merge 5 --squash --delete-branch": {"code": 0}})
    assert merge_train.merge(5) == (True, False)
    assert calls(fake_gh) == ["pr merge 5 --squash --delete-branch"]


def test_merge_falls_back_to_admin_and_reports_the_bypass(fake_gh):
    script(fake_gh, {"pr merge 5 --rebase --delete-branch --admin": {"code": 0}})
    assert merge_train.merge(5, "rebase") == (True, True)
    assert calls(fake_gh)[-1].endswith("--admin")


def test_merge_reports_failure_when_even_admin_is_refused(fake_gh):
    script(fake_gh, {})
    assert merge_train.merge(5) == (False, True)


# ---------------------------------------------------------------- realign


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin plus a clone with `main` and `develop`, both at the same commit."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)

    work = tmp_path / "work"
    init(work)
    (work / "a.txt").write_text("one\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "one")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "origin", "main")
    git(work, "push", "-q", "origin", "main:develop")
    git(work, "fetch", "-q", "origin")
    return origin, work


def gh_cfg(root: Path) -> GhConfig:
    return GhConfig(root=root, integration_branch="develop", release_branch="main")


def test_realign_is_a_no_op_when_the_branches_are_the_same_commit(pair):
    _, work = pair
    changed, message = realign.realign(gh_cfg(work))
    assert changed is False
    assert "already matches" in message


def test_realign_refuses_when_develop_has_content_main_does_not(pair):
    _origin, work = pair
    git(work, "checkout", "-qB", "develop", "origin/develop")
    (work / "b.txt").write_text("extra\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "extra")
    git(work, "push", "-q", "origin", "develop")

    changed, message = realign.realign(gh_cfg(work))
    assert changed is False
    assert "left untouched" in message
    assert git(work, "rev-parse", "origin/develop") != git(work, "rev-parse", "origin/main")


def test_realign_converges_identical_trees_onto_one_history(pair):
    _origin, work = pair
    # Rewrite develop as a different commit with the SAME tree — what a rebase-merge
    # leaves behind, and the only case realign exists to fix.
    git(work, "checkout", "-qB", "develop", "origin/develop")
    git(work, "commit", "-q", "--allow-empty", "-m", "rewritten copy")
    git(work, "push", "-q", "origin", "develop")
    git(work, "fetch", "-q", "origin")
    assert git(work, "rev-parse", "origin/develop") != git(work, "rev-parse", "origin/main")

    changed, message = realign.realign(gh_cfg(work))
    assert changed is True
    assert "histories converged" in message
    git(work, "fetch", "-q", "origin")
    assert git(work, "rev-parse", "origin/develop") == git(work, "rev-parse", "origin/main")


def test_a_refused_push_is_raised_with_the_manual_command(pair):
    origin, work = pair
    git(work, "checkout", "-qB", "develop", "origin/develop")
    git(work, "commit", "-q", "--allow-empty", "-m", "rewritten copy")
    git(work, "push", "-q", "origin", "develop")
    git(work, "fetch", "-q", "origin")

    # Only now: realign must get past the tree check and be refused at the push, which is
    # exactly how a branch ruleset refuses a token without the admin role.
    hooks = origin / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-receive").write_text("#!/bin/sh\necho 'blocked by the ruleset' >&2\nexit 1\n")
    (hooks / "pre-receive").chmod(0o755)

    with pytest.raises(RuntimeError, match="could not realign develop") as raised:
        realign.realign(gh_cfg(work))
    assert "blocked by the ruleset" in str(raised.value)
    assert "git push --force-with-lease origin main:develop" in str(raised.value)


# ---------------------------------------------------------------- TOML versions


PYPROJECT = """[build-system]
requires = ["hatchling"]

[project]
name = "demo"
version = "1.2.3"
description = "x"

[tool.poetry]
version = "9.9.9"
"""


def test_a_toml_version_is_read_from_the_project_table(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    cfg = cfg_with_versions(tmp_path, "pyproject.toml")
    assert versioning.read_version(cfg) == "1.2.3"


def test_a_toml_without_a_project_version_is_skipped(tmp_path):
    (tmp_path / "a.toml").write_text('[tool.other]\nversion = "9.9.9"\n')
    (tmp_path / "v.py").write_text('__version__ = "2.0.0"\n')
    cfg = cfg_with_versions(tmp_path, "a.toml", "v.py")
    assert versioning.read_version(cfg) == "2.0.0"


def test_a_toml_that_does_not_parse_is_skipped(tmp_path):
    (tmp_path / "broken.toml").write_text("[project\nname = ")
    (tmp_path / "v.py").write_text('__version__ = "2.0.0"\n')
    cfg = cfg_with_versions(tmp_path, "broken.toml", "v.py")
    assert versioning.read_version(cfg) == "2.0.0"


def test_a_toml_version_is_read_at_a_git_ref(repo):
    (repo / "pyproject.toml").write_text(PYPROJECT)
    (repo / "broken.toml").write_text("[project\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")

    cfg = cfg_with_versions(repo, "broken.toml", "pyproject.toml")
    assert versioning.read_version_at(cfg, "HEAD") == "1.2.3"


def test_bumping_a_toml_touches_only_the_project_table(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text(PYPROJECT)
    cfg = cfg_with_versions(tmp_path, "pyproject.toml")

    assert versioning.apply_version(cfg, "1.3.0") == ["pyproject.toml"]
    patched = path.read_text()
    assert 'version = "1.3.0"' in patched
    assert 'version = "9.9.9"' in patched  # [tool.poetry] left alone
    assert versioning.read_version(cfg) == "1.3.0"


def test_bumping_a_toml_whose_project_table_is_last(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "demo"\nversion = "1.2.3"\n')
    cfg = cfg_with_versions(tmp_path, "pyproject.toml")
    versioning.apply_version(cfg, "1.3.0")
    assert versioning.read_version(cfg) == "1.3.0"


def test_a_toml_with_no_project_table_cannot_be_bumped(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 100\n")
    cfg = cfg_with_versions(tmp_path, "pyproject.toml")
    with pytest.raises(RuntimeError, match="no \\[project\\] table"):
        versioning.apply_version(cfg, "1.3.0")


def test_a_project_table_carrying_no_version_cannot_be_bumped(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n\n[tool.x]\n')
    cfg = cfg_with_versions(tmp_path, "pyproject.toml")
    with pytest.raises(RuntimeError, match="expected one \\[project\\] version"):
        versioning.apply_version(cfg, "1.3.0")
