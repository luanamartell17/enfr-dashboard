"""Dashboard ENFR (Encuesta Nacional de Factores de Riesgo) 2005-2018.

Lee el resultado del EDA (prevalencias por indicador, año y corte).
Fuente de datos, en este orden:
  1. La URL CSV definida en st.secrets["DATA_URL"] o en la variable de entorno DATA_URL
     (por ejemplo, la pestaña "dashboard" de Google Sheets que actualiza n8n).
  2. El archivo local data/enfr_eda.csv incluido en el repositorio.
"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Dashboard ENFR 2005-2018", page_icon="🩺", layout="wide")

INDICADORES = {
    "hta": "Hipertensión",
    "diabetes": "Diabetes",
    "colesterol_alto": "Colesterol alto",
    "obesidad": "Obesidad",
}
CORTES = {
    "sexo": "Sexo",
    "grupo_etario": "Grupo de edad",
    "quintil_ingreso": "Quintil de ingreso",
    "cobertura": "Cobertura de salud",
    "tabaco": "Consumo de tabaco",
    "region": "Región",
    "provincia": "Provincia",
}
ORDEN_CORTES = {
    "grupo_etario": ["18-24", "25-34", "35-49", "50-64", "65+"],
    "quintil_ingreso": ["Q1", "Q2", "Q3", "Q4", "Q5"],
    "tabaco": ["Nunca fumó", "Ex fumador", "Fumador actual"],
}
LOCAL_CSV = os.path.join(os.path.dirname(__file__), "data", "enfr_eda.csv")


def _data_url():
    try:
        url = st.secrets.get("DATA_URL", "")
    except Exception:
        url = ""
    return url or os.environ.get("DATA_URL", "")


def _a_numero(serie):
    """Acepta 0.2923, '0.2923' o '0,2923'."""
    s = serie.astype(str).str.strip()
    s = s.where(~s.str.contains(","), s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")


@st.cache_data(ttl=3600, show_spinner="Cargando datos...")
def cargar_datos():
    url = _data_url()
    origen = "archivo del repositorio (data/enfr_eda.csv)"
    df = None
    if url:
        try:
            df = pd.read_csv(url)
            origen = "Google Sheets (actualizado por n8n)"
        except Exception:
            df = None
    if df is None:
        df = pd.read_csv(LOCAL_CSV)

    df.columns = [c.strip().lower() for c in df.columns]
    for c in ["anio", "n", "prevalencia", "prevalencia_pct"]:
        df[c] = _a_numero(df[c])
    # Misma reparación que el nodo "Validar y reparar" de n8n:
    # si la prevalencia quedó fuera de [0, 1] (punto leído como separador de miles), se reconstruye desde el %.
    rota = ~df["prevalencia"].between(0, 1)
    df.loc[rota, "prevalencia"] = df.loc[rota, "prevalencia_pct"] / 100
    df["prevalencia_pct"] = (df["prevalencia"] * 100).round(1)
    df["anio"] = df["anio"].astype(int)
    df["indicador_nombre"] = df["indicador"].map(INDICADORES).fillna(df["indicador"])
    actualizado = str(df["actualizado"].dropna().max()) if "actualizado" in df.columns else "-"
    return df, origen, actualizado


df, origen, actualizado = cargar_datos()
anios = sorted(df["anio"].unique())
ultimo = max(anios)

# ---------------------------------------------------------------- encabezado
st.title("🩺 Factores de riesgo en Argentina · ENFR 2005-2018")
st.caption(
    f"Encuesta Nacional de Factores de Riesgo (INDEC). Prevalencias autorreportadas en población de 18 años o más. "
    f"Fuente de datos: {origen} · Última actualización: {actualizado}"
)

# ---------------------------------------------------------------- KPIs total país
total = df[df["corte_tipo"] == "total"]
st.subheader(f"Total país · {ultimo}")
cols = st.columns(len(INDICADORES))
for col, (cod, nombre) in zip(cols, INDICADORES.items()):
    serie = total[total["indicador"] == cod].set_index("anio")["prevalencia_pct"]
    if ultimo in serie.index:
        primero = min(serie.index)
        delta = serie[ultimo] - serie[primero]
        col.metric(nombre, f"{serie[ultimo]:.1f}%", f"{delta:+.1f} pp vs {primero}", delta_color="inverse")

tab_evol, tab_cortes, tab_prov, tab_stats, tab_datos = st.tabs(
    ["📈 Evolución", "👥 Por grupo", "🗺️ Provincias", "📊 Estadística", "📄 Datos"]
)

# ---------------------------------------------------------------- evolución
with tab_evol:
    st.markdown("**¿Cómo cambió cada condición entre 2005 y 2018?** (total país)")
    fig = px.line(
        total.sort_values("anio"), x="anio", y="prevalencia_pct", color="indicador_nombre", markers=True,
        labels={"anio": "Año", "prevalencia_pct": "Prevalencia (%)", "indicador_nombre": "Indicador"},
    )
    fig.update_xaxes(tickvals=anios)
    fig.update_layout(height=430, legend_title_text="", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.info(
        "La obesidad es la condición que más creció en el período; hipertensión y colesterol se mantienen altos. "
        "Ojo: son diagnósticos autorreportados, así que quien nunca se controló figura como 'sin diagnóstico'."
    )

# ---------------------------------------------------------------- por grupo
with tab_cortes:
    c1, c2, c3 = st.columns([1, 1, 1])
    ind = c1.selectbox("Indicador", list(INDICADORES), format_func=INDICADORES.get, key="ind_corte")
    cortes_disp = [c for c in CORTES if c != "provincia" and c in df["corte_tipo"].unique()]
    corte = c2.selectbox("Comparar por", cortes_disp, format_func=CORTES.get)
    anio_sel = c3.selectbox("Año", anios, index=len(anios) - 1, key="anio_corte")

    d = df[(df["indicador"] == ind) & (df["corte_tipo"] == corte)]
    orden = ORDEN_CORTES.get(corte, sorted(d["corte_valor"].unique()))

    d_anio = d[d["anio"] == anio_sel]
    fig = px.bar(
        d_anio, x="corte_valor", y="prevalencia_pct", text="prevalencia_pct",
        category_orders={"corte_valor": orden},
        labels={"corte_valor": CORTES[corte], "prevalencia_pct": "Prevalencia (%)"},
        hover_data={"n": True},
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", marker_color="#2563eb")
    fig.update_layout(height=420, title=f"{INDICADORES[ind]} por {CORTES[corte].lower()} · {anio_sel}")
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.line(
        d.sort_values("anio"), x="anio", y="prevalencia_pct", color="corte_valor", markers=True,
        category_orders={"corte_valor": orden},
        labels={"anio": "Año", "prevalencia_pct": "Prevalencia (%)", "corte_valor": CORTES[corte]},
    )
    fig2.update_xaxes(tickvals=anios)
    fig2.update_layout(height=380, title="Evolución por grupo")
    st.plotly_chart(fig2, use_container_width=True)

    if len(d_anio) >= 2:
        mx = d_anio.loc[d_anio["prevalencia_pct"].idxmax()]
        mn = d_anio.loc[d_anio["prevalencia_pct"].idxmin()]
        st.markdown(
            f"En **{anio_sel}**, el grupo con mayor prevalencia de **{INDICADORES[ind].lower()}** es "
            f"**{mx['corte_valor']}** ({mx['prevalencia_pct']:.1f}%) y el de menor es **{mn['corte_valor']}** "
            f"({mn['prevalencia_pct']:.1f}%): una brecha de **{mx['prevalencia_pct'] - mn['prevalencia_pct']:.1f} pp**."
        )

# ---------------------------------------------------------------- provincias
with tab_prov:
    c1, c2 = st.columns(2)
    ind_p = c1.selectbox("Indicador", list(INDICADORES), format_func=INDICADORES.get, key="ind_prov")
    anio_p = c2.selectbox("Año", anios, index=len(anios) - 1, key="anio_prov")
    p = df[(df["indicador"] == ind_p) & (df["corte_tipo"] == "provincia") & (df["anio"] == anio_p)]
    p = p.sort_values("prevalencia_pct")
    tot = total[(total["indicador"] == ind_p) & (total["anio"] == anio_p)]["prevalencia_pct"]

    fig = px.bar(
        p, x="prevalencia_pct", y="corte_valor", orientation="h", text="prevalencia_pct",
        labels={"prevalencia_pct": "Prevalencia (%)", "corte_valor": ""}, hover_data={"n": True},
        color="prevalencia_pct", color_continuous_scale="Blues",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    if len(tot):
        fig.add_vline(x=float(tot.iloc[0]), line_dash="dash", line_color="#dc2626",
                      annotation_text=f"Total país {float(tot.iloc[0]):.1f}%", annotation_position="top")
    fig.update_layout(height=720, coloraxis_showscale=False,
                      title=f"{INDICADORES[ind_p]} por provincia · {anio_p}")
    st.plotly_chart(fig, use_container_width=True)

    top = p.sort_values("prevalencia_pct", ascending=False).head(5)
    st.markdown("**Top 5 provincias:** " + " · ".join(f"{r.corte_valor} ({r.prevalencia_pct:.1f}%)" for r in top.itertuples()))
    st.caption("Las provincias con muestras chicas (n bajo) tienen más margen de error; ver la columna n al pasar el mouse.")

# ---------------------------------------------------------------- estadística
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@st.cache_data(show_spinner=False)
def leer_csv(nombre, **kw):
    ruta = os.path.join(DATA_DIR, nombre)
    return pd.read_csv(ruta, **kw) if os.path.exists(ruta) else None


with tab_stats:
    st.markdown(
        "Medidas estadísticas sobre los microdatos de la **ENFR**: media y dispersión de las variables "
        "continuas, correlación entre condiciones, odds ratio de factores asociados a la hipertensión y "
        "prevalencia estandarizada por edad."
    )

    # --- media y varianza
    st.subheader("Media y dispersión")
    m1, m2 = st.columns([1, 1])
    with m1:
        st.markdown("**Variables binarias: la media es la prevalencia**")
        t18 = total[total["anio"] == ultimo].copy()
        t18["Media (prevalencia)"] = t18["prevalencia"].round(3)
        t18["Varianza p(1-p)"] = (t18["prevalencia"] * (1 - t18["prevalencia"])).round(3)
        t18["Desvío"] = (t18["Varianza p(1-p)"] ** 0.5).round(3)
        st.dataframe(
            t18[["indicador_nombre", "Media (prevalencia)", "Varianza p(1-p)", "Desvío"]]
            .rename(columns={"indicador_nombre": "Condición"}),
            hide_index=True, use_container_width=True,
        )
        st.caption("En una variable 0/1 la media es la proporción de casos y la varianza es p·(1−p).")
    with m2:
        st.markdown("**Variables continuas: edad e IMC**")
        desc = leer_csv("enfr_descriptivas.csv")
        if desc is not None:
            st.dataframe(desc, hide_index=True, use_container_width=True)
        else:
            st.info("Falta `data/enfr_descriptivas.csv` (media, desvío, varianza, mediana y cuartiles de edad e IMC). "
                    "Se genera en la sección 10 del notebook del EDA.")

    # --- correlación
    st.subheader("Matriz de correlación")
    corr = leer_csv("enfr_correlacion.csv", index_col=0)
    if corr is not None:
        corr.index = corr.index.str.replace("imc", "IMC").str.replace("edad", "Edad")
        corr.columns = corr.columns.str.replace("imc", "IMC").str.replace("edad", "Edad")
        fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto")
        fig.update_layout(height=470, coloraxis_colorbar_title="r")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            "- Las cuatro condiciones se correlacionan **en forma positiva y baja (0,11 a 0,21)**: tienden a darse "
            "en las mismas personas, lo que respalda el hallazgo de la **acumulación de condiciones**.\n"
            "- La **edad** es la variable más asociada a la hipertensión (r = 0,34).\n"
            "- Obesidad e IMC (r = 0,78) están correlacionados **por construcción**: la obesidad se define como IMC ≥ 30."
        )

    # --- odds ratio
    st.subheader("Factores asociados a la hipertensión (odds ratio)")
    orr = leer_csv("enfr_odds_ratio.csv")
    if orr is not None:
        orr = orr.sort_values("odds_ratio")
        orr["sentido"] = orr["odds_ratio"].apply(lambda v: "Aumenta las chances" if v > 1 else "Reduce las chances")
        fig = px.scatter(
            orr, x="odds_ratio", y="factor", color="sentido",
            error_x=orr["ic_alto"] - orr["odds_ratio"], error_x_minus=orr["odds_ratio"] - orr["ic_bajo"],
            color_discrete_map={"Aumenta las chances": "#dc2626", "Reduce las chances": "#2563eb"},
            labels={"odds_ratio": "Odds ratio (IC 95%)", "factor": "", "sentido": ""},
            hover_data={"ic_bajo": ":.2f", "ic_alto": ":.2f", "sentido": False},
        )
        fig.add_vline(x=1, line_dash="dash", line_color="gray")
        fig.update_traces(marker_size=11)
        fig.update_layout(height=430, xaxis_type="log")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            "**Cómo leerlo:** OR = 1 es la línea punteada, sin asociación. Si todo el intervalo queda a la derecha, el factor "
            "se asocia con **más** hipertensión diagnosticada; si queda a la izquierda, con **menos**. "
            "Tener 50 años o más (OR 3,9), diabetes (2,9) y colesterol alto (2,7) son los factores más fuertes.\n\n"
            "**Ojo con los OR menores a 1** (fumar, baja actividad física, no tener cobertura): no significan que "
            "protejan. Con datos transversales y diagnósticos autorreportados reflejan **causalidad inversa** "
            "(quien recibe el diagnóstico deja de fumar) o **sesgo de diagnóstico** (quien no tiene cobertura se "
            "controla menos y no sabe que es hipertenso)."
        )

    # --- estandarizada
    st.subheader("Hipertensión por provincia (2018): cruda vs. estandarizada por edad")
    est = leer_csv("enfr_estandarizada.csv")
    if est is not None:
        est = est.sort_values("estandarizada_pct")
        larga = est.melt(id_vars=["provincia", "n"], value_vars=["cruda_pct", "estandarizada_pct"],
                         var_name="tipo", value_name="pct")
        larga["tipo"] = larga["tipo"].map({"cruda_pct": "Cruda", "estandarizada_pct": "Estandarizada por edad"})
        fig = px.scatter(
            larga, x="pct", y="provincia", color="tipo", hover_data={"n": True},
            color_discrete_map={"Cruda": "#94a3b8", "Estandarizada por edad": "#2563eb"},
            labels={"pct": "Prevalencia de hipertensión (%)", "provincia": "", "tipo": ""},
            category_orders={"provincia": est["provincia"].tolist()},
        )
        fig.update_traces(marker_size=10)
        fig.update_layout(height=720)
        st.plotly_chart(fig, use_container_width=True)
        mayor = est.loc[est["diferencia_pp"].abs().idxmax()]
        st.markdown(
            "La estandarización ajusta cada provincia como si todas tuvieran **la misma estructura de edad**, "
            "así se comparan sin que pese tener una población más envejecida. "
            f"El cambio más grande es **{mayor['provincia']}** ({mayor['diferencia_pp']:+.1f} pp). "
            "Formosa sigue primera aun después de ajustar: su prevalencia alta no se explica por la edad."
        )
        st.dataframe(est.sort_values("estandarizada_pct", ascending=False), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- datos
with tab_datos:
    st.markdown("Tabla completa del EDA. Se puede filtrar y descargar.")
    f1, f2 = st.columns(2)
    sel_ind = f1.multiselect("Indicadores", list(INDICADORES), default=list(INDICADORES), format_func=INDICADORES.get)
    sel_cor = f2.multiselect("Cortes", sorted(df["corte_tipo"].unique()), default=sorted(df["corte_tipo"].unique()))
    tabla = df[df["indicador"].isin(sel_ind) & df["corte_tipo"].isin(sel_cor)]
    tabla = tabla[["indicador", "anio", "corte_tipo", "corte_valor", "n", "prevalencia", "prevalencia_pct", "fuente"]]
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8"), "enfr_filtrado.csv", "text/csv")

st.divider()
st.caption(
    "Pipeline: .txt crudos de la ENFR (Google Drive) → ETL → CSV limpios en Drive → EDA → este dashboard. "
    "n = cantidad de encuestados en cada grupo."
)
