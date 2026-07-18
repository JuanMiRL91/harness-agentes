# Arquitectura

> **Plantilla** — este documento es la fuente de **detalle fino** del proyecto: se
> rellena y se mantiene al implementar. `harness/check_docs.py` cruza los símbolos
> públicos del diff de cada sesión contra este fichero (y `data-models.md` /
> `CLAUDE.md`): toda función pública nueva debe quedar mencionada aquí.

## Decisiones de arquitectura (cerradas)

_Lista de decisiones tomadas y cerradas, con su justificación en una o dos líneas.
Ejemplos: stack elegido, persistencia, fuentes de datos externas, qué queda fuera
del alcance. Las decisiones abiertas NO van aquí: van al backlog o a ideas._

- ...

## Mapa de módulos

_Una sección por módulo de `core/` y `ui/`, con sus funciones públicas: firma breve,
qué hace, qué lanza. Este es el nivel de detalle que NO va en `CLAUDE.md` (allí solo
el mapa de una línea por módulo)._

### core/<modulo>.py

- `funcion_publica(arg) -> tipo` — qué hace, invariantes, excepciones.

### ui/<pagina>.py

- ...

## Hallazgos verificados en vivo

_Comportamientos de APIs externas, series de datos, límites o rarezas comprobadas
empíricamente durante el desarrollo. Evita re-descubrirlos en cada sesión._

- ...
