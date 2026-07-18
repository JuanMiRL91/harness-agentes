---
name: add-bug
description: Registrar un bug nuevo en el backlog del harness (harness/feature_list.json) del proyecto, en estado "pending" y con el prefijo de nombre BUG_ para que el agente lo recoja ANTES que las features. Úsala cuando el usuario reporte un error, un fallo, un traceback o un comportamiento incorrecto para anotarlo (no para arreglarlo en el momento).
---

# Añadir un bug a `harness/feature_list.json`

Registra un **bug** en el mismo backlog que las features, pero marcándolo con el prefijo
`BUG_` en `name`. Ese prefijo es lo que hace que el agente que lee `AGENTS.md` lo coja
**antes** que cualquier feature `pending` (ver §4 de `AGENTS.md`). **No arregla** el bug:
solo lo registra en estado `"pending"`.

Para registrar features normales usa la skill hermana `add-feature`. Este skill comparte su
esquema y convenciones; aquí solo cambian el prefijo `BUG_` y la plantilla de `acceptance`.

## Fichero y esquema

`harness/feature_list.json` (raíz del repo). Array `features` de objetos planos con **exactamente**
estos campos (indentación de 2 espacios), igual que una feature. Las tareas cerradas NO están aquí:
`close.sh` las mueve a `harness/feature_list_archive.json` (mismo esquema, solo `done`/`Cancelled`);
los ids son **globales** entre ambos ficheros:

```jsonc
{
  "id": 34,                          // entero, secuencial = (max id actual) + 1
  "name": "BUG_cotizacion_vacia",    // SIEMPRE prefijo BUG_ + slug snake_case
  "title": "Título en español",      // corto, qué falla
  "description": "Síntoma + traceback completo + fichero/función donde ocurre + cómo reproducir. Termina SIEMPRE con una línea 'Verificación E2E: sí — <páginas a recorrer>' o 'Verificación E2E: no — <motivo>' (ver convenciones).",
  "acceptance": [
    "Reproducir el error y localizar la causa en <fichero>",
    "Arreglar el bug — comprobable con <comando o paso de UI concreto que antes fallaba>",
    "tests/test_X.py cubre el caso para que no vuelva a ocurrir (pytest tests/test_X.py -k caso)"
  ],
  "status": "pending"                // SIEMPRE pending al crear
}
```

No añadas campos extra (no hay `priority`, `type`, `category`…). El "tipo bug" se codifica
**solo** con el prefijo `BUG_` en `name`. No cambies las `rules`.

## Convenciones

- **`name`**: **siempre** empieza por `BUG_`, seguido de un slug `snake_case` corto y
  descriptivo en inglés (`BUG_cotizacion_vacia`, `BUG_duplicate_key_ficha`). El prefijo es
  obligatorio: es el marcador que prioriza el bug.
- **`id`**: secuencial, nunca se reutiliza ni se renumera. El siguiente = max entre
  `feature_list.json` **y** `feature_list_archive.json` + 1.
- **`description`**: pega el **traceback completo** si lo hay, indica el fichero/función y los
  pasos para reproducir (qué pantalla/acción lo dispara). Cuanto más concreto, mejor.
  Si el bug puede depender del sistema (encoding, rutas, `python` vs `python3`…), anota en qué
  máquina ocurrió si el proyecto corre en varias: hay bugs específicos de SO.
- **`acceptance`**: por defecto sigue el patrón *reproducir → arreglar → test de regresión*.
  Ajusta el nombre del test al área afectada (`tests/test_<módulo>.py`).
  Cada criterio debe ser **auto-comprobable**: indica el comando exacto del test, o —si el
  síntoma es de UI— el paso observable prefijado `UI:` (página/acción/resultado esperado),
  verificable con la skill `verify`. Así el agente puede cerrar el bug como condición de
  salida de un loop `/goal` sin intervención humana.
- **Verificación E2E (skill `verify`)**: la última línea de `description` declara si el
  fix requiere la verificación E2E con la app real al cerrarlo (solo se ejecuta justo
  antes de `./harness/close.sh` o por petición explícita del usuario, nunca en el init):
  - `Verificación E2E: sí — <páginas/pestañas a recorrer>` si el síntoma es de UI o el
    fix toca `core/` con impacto visible en alguna página (lo habitual en bugs).
  - `Verificación E2E: no — <motivo>` para fixes pequeños sin síntoma de UI: solo
    `harness/`/`tests/`/docs, o un fallo de `core/` totalmente cubierto por el test de
    regresión sin efecto observable en pantalla.
  En caso de duda, `sí`. Si es `no`, los criterios de `acceptance` no deben incluir
  pasos `UI:` (serían incoherentes).
- **Idioma**: `title`/`description`/`acceptance` en español; nombres de código, claves y
  ficheros en inglés.
- **`status`**: al crear, **siempre `pending`**.

## Flujo de trabajo

1. **Entender el bug.** Identifica síntoma, traceback, fichero/función y reproducción. Si el
   usuario pega un error de Streamlit/Python, consérvalo entero en `description`.
2. **Leer el backlog pendiente** (no solo el código actual):
   ```bash
   python3 -c "
   import json
   for f in json.load(open('harness/feature_list.json'))['features']:
       if f['status'] == 'pending': print(f['id'], f['name'], '·', f['title'])
   "
   ```
   Con dos objetivos:
   - **Evitar duplicados**: si un `BUG_*` pendiente ya registra el mismo síntoma, díselo al
     usuario en vez de duplicarlo.
   - **Usarlas como contexto**: si una tarea `pending` (bug o feature) va a reescribir o
     reestructurar el código donde ocurre el fallo, deja la relación explícita en
     `description` (p. ej. "el código afectado lo reescribe #NN; verificar si el fix sigue
     aplicando después") y ajusta `acceptance` a cómo quedará ese código, no solo a cómo
     está hoy. Lee la `description` completa de las pendientes que toquen la misma área.
3. **Explorar lo justo.** Para referenciar bien el fichero/función, mira el "Mapa de módulos"
   de `harness/docs/architecture.md` (esquemas JSON en `harness/docs/data-models.md`); lee el
   fichero concreto solo si hace falta precisión. No re-explores el repo.
4. **Calcular el siguiente id** (no asumas, y hazlo **justo antes de escribir**: otra sesión o
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
5. **Redactar y añadir** la entrada justo antes del `]` de cierre del array `features`, con
   `name` que empiece por `BUG_`, id consecutivo, `status: "pending"` y la indentación del fichero.
6. **Validar** (ver abajo).
7. **Resumir** al usuario la entrada creada (`id · name · título`) y recordarle que, al leer
   `AGENTS.md`, el agente cogerá este bug antes que las features pending. **No** commitear salvo
   que lo pida; **no** marcar `in_progress`; **no** arreglar el bug.

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
nuevo = max(fs, key=lambda f: f['id'])
assert nuevo['name'].upper().startswith('BUG'), 'el bug nuevo debe empezar por BUG_'
print('OK:', len(fs), 'activas ·', len(arch), 'archivadas; ultimo bug:', nuevo['name'])
"
git diff harness/feature_list.json   # solo la entrada añadida antes del ] final; resto intacto
```

## Qué NO hacer

- No omitir el prefijo `BUG_` (sin él, el bug no se prioriza).
- No marcar `done`/`in_progress` ni arreglar el código en este flujo.
- No commitear ni hacer push salvo petición explícita.
- No añadir campos fuera del esquema (nada de `type`/`category`/`priority`) ni cambiar las `rules`.
- No tocar entradas existentes (ids inmutables).
