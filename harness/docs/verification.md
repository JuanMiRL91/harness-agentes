# Verificación — cómo saber que tu trabajo funciona

## Antes de declarar una feature como `done`

1. **Ejecuta `./harness/init.sh`** — debe terminar sin errores (`[OK]` en todos los checks,
   incluyendo el check de **Contratos UI↔core**).
2. **Tests verdes:** todos los tests del módulo afectado pasan.
   ```bash
   python -m pytest tests/ -v
   ```
3. **Verificación E2E de la UI (skill `verify`):** si la `description` de la tarea dice
   `Verificación E2E: sí` (o, si no dice nada, cuando el cambio toca `core/` o `ui/`),
   ejecuta la skill `verify` (`.claude/skills/verify/SKILL.md`): arranca la app real,
   recorre las páginas afectadas interactuando con el flujo cambiado, y comprueba que no
   hay errores nuevos en el log de la app ni en la terminal. Los tests no sustituyen este
   paso. Se ejecuta **solo aquí** (una vez, justo antes de `close.sh`) o cuando el usuario
   pida verificar explícitamente — nunca al inicio de sesión ni en `init.sh`. Si la tarea
   dice `Verificación E2E: no`, este paso se salta.
4. **Criterios de `acceptance` uno a uno:** cada criterio de la tarea en
   `harness/feature_list.json` indica su método de comprobación (comando de test o paso
   `UI:`); verifícalos todos antes de marcar `done`.
5. **Sin residuos:** no hay `print()` de debug, TODOs sin contexto, ni archivos temporales.

## Pruebas por capa

### core/
- `python -m pytest tests/test_<módulo>.py -v`
- Para módulos con I/O, usa directorios temporales reales.
- Para clientes de APIs externas, mockea las llamadas HTTP con `unittest.mock`.

### UI
- Arranca la app con su comando de entrada (documentado en `conventions.md`).
- Verifica que las páginas principales cargan sin excepciones en la terminal.

## Checks de integridad del harness

`./harness/init.sh` verifica automáticamente:
- Python 3.9+ instalado.
- Archivos obligatorios presentes (`AGENTS.md`, `harness/feature_list.json`,
  `harness/feature_list_archive.json`, `harness/progress/current.md`, `harness/docs/`).
- Solo una feature en estado `in_progress` a la vez; el archivo de cerradas solo contiene
  `done`/`Cancelled` y no hay ids duplicados entre activo y archivo.
- Tests ejecutados correctamente (en orden alfabético y en orden inverso, para detectar
  estado compartido entre ficheros de test).
- **Contratos UI↔core** (`harness/check_contracts.py`): todos los símbolos que `ui/` importa
  de `core/` existen realmente. Detecta `AttributeError` e `ImportError` en runtime antes
  de arrancar la app. Si este check falla, la app **no arrancará**.
- **Texto placeholder** (`harness/check_placeholder.py`): ningún literal de cadena de
  `core/`/`ui/` contiene texto de relleno de la lista negra.

## Cierre de sesión

Cuando la feature esté `done`, ejecuta:
```bash
./harness/close.sh
```
El script verifica `init.sh`, detecta si `CLAUDE.md`/`README.md`/
`harness/docs/architecture.md` necesitan actualización — checks binarios más el cruce
determinista de `harness/check_docs.py`, que lista los símbolos públicos del diff que
faltan/sobran en los docs y los módulos de `core/`/`ui/` sin mención en la Estructura
del `README.md` —, y si el commit es un `fix` recuerda el **ciclo sistémico**: qué check
del harness habría detectado el bug (añádelo con la skill `improve-harness`, o anota en
`current.md` por qué no aplica). Después mueve `current.md` a `history.md`, lo resetea y
hace el commit automático.

Antes de `close.sh`, pasa `/code-review` sobre el diff de la sesión (revisión con
contexto fresco) y aplica o descarta razonadamente sus hallazgos (ver `AGENTS.md` §5).
