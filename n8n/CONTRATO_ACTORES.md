# Cómo se conecta el flujo de n8n con los Actores de Apify

El workflow `n8n/pipeline_enfr.json` usa los tres Actores **tal como están**. Este documento describe qué
les manda n8n y qué toma de cada uno.

```
Google Drive  ENFR_pipeline/01_crudo  (4 .txt de INDEC)
   │  n8n descarga los .txt y los sube al key-value store "enfr-crudo" de Apify
   ▼
Actor ETL  (santibelver/etl)          input  {kvStoreId: <enfr-crudo>, noMedidoComoNegativo: true}
   │                                   output store del run: enfr_armonizado.csv + diccionario y reportes QA
   ▼
Actor EDA  (santibelver/eda)          input  {kvStoreId: <store del run del ETL>, claveDataset: "enfr_armonizado.csv",
   │                                          anio: 2018, afBajo: 3}
   │                                   output store del run: enfr_descriptivas / correlacion / odds_ratio / estandarizada .csv
   ▼
Actor inferencia  (source-code.zip)   n8n baja enfr_armonizado.csv, filtra el año 2018 y lo manda en lotes de 3.000:
   │                                   input  {registros: [{id, edad, mujer, ...features}], incluirEntrada: false}
   │                                   output un item por persona: probabilidad_hta, alerta, nivel_riesgo
   │                                   n8n arma enfr_riesgo_2018.csv y enfr_kpi_riesgo.csv (% en alerta, recall, precisión)
   ▼
n8n guarda todo en Drive  ENFR_pipeline/02_resultados  y publica los CSV chicos en GitHub  data/
   ▼
Streamlit (https://generative-s.streamlit.app) se actualiza solo con cada commit en data/
```

## Detalles

- **Nombres en el store crudo:** n8n reemplaza los espacios y caracteres no permitidos del nombre del archivo
  de Drive por `_` (las claves de Apify solo aceptan `a-z A-Z 0-9 ! - _ . ' ( )`). El Actor ETL detecta el año por el nombre.
- **Espera:** n8n arranca cada Actor de forma asíncrona y consulta su estado cada 20-30 s hasta `SUCCEEDED`.
  Si termina en `FAILED`, `ABORTED` o `TIMED-OUT`, el flujo se detiene con el link al log del run.
- **Inferencia opcional:** el modelo no corre en el flujo: el Actor `hta-predict` lo usa la página
  https://generative-s.netlify.app por API. El paso queda preparado en el workflow; mientras el parámetro
  `actor_inferencia` diga `PEGAR_...`, se saltea y el flujo publica igual los resultados del ETL y del EDA.
- **`enfr_eda.csv`** (prevalencias por año y grupo, que usan las pestañas Evolución, Por grupo y Provincias) no lo
  genera ningún Actor: el dashboard sigue usando el de `data/` del repo. Si en algún momento un Actor lo publica con
  ese nombre, el flujo ya lo recoge (está en `salidas_eda`).
- **Archivos que van a GitHub** (parámetro `archivos_github`): solo los CSV que el dashboard lee con el mismo
  formato que generan los Actores (`enfr_correlacion.csv`, `enfr_estandarizada.csv`, y los de riesgo y KPIs de la
  inferencia). `enfr_descriptivas.csv` y `enfr_odds_ratio.csv` del repo son versiones más completas (todos los años y OR
  ajustado por edad) que las del Actor EDA, así que no se pisan. Todo lo que generan los Actores (dataset limpio, QA y EDA)
  queda guardado en Drive (`02_resultados`).
- **Commits de a uno:** n8n publica en GitHub un archivo por vez (1,5 s entre cada uno); si salen en paralelo, GitHub
  rechaza los que llegan con la rama desactualizada.

## Credenciales en n8n

| Credencial | Tipo en n8n | Para qué |
|---|---|---|
| Google Drive | Google Drive OAuth2 API | leer `01_crudo` y escribir en `02_resultados` |
| Apify API | Header Auth: nombre `Authorization`, valor `Bearer <token de Apify>` | subir los .txt, correr los Actores, leer resultados |
| GitHub | GitHub API (token con permiso *Contents: Read and write* sobre el repo) | actualizar `data/` para el dashboard |

Los tokens se cargan **solo** en las credenciales de n8n: nunca en el workflow, en el código ni en GitHub.

Los Actores de Santino corren con la cuenta dueña del token de Apify que se cargue en n8n: esa cuenta necesita
acceso a los Actores (compartidos con ella) y al store `enfr-crudo`, que n8n crea en esa misma cuenta.
