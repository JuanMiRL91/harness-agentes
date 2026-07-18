#!/usr/bin/env bash
# harness/close.sh — Protocolo de cierre de sesión.
# Ejecutar cuando una feature quede marcada como "done" en feature_list.json.
# Uso: ./harness/close.sh  (desde la raíz del proyecto)
#
# Pasos:
#   1. Verifica que init.sh pasa al 100%
#   2. Lee la feature recién completada desde progress/current.md
#   3. Detecta cambios en core/ o ui/ y advierte si ni harness/docs/architecture.md
#      ni harness/docs/data-models.md fueron tocados; cruza además los símbolos
#      públicos del diff contra los docs (harness/check_docs.py, determinista)
#   3b. Si el commit es un fix (BUG_), recuerda el ciclo sistémico bug→check del harness
#   3c. Avisa si CLAUDE.md supera los 40.000 caracteres (debe mantenerse mínimo;
#      el detalle va a architecture.md/data-models.md, el changelog a history.md)
#   3d. Archiva las features done/Cancelled en harness/feature_list_archive.json
#      (el fichero activo queda solo con tareas abiertas; ids globales entre ambos)
#   4. Mueve progress/current.md al final de progress/history.md y lo resetea
#   5. Hace commit automático con mensaje convencional
#
# Códigos de salida:
#   0 = sesión cerrada (commit hecho, o nada que commitear)
#   1 = error (init.sh en rojo, o la feature de current.md no está "done")
#   3 = pausado: docs pendientes o CLAUDE.md >40k — corrige y re-ejecuta close.sh
#       (con stdin no interactivo, p. ej. un agente, la pausa es automática)

set -euo pipefail

# Windows: cuando stdout de Python NO es una consola real (aquí, capturado por
# `$(...)` de bash), Python usa el códec de la página de códigos ANSI del
# sistema (p.ej. cp1252 en Windows en español) en vez de UTF-8 — corrompe
# cualquier tilde/— que los bloques `"$PY" -c "..."` de este script escriban
# a stdout para que bash los recoja (reproducido con el em-dash del header de
# history.md). Forzar UTF-8 aquí es un no-op en Linux/macOS (ya usan UTF-8).
export PYTHONIOENCODING=utf-8

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Detectar ejecutable Python (igual que init.sh)
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python3"
elif python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python"
else
    PY="python3"
fi

CURRENT="harness/progress/current.md"
HISTORY="harness/progress/history.md"
FEATURE_LIST="harness/feature_list.json"
FEATURE_ARCHIVE="harness/feature_list_archive.json"

echo "========================================"
echo "  $(basename "$ROOT") — close.sh"
echo "========================================"
echo ""

# ── 1. Entorno verde ──────────────────────────────────────────────────────────
echo "▸ Verificando entorno (harness/init.sh)..."
echo ""
if ! bash harness/init.sh; then
    echo ""
    fail "init.sh no pasa. Resuelve los errores antes de cerrar la sesión."
    exit 1
fi
echo ""

# ── 2. Detectar feature completada ───────────────────────────────────────────
echo "▸ Feature completada"

# Leer de current.md (antes de resetear)
FEATURE_LINE=$(grep -m1 "Feature en curso" "$CURRENT" 2>/dev/null || true)
FEATURE_ID=""
FEATURE_NAME=""

if echo "$FEATURE_LINE" | grep -qE "#[0-9]+"; then
    FEATURE_ID=$(echo "$FEATURE_LINE" | grep -oE "#[0-9]+" | head -1 | tr -d '#')
    # Extraer nombre de feature_list.json por id
    FEATURE_DATA=$("$PY" - <<PYEOF
import json, os
feat = None
for path in ("$FEATURE_LIST", "$FEATURE_ARCHIVE"):
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    feat = next((x for x in data["features"] if str(x["id"]) == "$FEATURE_ID"), None)
    if feat:
        break
if feat:
    print(f"{feat['name']}|{feat['title']}|{feat['status']}")
PYEOF
)
    FEATURE_NAME=$(echo "$FEATURE_DATA" | cut -d'|' -f1)
    FEATURE_TITLE=$(echo "$FEATURE_DATA" | cut -d'|' -f2)
    FEATURE_STATUS=$(echo "$FEATURE_DATA" | cut -d'|' -f3)

    if [ "$FEATURE_STATUS" != "done" ]; then
        warn "La feature #$FEATURE_ID ($FEATURE_NAME) no está marcada como 'done' en feature_list.json."
        warn "Márcala como done antes de cerrar la sesión."
        exit 1
    fi

    # Tipo de commit: fix para bugs, feat para el resto
    if echo "$FEATURE_NAME" | grep -qi "^BUG_"; then
        COMMIT_TYPE="fix"
    else
        COMMIT_TYPE="feat"
    fi

    ok "Feature #$FEATURE_ID: $FEATURE_NAME — $FEATURE_TITLE"
else
    COMMIT_TYPE="chore"
    # Sin #id: usar el texto de "Feature en curso" como título del chore (sesiones de
    # infraestructura sin entrada en el backlog).
    CHORE_TITLE=$(echo "$FEATURE_LINE" | sed -E 's/.*Feature en curso:\*{0,2}//; s/<!--.*-->//; s/^[[:space:]_]+//; s/[[:space:]_]+$//')
    if [ -n "$CHORE_TITLE" ] && [ "$CHORE_TITLE" != "ninguna" ]; then
        FEATURE_TITLE="$CHORE_TITLE"
        info "Sin id de feature — commit como 'chore: ${CHORE_TITLE}'."
    else
        warn "No se encontró referencia a feature en progress/current.md."
        info "El commit usará el mensaje genérico 'chore: cierre de sesión'."
        FEATURE_TITLE="cierre de sesión"
    fi
fi
echo ""

# ── 3. ¿Necesitan actualización architecture.md / data-models.md? ────────────
echo "▸ Comprobando documentación (harness/docs/architecture.md / data-models.md)"

# Ficheros de code modificados (staged + unstaged)
CHANGED_CODE=$(git status --porcelain -- core/ ui/ 2>/dev/null | wc -l | tr -d ' ')

if [ "$CHANGED_CODE" -gt 0 ]; then
    info "Hay $CHANGED_CODE fichero(s) modificado(s) en core/ o ui/."

    ARCH_CHANGED=$(git status --porcelain -- harness/docs/architecture.md 2>/dev/null | wc -l | tr -d ' ')
    DM_CHANGED=$(git status --porcelain -- harness/docs/data-models.md 2>/dev/null | wc -l | tr -d ' ')
    NEEDS_CONFIRM=0

    if [ "$ARCH_CHANGED" -eq 0 ] && [ "$DM_CHANGED" -eq 0 ]; then
        warn "Ni harness/docs/architecture.md ni data-models.md fueron modificados — ¿dónde queda documentado el cambio?"
        warn "Módulos/funciones/decisiones → architecture.md · esquemas JSON → data-models.md ·"
        warn "changelog → progress/current.md (lo archiva este script) · CLAUDE.md solo si cambia el mapa de una línea."
        NEEDS_CONFIRM=1
    else
        [ "$ARCH_CHANGED" -gt 0 ] && ok "harness/docs/architecture.md actualizado"
        [ "$DM_CHANGED" -gt 0 ] && ok "harness/docs/data-models.md actualizado"
    fi

    # Cruce determinista: símbolos públicos añadidos/eliminados en el diff vs
    # menciones en architecture.md / data-models.md / CLAUDE.md (lista exacta,
    # no solo "¿se tocó el doc?") + cobertura de todos los módulos core/ y ui/
    # en la sección Estructura de README.md
    if [ -f harness/check_docs.py ]; then
        if ! "$PY" harness/check_docs.py; then
            NEEDS_CONFIRM=1
        fi
    fi

    if [ "$NEEDS_CONFIRM" -eq 1 ]; then
        echo ""
        if [ -t 0 ]; then
            echo -e "${YELLOW}  ¿Proceder igualmente sin actualizar los docs? [s/N]${NC} \c"
            read -r RESPUESTA || RESPUESTA=""
        else
            RESPUESTA="N"
            warn "stdin no interactivo — pausa automática (un agente no puede saltarse este aviso)."
        fi
        if [[ ! "$RESPUESTA" =~ ^[sS]$ ]]; then
            warn "Sesión pausada (exit 3). Actualiza los docs y vuelve a ejecutar ./harness/close.sh"
            exit 3
        fi
    fi
else
    ok "Sin cambios en core/ o ui/ — docs no requieren actualización"
fi
echo ""

# ── 3b. Bug cerrado → mejora sistémica del harness ───────────────────────────
if [ "${COMMIT_TYPE:-}" = "fix" ]; then
    echo "▸ Ciclo sistémico (bug → check del harness)"
    HARNESS_CHANGED=$(git status --porcelain -- harness/ .claude/ 2>/dev/null | wc -l | tr -d ' ')
    if [ "$HARNESS_CHANGED" -eq 0 ]; then
        warn "Cierras un BUG_ sin cambios en harness/ ni .claude/ — ¿qué check habría detectado este bug antes?"
        warn "Si existe uno razonable, añádelo (skill improve-harness) antes de cerrar; si no aplica, anótalo en current.md ('Check sistémico: no aplica — motivo')."
    else
        ok "El fix incluye cambios en harness/ o .claude/ (ciclo sistémico atendido)"
    fi
    echo ""
fi

# ── 3c. CLAUDE.md debe mantenerse mínimo (≤40.000 caracteres) ─────────────────
echo "▸ Tamaño de CLAUDE.md"
CLAUDE_CHARS=$("$PY" -c "print(len(open('CLAUDE.md', encoding='utf-8').read()))" 2>/dev/null || echo 0)
if [ "$CLAUDE_CHARS" -gt 40000 ]; then
    warn "CLAUDE.md tiene $CLAUDE_CHARS caracteres (límite: 40000) — se inyecta entero en cada sesión."
    warn "Mueve el detalle a harness/docs/architecture.md o data-models.md; el changelog va a progress/history.md."
    if [ -t 0 ]; then
        echo -e "${YELLOW}  ¿Proceder igualmente con CLAUDE.md por encima del límite? [s/N]${NC} \c"
        read -r RESPUESTA_CLAUDE || RESPUESTA_CLAUDE=""
    else
        RESPUESTA_CLAUDE="N"
        warn "stdin no interactivo — pausa automática (un agente no puede saltarse este aviso)."
    fi
    if [[ ! "$RESPUESTA_CLAUDE" =~ ^[sS]$ ]]; then
        warn "Sesión pausada (exit 3). Reduce CLAUDE.md y vuelve a ejecutar ./harness/close.sh"
        exit 3
    fi
else
    ok "CLAUDE.md dentro del límite ($CLAUDE_CHARS / 40000 caracteres)"
fi
echo ""

# ── 3d. Archivar features cerradas ────────────────────────────────────────────
echo "▸ Archivando features cerradas (done/Cancelled → feature_list_archive.json)"
ARCHIVED_N=$("$PY" - <<'PYEOF'
import json

ACTIVE = "harness/feature_list.json"
ARCHIVE = "harness/feature_list_archive.json"

with open(ACTIVE, encoding="utf-8") as f:
    active = json.load(f)

try:
    with open(ARCHIVE, encoding="utf-8") as f:
        archive = json.load(f)
except FileNotFoundError:
    archive = {
        "project": active.get("project", ""),
        "description": "Archivo historico de features cerradas (done/Cancelled), "
                       "movidas aqui por close.sh. Ids globales con feature_list.json: "
                       "nunca se reutilizan ni se renumeran.",
        "rules": active.get("rules", {}),
        "features": [],
    }

closed = [f for f in active["features"] if f["status"] in ("done", "Cancelled")]
if closed:
    archive["features"].extend(closed)
    archive["features"].sort(key=lambda f: f["id"])
    active["features"] = [f for f in active["features"] if f["status"] not in ("done", "Cancelled")]
    for path, data in ((ACTIVE, active), (ARCHIVE, archive)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
print(len(closed))
PYEOF
)
if [ "${ARCHIVED_N:-0}" -gt 0 ]; then
    ok "${ARCHIVED_N} feature(s) archivada(s) en harness/feature_list_archive.json"
else
    ok "Nada que archivar (sin done/Cancelled en el fichero activo)"
fi
echo ""

# ── 4. Actualizar progress/ ───────────────────────────────────────────────────
echo "▸ Actualizando progress/"

IS_TEMPLATE=$("$PY" -c "
import re, sys
content = open('$CURRENT', encoding='utf-8').read()
# Plantilla vacía = tiene la línea de ninguna feature y ningún contenido real en Bitácora
empty = ('_ninguna_' in content) and ('- ...' in content)
print('1' if empty else '0')
")

if [ "$IS_TEMPLATE" = "0" ]; then
    TRANSFORMED=$("$PY" -c "
import re, sys
content = open('$CURRENT', encoding='utf-8').read()
content = re.sub(r'^> .*\n', '', content, flags=re.MULTILINE)
content = re.sub(r'\n{3,}', '\n\n', content)
date_m = re.search(r'\*\*Inicio:\*\*\s*(\d{4}-\d{2}-\d{2})', content)
date_str = date_m.group(1) if date_m else '????-??-??'
feat_line_m = re.search(r'\*\*Feature en curso:\*\*\s*(.+)', content)
header = None
if feat_line_m:
    val = re.sub(r'<!--.*?-->', '', feat_line_m.group(1)).strip()
    # Acepta '#N nombre', 'nombre (#N)', 'nombre [N]' — el orden y el
    # delimitador han variado entre sesiones, así que se busca el id en
    # cualquier posición en vez de exigir que vaya primero.
    id_m = re.search(r'#(\d+)|\[(\d+)\]', val)
    if id_m and val != '_ninguna_':
        fid = id_m.group(1) or id_m.group(2)
        name_part = (val[:id_m.start()] + val[id_m.end():]).strip(' ()[]' + chr(96) + ':')
        name_part = re.sub(r'^Feature\s+', '', name_part, flags=re.IGNORECASE).strip()
        if name_part:
            header = '## ' + date_str + ' — #' + fid + ' ' + name_part
if not header:
    header = '## ' + date_str + ' — Sesión cerrada'
content = re.sub(r'^# Ses.*', header, content, count=1, flags=re.MULTILINE)
sys.stdout.write(content)
")
    {
        echo ""
        echo "---"
        echo ""
        printf '%s\n' "$TRANSFORMED"
    } >> "$HISTORY"
    ok "Sesión añadida a history.md"
else
    info "current.md está vacío (plantilla), no se añade a history.md"
fi

cat > "$CURRENT" << 'TEMPLATE'
# Sesión actual

> Este archivo se vacía al cerrar cada sesión y se mueve a `history.md`.
> Mientras trabajas, **mantenlo actualizado en tiempo real**, no al final.

- **Feature en curso:** _ninguna_  <!-- formato: #N nombre_feature -->
- **Inicio:** _—_
- **Agente:** _—_

## Plan

_Describe en 3-5 bullets qué vas a hacer antes de tocar código._

## Bitácora

_Anota aquí cada paso significativo: archivos creados, decisiones, bloqueos._

- ...

## Próximo paso

_Si la sesión se interrumpe, lo primero que debe hacer la siguiente sesión._

---
TEMPLATE
ok "current.md reseteado a plantilla"
echo ""

# ── 5. Commit automático ──────────────────────────────────────────────────────
echo "▸ Commit automático"

git add -A

if git diff --cached --quiet; then
    info "Nada que commitear — el working tree ya estaba limpio."
else
    if [ -n "$FEATURE_ID" ]; then
        COMMIT_MSG="${COMMIT_TYPE}(#${FEATURE_ID}): ${FEATURE_NAME} — ${FEATURE_TITLE}"
    else
        COMMIT_MSG="chore: ${FEATURE_TITLE}"
    fi

    git commit -m "$COMMIT_MSG"
    ok "Commit: $COMMIT_MSG"
fi

echo ""
echo "========================================"
echo -e "${GREEN}  ✓ Sesión cerrada correctamente.${NC}"
echo "========================================"
