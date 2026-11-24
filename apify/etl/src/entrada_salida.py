"""Lectura de archivos desde un Key-Value Store de Apify (API REST) y URLs de salida. Sin lógica de negocio ni de ETL."""
import os
import re
from urllib.parse import quote

import httpx

API = os.environ.get("APIFY_API_BASE_URL", "https://api.apify.com").rstrip("/") + "/v2"


class EntradaInvalida(ValueError):
    """La entrada del Actor es incorrecta (mensaje pensado para quien arma el flujo en n8n)."""


def _headers():
    token = os.environ.get("APIFY_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def validar_entrada(entrada):
    """-> (kv_store_id, archivos|None, no_medido_como_negativo). `archivos` = [{'anio': int, 'clave': str}, ...]"""
    kv = str(entrada.get("kvStoreId") or "").strip()
    if not kv:
        raise EntradaInvalida("Falta 'kvStoreId': ID del Key-Value Store donde subiste los .txt de la ENFR.")
    archivos = entrada.get("archivos")
    if archivos:
        if not isinstance(archivos, list):
            raise EntradaInvalida("'archivos' debe ser una lista de objetos {'anio': 2009, 'clave': 'archivo.txt'}.")
        for a in archivos:
            if not isinstance(a, dict) or not str(a.get("clave", "")).strip() or not re.fullmatch(r"20\d{2}", str(a.get("anio", ""))):
                raise EntradaInvalida(f"Elemento inválido en 'archivos': {a!r}. Se espera {{'anio': 2009, 'clave': 'archivo.txt'}}.")
        archivos = [{"anio": int(a["anio"]), "clave": str(a["clave"]).strip()} for a in archivos]
    else:
        archivos = None
    return kv, archivos, bool(entrada.get("noMedidoComoNegativo", True))


async def _listar_claves(http, kv_store_id):
    claves, desde = [], None
    while True:
        params = {"limit": 1000, **({"exclusiveStartKey": desde} if desde else {})}
        r = await http.get(f"{API}/key-value-stores/{kv_store_id}/keys", params=params)
        if r.status_code == 404:
            raise EntradaInvalida(f"No existe el Key-Value Store '{kv_store_id}' (o este run no tiene acceso a él).")
        r.raise_for_status()
        d = r.json()["data"]
        claves += [i["key"] for i in d["items"]]
        if not d.get("isTruncated"):
            return claves
        desde = d["nextExclusiveStartKey"]


async def descargar_txt(kv_store_id, archivos, carpeta):
    """Baja los .txt del store a `carpeta` tal cual (bytes). Si `archivos` es None toma todas las claves *.txt.
    Si se indica el año explícito, el archivo se guarda como ENFR_<anio>.txt. Devuelve los nombres guardados."""
    os.makedirs(carpeta, exist_ok=True)
    nombres = []
    async with httpx.AsyncClient(headers=_headers(), timeout=300, follow_redirects=True) as http:
        if archivos is None:
            claves = await _listar_claves(http, kv_store_id)
            pares = [(k, k) for k in claves if k.lower().endswith(".txt")]
            if not pares:
                raise EntradaInvalida(f"El Key-Value Store {kv_store_id} no tiene archivos .txt (claves: {claves[:10]}).")
        else:
            pares = [(a["clave"], f"ENFR_{a['anio']}.txt") for a in archivos]
        for clave, nombre in pares:
            r = await http.get(f"{API}/key-value-stores/{kv_store_id}/records/{quote(clave, safe='')}")
            if r.status_code == 404:
                raise EntradaInvalida(f"No encontré la clave '{clave}' en el Key-Value Store {kv_store_id}.")
            r.raise_for_status()
            with open(os.path.join(carpeta, nombre), "wb") as f:
                f.write(r.content)
            nombres.append(nombre)
    return nombres


def url_registro(clave):
    """URL de la API para bajar un registro del store por defecto de este run (en n8n se usa con el token de Apify)."""
    return f"{API}/key-value-stores/{os.environ.get('APIFY_DEFAULT_KEY_VALUE_STORE_ID', '')}/records/{quote(clave, safe='')}"