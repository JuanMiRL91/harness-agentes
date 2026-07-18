---
name: add-feature
description: Añadir una o varias tareas nuevas al backlog del harness (harness/feature_list.json) del proyecto, en estado "pending" y con las convenciones del repo. Úsala cuando el usuario pida "añadir feature/tarea", "nueva feature", o describa implementaciones para registrar en el backlog (no para implementarlas).
---

# Añadir features a `harness/feature_list.json`

Registra tareas nuevas en el backlog del harness de agentes. **No implementa** las features: solo
las planifica y las añade en estado `"pending"` para que un agente las recoja después (regla
`one_feature_at_a_time`). Una entrada por cada implementación que indique el usuario, salvo que pida
agruparlas.

## Fichero y esquema

`harness/feature_list.json` (raíz del repo). Array `features` de objetos planos con **exactamente** estos
campos (indentación de 2 espacios). Las tareas cerradas NO están aquí: `close.sh` las mueve a
`harness/feature_list_archive.json` (mismo esquema, solo `done`/`Cancelled`); los ids son **globales**
entre ambos ficheros:

```jsonc
{
  "id": 32,                       // entero, secuencial = (max id actual) + 1, +1 por cada feature
  "name": "ui_pagina_algo",        // snake_case, prefijo por área (ver convenciones)
  "title": "Título en español",   // corto, descriptivo
  "description": "Qué y por qué. Referencia ficheros/funciones concretos. Para bugs, pega el traceback. Termina SIEMPRE con una línea 'Verificación E2E: sí — <páginas a recorrer>' o 'Verificación E2E: no — <motivo>' (ver convenciones).",
  "acceptance": [                 // criterios verificables Y auto-comprobables (ver convenciones)
    "tests/test_storage.py cubre que guardar_config persiste la clave nueva (pytest tests/test_storage.py -k config)",
    "UI: en la página afectada, el botón muestra 'Guardar' — verificable con la skill verify"
  ],
  "status": "pending"             // SIEMPRE pending al crear (nunca in_progress)
}
```

No añadas campos extra (no hay `priority`, `dependencies`, `category`...). Las dependencias se
explican en prosa dentro de `description`.

## Convenciones

- **`id`**: secuencial, nunca se reutiliza ni se renumera. El siguiente = max entre
  `feature_list.json` **y** `feature_list_archive.json` + 1.
- **`name`** (snake_case, en inglés) por prefijo de área:
  - `core_*` → núcleo (`core/…`)  ·  `ui_*` → UI (`ui/…`)
  - `harness_*` → infraestructura de desarrollo (`harness/…`)
  - `BUG_*` → bug. **Para registrar un bug usa la skill `add-bug`** (aplica el prefijo
    `BUG_` y lo prioriza en `AGENTS.md`); no registres bugs desde aquí.
  - refactor → verbo (`reorganizar_…`, `deduplicar_…`)
  - La lista no es cerrada: si surge un área nueva, usa un prefijo corto coherente con estos.
- **Idioma**: `title`/`description`/`acceptance` en español; nombres de código, claves y ficheros en inglés.
- **`acceptance`**: específico, verificable y **auto-comprobable**: cada criterio debe indicar
  CÓMO se comprueba, no solo qué debe cumplirse, para que un agente pueda verificarlo sin
  intervención humana (p.ej. como condición de salida de un loop `/goal`). Tres formas válidas:
  - un test concreto con su comando (`pytest tests/test_X.py -k caso`);
  - un comando/script cuya salida esperada se indica;
  - un paso de UI observable, prefijado `UI:`, describiendo página/acción/resultado —
    verificable con la skill `verify` (arranca la app real y recorre el flujo).
  Evita criterios vagos ("funciona bien") y criterios sin método de comprobación.
- **Verificación E2E (skill `verify`)**: la última línea de `description` declara si la
  tarea requiere la verificación E2E con la app real al cerrarla (es la skill más cara en
  tokens; solo se ejecuta justo antes de `./harness/close.sh` o por petición explícita
  del usuario, nunca en el init):
  - `Verificación E2E: sí — <páginas/pestañas a recorrer>` cuando la feature añade o
    cambia un flujo de UI, un cálculo que la UI muestra, o toca `core/` con impacto
    visible en alguna página.
  - `Verificación E2E: no — <motivo>` para cambios pequeños sin flujo de UI nuevo:
    solo `harness/`/`tests/`/docs, refactors internos sin cambio de comportamiento,
    ajustes de estilo/texto triviales cubiertos por un test.
  En caso de duda, `sí`. Si es `no`, los criterios de `acceptance` no deben incluir
  pasos `UI:` (serían incoherentes).
- **`status`** ∈ `pending | in_progress | done | blocked | Postponed | Cancelled`. Al crear: **siempre `pending`**.

## Flujo de trabajo

1. **Entender la petición.** Si el usuario lista varias implementaciones, normalmente = una feature por punto.
2. **Leer el backlog pendiente** (no solo el código actual):
   ```bash
   python3 -c "
   import json
   for f in json.load(open('harness/feature_list.json'))['features']:
       if f['status'] == 'pending': print(f['id'], f['name'], '·', f['title'])
   "
   ```
   Con dos objetivos:
   - **Evitar duplicados**: si una tarea `pending` ya cubre (total o parcialmente) lo pedido,
     díselo al usuario en vez de duplicarla.
   - **Usarlas como contexto de diseño**: si una tarea `pending` va a cambiar la estructura o
     el comportamiento del área afectada (esquema de datos, layout de carpetas/UI, firma o
     ubicación de una función…), redacta la nueva feature **contando con ese cambio futuro**,
     no solo contra el código de hoy, y deja la relación explícita en `description`
     (p. ej. "asume que #NN ya habrá dividido pendientes.py en dos secciones"). Lee la
     `description` completa de las pendientes que toquen la misma área, no solo el título.
3. **Decisiones de diseño primero.** Si una feature implica una elección no trivial (dónde guardar
   datos, comportamiento de UI, fuente de datos, alcance...), usa **AskUserQuestion ANTES de redactar**,
   ofreciendo una recomendación como primera opción. No inventes el enfoque.
4. **Explorar lo justo.** Para referenciar bien ficheros/funciones en `description`/`acceptance`,
   consulta el **"Mapa de módulos"** de `harness/docs/architecture.md` (los esquemas JSON
   están en `harness/docs/data-models.md`) y, si hace falta precisión, lee el fichero
   concreto (un módulo de `ui/` o `core/`). No re-explores todo el repo para tareas claras.
5. **Calcular el siguiente id** (no asumas, y hazlo **justo antes de escribir**: otra sesión o
   job en paralelo puede haber añadido entradas desde que abriste el fichero):
   ```bash
   python3 -c "
   import json
   mx = 0
   for p in ('harness/feature_list.json', 'harness/feature_list_archive.json'):
       try:
           mx = max([mx] + [f['id'] for f in json.load(open(p))['features']])
       except FileNotFoundError:
           pass
   print(mx + 1)
   "
   ```
6. **Redactar y añadir** las entradas justo antes del `]` de cierre del array `features`, con id
   consecutivo, `status: "pending"`, y respetando el esquema/indentación.
7. **Validar** (ver más abajo).
8. **Resumir** al usuario la tabla `id · name · título`. **No** commitear salvo que lo pida; **no**
   marcar `in_progress`; **no** implementar la feature.

## Verificación

```bash
python3 -c "
import json
d = json.load(open('harness/feature_list.json'))           # parsea sin error
fs = d['features']; valid = set(d['rules']['valid_status'])
try:
    arch = json.load(open('harness/feature_list_archive.json'))['features']
except FileNotFoundError:
    arch = []
ids = [f['id'] for f in fs] + [f['id'] for f in arch]
assert len(ids) == len(set(ids)), 'ids duplicados (archivo incluido)'
for f in fs:
    assert f['status'] in valid, f'status invalido en {f[\"id\"]}'
    assert set(f) == {'id','name','title','description','acceptance','status'}, f'campos raros en {f[\"id\"]}'
print('OK:', len(fs), 'activas ·', len(arch), 'archivadas')
"
git diff harness/feature_list.json   # solo entradas añadidas antes del ] final; resto intacto
```

## Qué NO hacer

- No marcar `done`/`in_progress` ni implementar el código de la feature.
- No commitear ni hacer push salvo petición explícita.
- No añadir campos fuera del esquema ni cambiar las `rules`.
- No tocar entradas existentes (ids inmutables).
