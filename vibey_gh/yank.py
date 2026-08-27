# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Yank superseded releases from a package index after a successful publish.

What this does is narrower than it sounds, and the semantics are worth stating plainly
because the mechanism is routinely reached for to mean something it does not mean.

PEP 592 defines a yanked release as one with "a serious problem which should prevent it
from being installed". Installers still resolve it when a pin demands it, so nothing is
reclaimed and no disk is freed; what changes is that every consumer pinned to that version
starts seeing a warning about a release that may be perfectly good.

There is no standard mechanism that expresses "superseded" per release. A Development
Status classifier is per-release metadata and published distributions are immutable, so it
cannot be applied after the fact. PEP 792 project status markers — `archived`,
`deprecated`, `quarantined` — are per-PROJECT and specify only read-side APIs, so they can
neither be scoped to an old release nor set programmatically. Yanking is the only
per-release lever an index exposes.

Two invariants make it survivable anyway:

- the version just published is NEVER yanked, so a publish cannot render itself unusable;
- `keep` holds back the newest N superseded releases, so a rollback target still exists.

Both indexes are off by default. TestPyPI is the defensible one to enable: a `.devN` build
there is disposable by construction and has no consumers to mislead.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from vibey_gh.config import GhConfig

PYPI = "pypi"
TESTPYPI = "testpypi"

_INDEX_JSON = {
    PYPI: "https://pypi.org/pypi/{project}/json",
    TESTPYPI: "https://test.pypi.org/pypi/{project}/json",
}
_UPLOAD = {
    PYPI: "https://upload.pypi.org/legacy/",
    TESTPYPI: "https://test.pypi.org/legacy/",
}


@dataclass
class YankReport:
    index: str
    yanked: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    problems: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return not self.problems


def released_versions(index: str, project: str, timeout: int = 30) -> list[str]:
    """Every version the index holds that is not already yanked.

    A release whose files are all yanked is already in the state this would put it in, so
    it is not reported — re-yanking it would be a no-op that still costs a request and
    still shows up in the summary as if something happened.
    """
    url = _INDEX_JSON[index].format(project=project)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise
    versions: list[str] = []
    for version, files in (payload.get("releases") or {}).items():
        if not files:
            continue
        if all(item.get("yanked") for item in files):
            continue
        versions.append(version)
    return versions


def order(version: str) -> tuple[int, ...] | None:
    """A sortable key for `N.N.N` and `N.N.N.devN`, or None if this cannot parse it.

    Deliberately not a PEP 440 implementation. This project has no dependencies, so
    `packaging` is not available, and half a version parser applied to epochs, local
    segments and post-releases would mis-order them silently — which here means warning on
    a release that is fine. Anything outside the shape this project actually publishes
    returns None and is left alone.

    A release sorts BELOW its own dev builds' base version: `1.2.0.dev5` precedes `1.2.0`,
    which is what makes a final release supersede the dev builds that anticipated it.
    """
    base, separator, dev = version.partition(".dev")
    parts = base.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    # `separator`, not `dev`: `1.2.0.dev` has the marker and an empty number, and testing
    # the number alone let it fall through and parse as the FINAL release `1.2.0` — a
    # malformed version silently read as a real one, which is how something good gets
    # yanked.
    if separator and not dev.isdigit():
        return None
    major, minor, patch = (int(part) for part in parts)
    # A final release is (…, 1, 0); a dev build of it is (…, 0, N) and so sorts first.
    return (major, minor, patch, 0, int(dev)) if dev else (major, minor, patch, 1, 0)


def supersede(versions: list[str], current: str, keep: int) -> list[str]:
    """Which versions to yank: everything below `current`, minus the newest `keep`.

    `current` is excluded by identity, not by ordering. A publish that yanked the thing it
    had just uploaded would be worse than useless, and leaving that to a version
    comparison is one parsing quirk away from exactly that.
    """
    here = order(current)
    if here is None:
        return []
    candidates = []
    for version in versions:
        if version == current:
            continue
        other = order(version)
        if other is None:
            continue
        if other < here:
            candidates.append((other, version))
    candidates.sort(reverse=True)
    return [version for _, version in candidates[keep:]]


def _yank_one(index: str, project: str, version: str, reason: str, token: str) -> str | None:
    """Yank one release. Returns an error string, or None on success."""
    run = subprocess.run(
        [
            "curl",
            "--silent",
            "--show-error",
            "--fail",
            "--request",
            "POST",
            "--form",
            ":action=yank",
            "--form",
            f"name={project}",
            "--form",
            f"version={version}",
            "--form",
            f"reason={reason}",
            "--user",
            f"__token__:{token}",
            _UPLOAD[index],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode:
        return f"{version}: {(run.stderr or run.stdout).strip()[:200]}"
    return None


def yank_superseded(
    cfg: GhConfig, index: str, project: str, current: str, token: str
) -> YankReport:
    """Yank everything the index holds below `current`, honouring `keep`."""
    enabled = cfg.yank.pypi if index == PYPI else cfg.yank.testpypi
    if not enabled:
        return YankReport(index, skipped=("disabled",))
    if not token:
        return YankReport(index, problems=(f"no token supplied for {index}",))

    try:
        versions = released_versions(index, project)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        # Never fail the release over this. The package is already published; a failure
        # here is bookkeeping, and turning it into a red release would misreport a
        # successful publish as a broken one.
        return YankReport(index, problems=(f"could not read {index}: {error}",))

    targets = supersede(versions, current, cfg.yank.keep)
    if not targets:
        return YankReport(index, skipped=("nothing superseded",))

    yanked: list[str] = []
    problems: list[str] = []
    for version in targets:
        # Not `error`: that name belongs to the `except ... as error` above, which Python
        # deletes when the block exits, so reusing it here reads a deleted variable.
        failure = _yank_one(index, project, version, cfg.yank.reason, token)
        if failure:
            problems.append(failure)
        else:
            yanked.append(version)
    return YankReport(index, yanked=tuple(yanked), problems=tuple(problems))
