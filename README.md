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
      → Actor de inferencia → riesgo de hipertensión por persona (2018)
  → n8n: guarda todo en Drive (ENFR_pipeline/02_resultados) y actualiza data/ en este repo
  → Streamlit (este repo) se republica solo y muestra los datos nuevos
```

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
notebooks/
  ENFR_EDA_estadistica.ipynb  cálculo de descriptivas, correlación, odds ratio y estandarización
n8n/
  pipeline_enfr.json       flujo principal: Drive → Actores de Apify (ETL, EDA, inferencia) → Drive + GitHub → dashboard
  CONTRATO_ACTORES.md      qué recibe y devuelve cada Actor dentro del flujo
  workflow_enfr.json       flujo anterior (publica la planilla del EDA en Google Sheets)
apify/
  etl/  eda/  inferencia/  código fuente de los 3 Actores de Apify (ver apify/README.md)
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
