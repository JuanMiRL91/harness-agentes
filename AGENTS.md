# AGENTS.md — Mapa de navegación para agentes de IA

> Este archivo es el **punto de entrada** para cualquier agente que trabaje en este
> repositorio. NO es una biblia de reglas: es un **mapa**. Lee solo lo que
> necesites cuando lo necesites (divulgación progresiva).

---

## 1. Antes de empezar (obligatorio)

1. Ejecuta `./harness/init.sh` y verifica que termina sin errores. Si falla, **para**
   y resuelve el entorno antes de tocar código.
2. Lee `harness/progress/current.md` para entender en qué estado quedó la última sesión.
3. Lee `harness/feature_list.json` y elige **una** tarea con estado `pending`. No
   trabajes en más de una a la vez. **Los bugs van primero**: si hay alguna
   tarea `pending` cuyo `name` empieza por `BUG_`, atáchala antes que cualquier
   feature (ver §4 para el criterio exacto).

## 2. Mapa del repositorio

| Archivo / carpeta              | Qué contiene                                                        | Cuándo leerlo          |
|--------------------------------|---------------------------------------------------------------------|------------------------|
| `harness/feature_list.json`    | Backlog ACTIVO (pending / in_progress / blocked); las done/Cancelled se archivan en `feature_list_archive.json` (ids globales) | Siempre, al empezar    |
| `harness/progress/current.md`  | Estado de la sesión actual                                          | Siempre, al empezar    |
| `harness/progress/history.md`  | Bitácora append-only de sesiones anteriores                         | Si necesitas contexto histórico |
| `harness/docs/architecture.md` | Decisiones de diseño y mapa de módulos función a función (detalle fino) | Antes de implementar   |
| `harness/docs/data-models.md`  | Esquema completo de los ficheros de datos                           | Antes de tocar datos   |
| `harness/docs/conventions.md`  | Reglas de estilo, nombres, estructura                               | Antes de escribir código |
| `harness/docs/verification.md` | Cómo verificar que tu trabajo funciona                              | Antes de declarar `done` |
| `harness/CHECKPOINTS.md`       | Criterios objetivos de "estado final correcto"                      | Para auto-evaluarte    |
| `CLAUDE.md`                    | Contexto mínimo del proyecto (decisiones, rutas, mapa de una línea) | Al inicio de sesión    |
| `core/`                        | Núcleo Python (lógica de negocio, independiente de la UI)           | Para implementar       |
| `ui/`                          | UI (sin lógica de negocio; llama a `core/`)                         | Para UI                |
| `harness/`                     | Herramientas de desarrollo: init.sh, close.sh, check_*.py, viewer.py | Para el harness       |
| `tests/`                       | Tests automáticos                                                   | Para verificar         |
| `docs/IDEAS.md`                | Cuaderno **personal del usuario** (ideas futuras) — **NUNCA editarlo** | Solo si el usuario pide analizarlo |

## 3. Reglas duras (no negociables)

- **Una sola feature a la vez.** No mezcles cambios de varias tareas en la misma sesión.
- **No declares una tarea `done` sin pruebas verdes.** Ejecuta `./harness/init.sh` y
  asegúrate de que el bloque de tests pasa al 100%.
- **Documenta lo que haces** en `harness/progress/current.md` mientras trabajas, no al final.
- **Actualiza la documentación afectada en la misma sesión** — cada cosa va a su documento,
  sin duplicar: detalle de módulos/funciones/decisiones → `harness/docs/architecture.md`;
  cambios de esquema de datos → `harness/docs/data-models.md`; changelog →
  `harness/progress/current.md` (lo archiva `close.sh` en `history.md`); `CLAUDE.md` SOLO
  si cambia el mapa de una línea o una decisión de arquitectura (mantenerlo <40k
  caracteres); `README.md` solo si cambia la visión de alto nivel. Ver "Mantenimiento de
  la documentación" en `CLAUDE.md`; `close.sh` lo verifica.
- **Cierra siempre la sesión con `./harness/close.sh`** — hace el commit automático.
- **Si no sabes algo, busca en `harness/docs/` o en `CLAUDE.md`** antes de inventarlo.
- **`docs/IDEAS.md` es intocable:** es el cuaderno personal del usuario. No lo edites, no lo
  reformatees, no lo "completes". Solo se lee cuando el usuario pida convertir ideas
  suyas en features de `harness/feature_list.json`.

## 4. Cómo elegir una tarea

**Los bugs tienen prioridad sobre las features.** Un bug es toda tarea cuyo `name`
empieza por `BUG_`. Entre las `pending`, primero los bugs por menor `id`; si no queda
ningún bug `pending`, la feature `pending` de menor `id`.

```
1. Abre harness/feature_list.json
2. Filtra por status == "pending"
3. Si hay bugs (name empieza por "BUG_"): coge el bug de menor "id"
   Si no hay bugs pending: coge la feature de menor "id"
4. Cambia su status a "in_progress" y guarda
5. Anota en harness/progress/current.md: feature, hora de inicio, plan breve
```

La línea "Feature en curso" de `current.md` debe llevar el formato `#N nombre_feature`
(el `#N` primero) — `close.sh` la parsea para titular la sesión en `history.md`.

Para elegir de forma determinista:

```bash
python3 -c "
import json
fs = [f for f in json.load(open('harness/feature_list.json'))['features'] if f['status']=='pending']
fs.sort(key=lambda f: (not f['name'].upper().startswith('BUG'), f['id']))
print('Siguiente:', fs[0]['id'], fs[0]['name'], '·', fs[0]['title']) if fs else print('Nada pending')
"
```

## 5. Cierre de sesión (lifecycle)

Cuando la feature esté completada:

1. **Verifica los criterios de `acceptance` uno a uno** con el método que cada uno indica
   (comando de test, o paso `UI:` con la skill `verify`, que arranca la app real). No
   marques `done` con criterios sin comprobar. La skill `verify` se ejecuta **una sola
   vez y solo aquí** (justo antes de `close.sh`), y únicamente si la `description` de la
   tarea dice `Verificación E2E: sí` (o tiene pasos `UI:` en `acceptance`); si dice
   `Verificación E2E: no`, sáltala. NUNCA la ejecutes al inicio de sesión ni como parte
   de `init.sh` — es la skill más cara en tokens del harness.
2. **Si la tarea era un `BUG_`, cierra también el ciclo sistémico:** pregúntate qué check
   del harness (`init.sh`, `close.sh`, `check_*.py`, un test) habría detectado este bug
   antes de llegar al usuario. Si existe uno razonable, añádelo **en la misma sesión**
   (skill `improve-harness`); si no aplica, anota en `harness/progress/current.md` una
   línea `Check sistémico: no aplica — <motivo>`. `close.sh` te lo recordará si cierras
   un fix sin tocar `harness/`.
3. **Revisión con contexto fresco:** pasa `/code-review` sobre el diff de la sesión antes
   del commit y aplica (o descarta razonadamente, dejándolo en `current.md`) los hallazgos.
   Excepción: en una orquestación del backlog (skill `orchestrate-backlog`) la revisión va
   agrupada al final del lote — el subagente implementer NO la pasa por feature.
4. Marca `status: "done"` en `harness/feature_list.json`.
5. Ejecuta `./harness/close.sh` — hace todo lo demás automáticamente:
   - Verifica que `init.sh` pasa al 100%.
   - Advierte si ni `harness/docs/architecture.md` ni `harness/docs/data-models.md`
     fueron tocados habiendo cambios en `core/`/`ui/`, cruza los símbolos públicos del
     diff contra los docs y la lista de módulos contra el README
     (`harness/check_docs.py`) y avisa si `CLAUDE.md` supera los 40.000 caracteres.
   - Si el commit es un `fix`, recuerda el ciclo sistémico bug → check del harness.
   - Archiva las features `done`/`Cancelled` en `harness/feature_list_archive.json`.
   - Mueve el resumen de `harness/progress/current.md` al final de `harness/progress/history.md`.
   - Resetea `harness/progress/current.md` a la plantilla.
   - Hace el commit con mensaje convencional (`feat(#N)` / `fix(#N)`).

   Códigos de salida: `0` = cerrado · `1` = error · `3` = **pausado** (docs pendientes o
   `CLAUDE.md` >40k) — corrige exactamente lo que indica y re-ejecuta `./harness/close.sh`;
   nunca intentes eludir el aviso (con stdin no interactivo la pausa es automática).

## 6. Si te bloqueas

- Relee la sección relevante de `harness/docs/` o `CLAUDE.md`.
- Si la herramienta no hace lo que esperas, **no inventes un workaround**:
  documenta el bloqueo en `harness/progress/current.md` y para la sesión.

---
