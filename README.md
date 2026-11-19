# Dashboard ENFR 2005-2018

Dashboard en Streamlit con los resultados del EDA de la Encuesta Nacional de Factores de Riesgo (INDEC):
prevalencia de hipertensión, diabetes, colesterol alto y obesidad por año, sexo, edad, ingreso,
cobertura, tabaco, región y provincia.

## Pipeline

```
.txt crudos ENFR (Google Drive)
  → n8n: ETL (script Python) → CSV limpios en Drive
  → n8n: EDA (script Python) → enfr_eda.csv / pestaña "dashboard" en Google Sheets
  → Streamlit (este repo) lee esos datos y los muestra
```

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
