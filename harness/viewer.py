"""
Visor del harness (backlog, ideas, historial).
Ejecutar con: streamlit run harness/viewer.py --server.port 8502
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
    """Vista única del backlog: fichero activo + archivo de cerradas, ordenada por id."""
    with open(FEATURE_LIST, encoding="utf-8") as f:
        data = json.load(f)
    archive = {
        "project": data.get("project", ""),
        "description": "Archivo histórico de features cerradas (done/Cancelled).",
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
    """Reparte la vista única: done/Cancelled al archivo, el resto al fichero activo
    (reactivar una feature archivada desde el viewer la devuelve al activo)."""
    features = data["features"]
    active = {k: v for k, v in data.items() if k not in ("features", "_archive_meta")}
    active["features"] = [f for f in features if f.get("status", "pending") not in ("done", "Cancelled")]
    archive = dict(data.get("_archive_meta", {}))
    archive["features"] = [f for f in features if f.get("status", "pending") in ("done", "Cancelled")]
    _write_json(FEATURE_LIST, active)
    _write_json(FEATURE_ARCHIVE, archive)


def parse_ideas(content: str) -> tuple:
    """Separa IDEAS.md en cabecera (todo lo anterior al primer '---') y lista de
    ideas [{'title', 'description'}], una por bloque separado por '---'."""
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
    """Reescribe IDEAS.md preservando la cabecera tal cual y una idea por bloque."""
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

tab_features, tab_history, tab_ideas = st.tabs(["📋 Features", "📖 Historial", "💡 Ideas"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB: HISTORIAL
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📖 Historial de sesiones")

    col_cur, col_hist = st.columns([1, 2])

    with col_cur:
        st.markdown("**Sesión actual** (`progress/current.md`)")
        if CURRENT_MD.exists():
            st.markdown(CURRENT_MD.read_text(encoding="utf-8"))
        else:
            st.info("progress/current.md no encontrado.")

    with col_hist:
        st.markdown("**Bitácora histórica** (`progress/history.md`)")
        if HISTORY_MD.exists():
            content = HISTORY_MD.read_text(encoding="utf-8")
            # Mostrar las entradas más recientes primero (split por "---")
            entries = [e.strip() for e in content.split("---") if e.strip()]
            for entry in reversed(entries):
                if entry.startswith("#"):
                    # Extraer la primera línea como título del expander
                    lines = entry.splitlines()
                    title = lines[0].lstrip("#").strip()
                    body = "\n".join(lines[1:]).strip()
                    with st.expander(title, expanded=(entry == entries[-1])):
                        st.markdown(body)
                else:
                    st.markdown(entry)
        else:
            st.info("progress/history.md no encontrado.")

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
    st.progress(progress, text=f"Progreso: {done_n}/{total_w_o_cancelled} completadas ({progress:.0%})")

    st.divider()

    # ── Filters ───────────────────────────────────────────────────────────────
    col_filter, col_sort = st.columns([3, 1])
    with col_filter:
        all_statuses = list(STATUS_CONFIG.keys())
        default_statuses = [e for e in all_statuses if e not in DEFAULT_STATUS_HIDDEN]
        selected_statuses = st.multiselect(
            "Filtrar por estado",
            options=all_statuses,
            default=default_statuses,
            format_func=lambda s: STATUS_CONFIG[s]["label"],
        )
    with col_sort:
        sort_by = st.selectbox("Ordenar por", ["ID", "Estado", "Nombre"])

    visible = [f for f in features if f.get("status") in selected_statuses]
    if sort_by == "ID":
        visible = sorted(visible, key=lambda f: f["id"])
    elif sort_by == "Estado":
        visible = sorted(visible, key=lambda f: STATUS_CONFIG.get(f.get("status", ""), {}).get("order", 99))
    else:
        visible = sorted(visible, key=lambda f: f.get("name", ""))

    # ── Feature cards ─────────────────────────────────────────────────────────
    st.subheader(f"Features ({len(visible)} visibles)")

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
                        "Cambiar a",
                        options=["—"] + options,
                        key=f"sel_{feat['id']}",
                        label_visibility="collapsed",
                    )
                    if new_status != "—":
                        feat["status"] = new_status
                        save(data)
                        st.rerun()

            st.markdown("---", unsafe_allow_html=False)

    st.caption("Las features nuevas se dan de alta con las skills `/add-feature` y `/add-bug`.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: IDEAS
# ══════════════════════════════════════════════════════════════════════════════
with tab_ideas:
    st.subheader("💡 Ideas (`docs/IDEAS.md`)")

    if not IDEAS_MD.exists():
        st.info("docs/IDEAS.md no encontrado en el repo.")
    else:
        ideas_header, ideas = parse_ideas(IDEAS_MD.read_text(encoding="utf-8"))
        st.caption(
            f"{len(ideas)} ideas · cuaderno personal: se edita solo desde aquí o a mano, "
            "nunca por agentes."
        )

        # ── Añadir idea ───────────────────────────────────────────────────────
        with st.form("add_idea", clear_on_submit=True):
            st.markdown("**➕ Añadir idea**")
            add_title = st.text_input("Título", placeholder="ej: Gráficos con etiquetas en barras")
            add_desc = st.text_area(
                "Descripción", height=110,
                placeholder="Detalle de la idea (opcional).",
            )
            if st.form_submit_button("Añadir idea", type="primary"):
                if not add_title.strip():
                    st.error("El título es obligatorio.")
                else:
                    ideas.append({"title": add_title.strip(), "description": add_desc.strip()})
                    save_ideas(ideas_header, ideas)
                    st.rerun()

        st.divider()

        # ── Listado + edición ─────────────────────────────────────────────────
        for i, idea in enumerate(ideas):
            idea_key = hashlib.md5(
                f"{idea['title']}\x00{idea['description']}".encode()
            ).hexdigest()[:10]
            col_top, col_up, col_down, col_bottom, col_expander = st.columns(
                [0.04, 0.04, 0.04, 0.04, 0.84]
            )
            with col_top:
                if st.button(
                    "⏫", key=f"idea_top_{i}", disabled=(i == 0), help="Subir al principio",
                ):
                    ideas.insert(0, ideas.pop(i))
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_up:
                if st.button("▲", key=f"idea_up_{i}", disabled=(i == 0), help="Subir idea"):
                    ideas[i - 1], ideas[i] = ideas[i], ideas[i - 1]
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_down:
                if st.button(
                    "▼", key=f"idea_down_{i}", disabled=(i == len(ideas) - 1), help="Bajar idea",
                ):
                    ideas[i + 1], ideas[i] = ideas[i], ideas[i + 1]
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_bottom:
                if st.button(
                    "⏬", key=f"idea_bottom_{i}", disabled=(i == len(ideas) - 1),
                    help="Bajar al final",
                ):
                    ideas.append(ideas.pop(i))
                    save_ideas(ideas_header, ideas)
                    st.rerun()
            with col_expander, st.expander(f"💡 {idea['title'] or '(sin título)'}"):
                if idea["description"]:
                    st.markdown(idea["description"])
                    st.markdown("---")
                with st.form(f"edit_idea_{idea_key}"):
                    edit_title = st.text_input(
                        "Título", value=idea["title"], key=f"idea_t_{idea_key}",
                    )
                    edit_desc = st.text_area(
                        "Descripción", value=idea["description"], height=140,
                        key=f"idea_d_{idea_key}",
                    )
                    confirm_delete = st.checkbox(
                        "Confirmar borrado", key=f"idea_del_{idea_key}",
                        help="Marca esta casilla antes de pulsar Eliminar idea.",
                    )
                    col_save, col_del = st.columns(2)
                    save_clicked = col_save.form_submit_button("Guardar cambios")
                    delete_clicked = col_del.form_submit_button("🗑️ Eliminar idea")

                    if save_clicked:
                        if not edit_title.strip():
                            st.error("El título es obligatorio.")
                        else:
                            ideas[i] = {
                                "title": edit_title.strip(),
                                "description": edit_desc.strip(),
                            }
                            save_ideas(ideas_header, ideas)
                            st.rerun()
                    elif delete_clicked:
                        if not confirm_delete:
                            st.error("Marca 'Confirmar borrado' para eliminar la idea.")
                        else:
                            del ideas[i]
                            save_ideas(ideas_header, ideas)
                            st.rerun()
