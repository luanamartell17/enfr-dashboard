# Dashboard ENFR 2005-2018

Dashboard en Streamlit con los resultados del EDA de la Encuesta Nacional de Factores de Riesgo (INDEC):
prevalencia de hipertensión, diabetes, colesterol alto y obesidad por año, sexo, edad, ingreso,
cobertura, tabaco, región y provincia.

## Pipeline

```
.txt crudos ENFR (Google Drive, ENFR_pipeline/01_crudo)
  → n8n: los sube a Apify y corre los Actores
      → Actor ETL  → dataset limpio
      → Actor EDA  → descriptivas, correlación, odds ratio, estandarizada
  → n8n: guarda todo en Drive (ENFR_pipeline/02_resultados) y actualiza data/ en este repo
  → Streamlit (este repo) se republica solo y muestra los datos nuevos

Modelo (aparte del flujo):
  entrenamiento.py → modelo_hta_logreg.pkl (regresión logística, ENFR 2005-2018)
  → Actor de inferencia en Apify → la página https://generative-s.vercel.app lo consulta por API
```

- Dashboard: https://generative-s.streamlit.app
- Página de predicción: https://generative-s.vercel.app (código en `web/`)
- Actor de inferencia: https://console.apify.com/actors/bhqxlvFcUopkQ2xfE

## Modelo

Regresión logística para predecir hipertensión (autorreportada). Validación: train 2005-2013, test 2018.
ROC-AUC 0,767 en el test, con umbral de alerta 0,40: recall 0,66 y precisión 0,61. El modelo final se
reentrena con los 4 años (`apify/inferencia/entrenamiento/entrenamiento.py`).

## Estructura

```
app.py                     dashboard de Streamlit
data/
  crudo/                   dataset crudo: .txt originales de la base usuario ENFR (INDEC) 2005, 2009, 2013 y 2018
  enfr_eda.csv             prevalencias por indicador, año y corte (salida del EDA)
  enfr_descriptivas.csv    media, varianza, desvío y cuartiles de edad, IMC, peso y talla
  enfr_correlacion.csv     matriz de correlación
  enfr_odds_ratio.csv      odds ratio crudos y ajustados por edad (target: hipertensión)
  enfr_estandarizada.csv   hipertensión por provincia, cruda y estandarizada por edad
  micro/                   dataset limpio (salida del ETL): una fila por persona, un archivo por año
  inferencia/              resultado del modelo: 30 inferencias del Actor (casos válidos, faltantes y errores)
n8n/
  pipeline_enfr.json       flujo principal: Drive → Actores de Apify (ETL, EDA) → Drive + GitHub → dashboard
  CONTRATO_ACTORES.md      qué recibe y devuelve cada Actor dentro del flujo
  workflow_enfr.json       flujo anterior (publica la planilla del EDA en Google Sheets)
apify/
  etl/  eda/  inferencia/  código fuente de los 3 Actores de Apify (ver apify/README.md)
  inferencia/entrenamiento/entrenamiento.py  entrenamiento del modelo que usa el Actor de inferencia
web/                       página web (https://generative-s.vercel.app): EDA + predicción con el Actor de inferencia
```

Los workflows se importan en n8n con **⋯ → Import from file**.

## Datos

- Por defecto lee `data/enfr_eda.csv`.
- Si se define el secreto `DATA_URL` (en Streamlit Cloud: *Settings → Secrets*), lee esa URL CSV.
  Por ejemplo, la pestaña `dashboard` que actualiza n8n:

```toml
DATA_URL = "https://docs.google.com/spreadsheets/d/<ID>/gviz/tq?tqx=out:csv&sheet=dashboard"
```

  La planilla tiene que estar compartida como "Cualquier persona con el enlace puede ver".

## Correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```
