---
name: orchestrate-backlog
description: Orquestar el vaciado del backlog del proyecto (harness/feature_list.json) delegando cada tarea pending en subagentes Haiku/Sonnet secuenciales y agrupando la verificación E2E (skill verify) en UNA sola pasada final, para minimizar tokens y no agotar el límite de 5 horas. Úsala SIEMPRE que el usuario pida "dejar las features pending en done", "vaciar/procesar el backlog", "ve ejecutando agentes con las features", un /goal sobre varias tareas de feature_list.json, o cualquier petición de trabajar más de una tarea del backlog en la misma sesión — aunque no mencione la palabra "orquestar".
---

# Orquestar el backlog con subagentes

El chat principal (modelo frontier) actúa SOLO como orquestador: planifica, delega,
supervisa y verifica al final. **Nunca implementa código él mismo** — cada línea de
implementación que escribe el orquestador es el uso más caro posible de tokens. Los
tres sumideros de tokens que esta skill elimina:

1. **Un `/verify` por feature.** La skill `verify` (app real + navegador) es la más
   cara del harness. Si varias features tocan las mismas páginas, una sola pasada
   agrupada al final las cubre todas.
2. **Un `/code-review` por feature.** Un subagente revisándose a sí mismo con su propio
   contexto aporta poco: la revisión va agrupada al final, una sola pasada con contexto
   fresco sobre el diff completo del lote.
3. **Cada subagente re-derivando el protocolo.** El protocolo de implementación vive en
   el agente **`implementer`** (`.claude/agents/implementer.md`), no en el prompt: a
   cada subagente solo se le pasa la entrada JSON literal de su tarea.

## Fase 1 — Inventario y plan (orquestador, una sola vez)

1. `./harness/init.sh` — si falla, para y resuélvelo antes de delegar nada.
2. Lista las `pending` ordenadas (bugs `BUG_` primero por id, luego features por id):

   ```bash
   python3 -c "
   import json
   fs = [f for f in json.load(open('harness/feature_list.json'))['features'] if f['status']=='pending']
   fs.sort(key=lambda f: (not f['name'].upper().startswith('BUG'), f['id']))
   for f in fs: print(f['id'], f['name'], '·', f['title'])
   "
   ```

   (Las cerradas viven en `harness/feature_list_archive.json`; las pending, siempre en
   el fichero activo.)

3. Lee la entrada completa de cada pending (una vez; guárdalas para los prompts) y
   clasifícalas en un plan con tres columnas por tarea:
   - **Modelo:** `haiku` solo para cambios mecánicos (cambiar un default, renombrar,
     borrar un bloque delimitado, criterios verificables con grep); `sonnet` para todo
     lo demás (lógica en `core/`, UI nueva, tests con casos límite). El frontier no
     implementa nunca.
   - **E2E:** `sí`/`no` según la línea `Verificación E2E:` de la `description`; si no
     existe, `sí` cuando hay criterios `UI:` en `acceptance` o toca `core/`/`ui/`
     (criterio por defecto de la skill `verify`).
   - **Grupo de verify:** las páginas/pestañas a recorrer (de la línea E2E o de los
     pasos `UI:`). Tareas con páginas comunes comparten grupo.
4. Crea/actualiza `harness/progress/orchestrator.md` con el plan, una línea
   `Base del lote: <hash de git rev-parse HEAD>` (ancla del review agrupado de la
   Fase 3) y una sección `## Verify diferido` vacía. Este fichero es el estado
   persistente de la orquestación: si la sesión muere (límite de 5h, cierre), la
   siguiente invocación de esta skill lo lee y continúa donde quedó. Muéstrale el plan
   al usuario en una tabla corta antes de empezar (no pidas confirmación: la invocación
   de la skill ya es la orden).

## Fase 2 — Un subagente por tarea (secuencial, nunca en paralelo)

Las tareas comparten ficheros (`feature_list.json`, `current.md`, git) y la regla del
repo es una feature a la vez: lanza los subagentes **de uno en uno** y espera el
resultado (`run_in_background: false`).

Lanza cada tarea con el agente **`implementer`** — su protocolo completo vive en
`.claude/agents/implementer.md`, NO lo dupliques en el prompt — pasando el `model` del
plan (`haiku` mecánicas · `sonnet` el resto). Prompt mínimo:

```
TAREA (harness/feature_list.json):
<entrada JSON completa, literal>
```

más, solo si aplica, 1-3 líneas de contexto específico (relación con otra tarea del
lote, decisión ya tomada por el usuario).

Tras cada subagente, el orquestador (barato, sin releer ficheros grandes):

- Confirma el commit: `git log --oneline -1` contiene `(#<id>)`; y el status `done` con
  un one-liner (OJO: close.sh archiva la entrada al cerrar — búscala en ambos ficheros):

  ```bash
  python3 -c "
  import json
  fid = <id>
  for p in ('harness/feature_list.json', 'harness/feature_list_archive.json'):
      for f in json.load(open(p))['features']:
          if f['id'] == fid: print(p, '->', f['status'])
  "
  ```

- **Escalera de reintentos** si no hay commit o el status no es `done`:
  1. Relanza UNA vez el mismo subagente vía SendMessage con el error concreto
     (conserva su contexto).
  2. Si vuelve a fallar, lanza un `implementer` NUEVO con el modelo un nivel por
     encima (`haiku`→`sonnet`, `sonnet`→`opus`); prompt = entrada JSON + resumen de qué
     se intentó y qué error dio (contexto limpio: no arrastres el transcript).
  3. Si también falla, marca la tarea `blocked` en el plan de `orchestrator.md` y sigue
     con la siguiente (no la arregles tú en el chat principal salvo que sea trivial).
- Añade los criterios `UI:` de la tarea a `## Verify diferido` de `orchestrator.md`.
- No arrastres el chat: tu estado son 3-4 líneas por tarea (el State Summary), no el
  transcript del subagente.

## Fase 3 — Review y verify agrupados (una sola vez, al final)

Cuando no queden pending (o al reanudar una orquestación con `## Verify diferido` no
vacío):

1. **Review agrupado:** pasa la skill `code-review` (effort medium) UNA vez sobre el
   diff completo del lote (`git diff <Base del lote>..HEAD`; el hash está en
   `orchestrator.md`). Hallazgos confirmados → regístralos como `BUG_` (convenciones de
   la skill `add-bug`) y ciérralos con subagentes `implementer` (sonnet) por el
   protocolo de la Fase 2. Una sola pasada de review por orquestación: los commits de
   estos fixes NO re-disparan otro review.
2. **Verify agrupado:** ejecuta la skill `verify` UNA vez sobre la **unión** de
   páginas/pestañas de `## Verify diferido`, comprobando explícitamente cada criterio
   `UI:` diferido (no un paseo genérico: cada criterio, su resultado medido). Va
   después del review para cubrir también sus fixes.
3. Si todo pasa: vacía `orchestrator.md` (déjalo con el header y "_sin orquestación
   activa_") y commitea ese cierre como `chore: verify agrupado de #N..#M` (aquí sí,
   commit directo — no hay feature que cerrar).
4. Si el verify falla algo: los commits de las features ya existen — se arregla hacia
   delante. Registra el fallo como `BUG_` (convenciones de la skill `add-bug`), lanza
   un `implementer` (sonnet) para el fix con el protocolo de la Fase 2, y repite el
   check fallido. No repitas la pasada entera si el resto de criterios ya pasaron.

## Límite de 5 horas — reanudación

El diseño ya es tolerante a cortes: `feature_list.json` (status), git (commits por
feature) y `orchestrator.md` (plan + verify diferido) reconstruyen el estado
completo; reanudar = volver a invocar esta skill.

No hay forma fiable de leer el % de uso desde dentro de la sesión: no lo chequees
ni lo estimes. Los únicos disparadores válidos son que **el usuario avise**
("límite al 90%", "se ha agotado, se resetea a las 18:00") o que **un turno falle
por rate limit** con hora de reset visible. En ese caso:

- **No lances más subagentes**: una feature a medias con el límite agotado deja el
  repo sucio. Deja `orchestrator.md` al día.
- Programa la reanudación con **CronCreate**: un cron **one-shot** a la hora de
  reset **+5 min de margen**, con el prompt: "Invoca la skill orchestrate-backlog
  y reanuda la orquestación desde harness/progress/orchestrator.md". Confírmale al
  usuario la hora programada y que la sesión debe seguir abierta (los crons
  one-shot solo disparan con la sesión viva o reanudada con --resume/--continue;
  caducan a los 7 días). Si CronCreate no está disponible, dilo y pide al usuario
  que reabra el chat con esa misma frase tras el reset.
- Tras reanudar, borra el cron si sigue listado (CronDelete) y continúa la Fase 2.

No programes crons periódicos "por si acaso": quemarían turnos del límite nuevo.

## Qué NO hacer

- No implementar código en el chat principal (frontier) — ni "arreglitos rápidos".
- No lanzar subagentes en paralelo sobre el backlog (ficheros compartidos + regla
  de una feature a la vez).
- No ejecutar `verify` ni `code-review` por feature: ambos van agrupados al final.
- No duplicar el protocolo del implementer en el prompt (vive en
  `.claude/agents/implementer.md`); el prompt es la entrada JSON + contexto puntual.
- No pasar AGENTS.md/CLAUDE.md/architecture.md enteros en el prompt del subagente:
  el subagente lee ficheros concretos solo si la tarea los cita.
- No saltarse los avisos de close.sh: exit 3 = corregir lo que indica y re-ejecutar.
- No tocar `docs/IDEAS.md` jamás.
