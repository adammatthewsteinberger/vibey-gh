# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""Tests for the `vibey-gh` command surface.

The CLI is thin by design — the decisions live in the modules beside it — so these tests
check wiring and exit codes rather than re-testing the logic.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vibey_gh import merge_train
from vibey_gh import realign as realign_mod
from vibey_gh.cli import main
from vibey_gh.merge_train import Verdict


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q", ".")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text('__version__ = "1.0.0"\n')
    (tmp_path / "manifest.json").write_text(json.dumps({"metadata": {"version": "1.0.0"}}) + "\n")
    (tmp_path / "content").mkdir()
    (tmp_path / "content" / "a.md").write_text("a\n")
    (tmp_path / ".vibey-gh.toml").write_text(
        '[fingerprint]\nsources = ["src/*.py"]\n'
        '[version]\nfiles = ["src/__init__.py", "manifest.json"]\n'
        'content_paths = ["content/"]\ncode_paths = ["src/"]\n'
        '[merge_train]\nowner = "owner"\ntrusted_authors = ["owner"]\n'
    )
    git("add", "-A")
    git("commit", "-qm", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_install_then_check_passes(repo, capsys):
    assert main(["check", "--ci"]) == 1  # nothing installed, no headers
    assert main(["install"]) == 0
    assert main(["check", "--ci", "--apply"]) == 0
    assert "ok" in capsys.readouterr().out


def test_check_quiet_is_exit_status_only(repo, capsys):
    assert main(["check", "--ci", "--quiet"]) == 1
    assert capsys.readouterr().out == ""


def test_check_reports_a_missing_commit_trailer(repo, capsys):
    main(["check", "--ci", "--apply"])
    # --no-verify, because `install` puts in the commit-msg hook that would add the
    # trailer for us — the point here is a commit that escaped it.
    subprocess.run(
        ["git", "commit", "-q", "--no-verify", "--allow-empty", "-m", "bare"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert main(["check", "--ci", "--commits", "HEAD~1..HEAD"]) == 1
    assert "trailer" in capsys.readouterr().err


def test_version_reports_none_when_nothing_shipped(repo, capsys):
    subprocess.run(["git", "branch", "-q", "base"], cwd=repo, check=True)
    (repo / "README.md").write_text("docs\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "docs"], cwd=repo, check=True, capture_output=True)
    assert main(["version", "--since", "base"]) == 0
    assert capsys.readouterr().out.strip() == "none"


def test_version_bumps_minor_and_can_apply(repo, capsys):
    subprocess.run(["git", "branch", "-q", "base"], cwd=repo, check=True)
    (repo / "content" / "a.md").write_text("changed\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "content"], cwd=repo, check=True, capture_output=True)

    assert main(["version", "--since", "base", "--explain", "--apply"]) == 0
    assert capsys.readouterr().out.strip() == "1.1.0"
    assert '__version__ = "1.1.0"' in (repo / "src" / "__init__.py").read_text()
    assert json.loads((repo / "manifest.json").read_text())["metadata"]["version"] == "1.1.0"


def test_version_dev_builds(repo, capsys):
    assert main(["version", "--dev", "11"]) == 0
    assert capsys.readouterr().out.strip() == "1.0.0.dev11"
    assert main(["version", "--dev", "12", "--apply"]) == 0
    capsys.readouterr()
    assert "1.0.0.dev12" in (repo / "src" / "__init__.py").read_text()


def test_merge_train_with_nothing_open(repo, capsys, monkeypatch):
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [])
    assert main(["merge-train"]) == 0
    assert "no open pull requests" in capsys.readouterr().out


def test_merge_train_merges_ready_and_skips_the_rest(repo, capsys, monkeypatch):
    prs = [{"number": 1}, {"number": 2}]
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: prs)
    monkeypatch.setattr(
        merge_train,
        "judge",
        lambda pr, cfg: Verdict(pr["number"], "t", "owner", None if pr["number"] == 1 else "draft"),
    )
    merged: list[int] = []
    monkeypatch.setattr(merge_train, "merge", lambda n, m: (merged.append(n), (True, True))[1])

    assert main(["merge-train"]) == 0
    out = capsys.readouterr().out
    assert merged == [1]
    assert "#1 squash-merged (review requirement bypassed)" in out
    assert "#2 skipped — draft" in out
    assert "merged 1, skipped 1" in out


def test_merge_train_dry_run_merges_nothing(repo, capsys, monkeypatch):
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [{"number": 3}])
    monkeypatch.setattr(merge_train, "judge", lambda pr, cfg: Verdict(3, "t", "owner", None))
    monkeypatch.setattr(merge_train, "merge", lambda n, m: pytest.fail("dry run must not merge"))
    assert main(["merge-train", "--dry-run"]) == 0
    assert "would merge" in capsys.readouterr().out


def test_merge_train_reports_a_refused_merge(repo, capsys, monkeypatch):
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [{"number": 9}])
    monkeypatch.setattr(merge_train, "judge", lambda pr, cfg: Verdict(9, "t", "owner", None))
    monkeypatch.setattr(merge_train, "merge", lambda n, m: (False, True))
    assert main(["merge-train"]) == 0
    assert "could not be merged" in capsys.readouterr().out


def test_realign_success_and_failure(repo, capsys, monkeypatch):
    monkeypatch.setattr(realign_mod, "realign", lambda cfg: (True, "converged"))
    assert main(["realign"]) == 0
    assert "converged" in capsys.readouterr().out

    def boom(cfg):
        raise RuntimeError("refused by the ruleset")

    monkeypatch.setattr(realign_mod, "realign", boom)
    assert main(["realign"]) == 1
    assert "refused by the ruleset" in capsys.readouterr().err


def test_trailer_helpers(repo, capsys):
    main(["trailer"])
    assert capsys.readouterr().out.startswith("Made-With:")
    main(["trailer-key"])
    assert capsys.readouterr().out.strip() == "Made-With"


def test_check_names_the_commit_range_it_cleared(repo, capsys):
    main(["install"])
    main(["check", "--ci", "--apply"])
    capsys.readouterr()
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "fingerprinted"],
        cwd=repo,
        check=True,
        capture_output=True,
    )  # the hook adds the trailer

    assert main(["check", "--ci", "--commits", "HEAD~1..HEAD"]) == 0
    assert "every commit in HEAD~1..HEAD" in capsys.readouterr().out


def held(number: int = 7, author: str = "outsider") -> Verdict:
    return Verdict(
        number,
        "their work",
        author,
        "from @outsider and not approved — needs owner's review",
        held_for_review=True,
    )


def test_a_pull_request_held_on_the_owner_is_labelled_and_announced(repo, monkeypatch, capsys):
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [{"number": 7}])
    monkeypatch.setattr(merge_train, "judge", lambda pr, cfg: held())
    calls: list[tuple] = []
    monkeypatch.setattr(
        merge_train, "hold_for_review", lambda v, cfg, label: calls.append((v.number, label))
    )

    assert main(["merge-train"]) == 0
    assert calls == [(7, "needs-human-review")]
    assert "#7 skipped" in capsys.readouterr().out


def test_a_dry_run_labels_nothing_and_announces_nothing(repo, monkeypatch):
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [{"number": 7}])
    monkeypatch.setattr(merge_train, "judge", lambda pr, cfg: held())
    monkeypatch.setattr(
        merge_train,
        "hold_for_review",
        lambda *a, **k: pytest.fail("a dry run must not touch the PR"),
    )
    assert main(["merge-train", "--dry-run"]) == 0


def test_labelling_can_be_turned_off(repo, monkeypatch):
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [{"number": 7}])
    monkeypatch.setattr(merge_train, "judge", lambda pr, cfg: held())
    monkeypatch.setattr(
        merge_train, "hold_for_review", lambda *a, **k: pytest.fail("--label '' means do nothing")
    )
    assert main(["merge-train", "--label", ""]) == 0


def test_an_ordinary_skip_is_not_announced(repo, monkeypatch):
    """A draft is the contributor's to fix; nobody needs paging about it."""
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [{"number": 7}])
    monkeypatch.setattr(merge_train, "judge", lambda pr, cfg: Verdict(7, "t", "someone", "draft"))
    monkeypatch.setattr(
        merge_train,
        "hold_for_review",
        lambda *a, **k: pytest.fail("a draft is not held for review"),
    )
    assert main(["merge-train"]) == 0


def test_the_run_writes_a_markdown_summary(repo, monkeypatch, tmp_path):
    monkeypatch.setattr(
        merge_train, "open_pull_requests", lambda cfg: [{"number": 1}, {"number": 2}]
    )
    monkeypatch.setattr(
        merge_train,
        "judge",
        lambda pr, cfg: Verdict(
            pr["number"], f"pr {pr['number']}", "owner", None if pr["number"] == 1 else "draft"
        ),
    )
    monkeypatch.setattr(merge_train, "merge", lambda n, m: (True, False))

    out = tmp_path / "summary.md"
    assert main(["merge-train", "--summary", str(out)]) == 0

    body = out.read_text()
    assert "| PR | Title | Outcome |" in body
    assert "| #1 | pr 1 | squash-merged |" in body
    assert "| #2 | pr 2 | skipped — draft |" in body
    assert "Merged 1, skipped 1." in body


def test_the_summary_defaults_to_the_actions_job_summary(repo, monkeypatch, tmp_path):
    out = tmp_path / "gh-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(out))
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [])
    assert main(["merge-train"]) == 0
    assert "No open pull requests." in out.read_text()


def test_a_summary_that_cannot_be_written_does_not_fail_the_train(
    repo, monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(merge_train, "open_pull_requests", lambda cfg: [])
    assert main(["merge-train", "--summary", str(tmp_path / "no-such-dir" / "s.md")]) == 0
    assert "could not write the summary" in capsys.readouterr().err
