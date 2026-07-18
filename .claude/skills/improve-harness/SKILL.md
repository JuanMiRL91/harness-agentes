---
name: improve-harness
description: Mejorar o extender el harness de desarrollo del proyecto. Úsala cuando el usuario pida añadir verificaciones a init.sh/close.sh, mejorar checks existentes, añadir nuevos scripts al harness, o cualquier cambio en la infraestructura de desarrollo (no en la app en sí).
---

# Mejorar el harness

El harness es la **infraestructura de desarrollo** del proyecto. No es parte de la app.

## Mapa del harness

| Archivo | Qué hace | Cuándo modificar |
|---------|----------|-----------------|
| `harness/init.sh` | Verificación pre-trabajo: Python ≥3.9, archivos obligatorios, feature_list.json, dependencias (`check_deps.py`), tests, contratos UI↔core (`check_contracts.py`) | Para añadir/modificar checks que deben pasar antes de trabajar |
| `harness/close.sh` | Cierre de sesión: llama init.sh, detecta docs desactualizados (architecture.md/data-models.md + `check_docs.py`), avisa si CLAUDE.md supera 40k caracteres, recuerda el ciclo sistémico bug→check en commits `fix`, archiva features done/Cancelled → feature_list_archive.json, archiva current.md→history.md, hace commit automático. Exit: 0 cerrado · 1 error · 3 pausado (stdin no interactivo = pausa automática) | Para modificar el flujo de cierre |
| `harness/check_contracts.py` | Verifica que todos los imports `ui/→core/` apuntan a símbolos reales | Para añadir nuevos tipos de contrato |
| `harness/check_docs.py` | Cruce determinista de docs: símbolos públicos añadidos/eliminados en el diff de la sesión (`core/*.py`, `ui/common.py` vs HEAD, por AST) vs menciones en `architecture.md`/`data-models.md`/`CLAUDE.md` (símbolo nuevo: basta mención en UNO; eliminado: no debe quedar en ninguno) + cobertura de módulos en README.md (todo `core/*.py`, `ui/*.py`, `ui/pages/*.py` debe aparecer por nombre en la Estructura; corre siempre, no depende del diff); exit 1 informativo (solo activa la confirmación de close.sh) | Para ampliar qué ficheros o docs se cruzan |
| `harness/check_deps.py` | Detecta imports de terceros no declarados en `requirements.txt` y los añade automáticamente | Para ampliar detección de dependencias |
| `harness/feature_list.json` | Backlog ACTIVO de features y bugs (pending/in_progress/blocked) | Solo via `/add-feature` y `/add-bug`, nunca directamente |
| `harness/feature_list_archive.json` | Archivo de features cerradas (done/Cancelled), ids globales con el activo | Solo lo escriben close.sh (paso 3d) y el viewer al reactivar una entrada |
| `harness/viewer.py` | Streamlit viewer del backlog (vista única activo+archivo; al cambiar un status reparte cada feature a su fichero) | Para mejorar visualización del progreso |
| `harness/progress/current.md` | Estado de la sesión activa (close.sh lo lee y archiva) | Se actualiza durante la sesión de trabajo |
| `harness/progress/history.md` | Bitácora histórica append-only | Solo se escribe via close.sh |
| `harness/docs/` | architecture.md (detalle fino de módulos/decisiones), data-models.md (esquemas JSON), conventions.md, verification.md | Para actualizar documentación técnica |
| `harness/CHECKPOINTS.md` | Criterios objetivos de estado final correcto | Para añadir nuevos puntos de evaluación |
| `AGENTS.md` (raíz) | Contrato que lee el agente: cómo elegir tarea (§4, bugs `BUG_` primero), reglas duras, lifecycle con init.sh/close.sh | Si el cambio altera el flujo del agente (prioridades, estados, pasos de sesión), mantenerlo en sincronía |
| `.claude/settings.json` | Permisos versionados de Claude Code: allow (init/close/pytest/git de lectura) + deny (Edit/Write de docs/IDEAS.md e history.md) | Para endurecer/relajar permisos en ambas máquinas |
| `.claude/agents/implementer.md` | Subagente nativo que implementa UNA tarea del backlog (protocolo completo; lo lanza orchestrate-backlog con haiku/sonnet/opus) | Si cambia el protocolo por tarea del subagente |

## Compatibilidad Windows/Linux

Los scripts bash usan `$PY` (no `python3` directamente). Ambos `init.sh` y `close.sh` detectan el ejecutable correcto al inicio:

```bash
# Al inicio de init.sh y close.sh — en Windows Git Bash, python3 puede ser el stub de Microsoft Store
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python3"
elif python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python"
else
    PY="python3"  # fallback; la sección 1 dará el error claro
fi
```

Todo uso de Python en los scripts usa `"$PY"`, nunca `python3` directamente.

Los scripts Python del harness (`check_deps.py`, `check_contracts.py`) pueden tener problemas de encoding en Windows (cp1252 no soporta caracteres como `✓`, `✗`, `↔`). Usar solo ASCII en los mensajes de salida de estos scripts.

## Estructura de init.sh

Secciones numeradas. Patrón de cada sección:
```bash
# ── N. Descripción ────────────────────────────────────────────────────────────
echo ""
echo "▸ Descripción"
# ... checks ...
[ $? -ne 0 ] && FAILED=1
```

Secciones actuales:
1. Python 3.9+ (con detección `$PY`)
2. Archivos obligatorios del harness
3. Validar feature_list.json
4. Dependencias (via `$PY harness/check_deps.py`)
5. Tests (`$PY -m pytest` con fallback a unittest)
6. Contratos UI↔core (via `$PY harness/check_contracts.py`)

Para añadir una sección: insertarla antes del bloque "Resultado final" con el número siguiente.

**Regla de severidad**: `fail()` incrementa `$FAILED` y bloquea el inicio. `warn()` solo informa. Usa `warn()` para issues recuperables (deps no instaladas, docs no actualizados). Usa `fail()` para issues que impedirán el trabajo (Python no encontrado, tests fallando, contratos rotos).

## check_deps.py — cómo funciona

1. Escanea imports AST de `core/`, `ui/`, `tests/`
2. Filtra stdlib (`sys.stdlib_module_names` en 3.10+, lista estática en 3.9) y módulos locales (`core`, `ui`, `tests`, ficheros `.py` en raíz)
3. Resuelve import→package via `IMPORT_TO_PKG` (mapeo manual para casos que difieren) → `packages_distributions()` → fallback al propio nombre del import
4. Si el package no está en `requirements.txt` → lo añade con `pkg>=major.minor` (versión instalada) o sin versión si no está instalado
5. Verifica que lo declarado en `requirements.txt` esté instalado → WARN si no
6. Exit code siempre 0 (nunca bloquea el harness)

Para ampliar el mapeo import→package: añadir entradas a `IMPORT_TO_PKG` en `check_deps.py`:
```python
IMPORT_TO_PKG = {
    "dotenv":   "python-dotenv",
    "PIL":      "Pillow",
    # añadir aquí casos nuevos
}
```

## Estructura de close.sh

Pasos fijos (no reordenar):
1. Verifica que init.sh pasa al 100%
2. Lee feature completada desde current.md (busca `#N` en línea "Feature en curso"; la entrada se busca en feature_list.json Y feature_list_archive.json). Sin `#N`, el texto de esa línea se usa como título del commit `chore:`
3. Detecta cambios en `core/` o `ui/` y advierte si ni harness/docs/architecture.md ni harness/docs/data-models.md se tocaron (3c: avisa además si CLAUDE.md supera 40k caracteres). Las pausas terminan con **exit 3**; con stdin no interactivo la pausa es automática, sin pregunta
3d. Archiva las features done/Cancelled en feature_list_archive.json (orden por id; crea el fichero si no existe)
4. Archiva current.md → history.md y resetea current.md a plantilla
5. `git add -A` + commit con mensaje convencional

Tipo de commit: `fix` para nombres que empiezan por `BUG_`, `feat` para el resto.
Mensaje: `fix(#N): name — title` o `feat(#N): name — title`.

Para añadir lógica nueva: dentro de un paso existente, o como nuevo paso entre 3 y 4.

## Convenciones de los scripts del harness

- **Python del harness** (check_deps.py, check_contracts.py, etc.):
  - Sin dependencias externas — solo stdlib + módulos del proyecto vía `sys.path.insert(0, str(ROOT))`.
    Excepción: `viewer.py` (usa Streamlit) — es una app de visualización, no un check que
    deba correr en cualquier entorno.
  - Colores como constantes: `GREEN = "\033[0;32m"`, `YELLOW = "\033[1;33m"`, `RED = "\033[0;31m"`, `NC = "\033[0m"`
  - Solo ASCII en salida (no `✓`, `✗`, `↔` — fallan en Windows cp1252)
  - `main() -> int`, `if __name__ == "__main__": sys.exit(main())`
  - `ROOT = Path(__file__).parent.parent`
- **Bash** (init.sh, close.sh):
  - Funciones `ok()`, `warn()`, `fail()` para output
  - `$PY` en vez de `python3` o `python`
  - `set -euo pipefail` al inicio
  - Mensajes al usuario en español

## Flujo para añadir una mejora al harness

1. Identifica qué componente afecta el cambio (init.sh, close.sh, check_*.py, docs, …).
2. Lee el fichero completo antes de editar — init.sh llama check_deps.py y check_contracts.py; close.sh llama init.sh.
3. Si añades un nuevo script Python: sigue el patrón de check_deps.py/check_contracts.py.
4. Si añades una sección a init.sh: inserta antes del "Resultado final", usa `$PY`, elige warn vs fail según severidad.
5. Verifica con `bash harness/init.sh` que todo pasa.
6. Si el cambio afecta la arquitectura del harness, actualiza `harness/CHECKPOINTS.md` y la
   sección "Harness de desarrollo" de `CLAUDE.md`; si altera el flujo que sigue el agente
   (prioridades, estados, pasos de sesión), actualiza también `AGENTS.md` y las skills
   `add-feature`/`add-bug` si documentan ese comportamiento.

## Qué NO hacer

- No añadir dependencias externas a los scripts Python del harness.
- No reordenar los pasos de close.sh.
- No usar `python3` directamente — siempre `"$PY"`.
- No poner caracteres no-ASCII en la salida de scripts Python del harness.
- No modificar `harness/feature_list.json` directamente desde código — solo via `/add-feature` y `/add-bug`.
- No convertir en `fail()` checks que son informativos (como "docs no actualizados").
