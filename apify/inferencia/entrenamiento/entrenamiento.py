"""Entrenamiento – modelo de hipertensión (hta) con el dataset limpio de la ENFR (salida de ETL.py).

Pasos (equivalen a las secciones 10-13 del notebook ENFR_ETL_y_modelo):
  1. Carga el dataset limpio y arma X, y, w (solo filas con `hta` conocida).
  2. Evalúa la regresión logística: validación cruzada de 5 folds sobre 2005-2013 y test en 2018.
     Con --comparar también evalúa Random Forest y Gradient Boosting.
  3. Re-entrena la regresión logística con todos los años y la guarda en un .pkl con su metadata
     (features en orden, umbral, métricas, versiones de librerías).
  4. Guarda una copia en base64 (.pkl.b64) verificada, para subir el modelo a Apify desde el editor web.

Salidas: modelo_hta_logreg.pkl, modelo_hta_logreg.pkl.b64, metricas_modelo.csv (+ comparacion_modelos.csv con --comparar)
"""
import argparse
import base64
import datetime
import glob
import hashlib
import logging
import os
import pickle
import platform
import time

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

log = logging.getLogger("entrenamiento")

# ---- Parámetros -------------------------------------------------------------
TARGET = "hta"
ANIOS_TRAIN = [2005, 2009, 2013]     # train para validar; 2018 es el test
ANIO_TEST = 2018
ENTRENAR_CON = [2005, 2009, 2013, 2018]   # años del modelo final
UMBRAL = 0.40                        # prob >= UMBRAL -> alerta. Más bajo = detecta más casos pero más falsos positivos
N_FOLDS = 5
MODELO_PRINCIPAL = "Regresión logística"
NOMBRE_PKL = "modelo_hta_logreg.pkl"

EXCLUIR = [
    "id_unico", "id_original", "anio", "peso_muestral", "peso_rel",   # identificadores y pesos
    "hta",                      # es el target
    "hta_medida",               # delata el target: si nunca se midió la presión, hta es NaN
    "riesgo_cardiometabolico",  # contiene a hta
    "n_condiciones",            # contiene a hta
    "salud_regular_mala",       # redundante con salud_autopercibida
    # "salud_autopercibida",    # <- agregar para un modelo que no use la percepción subjetiva de salud
    # "colesterol_medido",      # <- agregar si no se quiere el proxy de acceso a controles médicos
]
CATEGORICAS_BASE = ["provincia", "region", "condicion_actividad", "tabaco"]


# =============================================================================
# 1 · Datos
# =============================================================================
def cargar_dataset(entrada):
    """Lee el dataset limpio de `entrada` (carpeta): enfr_armonizado.parquet -> .csv.gz -> .csv -> enfr_*_limpio.csv."""
    p = os.path.join(entrada, "enfr_armonizado")
    if os.path.exists(p + ".parquet"):
        return pd.read_parquet(p + ".parquet")
    for ext in (".csv.gz", ".csv"):
        if os.path.exists(p + ext):
            return pd.read_csv(p + ext)
    archivos = sorted(glob.glob(os.path.join(entrada, "enfr_*_limpio.csv")))
    if archivos:
        return pd.concat([pd.read_csv(a) for a in archivos], ignore_index=True)
    raise FileNotFoundError(f"No encontré el dataset limpio en {entrada}")


def preparar_xy(df, anios=None, target=TARGET, excluir=EXCLUIR):
    """-> X, y, w. Solo filas con target conocido; todo lo demás son features salvo `excluir`."""
    d = df if anios is None else df[df["anio"].isin(anios)]
    d = d[d[target].notna()]
    feats = [c for c in d.columns if c not in excluir]
    return d[feats].astype("float32"), d[target].astype("float32"), d["peso_rel"].astype("float32")


# =============================================================================
# 2 · Modelos
# =============================================================================
def _imputador():
    return SimpleImputer(strategy="median", add_indicator=True)


def construir_modelos(columnas):
    """{nombre: Pipeline sklearn} para las columnas dadas (las categóricas se detectan por nombre)."""
    cat = [c for c in CATEGORICAS_BASE if c in columnas]
    num = [c for c in columnas if c not in cat]
    return {
        "Regresión logística": Pipeline([
            ("prep", ColumnTransformer([
                ("num", Pipeline([("imp", _imputador()), ("sc", StandardScaler())]), num),
                ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                                  ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=50))]), cat)])),
            ("m", LogisticRegression(max_iter=2000, C=1.0))]),
        "Random Forest": Pipeline([
            ("imp", _imputador()),
            ("m", RandomForestClassifier(n_estimators=200, min_samples_leaf=30, max_features="sqrt", n_jobs=-1, random_state=0))]),
        "Gradient Boosting (HGB)": Pipeline([
            ("m", HistGradientBoostingClassifier(max_iter=250, learning_rate=0.06, max_leaf_nodes=20,
                                                 l2_regularization=1.0, random_state=0))]),
    }


def _proba(modelo, X):
    return modelo.predict_proba(X)[:, 1]


def _fit(pipe, X, y, w):
    """Ajusta un pipeline pasando los pesos al último paso."""
    pipe.fit(X, y, **{pipe.steps[-1][0] + "__sample_weight": np.asarray(w)})
    return pipe


def evaluar_modelos(modelos, Xtr, ytr, wtr, Xte, yte, wte, n_folds=N_FOLDS):
    """CV estratificada sobre train + test. Devuelve (tabla de resultados, {nombre: pipeline ajustado con todo el train})."""
    skf = StratifiedKFold(n_folds, shuffle=True, random_state=0)
    filas, ajustados = [], {}
    for nombre, pipe in modelos.items():
        t0, aucs, briers = time.time(), [], []
        for itr, iva in skf.split(Xtr, ytr):
            _fit(pipe, Xtr.iloc[itr], ytr.iloc[itr], wtr.iloc[itr].values)
            p = _proba(pipe, Xtr.iloc[iva])
            aucs.append(roc_auc_score(ytr.iloc[iva], p, sample_weight=wtr.iloc[iva]))
            briers.append(brier_score_loss(ytr.iloc[iva], p, sample_weight=wtr.iloc[iva]))
        _fit(pipe, Xtr, ytr, wtr.values)                       # modelo con todo el train
        pt = _proba(pipe, Xte)
        ajustados[nombre] = pipe
        filas.append({"modelo": nombre, "AUC_cv_media": np.mean(aucs), "AUC_cv_std": np.std(aucs),
                      "AUC_test_2018": roc_auc_score(yte, pt, sample_weight=wte),
                      "Brier_test_2018": brier_score_loss(yte, pt, sample_weight=wte), "segundos": time.time() - t0})
        log.info("%s: AUC cv %.4f | AUC test %.4f", nombre, np.mean(aucs), filas[-1]["AUC_test_2018"])
    resultados = pd.DataFrame(filas).set_index("modelo").round(4).sort_values("AUC_test_2018", ascending=False)
    return resultados, ajustados


def metricas_umbral(modelo, Xte, yte, resultados_fila, umbral):
    """Métricas del modelo (train 2005-2013, test 2018) más recall y precisión con el umbral elegido."""
    pred = _proba(modelo, Xte) >= umbral
    tp = ((pred == 1) & (yte == 1)).sum()
    return {**resultados_fila.to_dict(), "umbral": umbral,
            "recall_2018": float(tp / (yte == 1).sum()), "precision_2018": float(tp / max(pred.sum(), 1))}


# =============================================================================
# 3 · Entrenamiento final y artefacto
# =============================================================================
def entrenar_final(modelos, df, anios=ENTRENAR_CON):
    """Re-entrena la regresión logística con `anios` y devuelve (pipeline, lista de features en orden)."""
    Xf, yf, wf = preparar_xy(df, anios=anios)
    modelo = _fit(clone(modelos[MODELO_PRINCIPAL]), Xf, yf, wf.values)
    return modelo, list(Xf.columns)


def armar_artefacto(modelo, features, umbral, metricas, anios=ENTRENAR_CON):
    return dict(
        modelo=modelo,                       # Pipeline sklearn (imputación + escalado + one-hot + regresión logística)
        features=features,                   # orden exacto de columnas esperado
        target=TARGET, umbral=umbral,
        anios_entrenamiento=anios,
        metricas_validacion=metricas,
        descripcion="Probabilidad de hipertensión diagnosticada (autorreporte) a partir de la ENFR 2005-2018.",
        codificacion=dict(mujer="1 mujer, 0 varón", tabaco="1 actual, 2 ex, 3 nunca", salud_autopercibida="1 excelente ... 5 mala",
                          condicion_actividad="1 ocupado, 2 desocupado, 3 inactivo", quintil_ingreso="1 (más bajo) ... 5",
                          binarias="1 sí, 0 no"),
        versiones=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__),
        creado=datetime.datetime.now().isoformat(timespec="seconds"),
    )


def guardar_artefacto(artefacto, salida, nombre=NOMBRE_PKL, guardar_b64=True):
    """Guarda el .pkl y (opcional) una copia base64 de una sola línea, verificando que reproduce el modelo.
    El editor web de Apify corrompe archivos binarios: el .b64 es texto plano y se puede pegar sin riesgo."""
    os.makedirs(salida, exist_ok=True)
    ruta = os.path.join(salida, nombre)
    with open(ruta, "wb") as f:
        pickle.dump(artefacto, f, protocol=4)
    rutas = {"pkl": ruta}
    if guardar_b64:
        raw = open(ruta, "rb").read()
        assert raw[:1] == b"\x80", "El .pkl no empieza con el byte de pickle (0x80): está dañado"
        ruta_b64 = ruta + ".b64"
        with open(ruta_b64, "wb") as f:
            f.write(base64.b64encode(raw))
        b64 = open(ruta_b64, "rb").read()
        assert b"\n" not in b64 and b"\r" not in b64 and b" " not in b64, "El .b64 debe ser una sola línea sin espacios"
        assert base64.b64decode(b64) == raw, "El .b64 no reproduce el .pkl"
        art = pickle.loads(base64.b64decode(b64))
        assert {"modelo", "features", "umbral", "versiones"} <= set(art), "El artefacto no tiene las claves esperadas"
        rutas["b64"] = ruta_b64
        log.info("sha256(.pkl) %s... | .pkl %s bytes | .b64 %s caracteres", hashlib.sha256(raw).hexdigest()[:16],
                 f"{len(raw):,}", f"{len(b64):,}")
    v = artefacto["versiones"]
    log.info("Versiones a fijar en el Actor: Python %s (FROM apify/actor-python:%s) | scikit-learn==%s",
             v["python"], ".".join(v["python"].split(".")[:2]), v["sklearn"])
    return rutas


# =============================================================================
# Pipeline
# =============================================================================
def run_entrenamiento(entrada, salida, umbral=UMBRAL, comparar=False, n_folds=N_FOLDS, df=None):
    """Evalúa, re-entrena con todos los años y guarda el modelo.

    entrada: carpeta con el dataset limpio (se ignora si se pasa `df`) | salida: carpeta donde se guarda todo.
    comparar: True evalúa además Random Forest y Gradient Boosting (tarda más).
    Devuelve dict con: resultados, metricas, artefacto, rutas.
    """
    if df is None:
        df = cargar_dataset(entrada)
    Xtr, ytr, wtr = preparar_xy(df, anios=ANIOS_TRAIN)
    Xte, yte, wte = preparar_xy(df, anios=[ANIO_TEST])
    log.info("train %s, test %s | prevalencia hta: train %.1f%%, test %.1f%%", Xtr.shape, Xte.shape, ytr.mean() * 100, yte.mean() * 100)
    log.info("Features: %s", list(Xtr.columns))

    modelos = construir_modelos(list(Xtr.columns))
    a_evaluar = modelos if comparar else {MODELO_PRINCIPAL: modelos[MODELO_PRINCIPAL]}
    resultados, ajustados = evaluar_modelos(a_evaluar, Xtr, ytr, wtr, Xte, yte, wte, n_folds)
    metricas = metricas_umbral(ajustados[MODELO_PRINCIPAL], Xte, yte, resultados.loc[MODELO_PRINCIPAL], umbral)
    log.info("Con umbral %s: recall %.2f, precisión %.2f (test 2018)", umbral, metricas["recall_2018"], metricas["precision_2018"])

    modelo_final, features = entrenar_final(modelos, df)
    artefacto = armar_artefacto(modelo_final, features, umbral, metricas)
    rutas = guardar_artefacto(artefacto, salida)

    pd.DataFrame([metricas]).to_csv(os.path.join(salida, "metricas_modelo.csv"), index=False)
    if comparar:
        resultados.to_csv(os.path.join(salida, "comparacion_modelos.csv"))
    return dict(resultados=resultados, metricas=metricas, artefacto=artefacto, rutas=rutas)


def main():
    ap = argparse.ArgumentParser(description="Entrenamiento del modelo de hipertensión (ENFR)")
    ap.add_argument("--entrada", required=True, help="carpeta con el dataset limpio (salida de ETL.py)")
    ap.add_argument("--salida", required=True, help="carpeta donde guardar el modelo y las métricas")
    ap.add_argument("--umbral", type=float, default=UMBRAL, help="umbral de alerta (default 0.40)")
    ap.add_argument("--comparar", action="store_true", help="evaluar también Random Forest y Gradient Boosting")
    ap.add_argument("--folds", type=int, default=N_FOLDS, help="folds de validación cruzada (default 5)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_entrenamiento(args.entrada, args.salida, args.umbral, args.comparar, args.folds)


if __name__ == "__main__":
    main()
