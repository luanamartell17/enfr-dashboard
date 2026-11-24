"""Validación de registros y construcción de las 25 features que espera el modelo. No depende de Apify."""
import math

import numpy as np
import pandas as pd

RANGOS = {"edad": (18, 110), "peso_kg": (30, 250), "talla_cm": (120, 220), "imc": (12, 70)}
REQUERIDOS = ("edad", "mujer")
PASSTHROUGH = ("id",)          # se devuelve tal cual en la salida; no es feature


def _num(v):
    """Convierte a float; None / texto no numérico / NaN -> None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def validar_registro(r):
    """Devuelve la lista de errores que impiden predecir (vacía si el registro es válido)."""
    if not isinstance(r, dict):
        return ["el registro debe ser un objeto JSON (clave: valor)"]
    errores = []
    edad = _num(r.get("edad"))
    if edad is None:
        errores.append("falta 'edad' (obligatorio, número)")
    elif not RANGOS["edad"][0] <= edad <= RANGOS["edad"][1]:
        errores.append(f"'edad' fuera de rango ({RANGOS['edad'][0]}-{RANGOS['edad'][1]})")
    if _num(r.get("mujer")) not in (0.0, 1.0):
        errores.append("'mujer' es obligatorio y debe ser 1 (mujer) o 0 (varón)")
    for k, v in r.items():
        if k not in PASSTHROUGH and v is not None and _num(v) is None:
            errores.append(f"'{k}' no es numérico: {v!r}")
    return errores


def armar_features(registros, features):
    """registros válidos -> (DataFrame con las columnas exactas y en el orden del modelo, advertencias por registro).

    - Calcula imc, obesidad, sobrepeso y grupo_etario.
    - Valores fuera de rango (peso, talla, imc) pasan a NaN con una advertencia.
    - Claves desconocidas (p. ej. 'peso' en vez de 'peso_kg') se informan como advertencia.
    - Lo que falta queda NaN: el modelo lo imputa.
    """
    filas, advertencias = [], []
    for r in registros:
        adv = [f"campo desconocido ignorado: '{k}'" for k in r if k not in features and k not in PASSTHROUGH]
        fila = {k: _num(v) for k, v in r.items() if k in features}
        for c, (lo, hi) in RANGOS.items():
            if fila.get(c) is not None and not lo <= fila[c] <= hi:
                adv.append(f"'{c}'={fila[c]} fuera de rango ({lo}-{hi}): se ignora")
                fila[c] = None
        filas.append(fila); advertencias.append(adv)

    X = pd.DataFrame(filas, dtype="float64")
    for c in ("peso_kg", "talla_cm", "imc"):
        if c not in X: X[c] = np.nan
    imc_calc = X["peso_kg"] / (X["talla_cm"] / 100) ** 2
    X["imc"] = X["imc"].fillna(imc_calc)
    fuera = X["imc"].notna() & ~X["imc"].between(*RANGOS["imc"])
    for i in np.where(fuera)[0]: advertencias[i].append(f"imc={X['imc'].iloc[i]:.1f} fuera de rango: se ignora")
    X.loc[fuera, "imc"] = np.nan
    X["obesidad"] = np.where(X["imc"].isna(), np.nan, (X["imc"] >= 30).astype(float))
    X["sobrepeso"] = np.where(X["imc"].isna(), np.nan, (X["imc"] >= 25).astype(float))
    X["grupo_etario"] = pd.cut(X["edad"], [17, 24, 34, 49, 64, 200], labels=[1, 2, 3, 4, 5]).astype(float)
    return X.reindex(columns=features), advertencias