"""ETL – Encuesta Nacional de Factores de Riesgo (ENFR) 2005 · 2009 · 2013 · 2018.

Toma los .txt de la base usuario de cada edición, los pasa a formato tipado, armoniza las variables entre años,
las limpia, construye las variables objetivo y exporta un dataset único listo para el EDA / entrenamiento.

Uso como módulo:
    from ETL import run_etl
    resultado = run_etl("carpeta/con/txt", "carpeta/salida")

Uso por línea de comandos:
    python ETL.py --entrada carpeta/con/txt --salida carpeta/salida

Salidas (en --salida):
    enfr_armonizado.csv / enfr_armonizado.parquet (o .csv.gz si no hay pyarrow)  <- dataset limpio
    diccionario_variables.csv, qa_nulos_por_anio.csv, qa_log_limpieza.csv, qa_validacion_oficial.csv
    tipado_por_anio/enfr_YYYY_tipado.*   <- columnas originales por año, tipadas

No se imputan faltantes ni se escalan variables: eso va en el pipeline de entrenamiento (después del split).
"""
import argparse
import glob
import logging
import os
import re

import numpy as np
import pandas as pd

log = logging.getLogger("ETL")

# ---- Parámetros por defecto -------------------------------------------------
ANIOS = (2005, 2009, 2013, 2018)          # ediciones a procesar

# Target compuesto: ¿"no medido" cuenta como "sin la condición"?
#   True  -> diagnóstico autorreportado (quien nunca se midió se asume sin diagnóstico). Recomendado.
#   False -> estricto (queda NaN si alguna condición es desconocida y ninguna es positiva). Sesga hacia positivos.
NO_MEDIDO_COMO_NEGATIVO = True

# Rangos plausibles (fuera de rango -> NaN, se registra en el log)
RANGOS = dict(edad=(18, 110), peso_kg=(30, 250), talla_cm=(120, 220), imc=(12, 70), fv_promedio_diario=(0, 20))

# ---- Armonización entre ediciones -------------------------------------------
# Para cada variable armonizada: de qué columna sale en cada año (None = no existe esa variable en esa edición -> NaN).
# Codificaciones: Sí/No = 1/2; 9 (2005-2013) / 99 (2018) = NS/NC -> NaN. Hipertensión/colesterol solo se preguntan a quien
# se midió alguna vez; "diagnóstico" = 1 o 2 en la pregunta "¿le dijeron que tiene...?" (3 = no). Cobertura 2005/2009
# (multi-categoría): 8 = sin cobertura. Tabaco: 1 actual, 2 ex, 3 nunca.
SPEC = {
    2005: dict(id="identifi", peso="ponderacion", provincia="prov", region="region", sexo="chch04", edad="chch05",
               instr="nivinstr", cob="cs", cob_tipo="multi", act="c_act", quintil="itf_uc_quintiles", hogar="cant_componentes",
               salud="cisg01", tabaco="consumo_tabaco_100", af=None, reg="c_reg", epi="c_epi", fv=None, cumple_fv=None,
               ha_med="ciha01", ha_dx="ciha03", col_med="cico01", col_dx="cico03", dia="cidi01",
               peso_kg="cipc05", talla_cm="cipc06"),
    2009: dict(id="identifi", peso="ponderacion", provincia="prvnc", region="region", sexo="bhch04", edad="bhch05",
               instr="nivinstr", cob="cob_salud", cob_tipo="multi", act="c_act", quintil="itf_uc_quintiles", hogar="cant_componentes",
               salud="bisg01", tabaco="con_ta", af="niv_af", reg="c_reg", epi=None, fv="promedio_fv_diario", cumple_fv="fruyver",
               ha_med="biha01", ha_dx="biha03", col_med="bico01", col_dx="bico03", dia="bidi01",
               peso_kg="bipc05", talla_cm="bipc06"),
    2013: dict(id="id", peso="ponderacion", provincia="cod_provincia", region="region", sexo="bhch04", edad="bhch05",
               instr="nivel_instruccion", cob="cobertura_salud", cob_tipo="bin", act="condicion_actividad", quintil="itf_uc_quintiles",
               hogar="cant_componentes", salud="bisg01", tabaco="consumo_tabaco_100", af="nivel_actividad_fisica",
               reg="c_reg", epi="c_epi", fv="promedio_fv_diario", cumple_fv="fruyver",
               ha_med="biha01", ha_dx="biha03", col_med="bico01", col_dx="bico03", dia="bidi01",
               peso_kg="bipc05", talla_cm="bipc06"),
    2018: dict(id="id", peso="wf1p", provincia="cod_provincia", region="region", sexo="bhch03", edad="bhch04",
               instr="nivel_instruccion", cob="cobertura_salud", cob_tipo="bin", act="condicion_actividad", quintil="quintil_uc",
               hogar="cant_componentes", salud="bisg01", tabaco="consumo_tabaco_100", af="nivel_actividad_fisica",
               reg="consumo_regular_riesgo", epi="consumo_episodico_excesivo", fv="promedio_fv_diario", cumple_fv="consumo_fv",
               ha_med="biha01", ha_dx="biha03", col_med="bico01", col_dx="bico03", dia="bidi01",
               peso_kg="bipc04", talla_cm="bipc05"),
}
# Variables oficiales de INDEC contra las que se valida la regla propia
OFICIALES = {2009: dict(hta="prv_ha", col="prv_col", dia="prv_dia"),
             2013: dict(hta="prevalencia_hipertension", col="prevalencia_colesterol", dia="prevalencia_diabetes"),
             2018: dict(hta="prevalencia_hipertension", col="prevalencia_colesterol", dia="prevalencia_diabetes")}
NSNC_PESO_TALLA = (999, 9999)     # códigos de "no sabe" en peso/talla autorreportados (2005-2013)

COND = ["hta", "diabetes", "colesterol_alto", "obesidad"]
TARGETS = ["hta", "diabetes", "colesterol_alto", "obesidad", "n_condiciones", "riesgo_cardiometabolico", "salud_regular_mala"]

# Diccionario de variables del dataset final (variable, rol, descripción)
DICC = [
    ("id_unico", "id", "Identificador único: año_idoriginal"),
    ("id_original", "id", "Identificador en el archivo original"),
    ("anio", "meta", "Edición de la ENFR"),
    ("peso_muestral", "peso", "Factor de expansión (2018: wf1p). No comparable en escala entre años"),
    ("peso_rel", "peso", "peso_muestral / media del año. Usar como sample_weight al combinar años"),
    ("provincia", "feature cat", "Código INDEC de provincia"),
    ("region", "feature cat", "Región (1 GBA, 2 Pampeana, 3 NOA, 4 NEA, 5 Cuyo, 6 Patagonia; verificar con diccionario INDEC)"),
    ("mujer", "feature bin", "1 mujer, 0 varón"),
    ("edad", "feature num", "Años (18-110)"),
    ("grupo_etario", "feature ord", "1: 18-24, 2: 25-34, 3: 35-49, 4: 50-64, 5: 65+"),
    ("nivel_instruccion", "feature ord", "1..7 (INDEC); el código 8 se pasa a NaN"),
    ("tiene_cobertura", "feature bin", "1 tiene cobertura de salud (obra social/prepaga/etc.), 0 no"),
    ("condicion_actividad", "feature cat", "1 ocupado, 2 desocupado, 3 inactivo"),
    ("quintil_ingreso", "feature ord", "Quintil de ingreso per cápita del hogar (1 más bajo)"),
    ("cant_componentes", "feature num", "Cantidad de integrantes del hogar"),
    ("salud_autopercibida", "feature ord", "1 excelente, 2 muy buena, 3 buena, 4 regular, 5 mala"),
    ("tabaco", "feature cat", "1 fumador actual, 2 ex fumador, 3 nunca"),
    ("actividad_fisica", "feature ord", "Nivel de actividad física INDEC (1-3). NaN en 2005. Verificar sentido del orden con el diccionario INDEC"),
    ("alcohol_regular_riesgo", "feature bin", "Consumo regular de riesgo (1 sí)"),
    ("alcohol_episodico", "feature bin", "Consumo episódico excesivo (1 sí). NaN en 2009"),
    ("fv_promedio_diario", "feature num", "Porciones diarias de frutas y verduras. NaN en 2005. Puede haber diferencias de cálculo entre ediciones"),
    ("cumple_5_fyv", "feature bin", "Consume 5+ porciones de frutas y verduras por día. NaN en 2005"),
    ("peso_kg", "feature num", "Peso autorreportado (kg)"),
    ("talla_cm", "feature num", "Talla autorreportada (cm)"),
    ("imc", "feature num", "peso / talla^2 con medidas autorreportadas"),
    ("hta_medida", "aux", "Se midió la presión alguna vez. Auxiliar (leakage para hta / compuestos)"),
    ("colesterol_medido", "aux", "Se midió el colesterol alguna vez. Auxiliar (leakage para colesterol_alto / compuestos)"),
    ("hta", "target / feature", "Hipertensión diagnosticada (NaN si nunca se midió la presión)"),
    ("colesterol_alto", "target / feature", "Colesterol alto diagnosticado (NaN si nunca se midió)"),
    ("diabetes", "target / feature", "Diabetes o glucemia elevada diagnosticada"),
    ("obesidad", "target / feature", "IMC >= 30"),
    ("sobrepeso", "feature bin", "IMC >= 25 (incluye obesidad)"),
    ("salud_regular_mala", "target", "Autopercibe salud regular o mala"),
    ("n_condiciones", "target", "Nº de condiciones entre hta, diabetes, colesterol_alto, obesidad (0-4)"),
    ("riesgo_cardiometabolico", "target", "1 si tiene al menos una de las 4 condiciones; ver NO_MEDIDO_COMO_NEGATIVO"),
]


# =============================================================================
# 1 · Archivos de entrada, lectura y tipado
# =============================================================================
def detectar_archivos(carpeta, anios=ANIOS):
    """{anio: ruta} buscando los .txt de la carpeta. El año se detecta por el nombre del archivo (...2009...)."""
    archivos = {}
    for p in sorted(glob.glob(os.path.join(carpeta, "*.txt"))):
        en_nombre = re.findall(r"(?<!\d)(20\d{2})(?!\d)", os.path.basename(p))
        if en_nombre and int(en_nombre[-1]) in anios:
            archivos[int(en_nombre[-1])] = p
    faltan = [a for a in anios if a not in archivos]
    if faltan:
        raise FileNotFoundError(f"Faltan archivos para los años: {faltan}. Encontrados: {archivos}")
    return archivos


def leer_enfr(path):
    """Lee un .txt de la ENFR (separador |, BOM, comillas) todo como texto, con columnas en minúscula."""
    df = pd.read_csv(path, sep="|", dtype=str, encoding="utf-8-sig", keep_default_na=False,
                     quotechar='"', low_memory=False)
    df.columns = [c.strip().strip('"').lower() for c in df.columns]
    return df


def tipar(df):
    """Strings -> numérico compacto. Vacío/espacios -> NaN, coma decimal -> punto. Devuelve (df_tipado, columnas_no_numericas)."""
    out, no_num = {}, []
    for c in df.columns:
        s = df[c].astype("string").str.strip().replace("", pd.NA)
        n = pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")   # algunas columnas vienen con coma decimal
        if n.notna().sum() < s.notna().sum():            # hay valores no numéricos: se deja como texto
            out[c] = s
            no_num.append(c)
            continue
        if (n.dropna() % 1 == 0).all():
            mx, mn = (n.max(), n.min()) if n.notna().any() else (0, 0)
            out[c] = n.astype("Int16" if -32000 < mn and mx < 32000 else "Int32")
        else:
            out[c] = n.astype("float32")
    return pd.DataFrame(out), no_num


def guardar_df(df, path_sin_ext):
    """Parquet si hay pyarrow; si no, CSV comprimido. Devuelve la ruta escrita."""
    try:
        df.to_parquet(path_sin_ext + ".parquet", index=False)
        return path_sin_ext + ".parquet"
    except ImportError:
        df.to_csv(path_sin_ext + ".csv.gz", index=False)
        return path_sin_ext + ".csv.gz"


def cargar_raw(archivos, salida=None):
    """{anio: DataFrame tipado con TODAS las columnas originales}. Si se da `salida`, guarda cada año en tipado_por_anio/."""
    raw = {}
    if salida:
        os.makedirs(os.path.join(salida, "tipado_por_anio"), exist_ok=True)
    for anio, path in sorted(archivos.items()):
        df, no_num = tipar(leer_enfr(path))
        raw[anio] = df
        destino = ""
        if salida:
            destino = os.path.basename(guardar_df(df, os.path.join(salida, "tipado_por_anio", f"enfr_{anio}_tipado")))
        log.info("%s: %s filas x %s cols | no numéricas: %s | %s", anio, f"{df.shape[0]:,}", df.shape[1], no_num or "-", destino)
    return raw


# =============================================================================
# 2 · Auditoría de datos crudos
# =============================================================================
def auditar(raw):
    """Resumen de calidad por año: filas, columnas, duplicados y % de nulos."""
    filas = []
    for a, df in raw.items():
        idc = df.columns[0]
        filas.append(dict(anio=a, filas=len(df), columnas=df.shape[1], col_id=idc,
                          ids_duplicados=int(df[idc].duplicated().sum()),
                          filas_duplicadas=int(df.duplicated().sum()),
                          pct_nulos_total=round(float(df.isna().mean().mean()) * 100, 1)))
    return pd.DataFrame(filas).set_index("anio")


# =============================================================================
# 3 · Armonización entre ediciones
# =============================================================================
def g(df, col):
    """Columna como float64; si la variable no existe en esa edición -> NaN."""
    if col is None or col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return df[col].astype("float64")


def binaria(s, si=1, no=2):
    """si->1, no->0, cualquier otro código (9/99 = NS/NC, vacío) -> NaN."""
    return pd.Series(np.select([s == si, s == no], [1.0, 0.0], default=np.nan), index=s.index)


def armonizar(df, anio):
    """Una edición (tipada) -> DataFrame con las variables armonizadas."""
    s, o = SPEC[anio], pd.DataFrame(index=df.index)
    o["anio"] = anio
    o["id_original"] = df[s["id"]].astype("Int64").astype(str)
    o["id_unico"] = str(anio) + "_" + o["id_original"]
    o["peso_muestral"] = g(df, s["peso"])
    o["provincia"] = g(df, s["provincia"])
    o["region"] = g(df, s["region"])
    # --- sociodemográficas
    sexo = g(df, s["sexo"])
    o["mujer"] = binaria(sexo, si=2, no=1)
    o["edad"] = g(df, s["edad"])
    instr = g(df, s["instr"])
    o["nivel_instruccion"] = instr.where(instr.between(1, 7))                       # 8 = otro/especial -> NaN
    cob = g(df, s["cob"])
    if s["cob_tipo"] == "multi":
        o["tiene_cobertura"] = pd.Series(np.select([cob == 8, cob.between(1, 7)], [0.0, 1.0], default=np.nan), index=df.index)
    else:
        o["tiene_cobertura"] = binaria(cob, si=1, no=2)
    act = g(df, s["act"])
    o["condicion_actividad"] = act.where(act.isin([1, 2, 3]))                        # 1 ocupado, 2 desocupado, 3 inactivo
    q = g(df, s["quintil"])
    o["quintil_ingreso"] = q.where(q.between(1, 5))
    o["cant_componentes"] = g(df, s["hogar"])
    # --- percepción y hábitos
    sal = g(df, s["salud"])
    o["salud_autopercibida"] = sal.where(sal.between(1, 5))                          # 1 excelente ... 5 mala
    tab = g(df, s["tabaco"])
    o["tabaco"] = tab.where(tab.isin([1, 2, 3]))                                     # 1 actual, 2 ex, 3 nunca
    af = g(df, s["af"])
    o["actividad_fisica"] = af.where(af.isin([1, 2, 3]))                             # ordinal INDEC (ver diccionario)
    o["alcohol_regular_riesgo"] = binaria(g(df, s["reg"]))
    o["alcohol_episodico"] = binaria(g(df, s["epi"]))
    o["fv_promedio_diario"] = g(df, s["fv"])
    o["cumple_5_fyv"] = binaria(g(df, s["cumple_fv"]))
    # --- medidas autorreportadas
    pk, tc = g(df, s["peso_kg"]), g(df, s["talla_cm"])
    o["peso_kg"] = pk.mask(pk.isin(NSNC_PESO_TALLA))
    o["talla_cm"] = tc.mask(tc.isin(NSNC_PESO_TALLA))
    # --- condiciones de salud (autorreportadas)
    o["hta_medida"] = binaria(g(df, s["ha_med"]))
    dx = g(df, s["ha_dx"])
    o["hta"] = pd.Series(np.select([o["hta_medida"].eq(1) & dx.isin([1, 2]), o["hta_medida"].eq(1) & dx.eq(3)],
                                   [1.0, 0.0], default=np.nan), index=df.index)
    o["colesterol_medido"] = binaria(g(df, s["col_med"]))
    cdx = g(df, s["col_dx"])
    o["colesterol_alto"] = pd.Series(np.select([o["colesterol_medido"].eq(1) & cdx.eq(1), o["colesterol_medido"].eq(1) & cdx.eq(2)],
                                               [1.0, 0.0], default=np.nan), index=df.index)
    o["diabetes"] = binaria(g(df, s["dia"]))
    return o


def armonizar_todos(raw):
    """Concatena todas las ediciones armonizadas (sin limpiar)."""
    return pd.concat([armonizar(raw[a], a) for a in sorted(raw)], ignore_index=True)


# =============================================================================
# 4 · Limpieza
# =============================================================================
def limpiar(H):
    """Duplicados, filas sin variables críticas, valores fuera de rango (-> NaN) e IMC. Devuelve (H_limpio, log_df)."""
    registro = []

    def anotar(paso, anio, n, detalle=""):
        registro.append(dict(paso=paso, anio=anio, afectados=int(n), detalle=detalle))

    # 1) duplicados por id
    dup = H.duplicated("id_unico", keep="first")
    for a, n in H[dup].groupby("anio").size().items():
        anotar("duplicados_id", a, n, "se elimina")
    H = H[~dup].copy()

    # 2) filas sin variables críticas (necesarias para cualquier modelo/ponderación)
    for col in ["edad", "mujer", "peso_muestral"]:
        m = H[col].isna()
        for a, n in H[m].groupby("anio").size().items():
            anotar(f"sin_{col}", a, n, "se elimina la fila")
        H = H[~m]
    m = H["peso_muestral"] <= 0
    for a, n in H[m].groupby("anio").size().items():
        anotar("peso_muestral<=0", a, n, "se elimina la fila")
    H = H[~m].copy()

    # 3) valores fuera de rango -> NaN
    for col, (lo, hi) in RANGOS.items():
        if col == "imc":
            continue                                    # se controla después de calcularlo
        fuera = H[col].notna() & ~H[col].between(lo, hi)
        for a, n in H[fuera].groupby("anio").size().items():
            anotar(f"fuera_de_rango_{col}", a, n, f"fuera de [{lo}, {hi}] -> NaN")
        H.loc[fuera, col] = np.nan

    # 4) IMC (peso / talla^2)
    H["imc"] = H["peso_kg"] / (H["talla_cm"] / 100) ** 2
    lo, hi = RANGOS["imc"]
    fuera = H["imc"].notna() & ~H["imc"].between(lo, hi)
    for a, n in H[fuera].groupby("anio").size().items():
        anotar("fuera_de_rango_imc", a, n, f"fuera de [{lo}, {hi}] -> NaN")
    H.loc[fuera, "imc"] = np.nan

    log_df = pd.DataFrame(registro, columns=["paso", "anio", "afectados", "detalle"])
    log.info("Filas tras limpieza: %s", f"{len(H):,}")
    return H, log_df


# =============================================================================
# 5 · Variables objetivo
# =============================================================================
def construir_targets(H, no_medido_como_negativo=NO_MEDIDO_COMO_NEGATIVO):
    """Agrega obesidad, sobrepeso, salud_regular_mala, n_condiciones y riesgo_cardiometabolico."""
    H["obesidad"] = np.where(H["imc"].isna(), np.nan, (H["imc"] >= 30).astype(float))
    H["sobrepeso"] = np.where(H["imc"].isna(), np.nan, (H["imc"] >= 25).astype(float))      # incluye obesidad
    H["salud_regular_mala"] = np.where(H["salud_autopercibida"].isna(), np.nan, (H["salud_autopercibida"] >= 4).astype(float))

    cond = H[COND].fillna(0) if no_medido_como_negativo else H[COND]
    algun_pos = (cond == 1).any(axis=1)
    todos_conocidos = cond.notna().all(axis=1)
    H["n_condiciones"] = np.where(todos_conocidos, cond.sum(axis=1), np.nan)
    H["riesgo_cardiometabolico"] = np.where(algun_pos, 1.0, np.where(todos_conocidos, 0.0, np.nan))
    return H


def resumen_targets(H):
    """Prevalencia SIN ponderar por año de cada target y % de nulos."""
    resumen = H.groupby("anio")[TARGETS].mean().round(3).T
    resumen.columns = [f"prev_{c}" for c in resumen.columns]
    resumen["pct_nulos"] = (H[TARGETS].isna().mean() * 100).round(1)
    return resumen


# =============================================================================
# 6 · Validación contra las variables oficiales de INDEC
# =============================================================================
def validar_contra_oficiales(H, raw, umbral_pct=98.0):
    """Compara la regla propia (hta, colesterol_alto, diabetes) con las prevalencias oficiales de 2009, 2013 y 2018."""
    filas = []
    Hi = H.set_index(["anio", "id_original"])
    for a, of in OFICIALES.items():
        if a not in raw:
            continue
        r = raw[a]
        ids = r[SPEC[a]["id"]].astype("Int64").astype(str)
        for nombre, var_propia in [("hta", "hta"), ("col", "colesterol_alto"), ("dia", "diabetes")]:
            oficial = pd.Series(binaria(r[of[nombre]].astype("float64")).values, index=ids.values)
            propia = Hi.loc[a][var_propia]
            j = pd.concat([oficial.rename("of"), propia.rename("propia")], axis=1, join="inner")
            j = j[j["of"].notna() | j["propia"].notna()]
            filas.append(dict(anio=a, variable=var_propia, comparados=len(j),
                              coinciden_pct=round(100 * (j["of"].fillna(-1) == j["propia"].fillna(-1)).mean(), 2)))
    validacion = pd.DataFrame(filas)
    if len(validacion) and not (validacion["coinciden_pct"] > umbral_pct).all():
        raise AssertionError("La regla propia no replica la variable oficial: revisar SPEC")
    return validacion


# =============================================================================
# 7 · Tipos finales y diccionario
# =============================================================================
def finalizar_tipos(H):
    """Agrega peso_rel y grupo_etario, optimiza tipos y ordena columnas."""
    # peso relativo dentro de cada año (media 1): permite combinar años sin que uno domine por tener más población expandida
    H["peso_rel"] = H["peso_muestral"] / H.groupby("anio")["peso_muestral"].transform("mean")
    H["grupo_etario"] = pd.cut(H["edad"], [17, 24, 34, 49, 64, 200], labels=[1, 2, 3, 4, 5]).astype("float")   # 1:18-24 ... 5:65+

    enteros = ["anio", "provincia", "region", "mujer", "edad", "nivel_instruccion", "tiene_cobertura", "condicion_actividad",
               "quintil_ingreso", "cant_componentes", "salud_autopercibida", "tabaco", "actividad_fisica", "alcohol_regular_riesgo",
               "alcohol_episodico", "cumple_5_fyv", "hta_medida", "hta", "colesterol_medido", "colesterol_alto", "diabetes",
               "obesidad", "sobrepeso", "salud_regular_mala", "n_condiciones", "riesgo_cardiometabolico", "grupo_etario"]
    for c in enteros:
        H[c] = H[c].round().astype("Int16" if c in ("anio", "provincia", "edad", "cant_componentes") else "Int8")
    for c in ["peso_muestral", "peso_rel", "peso_kg", "talla_cm", "imc", "fv_promedio_diario"]:
        H[c] = H[c].astype("float32")
    primeras = ["id_unico", "anio", "peso_muestral", "peso_rel"]
    H = H[primeras + [c for c in H.columns if c not in ("id_unico", "id_original", *primeras)] + ["id_original"]]
    return H.reset_index(drop=True)


def construir_diccionario(H):
    """(diccionario con % de datos disponibles por año, % de nulos por variable y año)."""
    orden = [d[0] for d in DICC]
    assert set(orden) == set(H.columns), f"Columnas sin documentar: {set(H.columns) ^ set(orden)}"
    disp = H.groupby("anio").apply(lambda x: (x.notna().mean() * 100).round(0)).T
    disp.loc["anio"] = 100.0
    diccionario = (pd.DataFrame(DICC, columns=["variable", "rol", "descripcion"]).set_index("variable")
                   .join(disp.add_prefix("pct_no_nulo_")).loc[orden])
    qa_nulos = H.groupby("anio").apply(lambda x: (x.isna().mean() * 100).round(1)).T
    return diccionario, qa_nulos


# =============================================================================
# 8 · Exportación y pipeline completo
# =============================================================================
def exportar(H, diccionario, qa_nulos, log_limpieza, validacion, salida):
    """Guarda dataset limpio y reportes en `salida`. Devuelve {nombre: ruta}."""
    os.makedirs(salida, exist_ok=True)
    rutas = {"dataset": guardar_df(H, os.path.join(salida, "enfr_armonizado"))}
    rutas["dataset_csv"] = os.path.join(salida, "enfr_armonizado.csv")          # formato de intercambio (Drive / EDA / Apify)
    H.to_csv(rutas["dataset_csv"], index=False)
    for nombre, tabla, con_indice in [("diccionario_variables.csv", diccionario, True), ("qa_nulos_por_anio.csv", qa_nulos, True),
                                      ("qa_log_limpieza.csv", log_limpieza, False), ("qa_validacion_oficial.csv", validacion, False)]:
        rutas[nombre] = os.path.join(salida, nombre)
        tabla.to_csv(rutas[nombre], index=con_indice)
    return rutas


def run_etl(entrada, salida, anios=ANIOS, no_medido_como_negativo=NO_MEDIDO_COMO_NEGATIVO, guardar_tipado=True):
    """Pipeline completo: .txt -> dataset limpio y armonizado.

    entrada: carpeta con los .txt de la ENFR | salida: carpeta donde se guarda todo.
    Devuelve dict con: dataset (DataFrame), diccionario, qa_nulos, log_limpieza, validacion, auditoria, resumen_targets, rutas.
    """
    archivos = detectar_archivos(entrada, anios)
    for a, p in sorted(archivos.items()):
        log.info("%s -> %s (%.1f MB)", a, os.path.basename(p), os.path.getsize(p) / 1e6)
    raw = cargar_raw(archivos, salida if guardar_tipado else None)
    auditoria = auditar(raw)
    H = armonizar_todos(raw)
    log.info("Dataset armonizado (sin limpiar): %s", H.shape)
    H, log_limpieza = limpiar(H)
    H = construir_targets(H, no_medido_como_negativo)
    resumen = resumen_targets(H)
    validacion = validar_contra_oficiales(H, raw)
    H = finalizar_tipos(H)
    diccionario, qa_nulos = construir_diccionario(H)
    rutas = exportar(H, diccionario, qa_nulos, log_limpieza, validacion, salida)
    log.info("Guardado: %s | %s filas x %s columnas", rutas["dataset_csv"], f"{H.shape[0]:,}", H.shape[1])
    return dict(dataset=H, diccionario=diccionario, qa_nulos=qa_nulos, log_limpieza=log_limpieza, validacion=validacion,
                auditoria=auditoria, resumen_targets=resumen, rutas=rutas)


def main():
    ap = argparse.ArgumentParser(description="ETL de la ENFR (2005, 2009, 2013, 2018)")
    ap.add_argument("--entrada", required=True, help="carpeta con los .txt de la ENFR")
    ap.add_argument("--salida", required=True, help="carpeta de salida (dataset limpio y reportes)")
    ap.add_argument("--estricto", action="store_true", help="targets compuestos: 'no medido' queda como desconocido (NO_MEDIDO_COMO_NEGATIVO=False)")
    ap.add_argument("--sin-tipado", action="store_true", help="no guardar los datos tipados por año")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_etl(args.entrada, args.salida, no_medido_como_negativo=not args.estricto, guardar_tipado=not args.sin_tipado)


if __name__ == "__main__":
    main()
