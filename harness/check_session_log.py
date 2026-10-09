#!/usr/bin/env python3
"""Session log gate: if the active backlog has `done` tasks, `current.md` must narrate them.

Without it close.sh would fall back silently to a generic `chore:` commit and append
nothing to `history.md` (feature -> commit traceability lost). Checks, only when there
are `done` tasks in `harness/feature_list.json` (before close.sh archives them):

* `current.md` is not the untouched template (same rule as close.sh's IS_TEMPLATE);
* the `Feature in progress` line carries a `#N` marker that is one of the `done` ids;
* every `done` id is cited as `#N` somewhere in `current.md`.

Usage: `python3 harness/check_session_log.py` from the repo root. Exit 1 = log missing
(close.sh turns it into its exit 3, "paused: fix and re-run").
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_LIST = Path("harness/feature_list.json")
CURRENT = Path("harness/progress/current.md")

GREEN = "\033[0;32m"
RED = "\033[0;31m"
NC = "\033[0m"

_RE_FEATURE_LINE = re.compile(r"^.*Feature in progress:\**[ \t]*(.*)$", re.MULTILINE)
_RE_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_ID = re.compile(r"#(\d+)|\[(\d+)\]")


def done_ids(path: Path = FEATURE_LIST) -> list[int]:
    """Ids of the `done` tasks in the ACTIVE backlog (`Cancelled` needs no narrative)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [f["id"] for f in data.get("features", []) if f.get("status") == "done"]


def is_template(content: str) -> bool:
    """Exact replica of close.sh's IS_TEMPLATE: placeholder line AND empty `- ...` log bullet.

    Checked per line, so a real log that quotes those markers is not mistaken for the template.
    """
    lines = content.splitlines()
    placeholder = any(
        ln.startswith("- **Feature in progress:**") and "_none_" in ln for ln in lines
    )
    empty_log = any(ln.strip() == "- ..." for ln in lines)
    return placeholder and empty_log


def marker_ids(content: str) -> list[int]:
    """Ids on the `Feature in progress` line (HTML comment stripped)."""
    m = _RE_FEATURE_LINE.search(content)
    if not m:
        return []
    value = _RE_COMMENT.sub("", m.group(1)).strip()
    return [int(a or b) for a, b in _RE_ID.findall(value)]


def is_cited(content: str, fid: int) -> bool:
    """`#<fid>` or `[<fid>]` anywhere; `\\b` keeps `#27` from matching inside `#277`."""
    return re.search(rf"#{fid}\b|\[{fid}\]", content) is not None


def check(list_path: Path = FEATURE_LIST, current_path: Path = CURRENT) -> list[str]:
    """Returns the problems found (empty = all good)."""
    pending = done_ids(list_path)
    if not pending:
        return []

    cited = ", ".join(f"#{i}" for i in pending)
    try:
        content = current_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"{current_path} does not exist but there are done tasks ({cited})."]

    if is_template(content):
        return [
            f"{current_path} is still the empty template and there are done tasks ({cited}): "
            "close.sh would commit 'chore: session close' and append nothing to history.md."
        ]

    problems: list[str] = []
    marker = marker_ids(content)
    if not marker:
        problems.append(
            f"The 'Feature in progress' line has no '#N' marker and there are done tasks "
            f"({cited}): the commit would be 'chore:' instead of 'feat(#N)'/'fix(#N)'."
        )
    elif not set(marker) & set(pending):
        problems.append(
            "The 'Feature in progress' line points to "
            + ", ".join(f"#{i}" for i in marker)
            + f", which is not among the done tasks ({cited})."
        )

    missing = [f"#{i}" for i in pending if not is_cited(content, i)]
    if missing:
        problems.append(
            "Done task(s) never mentioned in current.md: " + ", ".join(missing)
            + " — their entry would never reach history.md."
        )
    return problems


def main() -> int:
    problems = check()
    if not problems:
        print(f"{GREEN}[OK]{NC}   Session log consistent with the done tasks.")
        return 0
    for p in problems:
        print(f"{RED}[FAIL]{NC} {p}")
    print(
        f"\n{RED}Write the log in harness/progress/current.md with the marker "
        f"'- **Feature in progress:** #N feature_name' and re-run close.sh.{NC}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
