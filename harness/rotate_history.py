#!/usr/bin/env python3
"""Size-based rotation of the session log `harness/progress/history.md`.

When it exceeds THRESHOLD bytes, the oldest entries move to
`harness/progress/archive/history-NNN.md` until it drops below KEEP (hysteresis, so it
does not rotate on every close). Cuts are always at entry boundaries and archive files
are immutable; only the header of history.md (title, note, range table) is regenerated.

Usage: python3 harness/rotate_history.py [--check | --dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

ROOT = Path(__file__).parent.parent
PROGRESS = ROOT / "harness" / "progress"
HISTORY = PROGRESS / "history.md"
ARCHIVE_DIR = PROGRESS / "archive"

THRESHOLD = 200_000
KEEP = 100_000
CHUNK = 200_000

TITLE = "# Session history"
ENTRY_RE = re.compile(r"(?m)^## (\d{4}-\d{2}-\d{2}|\?{4}-\?{2}-\?{2})(?!\S).*$")
SEPARATOR = "\n---\n\n"
SESSION_MARK = re.compile(r"(?m)^-? *\*\*Feature in progress:\*\*")


class Entry:
    def __init__(self, date: str, title: str, text: str) -> None:
        self.date = date
        self.title = title
        self.text = text.rstrip() + "\n"

    def __len__(self) -> int:
        return len(self.text.encode("utf-8"))


def parse_entries(content: str) -> list[Entry]:
    """Splits the markdown into entries in file (append) order, dropping header and separators."""
    matches = list(ENTRY_RE.finditer(content))
    entries: list[Entry] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[m.start():end].rstrip()
        # Strip every trailing "---": render() puts back exactly one, so parse→render is idempotent.
        while True:
            stripped = re.sub(r"\n*-{3,}\s*$", "", block).rstrip()
            if stripped == block:
                break
            block = stripped
        entries.append(Entry(m.group(1), m.group(0).lstrip("#").strip(), block))
    return entries


def glued_sessions(entries: list[Entry]) -> list[Entry]:
    """Entries with more than one session marker: a session archived without its `## <date>` header."""
    return [e for e in entries if len(SESSION_MARK.findall(e.text)) > 1]


def archive_files() -> list[Path]:
    if not ARCHIVE_DIR.is_dir():
        return []
    return sorted(ARCHIVE_DIR.glob("history-[0-9][0-9][0-9].md"))


def date_range(entries: list[Entry]) -> tuple[str, str]:
    dates = sorted(e.date for e in entries)
    return dates[0], dates[-1]


def render_header(active: list[Entry]) -> str:
    lines = [
        TITLE,
        "",
        "> **Append-only** log: only `harness/close.sh` writes here, archiving `current.md`",
        "> when each session closes. Do not edit by hand. Read it with `grep`, never whole.",
        ">",
        f"> Above {THRESHOLD // 1000} KB, `harness/rotate_history.py` moves the oldest entries",
        f"> to `archive/` until it is under {KEEP // 1000} KB (immutable files).",
        "",
    ]
    archives = archive_files()
    if archives:
        lines += [
            "## Archived sessions",
            "",
            "| File | Sessions | From | To |",
            "|------|---------:|------|----|",
        ]
        for path in archives:
            arch = parse_entries(path.read_text(encoding="utf-8"))
            if arch:
                start, end = date_range(arch)
                lines.append(f"| `archive/{path.name}` | {len(arch)} | {start} | {end} |")
        if active:
            start, end = date_range(active)
            lines.append(f"| `history.md` (active) | {len(active)} | {start} | {end} |")
        lines.append("")
    return "\n".join(lines)


def render(entries: list[Entry], header: str) -> str:
    """Header + entries separated by a single "---", plus a closing one (what close.sh appends after)."""
    if not entries:
        return header
    return f"{header}\n---\n\n{SEPARATOR.join(e.text for e in entries)}\n---\n"


def next_archive_index() -> int:
    existing = archive_files()
    return int(existing[-1].stem.split("-")[-1]) + 1 if existing else 1


def chunk_by_size(entries: list[Entry], limit: int) -> list[list[Entry]]:
    """Groups entries into chunks of <= limit bytes without splitting any (a huge one goes alone)."""
    chunks: list[list[Entry]] = []
    current: list[Entry] = []
    size = 0
    for entry in entries:
        if current and size + len(entry) > limit:
            chunks.append(current)
            current, size = [], 0
        current.append(entry)
        size += len(entry)
    if current:
        chunks.append(current)
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if rotation is due (no writes)")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    if not HISTORY.is_file():
        print(f"{RED}[FAIL]{NC} {HISTORY} not found")
        return 1

    content = HISTORY.read_text(encoding="utf-8")
    size = len(content.encode("utf-8"))
    entries = parse_entries(content)
    if not entries:
        print(f"{GREEN}[OK]{NC}   history.md has no session entries; nothing to rotate")
        return 0

    for entry in glued_sessions(entries):
        print(f"{YELLOW}[WARN]{NC} '{entry.title}' contains another session without its "
              f"'## <date>' header")

    if size <= THRESHOLD:
        if not (args.check or args.dry_run):
            new = render(entries, render_header(entries))
            if new != content:
                HISTORY.write_text(new, encoding="utf-8")
        print(f"{GREEN}[OK]{NC}   history.md {size // 1000} KB / {THRESHOLD // 1000} KB "
              f"({len(entries)} sessions) -- no rotation")
        return 0

    if args.check:
        print(f"{YELLOW}[WARN]{NC} history.md {size // 1000} KB exceeds "
              f"{THRESHOLD // 1000} KB -- rotation due")
        return 1

    evicted: list[Entry] = []
    active = list(entries)
    while len(active) > 1 and sum(len(e) for e in active) > KEEP:
        evicted.append(active.pop(0))

    index = next_archive_index()
    plan = [(f"history-{index + n:03d}.md", chunk)
            for n, chunk in enumerate(chunk_by_size(evicted, CHUNK))]
    for name, chunk in plan:
        start, end = date_range(chunk)
        print(f"{GREEN}[OK]{NC}   archive/{name}: {len(chunk)} sessions ({start} -> {end})")
    if args.dry_run:
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for name, chunk in plan:
        start, end = date_range(chunk)
        header = "\n".join([
            f"# Session history — {name.replace('.md', '')}",
            "",
            f"> Sessions archived from `{start}` to `{end}` ({len(chunk)} entries).",
            "> Immutable file generated by `harness/rotate_history.py`. Do not edit.",
            "",
        ])
        (ARCHIVE_DIR / name).write_text(render(chunk, header), encoding="utf-8")

    HISTORY.write_text(render(active, render_header(active)), encoding="utf-8")
    print(f"{GREEN}[OK]{NC}   history.md: {len(active)} sessions after rotation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
