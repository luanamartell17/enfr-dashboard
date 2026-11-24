"""Lectura del dataset limpio desde un Key-Value Store de Apify (API REST) y URLs de salida. Sin lógica de EDA."""
import os
from urllib.parse import quote

import httpx

API = os.environ.get("APIFY_API_BASE_URL", "https://api.apify.com").rstrip("/") + "/v2"


class EntradaInvalida(ValueError):
    """La entrada del Actor es incorrecta (mensaje pensado para quien arma el flujo en n8n)."""


def _headers():
    token = os.environ.get("APIFY_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def validar_entrada(entrada):
    """-> (kv_store_id, clave_dataset, anio, af_bajo)"""
    kv = str(entrada.get("kvStoreId") or "").strip()
    if not kv:
        raise EntradaInvalida("Falta 'kvStoreId': ID del Key-Value Store donde está el dataset limpio (enfr_armonizado.csv).")
    clave = str(entrada.get("claveDataset") or "enfr_armonizado.csv").strip()
    try:
        anio, af_bajo = int(entrada.get("anio", 2018)), int(entrada.get("afBajo", 3))
    except (TypeError, ValueError):
        raise EntradaInvalida("'anio' y 'afBajo' deben ser números enteros.")
    return kv, clave, anio, af_bajo


async def descargar_dataset(kv_store_id, clave, destino):
    """Baja el dataset limpio (CSV o CSV.gz) a la ruta `destino`."""
    async with httpx.AsyncClient(headers=_headers(), timeout=300, follow_redirects=True) as http:
        r = await http.get(f"{API}/key-value-stores/{kv_store_id}/records/{quote(clave, safe='')}")
        if r.status_code == 404:
            raise EntradaInvalida(f"No encontré la clave '{clave}' en el Key-Value Store {kv_store_id} "
                                  "(o el store no existe / no hay acceso).")
        r.raise_for_status()
        with open(destino, "wb") as f:
            f.write(r.content)


def url_registro(clave):
    """URL de la API para bajar un registro del store por defecto de este run (en n8n se usa con el token de Apify)."""
    return f"{API}/key-value-stores/{os.environ.get('APIFY_DEFAULT_KEY_VALUE_STORE_ID', '')}/records/{quote(clave, safe='')}"