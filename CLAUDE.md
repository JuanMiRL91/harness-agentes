# <nombre-del-proyecto> — contexto del proyecto

> **Plantilla** — sustituye los `<placeholders>` al adoptar el harness. Este fichero se
> inyecta entero en cada sesión: se mantiene mínimo (**<40.000 caracteres siempre**,
> `close.sh` avisa si se supera). El detalle vive en `harness/docs/`.

<Una o dos líneas: qué es el proyecto, para quién, con qué stack.>

**Dónde está el detalle (no duplicarlo aquí):**

- `harness/docs/architecture.md` — decisiones cerradas y mapa de módulos función a función.
- `harness/docs/data-models.md` — esquema completo de los ficheros de datos.
- `harness/progress/history.md` + `harness/feature_list.json` — changelog por sesión/feature.

## Decisiones de arquitectura (cerradas)

- **Stack:** <núcleo en `core/` (independiente de la UI) + UI en `ui/`>.
- <Decisión cerrada 2: persistencia, fuentes de datos, alcance…>

## Rutas

- <Rutas y estructura de carpetas relevantes del proyecto.>
- `docs/IDEAS.md` — cuaderno personal del usuario, NO accionable, ningún agente lo edita.

## Mapa de módulos (una línea; detalle en `harness/docs/architecture.md`)

- `core/<modulo>.py` — <una línea>.
- `ui/<pagina>.py` — <una línea>.

## Harness de desarrollo

- `harness/init.sh` — verifica entorno antes de trabajar (Python, ficheros, deps, tests,
  contratos UI↔core).
- `harness/close.sh` — cierre de sesión: init.sh + checks de docs (`check_docs.py` +
  límite de 40k chars de este fichero) + ciclo sistémico bug→check + archivado de
  features cerradas → `feature_list_archive.json` + archivado `current.md`→`history.md`
  + commit convencional automático. Exit 3 = pausado (corregir docs y re-ejecutar).
- `harness/check_contracts.py` / `check_docs.py` / `check_deps.py` /
  `check_placeholder.py` — checks deterministas.
- `harness/feature_list.json` — backlog accionable ACTIVO (gestionar SOLO con
  `/add-feature` y `/add-bug`); las cerradas (done/Cancelled) van a
  `harness/feature_list_archive.json` (ids globales, lo mantiene `close.sh`).
- `harness/viewer.py` — visor Streamlit (features activo+archivo, historial).
- `.claude/skills/verify/` — verificación E2E de la app real; se ejecuta SOLO justo antes
  de `close.sh` si la tarea declara `Verificación E2E: sí`, o por petición explícita del
  usuario — nunca en el init (ver `AGENTS.md` §5 y `harness/docs/verification.md`).
- `.claude/skills/orchestrate-backlog/` — vaciar el backlog con subagentes `implementer`
  secuenciales (haiku/sonnet, escalado a opus en el 2º reintento), code-review + verify
  E2E agrupados en una pasada final y reanudación tras un corte de sesión (estado
  persistente en `harness/progress/orchestrator.md`).
- `.claude/agents/implementer.md` — subagente nativo con el protocolo de implementación
  de UNA tarea del backlog (el prompt del orquestador solo lleva el JSON de la tarea).
- `.claude/settings.json` — permisos versionados: allow de comandos del harness, deny de
  escritura en `docs/IDEAS.md` y `progress/history.md`.
- `harness/docs/` — architecture.md, data-models.md, conventions.md, verification.md.
- `harness/progress/` — `current.md` (sesión activa) + `history.md` (bitácora histórica).

## Optimización de tokens y modelos (orquestación)

Al orquestar trabajo con subagentes, minimizar consumo de tokens y delegar en modelos
más baratos/rápidos (p. ej. Haiku o Sonnet) siempre que la tarea lo permita:

- **Dividir pesado vs. ligero:** trocear features en tareas pequeñas y aisladas. Reservar
  el modelo frontier para decisiones de arquitectura, lógica compleja y debugging de
  fondo; delegar boilerplate, tests unitarios y refactors repetitivos a modelos menores
  con sub-prompts explícitos e hiperenfocados.
- **Contexto mínimo:** no pasar estructuras multi-fichero enteras a un subagente; solo la
  función/clase objetivo y sus dependencias directas.
- **Sub-prompts sin relleno:** los prompts a subagentes exigen salida directa (solo código
  o JSON/Markdown estricto, sin intros ni explicaciones).
- **Estado resumido:** antes de un nuevo ciclo de orquestación, condensar el historial en
  un bloque "State Summary" breve (<200 tokens) en vez de arrastrar el chat crudo.
- **Solo diffs:** pedir a los subagentes diffs de git o reemplazos de líneas concretas,
  nunca reescrituras de ficheros completos.
- **Escalado, no insistencia:** una tarea fallida se reintenta una vez con el mismo
  modelo (pasándole el error concreto) y una segunda escalando un nivel
  (haiku→sonnet→opus); si también falla, `blocked` y se sigue con la siguiente.

## Backlog e ideas futuras

- `harness/feature_list.json` es el **único backlog accionable** (skills `/add-feature` y
  `/add-bug`).
- `docs/IDEAS.md` es el **cuaderno personal del usuario**: **ningún agente lo edita
  nunca** — ni siquiera para corregir formato. Solo se lee cuando el usuario pida
  explícitamente convertir ideas en features del backlog.

## Mantenimiento de la documentación

Cada feature/bug que cambie `core/`, `ui/` o el harness deja la documentación alineada
**en la misma sesión**, antes de `./harness/close.sh` (que lo verifica). **Cada cosa va a
su documento — sin duplicar:**

1. `harness/docs/architecture.md` — el detalle fino de lo implementado: funciones públicas
   nuevas/renombradas/eliminadas, decisiones de diseño, hallazgos verificados en vivo
   (APIs, series, comportamientos). Es lo que `check_docs.py` cruza contra el diff.
2. `harness/docs/data-models.md` — cualquier cambio de esquema en un fichero de datos
   (clave nueva, renombrada, eliminada o con semántica distinta).
3. `harness/progress/current.md` → `history.md` — el changelog narrativo de la sesión
   (lo archiva `close.sh`). NUNCA escribir changelog en `CLAUDE.md` ni en architecture.md.
4. `CLAUDE.md` (este fichero) — SOLO si cambia el mapa de una línea (módulo/página
   nuevo/renombrado/eliminado), una decisión de arquitectura o estas reglas. Se mantiene
   mínimo: **por debajo de 40.000 caracteres siempre** (`close.sh` avisa si se supera).
5. `README.md` — solo si cambia la visión de alto nivel (estructura, uso, sincronización).
6. `harness/docs/conventions.md` / `verification.md` — solo si cambia una convención o el
   modo de verificar.

No documentar planes futuros en ningún doc: lo accionable vive en
`harness/feature_list.json`; las ideas sin madurar, en `docs/IDEAS.md`.

## Estado

<Fase actual del proyecto en 2-4 líneas. El detalle por feature está en
`harness/progress/history.md` y `harness/feature_list_archive.json`.>

## Comandos

```bash
pip install -r requirements.txt
<comando de arranque de la app>
streamlit run harness/viewer.py    # visor del backlog
./harness/init.sh                  # verificar entorno antes de trabajar
./harness/close.sh                 # cerrar sesión y hacer commit
```
