# Convenciones de código

## Python

- **Versión:** Python 3.9+
- **Estilo:** PEP 8, máximo 100 caracteres por línea
- **Nombres:**
  - Módulos y funciones: `snake_case`
  - Clases: `PascalCase`
  - Constantes: `UPPER_SNAKE`
  - Privadas: prefijo `_`
- **Strings:** comillas dobles. Interpolación con f-strings (no `.format()` ni `%`).
- **Imports:** stdlib → librerías externas → módulos locales. Un grupo por tipo, separados por línea en blanco.
- **Idioma:** UI y docs en español; código, claves y nombres de fichero en inglés.

## Comentarios

Por defecto **no** se escriben comentarios. Solo se permiten cuando explican el **porqué** (una restricción no obvia, un invariante sutil, un workaround con razón). Los nombres claros comunican el qué.

## Módulos `core/`

- Cada módulo tiene una responsabilidad única (ver `harness/docs/architecture.md`).
- Las funciones que pueden fallar lanzan excepciones con nombre, no devuelven `None`.
- No hay estado global mutable entre llamadas.
- `core/` no importa nada de `ui/`: el núcleo es reutilizable sin la UI.

## UI (`ui/`)

- La UI no contiene lógica de negocio. Llama a `core/` para todo cálculo.
- _Anota aquí el comando de arranque y los requisitos de versión del framework de UI._

## Tests (`tests/`)

- Un archivo de test por módulo de `core/`: `tests/test_<módulo>.py`.
- Usa `unittest.TestCase` con nombres descriptivos.
- Los tests de I/O usan directorios temporales reales (no mocks del filesystem).
- Ejecuta con: `python -m pytest tests/` o `python -m unittest discover tests/`.

## Harness (`harness/`)

- `init.sh` y `close.sh` se ejecutan desde la raíz del proyecto: `./harness/init.sh`.
- `check_*.py` y `viewer.py` son herramientas de desarrollo, no de producción.
- Los scripts del harness no dependen del framework de UI y deben ejecutarse en shell
  limpio (excepción: `viewer.py`, que usa Streamlit).

## Documentación

Cada feature/bug que cambie `core/`, `ui/` o el harness deja la documentación alineada
**en la misma sesión**, antes de `./harness/close.sh` (que lo verifica). Cada cosa va a
su documento, **sin duplicar**:

- `harness/docs/architecture.md` — la fuente de detalle fino: funciones públicas
  nuevas/renombradas/eliminadas, decisiones de diseño, hallazgos verificados en vivo.
- `harness/docs/data-models.md` — cualquier cambio de esquema en un fichero de datos
  (clave nueva, renombrada, eliminada o con semántica distinta).
- `harness/progress/current.md` — el changelog narrativo de la sesión (`close.sh` lo
  archiva en `history.md`). Nunca escribir changelog en `CLAUDE.md` ni architecture.md.
- `CLAUDE.md` — SOLO si cambia el mapa de una línea (módulo/página nuevo/renombrado/
  eliminado) o una decisión de arquitectura. Se mantiene por debajo de 40.000 caracteres
  (`close.sh` avisa si se supera).
- `README.md` — visión de alto nivel; actualizar solo si el cambio afecta a lo que describe.
- `harness/docs/conventions.md` / `verification.md` — solo si cambia una convención o el
  modo de verificar.

La documentación describe **lo implementado**, nunca planes futuros: lo accionable va a
`harness/feature_list.json` (skills `/add-feature`, `/add-bug`); las ideas sin madurar van
a `docs/IDEAS.md`, documento **personal del usuario** que ningún agente edita (solo se lee
cuando el usuario pida convertir ideas en features).
