# ENFR – EDA estadístico (Actor de Apify)

Calcula, ponderando con `peso_rel`, sobre una edición de la ENFR (por defecto 2018): descriptivas de edad e IMC, correlación,
odds ratios crudos de hipertensión y prevalencia de HTA por provincia (cruda y estandarizada por edad).
**No usa Google Drive**: lee el dataset limpio de un Key-Value Store y devuelve los resultados a n8n.

## Estructura
```
Dockerfile · requirements.txt
.actor/actor.json · .actor/input_schema.json
src/main.py            solo arma el Actor (entrada -> módulos -> salida)
src/EDA.py             lógica del EDA (run_eda)
src/entrada_salida.py  descarga del dataset desde el Key-Value Store
src/tooling_business.py archivos que se publican y resumen del run
```

## Entrada
| Campo | Obligatorio | Descripción |
|---|---|---|
| `kvStoreId` | sí | Store con el dataset limpio. **Para encadenar con el Actor ETL usar su `defaultKeyValueStoreId`** (sin pasar por Drive) |
| `claveDataset` | no | `enfr_armonizado.csv` por defecto (acepta también `.csv.gz`) |
| `anio` | no | Edición a analizar, 2018 por defecto |
| `afBajo` | no | Código de "actividad física baja" (3 por defecto; verificar con el diccionario INDEC) |

## Salida
- **Key-Value Store del run** (CSV, UTF-8): `enfr_descriptivas.csv`, `enfr_correlacion.csv`, `enfr_odds_ratio.csv`,
  `enfr_estandarizada.csv` y `RESUMEN` (JSON).
- **Dataset del run**: un ítem con las URLs de los archivos y las 4 tablas como JSON (`tablas.descriptivas`,
  `tablas.correlacion`, `tablas.odds_ratio`, `tablas.estandarizada`), para escribirlas directo en una hoja desde n8n.
- Descarga: `GET https://api.apify.com/v2/key-value-stores/<defaultKeyValueStoreId>/records/<clave>` con
  `Authorization: Bearer <token>`.