"""EDA estadístico – ENFR 2018 (sobre el dataset limpio que genera ETL.py).

Calcula, ponderando con peso_rel:
  1. Descriptivas (media, varianza, desvío, cuartiles) de edad e IMC.
  2. Matriz de correlación de Pearson entre condiciones, IMC y edad.
  3. Odds ratios crudos de factores asociados a hipertensión (IC 95 % de Woolf).
  4. Prevalencia de hipertensión por provincia, cruda y estandarizada por edad (método directo; estándar = distribución
     etaria nacional de la edición analizada).

Uso como módulo:
    from EDA import run_eda
    resultado = run_eda("carpeta/con/enfr_armonizado", "carpeta/salida")

Línea de comandos:
    python EDA.py --entrada carpeta/con/dataset --salida carpeta/salida [--anio 2018] [--af-bajo 3]

Salidas: enfr_descriptivas.csv, enfr_correlacion.csv, enfr_odds_ratio.csv, enfr_estandarizada.csv
"""
import argparse
import glob
import logging
import os

import numpy as np
import pandas as pd

log = logging.getLogger("EDA")

COND = ["hta", "diabetes", "colesterol_alto", "obesidad"]
NOMBRE = {"hta": "Hipertensión", "diabetes": "Diabetes", "colesterol_alto": "Colesterol alto", "obesidad": "Obesidad"}
PROV = {2: "CABA", 6: "Buenos Aires", 10: "Catamarca", 14: "Córdoba", 18: "Corrientes", 22: "Chaco",
        26: "Chubut", 30: "Entre Ríos", 34: "Formosa", 38: "Jujuy", 42: "La Pampa", 46: "La Rioja",
        50: "Mendoza", 54: "Misiones", 58: "Neuquén", 62: "Río Negro", 66: "Salta", 70: "San Juan",
        74: "San Luis", 78: "Santa Cruz", 82: "Santa Fe", 86: "Santiago del Estero",
        90: "Tucumán", 94: "Tierra del Fuego"}
AF_BAJO = 3   # código de 'actividad física baja' en actividad_fisica (VERIFICAR con el diccionario INDEC)
MIN_N_PROVINCIA = 30


# =============================================================================
# Carga
# =============================================================================
def cargar_dataset(entrada):
    """Lee el dataset limpio desde `entrada` (carpeta). Orden de búsqueda:
    enfr_armonizado.csv -> .csv.gz -> .parquet -> enfr_*_limpio.csv (uno por año)."""
    for nombre in ("enfr_armonizado.csv", "enfr_armonizado.csv.gz"):
        p = os.path.join(entrada, nombre)
        if os.path.exists(p):
            return pd.read_csv(p)
    p = os.path.join(entrada, "enfr_armonizado.parquet")
    if os.path.exists(p):
        return pd.read_parquet(p)
    archivos = sorted(glob.glob(os.path.join(entrada, "enfr_*_limpio.csv")))
    if archivos:
        return pd.concat([pd.read_csv(a) for a in archivos], ignore_index=True)
    raise FileNotFoundError(f"No encontré el dataset limpio en {entrada}")


# =============================================================================
# Utilidades ponderadas
# =============================================================================
def prev(d, col):
    """Prevalencia ponderada con peso_rel. Devuelve (prevalencia, n)."""
    s = d[d[col].notna()]
    if len(s) == 0 or s["peso_rel"].sum() == 0:
        return np.nan, 0
    return float(np.average(s[col], weights=s["peso_rel"])), len(s)


def cuantil_ponderado(x, w, q):
    orden = np.argsort(x)
    x, w = np.asarray(x)[orden], np.asarray(w)[orden]
    acum = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q, acum, x))


# =============================================================================
# 1 · Descriptivas
# =============================================================================
def descriptivas(d):
    filas = []
    for col, etq in [("edad", "Edad (años)"), ("imc", "IMC (kg/m²)")]:
        s = d[[col, "peso_rel"]].dropna()
        x, w = s[col].astype(float), s["peso_rel"].astype(float)
        media = np.average(x, weights=w)
        var = np.average((x - media) ** 2, weights=w)
        filas.append({"variable": etq, "n": len(s), "media": round(media, 2), "varianza": round(var, 2),
                      "desvio": round(np.sqrt(var), 2), "minimo": round(x.min(), 1),
                      "q1": round(cuantil_ponderado(x, w, .25), 1), "mediana": round(cuantil_ponderado(x, w, .5), 1),
                      "q3": round(cuantil_ponderado(x, w, .75), 1), "maximo": round(x.max(), 1)})
    return pd.DataFrame(filas)


# =============================================================================
# 2 · Correlación
# =============================================================================
def correlacion(d):
    c = d[COND + ["imc", "edad"]].astype(float).corr().round(3)
    return c.rename(index=NOMBRE, columns=NOMBRE)


# =============================================================================
# 3 · Odds ratios crudos para hipertensión
# =============================================================================
def _binf(cond, base):
    """1/0 según cond; NaN donde la variable de origen es NaN."""
    return np.where(base.isna(), np.nan, cond.astype(float))


def odds_ratio_hta(d, af_bajo=AF_BAJO):
    h = d[d["hta"].notna()].copy()
    h["mayor_50"] = _binf(h["edad"] >= 50, h["edad"])
    h["fumador"] = _binf(h["tabaco"] == 1, h["tabaco"])
    h["sedentario"] = _binf(h["actividad_fisica"] == af_bajo, h["actividad_fisica"])
    h["sin_cob"] = _binf(h["tiene_cobertura"] == 0, h["tiene_cobertura"])
    h["q1_q2"] = _binf(h["quintil_ingreso"] <= 2, h["quintil_ingreso"])
    factores = [("Obesidad (IMC≥30)", "obesidad"), ("Diabetes", "diabetes"), ("Colesterol alto", "colesterol_alto"),
                ("Sobrepeso (IMC≥25)", "sobrepeso"), ("Tener 50 años o más", "mayor_50"), ("Fumador actual", "fumador"),
                ("Baja actividad física", "sedentario"), ("Ser mujer", "mujer"), ("Sin cobertura de salud", "sin_cob"),
                ("Quintil de ingreso 1 o 2", "q1_q2")]
    filas = []
    for etq, var in factores:
        s = h[[var, "hta"]].dropna()
        a = int(((s[var] == 1) & (s["hta"] == 1)).sum()); b = int(((s[var] == 1) & (s["hta"] == 0)).sum())
        c = int(((s[var] == 0) & (s["hta"] == 1)).sum()); dd = int(((s[var] == 0) & (s["hta"] == 0)).sum())
        if min(a, b, c, dd) == 0:                       # celda vacía: el OR no está definido (ej. variable sin datos en el año)
            log.warning("OR no calculable para %s (tabla 2x2 con celda en 0 o sin datos)", etq)
            filas.append({"factor": etq, "variable": var, "odds_ratio": np.nan, "ic_bajo": np.nan, "ic_alto": np.nan,
                          "significativo": np.nan})
            continue
        orr = (a * dd) / (b * c)
        ee = np.sqrt(1 / a + 1 / b + 1 / c + 1 / dd)
        lo, hi = np.exp(np.log(orr) - 1.96 * ee), np.exp(np.log(orr) + 1.96 * ee)
        filas.append({"factor": etq, "variable": var, "odds_ratio": round(orr, 3), "ic_bajo": round(lo, 3),
                      "ic_alto": round(hi, 3), "significativo": int(lo > 1 or hi < 1)})
    return pd.DataFrame(filas)


# =============================================================================
# 4 · Prevalencia de HTA por provincia, cruda y estandarizada por edad
# =============================================================================
def estandarizada_por_provincia(d, min_n=MIN_N_PROVINCIA):
    base = d[d["hta"].notna() & d["grupo_etario"].notna()]
    estandar = base.groupby("grupo_etario")["peso_rel"].sum() / base["peso_rel"].sum()   # población estándar
    filas = []
    for cod, nom in PROV.items():
        sub = base[base["provincia"] == cod]
        cruda, n = prev(d[d["provincia"] == cod], "hta")
        if n < min_n:
            continue
        tasas = {g: prev(sub[sub["grupo_etario"] == g], "hta")[0] for g in estandar.index}
        validos = [g for g in estandar.index if not np.isnan(tasas[g])]
        if not validos:
            continue
        est = sum(estandar[g] * tasas[g] for g in validos) / sum(estandar[g] for g in validos)
        filas.append({"provincia": nom, "prevalencia_cruda": round(cruda, 4), "prevalencia_estandarizada": round(est, 4),
                      "cruda_pct": round(cruda * 100, 1), "estandarizada_pct": round(est * 100, 1),
                      "diferencia_pp": round((est - cruda) * 100, 1), "n": n})
    return (pd.DataFrame(filas).sort_values("prevalencia_estandarizada", ascending=False).reset_index(drop=True))


# =============================================================================
# Pipeline
# =============================================================================
def run_eda(entrada, salida, anio=2018, af_bajo=AF_BAJO, df=None):
    """Corre el EDA estadístico sobre la edición `anio` y guarda 4 CSV en `salida`.

    entrada: carpeta con el dataset limpio (se ignora si se pasa `df`).
    Devuelve dict con: descriptivas, correlacion, odds_ratio, estandarizada, rutas.
    """
    if df is None:
        df = cargar_dataset(entrada)
    d = df[df["anio"] == anio].copy()
    if d.empty:
        raise ValueError(f"No hay filas del año {anio} en el dataset")
    log.info("Muestra %s: %s personas", anio, f"{len(d):,}")

    res = dict(descriptivas=descriptivas(d), correlacion=correlacion(d),
               odds_ratio=odds_ratio_hta(d, af_bajo), estandarizada=estandarizada_por_provincia(d))

    os.makedirs(salida, exist_ok=True)
    rutas = {}
    for nombre, tabla, con_indice in [("enfr_descriptivas.csv", res["descriptivas"], False),
                                      ("enfr_correlacion.csv", res["correlacion"], True),
                                      ("enfr_odds_ratio.csv", res["odds_ratio"], False),
                                      ("enfr_estandarizada.csv", res["estandarizada"], False)]:
        rutas[nombre] = os.path.join(salida, nombre)
        tabla.to_csv(rutas[nombre], index=con_indice, encoding="utf-8")
    log.info("Guardados en %s", salida)
    res["rutas"] = rutas
    return res


def main():
    ap = argparse.ArgumentParser(description="EDA estadístico de la ENFR")
    ap.add_argument("--entrada", required=True, help="carpeta con el dataset limpio (salida de ETL.py)")
    ap.add_argument("--salida", required=True, help="carpeta donde guardar los CSV del EDA")
    ap.add_argument("--anio", type=int, default=2018, help="edición a analizar (default 2018)")
    ap.add_argument("--af-bajo", type=int, default=AF_BAJO, help="código de actividad física baja (default 3)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_eda(args.entrada, args.salida, args.anio, args.af_bajo)


if __name__ == "__main__":
    main()
