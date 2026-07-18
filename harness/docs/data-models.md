# Modelos de datos

> **Plantilla** — esquema completo de TODOS los ficheros de datos del proyecto
> (JSON, YAML, CSV…). Cada cambio de esquema (clave nueva, renombrada, eliminada o
> con semántica distinta) se documenta aquí **en la misma sesión** que lo introduce;
> `harness/check_docs.py` y `close.sh` lo verifican.

## Convenciones

- Claves de datos en inglés; textos visibles para el usuario en español.
- Escritura atómica (fichero temporal + rename) para todo JSON que edite la app.
- Ningún dato derivado/persistido dos veces: si se puede calcular, se calcula.

## <fichero>.json

Ruta: `<dónde vive>` · Lo escribe: `<módulo>` · Lo lee: `<módulos>`

```jsonc
{
  "clave": "tipo y semántica",
  "otra_clave": 0
}
```

Notas: casos límite, valores nulos, versionado del esquema si lo hay.
