# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Yanking superseded releases.

Yanking is a destructive, effectively irreversible signal applied to other people's
builds, so what is pinned here is mostly what it must REFUSE to do: never the version just
published, never a version it cannot parse, never anything at all unless asked.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from vibey_gh import yank
from vibey_gh.config import GhConfig, YankConfig


def _cfg(**kw) -> GhConfig:
    return GhConfig(root=Path("."), yank=YankConfig(**kw))


def test_it_is_off_on_both_indexes_by_default():
    """This marks other people's working builds as defective. Nobody inherits it."""
    default = YankConfig()
    assert default.pypi is False
    assert default.testpypi is False


@pytest.mark.parametrize("index", [yank.PYPI, yank.TESTPYPI])
def test_disabled_yanks_nothing(index):
    report = yank.yank_superseded(_cfg(), index, "pkg", "1.2.0", "token")
    assert report.yanked == ()
    assert report.skipped == ("disabled",)


def test_the_version_just_published_is_never_yanked():
    """The one invariant that must hold however the ordering behaves: a publish cannot
    render itself uninstallable."""
    versions = ["1.0.0", "1.1.0", "1.2.0"]
    assert "1.2.0" not in yank.supersede(versions, "1.2.0", keep=0)


def test_keep_preserves_a_rollback_target():
    versions = ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]
    assert yank.supersede(versions, "1.3.0", keep=0) == ["1.2.0", "1.1.0", "1.0.0"]
    assert yank.supersede(versions, "1.3.0", keep=1) == ["1.1.0", "1.0.0"]
    assert yank.supersede(versions, "1.3.0", keep=99) == []


def test_newer_releases_are_never_yanked():
    """Only what is BELOW the published version. A version above it is not superseded by
    it, and yanking one would be actively wrong."""
    versions = ["1.0.0", "2.0.0", "3.0.0"]
    assert yank.supersede(versions, "2.0.0", keep=0) == ["1.0.0"]


def test_a_dev_build_is_superseded_by_its_own_release():
    """`1.2.0.dev5` anticipates `1.2.0`, so publishing the release supersedes it. This is
    the whole point on TestPyPI, where every push leaves another `.devN`."""
    assert yank.order("1.2.0.dev5") < yank.order("1.2.0")
    versions = ["1.2.0.dev4", "1.2.0.dev5", "1.2.0"]
    assert yank.supersede(versions, "1.2.0", keep=0) == ["1.2.0.dev5", "1.2.0.dev4"]


@pytest.mark.parametrize(
    "version",
    [
        "1.0",
        "1.0.0.0",
        "1!1.0.0",
        "1.0.0+local",
        "1.0.0rc1",
        "not-a-version",
        "",
        "1.2.0.devX",  # a .dev suffix that is not a number
        "1.2.0.dev",  # ...or is missing entirely
    ],
)
def test_an_unparseable_version_is_left_alone(version):
    """This is not a PEP 440 implementation and does not pretend to be. Half a parser
    applied to epochs, locals and post-releases would mis-order them silently, and here
    that means yanking something good."""
    assert yank.order(version) is None
    assert yank.supersede([version], "9.9.9", keep=0) == []


def test_an_unparseable_current_version_yanks_nothing():
    assert yank.supersede(["1.0.0", "2.0.0"], "not-a-version", keep=0) == []


def test_a_missing_token_is_reported_rather_than_silently_skipped():
    report = yank.yank_superseded(_cfg(pypi=True), yank.PYPI, "pkg", "1.2.0", "")
    assert not report.ok
    assert "no token" in report.problems[0]


def _index(monkeypatch, payload: dict) -> None:
    class _Response:
        def __init__(self) -> None:
            self._body = json.dumps(payload).encode()

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(yank.urllib.request, "urlopen", lambda *a, **k: _Response())


def test_releases_already_fully_yanked_are_not_yanked_again(monkeypatch):
    """Re-yanking costs a request and reports as if something happened. It did not."""
    _index(
        monkeypatch,
        {
            "releases": {
                "1.0.0": [{"yanked": True}],
                "1.1.0": [{"yanked": False}],
                "1.2.0": [{"yanked": False}],
                "1.3.0": [],  # a release with no files at all
            }
        },
    )
    assert sorted(yank.released_versions(yank.PYPI, "pkg")) == ["1.1.0", "1.2.0"]


def test_an_unknown_project_has_no_releases(monkeypatch):
    def raise404(*a, **k):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(yank.urllib.request, "urlopen", raise404)
    assert yank.released_versions(yank.PYPI, "nope") == []


def test_an_unreachable_index_never_fails_the_release(monkeypatch):
    """The package is already published by the time this runs. A bookkeeping failure must
    not be reported as a broken release."""

    def boom(*a, **k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(yank.urllib.request, "urlopen", boom)
    report = yank.yank_superseded(_cfg(pypi=True), yank.PYPI, "pkg", "1.2.0", "token")
    assert not report.ok
    assert report.yanked == ()


def test_nothing_superseded_is_reported_as_such(monkeypatch):
    _index(monkeypatch, {"releases": {"1.2.0": [{"yanked": False}]}})
    report = yank.yank_superseded(_cfg(pypi=True), yank.PYPI, "pkg", "1.2.0", "token")
    assert report.skipped == ("nothing superseded",)
    assert report.yanked == ()


def test_each_superseded_release_is_yanked_once(monkeypatch):
    _index(
        monkeypatch,
        {
            "releases": {
                "1.0.0": [{"yanked": False}],
                "1.1.0": [{"yanked": False}],
                "1.2.0": [{"yanked": False}],
            }
        },
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(yank, "_yank_one", lambda i, p, v, r, t: calls.append((i, v)) or None)
    report = yank.yank_superseded(_cfg(pypi=True), yank.PYPI, "pkg", "1.2.0", "token")
    assert report.ok
    assert sorted(report.yanked) == ["1.0.0", "1.1.0"]
    assert [v for _, v in calls] == ["1.1.0", "1.0.0"]


def test_a_failed_yank_is_reported_without_stopping_the_others(monkeypatch):
    _index(
        monkeypatch,
        {"releases": {"1.0.0": [{"yanked": False}], "1.1.0": [{"yanked": False}]}},
    )
    monkeypatch.setattr(
        yank,
        "_yank_one",
        lambda i, p, v, r, t: "1.1.0: boom" if v == "1.1.0" else None,
    )
    report = yank.yank_superseded(_cfg(pypi=True), yank.PYPI, "pkg", "1.2.0", "token")
    assert report.yanked == ("1.0.0",)
    assert not report.ok


def test_keep_must_not_be_negative():
    with pytest.raises(ValueError, match="keep"):
        YankConfig(keep=-1)


def test_reason_must_not_be_empty():
    with pytest.raises(ValueError, match="reason"):
        YankConfig(reason="  ")


def test_a_non_404_index_error_is_not_swallowed(monkeypatch):
    """A 404 means "no such project", which is a real answer. A 500 or a 403 is not, and
    treating it as "no releases" would silently yank nothing while reporting success."""

    def raise500(*a, **k):
        raise urllib.error.HTTPError("u", 500, "Server Error", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(yank.urllib.request, "urlopen", raise500)
    with pytest.raises(urllib.error.HTTPError):
        yank.released_versions(yank.PYPI, "pkg")


def test_the_upload_call_targets_the_right_index_and_never_logs_the_token(monkeypatch):
    """The token is passed to curl, so it must not come back in an error string: these
    reports go to a job summary."""
    seen: dict[str, object] = {}

    class _Run:
        returncode = 1
        stdout = ""
        stderr = "403 Forbidden"

    def fake_run(argv, **kw):
        seen["argv"] = argv
        return _Run()

    monkeypatch.setattr(yank.subprocess, "run", fake_run)
    error = yank._yank_one(yank.TESTPYPI, "pkg", "1.0.0", "superseded", "secret-token")

    argv = seen["argv"]
    assert yank._UPLOAD[yank.TESTPYPI] in argv
    assert ":action=yank" in argv
    assert "1.0.0" in " ".join(argv)
    assert error is not None
    assert "403" in error
    assert "secret-token" not in error


def test_a_successful_upload_reports_no_error(monkeypatch):
    class _Run:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(yank.subprocess, "run", lambda *a, **k: _Run())
    assert yank._yank_one(yank.PYPI, "pkg", "1.0.0", "superseded", "t") is None


def test_a_release_whose_files_are_all_yanked_is_skipped_by_supersede(monkeypatch):
    """The already-yanked filter and the ordering meet here: a release the index reports as
    fully yanked never reaches `supersede`, so it is never re-yanked."""
    _index(
        monkeypatch,
        {"releases": {"1.0.0": [{"yanked": True}], "1.1.0": [{"yanked": False}]}},
    )
    calls: list[str] = []
    monkeypatch.setattr(yank, "_yank_one", lambda i, p, v, r, t: calls.append(v) or None)
    report = yank.yank_superseded(_cfg(pypi=True), yank.PYPI, "pkg", "1.2.0", "token")
    assert calls == ["1.1.0"]
    assert report.yanked == ("1.1.0",)


def test_the_cli_forwards_the_report_and_never_fails_the_release(monkeypatch, capsys):
    """A publish has already succeeded by the time this runs. Even a total failure to yank
    must exit 0, or a green release reports as broken."""
    from vibey_gh import cli

    monkeypatch.setattr(
        yank,
        "yank_superseded",
        lambda *a, **k: yank.YankReport(
            "pypi", yanked=("1.0.0",), skipped=("x",), problems=("boom",)
        ),
    )
    code = cli.main(["yank-superseded", "--index", "pypi", "--project", "p", "--version", "1.1.0"])
    out = capsys.readouterr()
    assert code == 0
    assert "1.0.0" in out.out
    assert "boom" in out.err


def test_the_cli_reads_the_token_from_the_environment(monkeypatch):
    from vibey_gh import cli

    seen: dict[str, str] = {}
    monkeypatch.setenv("VIBEY_GH_YANK_TOKEN", "from-env")
    monkeypatch.setattr(
        yank,
        "yank_superseded",
        lambda cfg, index, project, version, token: seen.update(token=token)
        or yank.YankReport(index),
    )
    cli.main(["yank-superseded", "--index", "pypi", "--project", "p", "--version", "1.1.0"])
    assert seen["token"] == "from-env"
