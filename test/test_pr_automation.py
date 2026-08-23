# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""Policy, persistence, and privileged-workflow tests for PR automation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vibey_gh import pr_automation as pa
from vibey_gh.config import GhConfig, PrAutomationConfig, load_config
from vibey_gh.install import installation_notices, render_workflow


def cfg(tmp_path: Path, **automation) -> GhConfig:
    return GhConfig(
        root=tmp_path,
        owner="owner",
        trusted_authors=("trusted[bot]",),
        pr_automation=PrAutomationConfig(**automation),
    )


def pr(**changes):
    value = {
        "number": 12,
        "title": "change",
        "state": "OPEN",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "",
        "headRefOid": "abc",
        "headRefName": "topic",
        "baseRefName": "develop",
        "author": {"login": "owner"},
        "labels": [],
        "comments": [],
        "statusCheckRollup": [],
    }
    value.update(changes)
    return value


def check(name="CI", status="COMPLETED", conclusion="SUCCESS", **extra):
    return {"name": name, "status": status, "conclusion": conclusion, **extra}


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"scan_workflows": ()}, "must not be empty"),
        ({"max_repair_attempts": 0}, "between 1 and 10"),
        ({"max_repair_attempts": 11}, "between 1 and 10"),
        ({"model": "  "}, "model must not be empty"),
        ({"scan_workflows": ("CI", "")}, "entries must be non-empty"),
        ({"ignored_checks": ("x", "x")}, "entries must be unique"),
    ],
)
def test_config_validation(kwargs, match):
    with pytest.raises(ValueError, match=match):
        PrAutomationConfig(**kwargs)


def test_config_parses_public_surface(tmp_path):
    (tmp_path / ".vibey-gh.toml").write_text("""[pr_automation]
enabled = false
scan_workflows = []
ignored_checks = ["custom"]
max_repair_attempts = 7
model = "model-x"
review_untrusted_authors = false
repair_untrusted_authors = false
replace_fork_prs = false
retain_schedule_backstop = false
""")
    value = load_config(tmp_path).pr_automation
    assert value == PrAutomationConfig(
        enabled=False,
        scan_workflows=(),
        ignored_checks=("custom",),
        max_repair_attempts=7,
        model="model-x",
        review_untrusted_authors=False,
        repair_untrusted_authors=False,
        replace_fork_prs=False,
        retain_schedule_backstop=False,
    )


def test_rendered_workflow_uses_config_and_is_valid_yaml_shape(tmp_path):
    source = Path(pa.__file__).parent / "templates/workflows/pr-automation.yml"
    rendered = render_workflow(
        source,
        cfg(
            tmp_path,
            scan_workflows=("CI: strict", "Docs"),
            model="chosen-model",
            retain_schedule_backstop=False,
        ),
    )
    assert 'workflows: ["CI: strict", "Docs"]' in rendered
    assert "--model chosen-model" in rendered
    assert "schedule backstop disabled" in rendered
    assert "__VIBEY_GH_" not in rendered

    intake = source.with_name("branch-intake.yml")
    rendered_intake = render_workflow(intake, cfg(tmp_path))
    assert "- develop" in rendered_intake
    assert "- main" in rendered_intake
    assert "__VIBEY_GH_" not in rendered_intake


def test_installation_notices_report_missing_secrets(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, '[{"name":"ANTHROPIC_API_KEY"}]', ""),
    )
    notices = installation_notices()
    assert any("AUTOMERGE_TOKEN" in item for item in notices)
    assert not any("ANTHROPIC_API_KEY" in item for item in notices)
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 0, "not-json", "")
    )
    assert any("ANTHROPIC_API_KEY" in item for item in installation_notices())


@pytest.mark.parametrize(
    "changes,state,reason",
    [
        ({"headRefOid": "new"}, "blocked", "stale event"),
        ({"state": "CLOSED"}, "blocked", "not open"),
        ({"isDraft": True}, "blocked", "draft"),
        ({"mergeable": "CONFLICTING"}, "conflict", "conflicts"),
        ({"reviewDecision": "CHANGES_REQUESTED"}, "blocked", "requested changes"),
        ({"labels": [pa.BLOCKED_LABEL]}, "blocked", "operator"),
        ({"labels": [{"name": pa.EXHAUSTED_LABEL}]}, "blocked", "exhausted"),
        (
            {"statusCheckRollup": [check(status="IN_PROGRESS", conclusion=None)]},
            "pending",
            "running",
        ),
        ({"statusCheckRollup": [check(conclusion="CANCELLED")]}, "blocked", "rerun"),
        ({"statusCheckRollup": [check(conclusion="FAILURE")]}, "repair", "failing"),
    ],
)
def test_evaluation_states(tmp_path, changes, state, reason):
    result = pa.evaluate(pr(**changes), cfg(tmp_path), expected_sha="abc")
    assert result.state == state
    assert reason in result.reason
    assert json.loads(result.to_json())["state"] == state


def test_evaluation_ignores_own_checks_and_accepts_context_shape(tmp_path):
    result = pa.evaluate(
        pr(
            statusCheckRollup=[
                check("PR automation / gate", conclusion="FAILURE"),
                {"context": "legacy", "conclusion": "NEUTRAL", "targetUrl": "u"},
                {"name": "skip", "conclusion": "SKIPPED", "detailsUrl": "v"},
            ]
        ),
        cfg(tmp_path),
        expected_sha="abc",
    )
    assert result.state == "ready"


def test_evaluation_waits_when_no_scan_result_exists(tmp_path):
    result = pa.evaluate(pr(), cfg(tmp_path), expected_sha="abc")
    assert result.state == "pending" and "no current-head" in result.reason


def test_retry_and_untrusted_review_policy(tmp_path):
    failed = pr(author={"login": "outsider"}, statusCheckRollup=[check(conclusion="FAILURE")])
    state = pa.AutomationState("abc", "abc", attempts=3)
    assert pa.evaluate(failed, cfg(tmp_path), expected_sha="abc", stored=state).state == "blocked"
    assert (
        pa.evaluate(failed, cfg(tmp_path, repair_untrusted_authors=False), expected_sha="abc").state
        == "blocked"
    )

    green = pr(author={"login": "outsider"}, statusCheckRollup=[check()])
    assert pa.evaluate(green, cfg(tmp_path), expected_sha="abc").state == "review"
    findings = pa.AutomationState("abc", "abc", review_sha="abc", review_passed=False)
    assert pa.evaluate(green, cfg(tmp_path), expected_sha="abc", stored=findings).state == "repair"
    findings.attempts = 3
    assert pa.evaluate(green, cfg(tmp_path), expected_sha="abc", stored=findings).state == "blocked"
    passed = pa.AutomationState("abc", "abc", review_sha="abc", review_passed=True)
    assert pa.evaluate(green, cfg(tmp_path), expected_sha="abc", stored=passed).state == "ready"
    assert (
        pa.evaluate(green, cfg(tmp_path, review_untrusted_authors=False), expected_sha="abc").state
        == "ready"
    )


def test_conflict_resolution_uses_and_enforces_repair_budget(tmp_path):
    conflicting = pr(mergeable="CONFLICTING", statusCheckRollup=[check()])
    first = pa.evaluate(conflicting, cfg(tmp_path), expected_sha="abc")
    assert first.state == "conflict"
    assert first.repair_attempt == 1
    assert first.failed_checks == ("Merge conflict with develop",)
    exhausted = pa.AutomationState("abc", "abc", attempts=3)
    result = pa.evaluate(conflicting, cfg(tmp_path), expected_sha="abc", stored=exhausted)
    assert result.state == "blocked"
    assert "conflict resolution budget" in result.reason


def test_external_repair_is_untrusted_even_for_owner(tmp_path):
    result = pa.evaluate(
        pr(labels=[pa.EXTERNAL_REPAIR_LABEL], statusCheckRollup=[check()]),
        cfg(tmp_path),
        expected_sha="abc",
    )
    assert result.trusted is False and result.state == "review"


@pytest.mark.parametrize("branch", ("", ":main", "topic:other", "--delete"))
def test_repair_refspec_rejects_deletion_or_option_syntax(branch):
    with pytest.raises(ValueError, match="unsafe repair branch"):
        pa.repair_refspec(branch)


@pytest.mark.parametrize("branch", ("topic", "develop", "main"))
def test_repair_refspec_allows_forward_updates_including_protected_branches(branch):
    assert pa.repair_refspec(branch) == f"HEAD:refs/heads/{branch}"


def test_state_marker_round_trip_and_malformed_comments():
    assert pa.parse_state(["ordinary", "<!-- vibey-gh-pr-automation:{bad} -->"]) is None
    state = pa.AutomationState("a", "b", 2, history=[{"kind": "repair"}])
    body = pa.state_body(state, " summary ")
    assert pa.parse_state([{"body": body}]) == state
    assert "summary" in body


def test_state_updates_review_repair_and_rejects_unknown_kind():
    review = pa.updated_state(pr(), {"head_sha": "abc", "pass": True}, kind="review")
    assert review.review_sha == "abc" and review.review_passed is True
    repair = pa.updated_state(
        pr(comments=[pa.state_body(review, "x")]),
        {"head_sha": "def", "fixable": True},
        kind="repair",
    )
    assert repair.attempts == 1 and repair.current_sha == "def" and repair.review_sha is None
    no_charge = pa.updated_state(pr(), {"fixable": False}, kind="repair")
    assert no_charge.attempts == 0
    with pytest.raises(ValueError, match="unknown record kind"):
        pa.updated_state(pr(), {}, kind="other")


def completed(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


def test_github_helpers_and_state_persistence(monkeypatch, tmp_path):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[:3] == ["gh", "repo", "view"]:
            return completed(out='{"nameWithOwner":"o/r"}')
        return completed(out="{}")

    monkeypatch.setattr(subprocess, "run", run)
    assert pa._gh_json("repo", "view") == {"nameWithOwner": "o/r"}
    state = pa.AutomationState("a", "a")
    pa.upsert_state(1, state, "new", [])
    pa.upsert_state(1, state, "edit", [{"body": pa.state_body(state, "x"), "databaseId": 9}])
    assert any(command[:3] == ["gh", "pr", "comment"] for command in calls)
    assert any("issues/comments/9" in " ".join(command) for command in calls)

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: completed(1, err="boom"))
    with pytest.raises(RuntimeError, match="gh api"):
        pa._gh_json("api", "x")
    with pytest.raises(RuntimeError, match="persist"):
        pa.upsert_state(1, state, "x", [])


def test_fetch_evaluate_record_and_labels(monkeypatch, tmp_path):
    monkeypatch.setattr(pa, "_gh_json", lambda *a: pr())
    assert pa.fetch_pr(12)["number"] == 12
    assert pa.evaluate_pr(12, "abc", cfg(tmp_path)).state == "pending"
    captured = []
    monkeypatch.setattr(pa, "upsert_state", lambda *a: captured.append(a))
    state = pa.record(12, {"head_sha": "abc", "pass": True, "summary": "ok"}, "review")
    assert state.review_passed and captured
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append(args) or completed())
    pa.ensure_labels()
    assert len(calls) == 4 and all(call[:3] == ["gh", "label", "create"] for call in calls)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"headRefOid": "new"}, "stale head"),
        ({"state": "CLOSED", "isDraft": True}, "not an open draft"),
        ({"isDraft": False}, "not an open draft"),
        ({"isDraft": True, "isCrossRepository": True}, "fork drafts"),
        ({"isDraft": True}, "no current-head"),
    ],
)
def test_ready_draft_unstable_states_are_noops(monkeypatch, tmp_path, changes, reason):
    monkeypatch.setattr(pa, "fetch_pr", lambda number: pr(**changes))
    result = pa.ready_draft(12, "abc", cfg(tmp_path))
    assert result["promoted"] is False
    assert reason in result["reason"]


@pytest.mark.parametrize("author", ("owner", "outsider"))
def test_ready_draft_promotes_green_trusted_or_reviewable_head(monkeypatch, tmp_path, author):
    draft = pr(
        isDraft=True,
        isCrossRepository=False,
        author={"login": author},
        statusCheckRollup=[check()],
    )
    monkeypatch.setattr(pa, "fetch_pr", lambda number: draft)
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args) or completed())
    assert pa.ready_draft(12, "abc", cfg(tmp_path))["promoted"] is True
    assert calls == [["gh", "pr", "ready", "12"]]


def test_ready_draft_reports_github_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pa,
        "fetch_pr",
        lambda number: pr(isDraft=True, isCrossRepository=False, statusCheckRollup=[check()]),
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(1, err="denied"))
    with pytest.raises(RuntimeError, match="could not mark PR ready"):
        pa.ready_draft(12, "abc", cfg(tmp_path))


def test_mirror_fork_success_and_failures(monkeypatch, tmp_path):
    fork = pr(
        author={"login": "alice"},
        headRepositoryOwner={"login": "alice"},
        headRepository={"name": "fork"},
    )
    monkeypatch.setattr(pa, "fetch_pr", lambda n: fork)
    calls = []

    def success(args, **kwargs):
        calls.append(args)
        if args[:3] == ["gh", "pr", "create"]:
            return completed(out="https://github.com/o/r/pull/44\n")
        return completed()

    monkeypatch.setattr(subprocess, "run", success)
    result = pa.mirror_fork(12, cfg(tmp_path))
    assert result["replacement_pr"] == 44
    assert any(command[:3] == ["gh", "pr", "close"] for command in calls)

    monkeypatch.setattr(pa, "fetch_pr", lambda n: pr(headRepositoryOwner={}, headRepository={}))
    with pytest.raises(RuntimeError, match="does not expose"):
        pa.mirror_fork(12, cfg(tmp_path))

    monkeypatch.setattr(pa, "fetch_pr", lambda n: fork)
    for failure, message in (("fetch", "fetch fork"), ("push", "publish"), ("create", "open")):

        def fail(args, failure=failure, **kwargs):
            joined = " ".join(args)
            if failure in joined or (failure == "create" and args[:3] == ["gh", "pr", "create"]):
                return completed(1, err="no")
            return completed()

        monkeypatch.setattr(subprocess, "run", fail)
        with pytest.raises(RuntimeError, match=message):
            pa.mirror_fork(12, cfg(tmp_path))
