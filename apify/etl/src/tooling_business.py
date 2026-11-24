"""Armado de la salida del Actor ETL (qué archivos se publican y cómo se resume el run)."""
import os

from .entrada_salida import url_registro

# Archivos que el Actor publica en su Key-Value Store (los demás que genere ETL.py no se suben)
ARCHIVOS_SALIDA = ["enfr_armonizado.csv", "diccionario_variables.csv", "qa_nulos_por_anio.csv",
                   "qa_log_limpieza.csv", "qa_validacion_oficial.csv"]


def resumen(resultado, nombres_txt, carpeta_salida):
    """Dict JSON-serializable con filas, columnas, validación y URLs de cada archivo (para n8n)."""
    H = resultado["dataset"]
    return {
        "estado": "ok",
        "txt_procesados": nombres_txt,
        "filas": int(len(H)),
        "columnas": int(H.shape[1]),
        "filas_por_anio": {str(k): int(v) for k, v in H.groupby("anio").size().items()},
        "validacion_vs_indec": resultado["validacion"].to_dict(orient="records"),
        "archivos": [{"clave": n, "bytes": os.path.getsize(os.path.join(carpeta_salida, n)), "url": url_registro(n)}
                     for n in ARCHIVOS_SALIDA],
    }