# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Enforce that every code change is attributable.

Two places, because a change can be either:

1. **Source files** carry a header comment — but only files whose language HAS comments,
   and only files that are code.
2. **Every commit** carries a trailer. This is what makes the rule total: a change to a
   Markdown document, a JSON manifest, or any generated artefact still arrives as a
   commit, and the commit is fingerprinted even when the file cannot be.

The second point is the whole design. A naive "comment in every changed file" rule cannot
express itself in JSON, and corrupts content whose bytes are meaningful — a generated
document verified against its source, or Markdown that a model loads as context. The
trailer covers those without touching them.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vibey_gh.config import GhConfig, load_config

# How far into a file the header may sit: enough for a shebang and a blank line, not
# enough for it to be buried where nobody reads.
HEAD_LINES = 5
CONVENTIONAL_SUBJECT = re.compile(r"^(?:[a-z][a-z0-9-]*)(?:\([a-z0-9][a-z0-9._/-]*\))?!?: [^\s].*$")


@dataclass
class Report:
    missing_header: list[Path]
    duplicate_header: list[Path]
    missing_trailer: list[str]
    invalid_subject: list[str]
    checked_files: int

    @property
    def ok(self) -> bool:
        return (
            not self.missing_header
            and not self.duplicate_header
            and not self.missing_trailer
            and not self.invalid_subject
        )


def conventional_subject(subject: str) -> bool:
    return bool(CONVENTIONAL_SUBJECT.fullmatch(subject.strip()))


def normalize_commit_message(message: str) -> str:
    """Return a Conventional Commit message without disturbing its body or trailers."""
    if not message:
        return message
    subject_line, separator, rest = message.partition("\n")
    carriage_return = "\r" if subject_line.endswith("\r") else ""
    subject = subject_line.removesuffix("\r").strip()
    if subject and not conventional_subject(subject):
        return f"chore: {subject}{carriage_return}{separator}{rest}"
    return message


def commits_with_invalid_subject(rev_range: str, cfg: GhConfig) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--no-merges", "--format=%H%x1f%s%x1e", rev_range],
        cwd=cfg.root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot read {rev_range}: {result.stderr.strip()}")
    invalid = []
    for record in filter(None, (item.strip("\n") for item in result.stdout.split("\x1e"))):
        sha, subject = (record.split("\x1f") + [""])[:2]
        if not conventional_subject(subject):
            invalid.append(f"{sha[:9]} {subject}")
    return invalid


def sources(cfg: GhConfig) -> list[Path]:
    seen: list[Path] = []
    for pattern in cfg.sources:
        for path in sorted(cfg.root.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.append(path)
    return seen


def header_occurrences(text: str, cfg: GhConfig) -> int:
    return sum(1 for line in text.splitlines()[:HEAD_LINES] if line.strip() == cfg.header)


def has_header(text: str, cfg: GhConfig) -> bool:
    return header_occurrences(text, cfg) > 0


def insert_header(text: str, cfg: GhConfig) -> str:
    """Header on line 1, or straight after a shebang if the file has one."""
    lines = text.splitlines(keepends=True)
    at = 1 if lines and lines[0].startswith("#!") else 0
    lines.insert(at, cfg.header + "\n")
    return "".join(lines)


def dedupe_header(text: str, cfg: GhConfig) -> str:
    """Collapse repeated header lines within the head window down to the first."""
    lines = text.splitlines(keepends=True)
    seen = False
    kept = []
    for index, line in enumerate(lines):
        if index < HEAD_LINES and line.strip() == cfg.header:
            if seen:
                continue
            seen = True
        kept.append(line)
    return "".join(kept)


def commits_missing_trailer(rev_range: str, cfg: GhConfig) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", rev_range],
        cwd=cfg.root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot read {rev_range}: {result.stderr.strip()}")

    pattern = re.compile(rf"^{re.escape(cfg.trailer_key)}:\s*\S", re.MULTILINE | re.IGNORECASE)
    missing = []
    for record in filter(None, (r.strip("\n") for r in result.stdout.split("\x1e"))):
        sha, subject, body = (record.split("\x1f") + ["", ""])[:3]
        if not pattern.search(body):
            missing.append(f"{sha[:9]} {subject}")
    return missing


def check(cfg: GhConfig | None = None, rev_range: str | None = None, apply: bool = False) -> Report:
    cfg = cfg or load_config()
    files = sources(cfg)

    occurrences = {p: header_occurrences(p.read_text(encoding="utf-8"), cfg) for p in files}
    missing = [p for p in files if occurrences[p] == 0]
    duplicated = [p for p in files if occurrences[p] > 1]
    if apply:
        for path in missing:
            path.write_text(insert_header(path.read_text(encoding="utf-8"), cfg), encoding="utf-8")
        for path in duplicated:
            path.write_text(dedupe_header(path.read_text(encoding="utf-8"), cfg), encoding="utf-8")
        missing = []
        duplicated = []

    trailers = commits_missing_trailer(rev_range, cfg) if rev_range else []
    subjects = commits_with_invalid_subject(rev_range, cfg) if rev_range else []
    return Report(
        missing_header=missing,
        duplicate_header=duplicated,
        missing_trailer=trailers,
        invalid_subject=subjects,
        checked_files=len(files),
    )
