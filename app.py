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
    st.subheader("Media y varianza")
    anio_mv = st.selectbox("Año", anios, index=len(anios) - 1, key="anio_mv")
    m1, m2 = st.columns([1, 1])
    with m1:
        st.markdown("**Condiciones (variables 0/1): la media es la prevalencia**")
        tb = total[total["anio"] == anio_mv].copy()
        tb["Media (prevalencia)"] = tb["prevalencia"].round(3)
        tb["Varianza p(1-p)"] = (tb["prevalencia"] * (1 - tb["prevalencia"])).round(3)
        tb["Desvío"] = (tb["Varianza p(1-p)"] ** 0.5).round(3)
        st.dataframe(
            tb[["indicador_nombre", "Media (prevalencia)", "Varianza p(1-p)", "Desvío"]]
            .rename(columns={"indicador_nombre": "Condición"}),
            hide_index=True, use_container_width=True,
        )
        st.caption("En una variable 0/1 la media es la proporción de casos y la varianza es p·(1−p).")
    with m2:
        st.markdown("**Variables continuas: edad e IMC**")
        desc = leer_csv("enfr_descriptivas.csv")
        if desc is not None:
            nombres_var = {"edad": "Edad (años)", "imc": "IMC (kg/m²)", "peso_kg": "Peso (kg)", "talla_cm": "Talla (cm)"}
            dv = desc[(desc["anio"] == anio_mv) & desc["variable"].isin(["edad", "imc"])].copy()
            dv["variable"] = dv["variable"].map(nombres_var)
            st.dataframe(
                dv[["variable", "media", "varianza", "desvio", "mediana", "q1", "q3"]].rename(columns={
                    "variable": "Variable", "media": "Media", "varianza": "Varianza", "desvio": "Desvío",
                    "mediana": "Mediana", "q1": "Q1", "q3": "Q3"}),
                hide_index=True, use_container_width=True,
            )
            st.caption("Q1 y Q3: cuartiles (el 50% central de la población está entre ambos).")
        else:
            st.info("Falta `data/enfr_descriptivas.csv`.")

    if desc is not None:
        imc = desc[desc["variable"] == "imc"].sort_values("anio")
        fig = px.line(imc, x="anio", y="media", markers=True,
                      labels={"anio": "Año", "media": "IMC medio (kg/m²)"})
        fig.add_scatter(x=imc["anio"], y=imc["q3"], mode="lines", line=dict(dash="dot", color="#94a3b8"), name="Q3")
        fig.add_scatter(x=imc["anio"], y=imc["q1"], mode="lines", line=dict(dash="dot", color="#94a3b8"), name="Q1")
        fig.add_hline(y=30, line_dash="dash", line_color="#dc2626", annotation_text="Obesidad (IMC 30)")
        fig.update_xaxes(tickvals=anios)
        fig.update_layout(height=340, title="IMC: media y cuartiles por año", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        i0, i1 = imc.iloc[0], imc.iloc[-1]
        st.markdown(
            f"El IMC medio subió de **{i0['media']:.1f}** a **{i1['media']:.1f}** y su varianza de "
            f"**{i0['varianza']:.1f}** a **{i1['varianza']:.1f}**: no solo aumenta el promedio, también se dispersa. "
            f"En {int(i1['anio'])}, el 25% de la población ya supera un IMC de **{i1['q3']:.1f}**, por encima del umbral de obesidad."
        )

    # --- correlación
    st.subheader("Matriz de correlación")
    corr = leer_csv("enfr_correlacion.csv", index_col=0)
    if corr is not None:
        # Se saca el IMC: la obesidad se define como IMC >= 30 y su correlación (0,78) es por construcción.
        quitar = [c for c in corr.columns if c.lower() == "imc"]
        corr = corr.drop(index=quitar, columns=quitar)
        corr.index = corr.index.str.replace("edad", "Edad")
        corr.columns = corr.columns.str.replace("edad", "Edad")
        fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="Blues", zmin=0, zmax=0.4, aspect="auto")
        fig.update_layout(height=440, coloraxis_colorbar_title="r")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            "- Las cuatro condiciones se correlacionan **en forma positiva y baja (0,11 a 0,21)**: tienden a darse "
            "en las mismas personas, lo que respalda el hallazgo de la **acumulación de condiciones**.\n"
            "- La **edad** es la variable más asociada a la hipertensión (r = 0,34).\n"
            "- La escala va de 0 a 0,4 para que se vean las diferencias; la diagonal (r = 1) queda fuera de escala. "
            "Se dejó afuera el IMC porque la obesidad se calcula a partir de él."
        )

    # --- odds ratio
    st.subheader("Factores asociados a la hipertensión (odds ratio)")
    orr = leer_csv("enfr_odds_ratio.csv")
    if orr is not None:
        if "or_ajustado_edad" in orr.columns:
            crudo = orr[["factor", "or_crudo", "crudo_ic_bajo", "crudo_ic_alto"]].set_axis(["factor", "or", "lo", "hi"], axis=1)
            ajust = orr[["factor", "or_ajustado_edad", "ajust_ic_bajo", "ajust_ic_alto"]].set_axis(["factor", "or", "lo", "hi"], axis=1)
            crudo["tipo"], ajust["tipo"] = "Crudo", "Ajustado por edad"
            largo = pd.concat([crudo, ajust], ignore_index=True)
        else:
            largo = orr[["factor", "odds_ratio", "ic_bajo", "ic_alto"]].set_axis(["factor", "or", "lo", "hi"], axis=1)
            largo["tipo"] = "Crudo"
        orden_f = largo[largo["tipo"] == largo["tipo"].iloc[-1]].sort_values("or")["factor"].tolist()
        fig = px.scatter(
            largo, x="or", y="factor", color="tipo",
            error_x=largo["hi"] - largo["or"], error_x_minus=largo["or"] - largo["lo"],
            color_discrete_map={"Crudo": "#94a3b8", "Ajustado por edad": "#2563eb"},
            category_orders={"factor": orden_f},
            labels={"or": "Odds ratio (IC 95%)", "factor": "", "tipo": ""},
            hover_data={"lo": ":.2f", "hi": ":.2f"},
        )
        fig.add_vline(x=1, line_dash="dash", line_color="gray")
        fig.update_traces(marker_size=10)
        fig.update_layout(height=480, xaxis_type="log", legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            "**Cómo leerlo:** OR = 1 es la línea punteada (sin asociación). A la derecha, el factor se asocia con **más** "
            "hipertensión diagnosticada; a la izquierda, con **menos**. Los puntos grises son el OR crudo y los azules el "
            "**ajustado por edad**, que es el que hay que mirar: la edad empuja casi todo hacia arriba.\n\n"
            "- Diabetes, obesidad y colesterol alto siguen duplicando las chances aun después de ajustar por edad.\n"
            "- **Sin cobertura** pasa de 0,71 (crudo) a 1,14 (ajustado): el efecto 'protector' era un artefacto de la edad.\n"
            "- **Fumador actual** sigue debajo de 1 mientras que **ex fumador** queda arriba: es consistente con "
            "**causalidad inversa** (quien recibe el diagnóstico deja de fumar). No significa que fumar proteja."
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
