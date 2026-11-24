"""Punto de entrada del Actor ETL ENFR.

Solo arma el Actor: lee la entrada, llama a los módulos y publica la salida. La lógica vive en:
  - ETL.py               -> pipeline de limpieza y armonización (run_etl)
  - entrada_salida.py    -> descarga de los .txt desde un Key-Value Store
  - tooling_business.py  -> qué archivos se publican y el resumen
El Actor no usa Google Drive: n8n sube los .txt al Key-Value Store y recoge los resultados.
"""
import tempfile
import os

from apify import Actor

from .ETL import run_etl
from .entrada_salida import EntradaInvalida, descargar_txt, validar_entrada
from .tooling_business import ARCHIVOS_SALIDA, resumen


async def main() -> None:
    async with Actor:
        try:
            kv_store_id, archivos, no_medido_como_negativo = validar_entrada(await Actor.get_input() or {})
            with tempfile.TemporaryDirectory() as tmp:
                carpeta_in, carpeta_out = os.path.join(tmp, "in"), os.path.join(tmp, "out")
                await Actor.set_status_message("Descargando archivos .txt")
                nombres = await descargar_txt(kv_store_id, archivos, carpeta_in)
                Actor.log.info("Archivos descargados: %s", nombres)

                await Actor.set_status_message("Ejecutando ETL")
                resultado = run_etl(carpeta_in, carpeta_out, no_medido_como_negativo=no_medido_como_negativo,
                                    guardar_tipado=False)

                await Actor.set_status_message("Publicando resultados")
                for nombre in ARCHIVOS_SALIDA:
                    with open(os.path.join(carpeta_out, nombre), "rb") as f:
                        await Actor.set_value(nombre, f.read(), content_type="text/csv; charset=utf-8")
                datos = resumen(resultado, nombres, carpeta_out)
        except (EntradaInvalida, FileNotFoundError, AssertionError) as e:
            await Actor.set_status_message(f"Error: {e}")
            raise
        await Actor.push_data(datos)
        await Actor.set_value("RESUMEN", datos)
        await Actor.set_status_message(f"ETL listo: {datos['filas']:,} filas x {datos['columnas']} columnas")