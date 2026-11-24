"""Armado de la salida del Actor EDA (qué archivos se publican y cómo se resume el run)."""
import os

from .entrada_salida import url_registro

ARCHIVOS_SALIDA = ["enfr_descriptivas.csv", "enfr_correlacion.csv", "enfr_odds_ratio.csv", "enfr_estandarizada.csv"]


def _registros(df, con_indice=False):
    """DataFrame -> lista de dicts JSON (NaN -> None) para que n8n pueda usar las tablas directamente."""
    df = df.reset_index() if con_indice else df
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


def resumen(resultado, anio, carpeta_salida):
    return {
        "estado": "ok",
        "anio": anio,
        "archivos": [{"clave": n, "bytes": os.path.getsize(os.path.join(carpeta_salida, n)), "url": url_registro(n)}
                     for n in ARCHIVOS_SALIDA],
        "tablas": {"descriptivas": _registros(resultado["descriptivas"]),
                   "correlacion": _registros(resultado["correlacion"], con_indice=True),
                   "odds_ratio": _registros(resultado["odds_ratio"]),
                   "estandarizada": _registros(resultado["estandarizada"])},
    }