"""Punto de entrada del Actor EDA ENFR.

Solo arma el Actor: lee la entrada, llama a los módulos y publica la salida. La lógica vive en:
  - EDA.py               -> cálculos estadísticos (run_eda)
  - entrada_salida.py    -> descarga del dataset limpio desde un Key-Value Store
  - tooling_business.py  -> qué archivos se publican y el resumen
El Actor no usa Google Drive: n8n sube el dataset (o pasa el store del Actor ETL) y recoge los resultados.
"""
import os
import tempfile

import pandas as pd
from apify import Actor

from .EDA import run_eda
from .entrada_salida import EntradaInvalida, descargar_dataset, validar_entrada
from .tooling_business import ARCHIVOS_SALIDA, resumen


async def main() -> None:
    async with Actor:
        try:
            kv_store_id, clave, anio, af_bajo = validar_entrada(await Actor.get_input() or {})
            with tempfile.TemporaryDirectory() as tmp:
                carpeta_out = os.path.join(tmp, "out")
                await Actor.set_status_message("Descargando dataset limpio")
                ruta = os.path.join(tmp, "dataset" + (".csv.gz" if clave.lower().endswith(".gz") else ".csv"))
                await descargar_dataset(kv_store_id, clave, ruta)
                df = pd.read_csv(ruta)
                Actor.log.info("Dataset leído: %s filas x %s columnas", f"{len(df):,}", df.shape[1])

                await Actor.set_status_message("Ejecutando EDA")
                resultado = run_eda(None, carpeta_out, anio=anio, af_bajo=af_bajo, df=df)

                await Actor.set_status_message("Publicando resultados")
                for nombre in ARCHIVOS_SALIDA:
                    with open(os.path.join(carpeta_out, nombre), "rb") as f:
                        await Actor.set_value(nombre, f.read(), content_type="text/csv; charset=utf-8")
                datos = resumen(resultado, anio, carpeta_out)
        except (EntradaInvalida, ValueError, KeyError) as e:
            await Actor.set_status_message(f"Error: {e}")
            raise
        await Actor.push_data(datos)
        await Actor.set_value("RESUMEN", datos)
        await Actor.set_status_message(f"EDA {anio} listo: {len(datos['archivos'])} archivos")