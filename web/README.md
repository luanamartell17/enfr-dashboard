# Página web – Dashboard analítico e inferencia de riesgo

Publicada en **https://generative-s.vercel.app**. Sitio estático (HTML + Tailwind + Plotly/Chart.js) que:

- muestra el EDA a partir de los CSV de `data/` (estandarizada por provincia, odds ratio, correlación, descriptivas, prevalencias);
- predice el riesgo de hipertensión de una persona llamando al Actor de inferencia `santibelver/hta-predict`
  por la API de Apify (`run-sync-get-dataset-items`).

```
index.html        estructura de la página
css/styles.css    estilos
js/app.js         carga de datos, gráficos, simulador y llamada al Actor de inferencia
data/*.csv        resultados del EDA que lee la página
```

## Token de Apify

En este repo el token está reemplazado por `PEGAR_TOKEN_DE_APIFY` (en `js/app.js` y en `index.html`):
un token en el código de una página pública lo puede leer cualquiera. Para desplegar, cargarlo en Vercel
o, mejor, hacer que la página llame a un webhook de n8n (o a una función serverless) que guarde el token
del lado del servidor.

## Correr localmente

Servir la carpeta con cualquier servidor estático, por ejemplo `python -m http.server` dentro de `web/`,
y abrir http://localhost:8000.
