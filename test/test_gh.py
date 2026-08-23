# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""Tests for the vibey-gh automation.

The readiness gate and the version decision are the parts most worth testing: both were
originally shell, where every case had to be exercised by hand and one of them was wrong
for a week. Here they are ordinary functions with an ordinary table of cases.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vibey_gh import fingerprints, install, merge_train, realign, versioning
from vibey_gh.cli import main as cli_main
from vibey_gh.config import GhConfig, PrAutomationConfig, load_config, normalise_actor

# --------------------------------------------------------------------------- helpers


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", ".")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text('__version__ = "1.2.3"\n')
    (tmp_path / "manifest.json").write_text(json.dumps({"metadata": {"version": "1.2.3"}}) + "\n")
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "thing.md").write_text("hello\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def cfg_for(root: Path, **kw) -> GhConfig:
    base = dict(
        root=root,
        sources=("src/*.py",),
        version_files=("src/__init__.py", "manifest.json"),
        content_paths=("content/",),
        code_paths=("src/",),
    )
    base.update(kw)
    return GhConfig(**base)


# --------------------------------------------------------------------------- config


def test_defaults_apply_without_a_config_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.header.startswith("# Made with love by Vibey")
    assert cfg.trailer_key == "Made-With"


def test_config_file_overrides_defaults(tmp_path):
    (tmp_path / ".vibey-gh.toml").write_text(
        '[fingerprint]\ntext = "X"\ntrailer = "By: X"\nsources = ["a/*.py"]\n'
        '[branches]\nintegration = "trunk"\n'
    )
    cfg = load_config(tmp_path)
    assert cfg.header == "# X"
    assert cfg.trailer_key == "By"
    assert cfg.sources == ("a/*.py",)
    assert cfg.integration_branch == "trunk"


@pytest.mark.parametrize(
    "given,expected",
    [
        ("app/claude", "claude"),
        ("claude[bot]", "claude"),
        ("app/github-actions", "github-actions"),
        ("adammatthewsteinberger", "adammatthewsteinberger"),
    ],
)
def test_bot_logins_normalise_to_one_spelling(given, expected):
    """gh writes `app/claude`; the rest of GitHub writes `claude[bot]`."""
    assert normalise_actor(given) == expected


# ---------------------------------------------------------------------- fingerprints


def test_header_is_detected_and_inserted(repo):
    cfg = cfg_for(repo)
    report = fingerprints.check(cfg)
    assert [p.name for p in report.missing_header] == ["__init__.py"]

    fingerprints.check(cfg, apply=True)
    assert fingerprints.check(cfg).ok


def test_header_goes_after_a_shebang(repo):
    cfg = cfg_for(repo)
    target = repo / "src" / "__init__.py"
    target.write_text('#!/usr/bin/env python3\n__version__ = "1.2.3"\n')
    fingerprints.check(cfg, apply=True)
    lines = target.read_text().splitlines()
    assert lines[0].startswith("#!")
    assert lines[1] == cfg.header


def test_missing_commit_trailer_is_reported(repo):
    cfg = cfg_for(repo)
    git(repo, "commit", "-q", "--allow-empty", "-m", "no trailer here")
    missing = fingerprints.commits_missing_trailer("HEAD~1..HEAD", cfg)
    assert len(missing) == 1 and "no trailer here" in missing[0]

    git(repo, "commit", "-q", "--allow-empty", "-m", f"has one\n\n{cfg.trailer}")
    assert fingerprints.commits_missing_trailer("HEAD~1..HEAD", cfg) == []


# ------------------------------------------------------------------------ versioning


@pytest.mark.parametrize(
    "version,level,expected",
    [
        ("1.2.3", "minor", "1.3.0"),
        ("1.2.3", "patch", "1.2.4"),
        ("2.17.0", "minor", "2.18.0"),
    ],
)
def test_bump(version, level, expected):
    assert versioning.bump(version, level) == expected


def test_read_version_from_python_and_json(repo):
    cfg = cfg_for(repo)
    assert versioning.read_version(cfg) == "1.2.3"
    cfg_json = cfg_for(repo, version_files=("manifest.json",))
    assert versioning.read_version(cfg_json) == "1.2.3"


def test_apply_version_writes_every_configured_file(repo):
    cfg = cfg_for(repo)
    versioning.apply_version(cfg, "9.9.9")
    assert '__version__ = "9.9.9"' in (repo / "src" / "__init__.py").read_text()
    assert json.loads((repo / "manifest.json").read_text())["metadata"]["version"] == "9.9.9"


@pytest.mark.parametrize(
    "change,expected,note",
    [
        ("content", "1.3.0", "packaged content changed -> minor"),
        ("code", "1.2.4", "only internal code -> patch"),
        ("docs", None, "nothing an installed user receives -> none"),
        (None, None, "no changes at all -> none"),
    ],
)
def test_version_decision_table(repo, change, expected, note):
    cfg = cfg_for(repo)
    git(repo, "branch", "-q", "base")
    if change == "content":
        (repo / "content" / "thing.md").write_text("changed\n")
    elif change == "code":
        (repo / "src" / "other.py").write_text("x = 1\n")
    elif change == "docs":
        (repo / "README.md").write_text("docs\n")
    if change:
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", change)

    new, why = versioning.decide(cfg, "base")
    assert new == expected, f"{note}: got {new} ({why})"


def test_a_deliberate_bump_is_never_doubled(repo):
    """Someone bumped by hand in a pull request; the automation must leave it alone."""
    cfg = cfg_for(repo)
    git(repo, "branch", "-q", "base")
    (repo / "content" / "thing.md").write_text("changed\n")
    versioning.apply_version(cfg, "5.0.0")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "manual bump")
    new, why = versioning.decide(cfg, "base")
    assert new is None and "deliberate bump" in why


def test_dev_version_is_pep440_and_ordered(repo):
    cfg = cfg_for(repo)
    assert versioning.dev_version(cfg, "42") == "1.2.3.dev42"
    assert versioning.dev_version(cfg, "build-7") == "1.2.3.dev7"


# ----------------------------------------------------------------------- merge train


def _pr(**kw):
    pr = dict(
        number=1,
        title="t",
        isDraft=False,
        mergeable="MERGEABLE",
        reviewDecision=None,
        statusCheckRollup=[{"status": "COMPLETED", "conclusion": "SUCCESS"}],
        author={"login": "owner"},
    )
    pr.update(kw)
    return pr


@pytest.mark.parametrize(
    "pr,ready,fragment",
    [
        (_pr(), True, None),
        (_pr(author={"login": "app/claude"}), True, None),
        (_pr(author={"login": "claude[bot]"}), True, None),
        (_pr(isDraft=True), False, "draft"),
        (_pr(mergeable="CONFLICTING"), False, "conflicts"),
        (_pr(reviewDecision="CHANGES_REQUESTED"), False, "changes requested"),
        (
            _pr(statusCheckRollup=[{"status": "IN_PROGRESS", "conclusion": None}]),
            False,
            "still running",
        ),
        (
            _pr(statusCheckRollup=[{"status": "COMPLETED", "conclusion": "FAILURE"}]),
            False,
            "failing",
        ),
        (_pr(statusCheckRollup=[]), True, None),
        (_pr(author={"login": "outsider"}), False, "not approved"),
        (_pr(author={"login": "outsider"}, reviewDecision="APPROVED"), True, None),
    ],
)
def test_readiness_gate(tmp_path, pr, ready, fragment):
    cfg = cfg_for(
        tmp_path,
        owner="owner",
        trusted_authors=("owner", "claude[bot]", "github-actions[bot]"),
        pr_automation=PrAutomationConfig(enabled=False),
    )
    verdict = merge_train.judge(pr, cfg)
    assert verdict.ready is ready
    if fragment:
        assert fragment in verdict.reason


def test_pull_request_recovers_fresh_exact_head_gate(monkeypatch):
    calls = []

    def fake(*args):
        calls.append(args)
        if args[:2] == ("pr", "view"):
            return _pr(headRefOid="abc", statusCheckRollup=[])
        if args[:2] == ("repo", "view"):
            return {"nameWithOwner": "owner/repo"}
        return {
            "check_runs": [
                {"name": "PR automation / gate", "status": "completed", "conclusion": "success"}
            ]
        }

    monkeypatch.setattr(merge_train, "_gh_json", fake)
    pr = merge_train.pull_request(1)
    assert pr["statusCheckRollup"][-1]["conclusion"] == "SUCCESS"
    assert any(args[0] == "api" for args in calls)


def test_exact_head_gate_lookup_skips_existing_missing_sha_and_nonpassing(monkeypatch):
    called = []
    monkeypatch.setattr(
        merge_train,
        "_gh_json",
        lambda *args: (
            called.append(args) or {"nameWithOwner": "owner/repo"}
            if args[0] == "repo"
            else {
                "check_runs": [
                    {"name": "PR automation / gate", "status": "completed", "conclusion": "failure"}
                ]
            }
        ),
    )
    existing = {"statusCheckRollup": [{"name": "PR automation / gate"}], "headRefOid": "x"}
    merge_train._include_exact_head_gate(existing)
    merge_train._include_exact_head_gate({"statusCheckRollup": []})
    failing = {"statusCheckRollup": [], "headRefOid": "x"}
    merge_train._include_exact_head_gate(failing)
    assert failing["statusCheckRollup"] == []


def test_open_pull_requests_reuses_exact_head_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(merge_train, "_gh_json", lambda *args: [{"number": 2}])
    monkeypatch.setattr(merge_train, "pull_request", lambda number: {"number": number})
    assert merge_train.open_pull_requests(cfg_for(tmp_path)) == [{"number": 2}]


# -------------------------------------------------------------------------- install


def test_install_places_hooks_and_reports_missing(repo):
    cfg = cfg_for(repo)
    ok, problems = install.installed(cfg, local=False)
    assert not ok and any("commit-msg" in p for p in problems)

    install.install(cfg, hooks_path=False)
    ok, problems = install.installed(cfg, local=False)
    assert ok, problems
    assert (repo / ".githooks" / "pre-push").exists()


def test_install_chains_an_existing_hook_instead_of_discarding_it(repo):
    cfg = cfg_for(repo)
    hooks = repo / ".githooks"
    hooks.mkdir()
    (hooks / "pre-push").write_text("#!/bin/sh\necho someone elses check\n")

    actions = install.install(cfg, hooks_path=False)
    assert any(a.hook == "pre-push" and a.outcome == "chained" for a in actions)
    assert "someone elses check" in (hooks / "pre-push.local").read_text()
    assert "vibey-gh" in (hooks / "pre-push").read_text()


def test_ci_mode_ignores_local_hooks_path(repo):
    """core.hooksPath is per-clone config no runner can satisfy; the FILES still count."""
    cfg = cfg_for(repo)
    install.install(cfg, hooks_path=False)
    assert install.installed(cfg, local=False)[0] is True
    assert install.installed(cfg, local=True)[0] is False


# --------------------------------------------------------------------------- realign


def test_realign_refuses_when_the_branches_differ(repo, monkeypatch):
    cfg = cfg_for(repo, integration_branch="develop", release_branch="main")
    monkeypatch.setattr(
        realign,
        "_git",
        lambda c, *a: subprocess.CompletedProcess(a, 1 if a[0] == "diff" else 0, "", ""),
    )
    changed, message = realign.realign(cfg)
    assert changed is False and "left untouched" in message


# ------------------------------------------------------------------------------ cli


def test_cli_check_reports_failure_then_success(repo, monkeypatch, capsys):
    (repo / ".vibey-gh.toml").write_text(
        '[fingerprint]\nsources = ["src/*.py"]\n[documentation]\nenabled=false\n'
    )
    monkeypatch.chdir(repo)
    assert cli_main(["check", "--ci"]) == 1
    install.install(load_config(repo), hooks_path=False)
    assert cli_main(["check", "--ci", "--apply"]) == 0


def test_cli_prints_the_trailer(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    cli_main(["trailer-key"])
    assert capsys.readouterr().out.strip() == "Made-With"
