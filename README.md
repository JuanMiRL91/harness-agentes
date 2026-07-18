# harness-agentes

Harness de desarrollo reutilizable para trabajar con agentes de IA (Claude Code) de
forma **autónoma pero verificable**: backlog en fichero, checks deterministas, cierre de
sesión con commit automático, y orquestación de subagentes optimizada en tokens.

Extraído de un proyecto real en uso diario (~190 features cerradas con este flujo).

## Filosofía

- **El repositorio es el sistema.** Todo el estado vive en ficheros versionados:
  backlog (`feature_list.json`), sesión activa (`progress/current.md`), bitácora
  (`progress/history.md`), documentación técnica (`harness/docs/`). Ninguna base de
  datos, ningún estado fuera de git.
- **Verificación real, no impresiones.** `init.sh` ejecuta los tests de verdad (dos
  veces: orden alfabético e inverso, para cazar estado compartido), valida contratos
  UI↔core por AST y detecta texto placeholder. `close.sh` no deja cerrar la sesión con
  docs desalineados.
- **Divulgación progresiva.** `AGENTS.md` es un mapa, no una biblia: el agente lee cada
  documento solo cuando lo necesita. `CLAUDE.md` se mantiene <40k caracteres (el
  harness lo verifica).
- **Ciclo sistémico bug → check.** Cada bug cerrado obliga a preguntarse qué check del
  harness lo habría detectado antes, y a añadirlo en la misma sesión.
- **Tokens como recurso escaso.** El modelo frontier orquesta y decide; los subagentes
  (Haiku/Sonnet) implementan. Review y verificación E2E van agrupadas al final del
  lote, no por feature.

## Componentes

| Componente | Qué hace |
|---|---|
| `AGENTS.md` | Punto de entrada del agente: cómo elegir tarea, reglas duras, lifecycle |
| `CLAUDE.md` | Contexto mínimo del proyecto (plantilla con placeholders) |
| `harness/init.sh` | Verificación pre-trabajo: Python, ficheros, backlog, deps, tests, contratos |
| `harness/close.sh` | Cierre de sesión: checks de docs, archivado, commit convencional automático |
| `harness/check_contracts.py` | Los imports `ui/ → core/` apuntan a símbolos reales (AST) |
| `harness/check_docs.py` | Símbolos públicos del diff cruzados contra los docs; módulos contra README |
| `harness/check_deps.py` | Imports de terceros no declarados → los añade a `requirements.txt` |
| `harness/check_placeholder.py` | Texto de relleno en literales de `core/`/`ui/` |
| `harness/feature_list.json` | Backlog activo; las cerradas van a `feature_list_archive.json` (ids globales) |
| `harness/progress/` | `current.md` (sesión activa) + `history.md` (bitácora append-only) |
| `harness/docs/` | architecture.md · data-models.md · conventions.md · verification.md |
| `harness/CHECKPOINTS.md` | Criterios objetivos de "estado final correcto" |
| `harness/viewer.py` | Visor Streamlit del backlog y el historial |
| `.claude/skills/add-feature` · `add-bug` | Alta de tareas en el backlog con esquema y validación |
| `.claude/skills/improve-harness` | Extender el propio harness (mapa interno + convenciones) |
| `.claude/skills/orchestrate-backlog` | Vaciar el backlog con subagentes secuenciales + review/verify agrupados |
| `.claude/skills/verify` | Verificación E2E con la app real y navegador (cara: solo al cierre) |
| `.claude/agents/implementer.md` | Subagente que implementa UNA tarea del backlog |
| `.claude/settings.json` | Permisos versionados (allow del harness, deny de IDEAS.md/history.md) |

## Ciclo de vida de una sesión

```
./harness/init.sh                  # entorno verde antes de tocar nada
  → elegir UNA tarea pending (bugs BUG_* primero)
  → implementar + documentar en current.md en tiempo real
  → verificar acceptance uno a uno (+ skill verify si la tarea lo declara)
  → /code-review sobre el diff
  → marcar done
./harness/close.sh                 # re-verifica, cruza docs, archiva, commit automático
```

Estados de una tarea: `pending → in_progress → done` (o `blocked`); `close.sh` archiva
las `done`/`Cancelled` y el id nunca se reutiliza.

## Adoptarlo en un proyecto nuevo

1. Copia el contenido de este repo a la raíz del proyecto (o úsalo como plantilla de
   GitHub).
2. Sustituye los `<placeholders>`:
   - `CLAUDE.md` — nombre, decisiones, rutas, mapa de módulos, comando de arranque.
   - `harness/feature_list.json` y `feature_list_archive.json` — `project` y `description`.
   - `.claude/skills/verify/SKILL.md` — `<comando de arranque>` y `<log de la app>`.
   - `harness/docs/` — rellena las plantillas de architecture/data-models y la sección
     de UI de conventions.md.
3. Crea las carpetas del layout esperado: `core/`, `ui/`, `tests/` (y `docs/IDEAS.md`
   si usas el cuaderno personal).
4. Ejecuta `./harness/init.sh` — debe terminar verde (sin tests aún, avisará con WARN).
5. Registra la primera tarea con `/add-feature` y trabaja con el ciclo de arriba.

### Supuestos del harness (adaptar si tu proyecto difiere)

- **Layout en capas Python:** `core/` (lógica) + `ui/` (presentación) + `tests/`.
  Si usas otros nombres, ajusta `SCAN_DIRS`/`UI_DIRS` en los `check_*.py` y las rutas
  `core/ ui/` en `init.sh`/`close.sh`.
- **Python ≥3.9**, tests con pytest (fallback unittest), deps en `requirements.txt`.
- **Idioma:** documentación y UI en español; código y claves en inglés.
- `check_docs.py` cruza `core/*.py` y `ui/common.py` (la frontera pública de la UI);
  amplía la lista si tu UI expone más módulos documentables.
- Los scripts detectan `python3`/`python` y fuerzan UTF-8: funcionan en macOS, Linux y
  Windows Git Bash.

## Créditos

Basado en el patrón de *harness engineering* de
[betta-tech](https://github.com/betta-tech):
[ejemplo-harness-subagentes](https://github.com/betta-tech/ejemplo-harness-subagentes) y
[harness-sdd](https://github.com/betta-tech/harness-sdd). La implementación de este
repo está reescrita y ampliada (cierre con commit automático y checks de documentación,
archivado del backlog, ciclo sistémico bug→check, orquestación con escalado de modelos
y verificación E2E agrupada), pero el diseño de partida —AGENTS.md como mapa,
`feature_list.json` como backlog, `init.sh` como puerta de entrada y `progress/` como
estado en disco— es suyo.

## Licencia

[MIT](LICENSE)
