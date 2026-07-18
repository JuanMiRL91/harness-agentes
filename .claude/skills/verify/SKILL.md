---
name: verify
description: Verificación E2E de la app tras un cambio en core/ o ui/ — arranca la app real, recorre las páginas afectadas con el navegador, y comprueba de forma cuantitativa que no hay excepciones nuevas ni en el log de la app ni en la terminal. Ejecutar SOLO como último paso antes de ./harness/close.sh (si la tarea la requiere) o cuando el usuario pida verificar explícitamente — NUNCA en init.sh ni al inicio de sesión. Los tests y check_contracts.py NO sustituyen este paso.
---

# Verificar la app de punta a punta

> **Adaptar al proyecto:** sustituye `<comando de arranque>` y `<log de la app>` por los
> valores reales (p. ej. `streamlit run ui/inicio.py` y `logs/app.log`) la primera vez
> que adoptes el harness.

Los tests de `tests/` y `harness/check_contracts.py` no ejercitan la UI real: hay bugs
que solo se ven **usando la app**. Esta skill codifica esa prueba manual como checks
reproducibles y cuantitativos. Cuanto más cuantitativo el check, mejor te
auto-verificas: cada paso de abajo tiene un criterio de éxito medible, no una impresión.

## Cuándo se ejecuta (y cuándo NO)

Solo hay **dos** disparadores válidos:

1. **Cierre de sesión:** como último paso antes de `./harness/close.sh`, cuando la tarea
   está completada y su `description` en `harness/feature_list.json` indica
   `Verificación E2E: sí` (o tiene criterios `UI:` en `acceptance`).
2. **Invocación directa del usuario:** solo si pide verificar de forma explícita e
   inequívoca ("verifica la app", "pasa /verify", "comprueba la UI de punta a punta").
   Una mención genérica a "comprobar" o "revisar" el código NO cuenta.

**NUNCA** ejecutarla al inicio de sesión, dentro de `./harness/init.sh`, ni como
exploración previa: es la skill más cara en tokens del harness y su valor está en
verificar el cambio YA hecho, no el estado de partida.

No aplica a cambios que solo tocan `harness/`, `tests/` o docs (ahí basta
`./harness/init.sh`), ni a tareas cuya `description` diga `Verificación E2E: no`
(cambios pequeños sin flujo de UI nuevo). Si la tarea toca `core/` o `ui/` y su
`description` no dice nada, aplica el criterio por defecto: ejecutarla.

## Elegir el navegador (en este orden)

1. **Navegador integrado** (app de escritorio de Claude): herramientas
   `mcp__Claude_Browser__*` (`preview_start`, `read_page`, `computer`, …).
   **Es la vía preferida**: arranca la app desde `.claude/launch.json`, gestiona el
   proceso y da acceso a logs del servidor (`preview_logs`) y consola del navegador
   (`read_console_messages`) sin trabajo extra.
2. **Chrome real** (`mcp__claude-in-chrome__*`, cárgalas vía ToolSearch en UNA llamada
   si están deferred): solo si el navegador integrado no está disponible. En este caso
   arranca la app tú mismo con Bash (ver variante del paso 2).
3. **Sin navegador**: si la UI renderiza por websocket (p. ej. Streamlit), un `curl` al
   puerto solo devuelve el shell HTML y NO sirve como verificación de contenido. Deja
   constancia explícita de que la verificación visual quedó pendiente del usuario (no
   la des por hecha).

## Procedimiento

### 1. Línea base de logs

```bash
BASE_LOG=$(wc -l < <log de la app> 2>/dev/null || echo 0)
```

### 2. Arrancar la app real

**Con navegador integrado (preferido):** `preview_start` — usa la configuración de
`.claude/launch.json` y abre la pestaña él solo. Guarda el `serverId` (para
`preview_logs`/`preview_stop`) y el `tabId` del resultado. Si la app ya estaba
arrancada de antes, `preview_start` reutiliza el servidor: recarga la página para
partir de estado limpio. NO arranques la app con Bash en esta vía.

**Fallback con Chrome real:** lánzala con Bash en background
(`run_in_background: true`):

```bash
<comando de arranque>   # en un puerto libre dedicado a verificación
```

y espera a que la salida indique que el servidor está listo. Si el puerto está
ocupado, usa otro.

**Criterio (ambas vías):** arranca sin traceback en <30s — compruébalo con
`preview_logs` (nivel `error`) o con la salida del proceso en background.

### 3. Recorrer las páginas con el navegador

Con el navegador elegido, abre la app y recorre:

1. **La página principal**: se renderiza sin mensaje de excepción.
2. **La página/pestaña afectada por el cambio de la sesión** — este es el paso
   importante: **interactúa con el flujo cambiado, no solo lo mires**. Si el cambio fue
   un botón/formulario, púlsalo/rellénalo y comprueba el estado resultante (¿el fichero
   de datos esperado cambió? ¿la fila muestra el valor nuevo?); si fue un cálculo,
   verifica un valor concreto contra el dato de origen.
3. Un pase rápido por el resto de páginas para detectar roturas colaterales: cada una
   carga sin excepción visible.

Consejos con el navegador integrado: para verificar texto y estructura prefiere
`read_page` (devuelve refs para `computer`/`form_input`) sobre screenshots; usa
`computer` para clics/teclado y `read_console_messages` con `onlyErrors: true` para
cazar errores JS del frontend.

Haz **screenshot** de la página afectada como evidencia (acción `screenshot` de
`computer` en cualquiera de las dos vías).

Precaución: si las páginas disparan llamadas a APIs externas, es normal que tarden;
un fallo de red externo NO es un fallo del cambio (compruébalo en el log: esas rutas
deben registrar warning y degradar sin romper).

### 4. Comprobar logs y salida

```bash
tail -n +$((BASE_LOG + 1)) <log de la app> | grep -nE "ERROR|Traceback" || echo "sin errores nuevos"
```

**Criterio:** cero líneas `ERROR`/`Traceback` nuevas atribuibles al cambio (un warning
de red externa documentado no cuenta). Revisa también la salida del proceso de la app:
con navegador integrado, `preview_logs` con `level: "error"`; con Bash en background,
la salida del proceso. Cero tracebacks.

### 5. Parar la app

Con navegador integrado: `preview_stop` con el `serverId`. Con Bash: mata el proceso
lanzado en el paso 2. No dejes procesos colgados.

## Resultado

Reporta como una lista de checks con su resultado medido (arranque OK, página X
renderiza, interacción Y produce Z, 0 errores nuevos en log), no como "todo funciona".
Si algún check falla, la feature NO está lista para `done` ni para `./harness/close.sh`.
