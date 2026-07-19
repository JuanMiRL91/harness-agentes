"""
Harness viewer (backlog, ideas, session history).
Run with: streamlit run harness/viewer.py --server.port 8502
"""

import hashlib
import json
import os
import re
from pathlib import Path

import streamlit as st

HARNESS = Path(__file__).parent
FEATURE_LIST = HARNESS / "feature_list.json"
FEATURE_ARCHIVE = HARNESS / "feature_list_archive.json"
HISTORY_MD = HARNESS / "progress" / "history.md"
CURRENT_MD = HARNESS / "progress" / "current.md"
IDEAS_MD = HARNESS.parent / "docs" / "IDEAS.md"

STATUS_CONFIG = {
    "done":        {"label": "✅ Done",       "color": "#1a7a4a", "bg": "#d4edda", "order": 0},
    "in_progress": {"label": "🔄 In progress", "color": "#856404", "bg": "#fff3cd", "order": 1},
    "pending":     {"label": "⏳ Pending",     "color": "#1a4a7a", "bg": "#d0e4f7", "order": 2},
    "blocked":     {"label": "🚫 Blocked",     "color": "#7a1a1a", "bg": "#f8d7da", "order": 3},
    "Postponed":   {"label": "⏸️ Postponed",   "color": "#555555", "bg": "#e2e3e5", "order": 4},
    "Cancelled":   {"label": "❌ Cancelled",   "color": "#6c2020", "bg": "#eddada", "order": 5},
}

DEFAULT_STATUS_HIDDEN = {"done", "blocked", "Postponed", "Cancelled"}


def load() -> dict:
    """Single backlog view: active file + archive of closed tasks, sorted by id."""
    with open(FEATURE_LIST, encoding="utf-8") as f:
        data = json.load(f)
    archive = {
        "project": data.get("project", ""),
        "description": "Historical archive of closed features (done/Cancelled).",
        "rules": data.get("rules", {}),
        "features": [],
    }
    if FEATURE_ARCHIVE.exists():
        with open(FEATURE_ARCHIVE, encoding="utf-8") as f:
            archive = json.load(f)
    data["_archive_meta"] = {k: v for k, v in archive.items() if k != "features"}
    data["features"] = sorted(data["features"] + archive["features"], key=lambda f: f["id"])
    return data


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def save(data: dict) -> None:
    """Splits the single view: done/Cancelled to the archive, the rest to the active
    file (reactivating an archived feature from the viewer returns it to active)."""
    features = data["features"]
    active = {k: v for k, v in data.items() if k not in ("features", "_archive_meta")}
    active["features"] = [f for f in features if f.get("status", "pending") not in ("done", "Cancelled")]
    archive = dict(data.get("_archive_meta", {}))
    archive["features"] = [f for f in features if f.get("status", "pending") in ("done", "Cancelled")]
    _write_json(FEATURE_LIST, active)
    _write_json(FEATURE_ARCHIVE, archive)


def parse_ideas(content: str) -> tuple:
    """Splits IDEAS.md into a header (everything before the first '---') and a list
    of ideas [{'title', 'description'}], one per block separated by '---'."""
    segments = re.split(r"^---\s*$", content, flags=re.MULTILINE)
    header = segments[0].rstrip()
    ideas = []
    for seg in segments[1:]:
        seg = seg.strip()
        if not seg:
            continue
        lines = seg.splitlines()
        title, body_lines = "", lines
        if lines[0].lstrip().startswith("##"):
            title = lines[0].lstrip("#").strip()
            body_lines = lines[1:]
        ideas.append({"title": title, "description": "\n".join(body_lines).strip()})
    return header, ideas


def save_ideas(header: str, ideas: list) -> None:
    """Rewrites IDEAS.md preserving the header as-is and one idea per block."""
    blocks = [header.rstrip()]
    for idea in ideas:
        lines = []
        if idea["title"].strip():
            lines.append(f"## {idea['title'].strip()}")
        if idea["description"].strip():
            lines.append(idea["description"].strip())
        blocks.append("\n".join(lines))
    content = "\n\n---\n\n".join(blocks).rstrip() + "\n"
    tmp = IDEAS_MD.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, IDEAS_MD)


def status_badge(status: str) -> str:
    cfg = STATUS_CONFIG.get(status, {"label": status, "color": "#333", "bg": "#eee"})
    return (
        f'<span style="background:{cfg["bg"]};color:{cfg["color"]};'
        f'padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;">'
        f'{cfg["label"]}</span>'
    )


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Harness",
    page_icon="🗂️",
    layout="wide",
)

st.markdown("""
<style>
.feature-card {
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
    background: #fff;
}
.feature-id {
    font-size: 0.72rem;
    color: #888;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.feature-title {
    font-size: 1.05rem;
    font-weight: 700;
    margin: 4px 0 2px;
    color: #1a1a2e;
}
.feature-desc {
    font-size: 0.88rem;
    color: #555;
    margin: 6px 0 10px;
}
.acceptance-item {
    font-size: 0.82rem;
    color: #444;
    margin: 2px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
data = load()
features = data["features"]

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🗂️ Harness")
st.caption(data.get("description", ""))

tab_features, tab_history, tab_ideas = st.tabs(["📋 Features", "📖 History", "💡 Ideas"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB: HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📖 Session history")

    col_cur, col_hist = st.columns([1, 2])

    with col_cur:
        st.markdown("**Current session** (`progress/current.md`)")
        if CURRENT_MD.exists():
            st.markdown(CURRENT_MD.read_text(encoding="utf-8"))
        else:
            st.info("progress/current.md not found.")

    with col_hist:
        st.markdown("**Historical log** (`progress/history.md`)")
        if HISTORY_MD.exists():
            content = HISTORY_MD.read_text(encoding="utf-8")
            # Show the most recent entries first (split by "---")
            entries = [e.strip() for e in content.split("---") if e.strip()]
            for entry in reversed(entries):
                if entry.startswith("#"):
                    # Extract the first line as the expander title
                    lines = entry.splitlines()
                    title = lines[0].lstrip("#").strip()
                    body = "\n".join(lines[1:]).strip()
                    with st.expander(title, expanded=(entry == entries[-1])):
                        st.markdown(body)
                else:
                    st.markdown(entry)
        else:
            st.info("progress/history.md not found.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: FEATURES
# ══════════════════════════════════════════════════════════════════════════════
with tab_features:

    # ── Progress summary ───────────────────────────────────────────────────────
    counts = {s: 0 for s in STATUS_CONFIG}
    for f in features:
        counts[f.get("status", "pending")] = counts.get(f.get("status", "pending"), 0) + 1

    total = len(features)
    done_n = counts.get("done", 0)
    total_w_o_cancelled = total - counts.get("Cancelled", 0)

    cols = st.columns(len(STATUS_CONFIG) + 1)
    cols[0].metric("Total features", total)
    for i, (status, cfg) in enumerate(STATUS_CONFIG.items()):
        cols[i + 1].metric(cfg["label"], counts.get(status, 0))

    progress = done_n / total_w_o_cancelled if total_w_o_cancelled else 0
    st.progress(progress, text=f"Progress: {done_n}/{total_w_o_cancelled} completed ({progress:.0%})")

    st.divider()

    # ── Filters ───────────────────────────────────────────────────────────────
    col_filter, col_sort = st.columns([3, 1])
    with col_filter:
        all_statuses = list(STATUS_CONFIG.keys())
        default_statuses = [e for e in all_statuses if e not in DEFAULT_STATUS_HIDDEN]
        selected_statuses = st.multiselect(
            "Filter by status",
            options=all_statuses,
            default=default_statuses,
            format_func=lambda s: STATUS_CONFIG[s]["label"],
        )
    with col_sort:
        sort_by = st.selectbox("Sort by", ["ID", "Status", "Name"])

    visible = [f for f in features if f.get("status") in selected_statuses]
    if sort_by == "ID":
        visible = sorted(visible, key=lambda f: f["id"])
    elif sort_by == "Status":
        visible = sorted(visible, key=lambda f: STATUS_CONFIG.get(f.get("status", ""), {}).get("order", 99))
    else:
        visible = sorted(visible, key=lambda f: f.get("name", ""))

    # ── Feature cards ─────────────────────────────────────────────────────────
    st.subheader(f"Features ({len(visible)} visible)")

    for feat in visible:
        status = feat.get("status", "pending")
        cfg = STATUS_CONFIG.get(status, {"label": status, "color": "#333", "bg": "#eee"})

        with st.container():
            st.markdown(
                f'<div class="feature-card" style="border-left: 4px solid {cfg["color"]};">'
                f'<div class="feature-id">#{feat["id"]} · {feat["name"]}</div>'
                f'<div class="feature-title">{feat["title"]}</div>'
                f'<div class="feature-desc">{feat.get("description", "")}</div>'
                + "".join(
                    f'<div class="acceptance-item">{"✓" if status == "done" else "○"} {a}</div>'
                    for a in feat.get("acceptance", [])
                )
                + "</div>",
                unsafe_allow_html=True,
            )

            action_cols = st.columns([1, 1, 6])
            with action_cols[0]:
                st.markdown(status_badge(status), unsafe_allow_html=True)

            transitions = {
                "pending":     ["in_progress", "Postponed", "Cancelled"],
                "in_progress": ["done", "blocked", "pending"],
                "blocked":     ["pending", "in_progress", "Cancelled"],
                "Postponed":   ["pending", "Cancelled"],
                "Cancelled":   ["pending"],
                "done":        [],
            }
            options = transitions.get(status, [])

            if options:
                with action_cols[1]:
                    new_status = st.selectbox(
                        "Change to",
                        options=["—"] + options,
                        key=f"sel_{feat['id']}",
                        label_visibility="collapsed",
                    )
                    if new_status != "—":
                        feat["status"] = new_status
                        save(data)
                        st.rerun()

            st.markdown("---", unsafe_allow_html=False)

    st.caption("New features are registered with the `/add-feature` and `/add-bug` skills.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: IDEAS
# ══════════════════════════════════════════════════════════════════════════════
with tab_ideas:
    st.subheader("💡 Ideas (`docs/IDEAS.md`)")

    if not IDEAS_MD.exists():
        st.info("docs/IDEAS.md not found in the repo.")
    else:
        ideas_header, ideas = parse_ideas(IDEAS_MD.read_text(encoding="utf-8"))
        st.caption(
            f"{len(ideas)} ideas · personal notebook: edited only from here or by hand, "
            "never by agents."
        )

        # ── Add idea ──────────────────────────────────────────────────────────
        with st.form("add_idea", clear_on_submit=True):
            st.markdown("**➕ Add idea**")
            add_title = st.text_input("Title", placeholder="e.g.: Charts with bar labels")
            add_desc = st.text_area(
                "Description", height=110,
                placeholder="Detail of the idea (optional).",
            )
            if st.form_submit_button("Add idea", type="primary"):
                if not add_title.strip():
                    st.error("The title is mandatory.")
                else:
                    ideas.append({"title": add_title.strip(), "description": add_desc.strip()})
                    save_ideas(ideas_header, ideas)
                    st.rerun()

        st.divider()

        # ── List + editing ────────────────────────────────────────────────────
        for i, idea in enumerate(ideas):
            idea_key = hashlib.md5(
                f"{idea['title']}\x00{idea['description']}".encode()
            ).hexdigest()[:10]
            col_top, col_up, col_down, col_bottom, col_expander = st.columns(
                [0.04, 0.04, 0.04, 0.04, 0.84]
            )
            with col_top:
                if st.button(
                    "⏫", key=f"idea_top_{i}", disabled=(i == 0), help="Move to top",
                ):
                    ideas.insert(0, ideas.pop(i))
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_up:
                if st.button("▲", key=f"idea_up_{i}", disabled=(i == 0), help="Move idea up"):
                    ideas[i - 1], ideas[i] = ideas[i], ideas[i - 1]
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_down:
                if st.button(
                    "▼", key=f"idea_down_{i}", disabled=(i == len(ideas) - 1), help="Move idea down",
                ):
                    ideas[i + 1], ideas[i] = ideas[i], ideas[i + 1]
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_bottom:
                if st.button(
                    "⏬", key=f"idea_bottom_{i}", disabled=(i == len(ideas) - 1),
                    help="Move to bottom",
                ):
                    ideas.append(ideas.pop(i))
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_expander, st.expander(f"💡 {idea['title'] or '(untitled)'}"):
                if idea["description"]:
                    st.markdown(idea["description"])
                    st.markdown("---")
                with st.form(f"edit_idea_{idea_key}"):
                    edit_title = st.text_input(
                        "Title", value=idea["title"], key=f"idea_t_{idea_key}",
                    )
                    edit_desc = st.text_area(
                        "Description", value=idea["description"], height=140,
                        key=f"idea_d_{idea_key}",
                    )
                    confirm_delete = st.checkbox(
                        "Confirm deletion", key=f"idea_del_{idea_key}",
                        help="Check this box before pressing Delete idea.",
                    )
                    col_save, col_del = st.columns(2)
                    save_clicked = col_save.form_submit_button("Save changes")
                    delete_clicked = col_del.form_submit_button("🗑️ Delete idea")

                    if save_clicked:
                        if not edit_title.strip():
                            st.error("The title is mandatory.")
                        else:
                            ideas[i] = {
                                "title": edit_title.strip(),
                                "description": edit_desc.strip(),
                            }
                            save_ideas(ideas_header, ideas)
                            st.rerun()
                    elif delete_clicked:
                        if not confirm_delete:
                            st.error("Check 'Confirm deletion' to delete the idea.")
                        else:
                            del ideas[i]
                            save_ideas(ideas_header, ideas)
                            st.rerun()
