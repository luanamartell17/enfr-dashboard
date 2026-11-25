# Código fuente de los Actores de Apify

Los tres Actores que usa el flujo de n8n (`n8n/pipeline_enfr.json`). En los tres, `main.py` solo arma el Actor
(lee la entrada, llama a los módulos y escribe la salida); la lógica vive en archivos aparte.

| Carpeta | Actor en Apify | Qué hace | Lógica |
|---|---|---|---|
| `etl/` | `santibelver/etl` | `.txt` crudos de la ENFR → dataset limpio y armonizado (`enfr_armonizado.csv`) + reportes de calidad | `src/ETL.py`, `src/entrada_salida.py`, `src/tooling_business.py` |
| `eda/` | `santibelver/eda` | dataset limpio → descriptivas, correlación, odds ratio y prevalencia estandarizada | `src/EDA.py`, `src/entrada_salida.py`, `src/tooling_business.py` |
| `inferencia/` | `santibelver/hta-predict` ([consola](https://console.apify.com/actors/bhqxlvFcUopkQ2xfE)) | personas → probabilidad de hipertensión con el modelo entrenado | `my_actor/preprocessing.py`, `my_actor/model.py`, `my_actor/tooling_business.py`; entrenamiento en `inferencia/entrenamiento/entrenamiento.py` |

## Cómo se usan

```
n8n: Drive 01_crudo → key-value store "enfr-crudo"
  → ETL  {kvStoreId: enfr-crudo}
  → EDA  {kvStoreId: store del run del ETL, anio: 2018}
n8n: resultados → Drive 02_resultados y GitHub data/ → dashboard Streamlit

Inferencia (fuera del flujo de n8n):
  entrenamiento.py → models/modelo_hta_logreg.pkl.b64 → Actor hta-predict
  la página https://generative-s.vercel.app le manda {registros: [...]} por la API de Apify
```

Ejemplo de salida del Actor de inferencia (30 casos, incluye datos faltantes y errores): `data/inferencia/dataset_hta-predict_inferencias.json`.

Detalle de entradas y salidas: `n8n/CONTRATO_ACTORES.md`.

## Configuración en Apify

- `etl` y `eda` corren con **Full permissions** (Settings → Actor permissions): necesitan leer el store que crea n8n
  y el store del run anterior.
- `requirements.txt` de `etl` y `eda` incluye `httpx` (lo usa `entrada_salida.py`).
- El modelo de `inferencia` va en `models/modelo_hta_logreg.pkl.b64` y exige la misma versión de scikit-learn con la que
  se entrenó (fijada en su `requirements.txt`).

## Desplegar desde esta carpeta

Con la CLI de Apify (`npm i -g apify-cli`), dentro de cada carpeta: `apify login` y después `apify push`.
