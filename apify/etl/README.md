# ENFR – ETL (Actor de Apify)

Convierte los `.txt` crudos de la Encuesta Nacional de Factores de Riesgo (2005, 2009, 2013, 2018) en un dataset limpio y
armonizado. **No usa Google Drive**: n8n sube los `.txt` a un Key-Value Store de Apify, ejecuta el Actor y recoge los resultados.

## Estructura
```
Dockerfile · requirements.txt
.actor/actor.json · .actor/input_schema.json
src/main.py            solo arma el Actor (entrada -> módulos -> salida)
src/ETL.py             lógica del ETL (run_etl)
src/entrada_salida.py  descarga de los .txt desde el Key-Value Store
src/tooling_business.py archivos que se publican y resumen del run
```

## Entrada
| Campo | Obligatorio | Descripción |
|---|---|---|
| `kvStoreId` | sí | ID del Key-Value Store donde están los `.txt` |
| `archivos` | no | `[{"anio": 2009, "clave": "x.txt"}, ...]`. Si se omite, usa todas las claves `*.txt` y detecta el año por el nombre (debe contener 2005/2009/2013/2018) |
| `noMedidoComoNegativo` | no | `true` por defecto (solo afecta a los targets compuestos) |

Las claves de un Key-Value Store solo admiten `a-z A-Z 0-9 ! - _ . ' ( )`: reemplazar espacios y otros caracteres del nombre
del archivo de Drive antes de subirlo.

## Salida
- **Key-Value Store del run** (CSV, UTF-8): `enfr_armonizado.csv` (dataset limpio), `diccionario_variables.csv`,
  `qa_nulos_por_anio.csv`, `qa_log_limpieza.csv`, `qa_validacion_oficial.csv`, y `RESUMEN` (JSON).
- **Dataset del run**: un ítem con el resumen (filas, columnas, filas por año, validación contra INDEC y la URL de cada archivo).
- Cada archivo se descarga con `GET https://api.apify.com/v2/key-value-stores/<defaultKeyValueStoreId>/records/<clave>`
  y header `Authorization: Bearer <token>`.

Si los `.txt` no cumplen la validación contra las prevalencias oficiales de INDEC (>98 % de coincidencia) o falta algún año,
el run termina en **FAILED** con el motivo en el mensaje de estado.