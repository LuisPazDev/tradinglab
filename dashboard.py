import streamlit as st
import json
import os
import pandas as pd

# =========================================================================
# CONFIGURACIÓN DE PÁGINA Y RUTAS
# =========================================================================
st.set_page_config(page_title="OMNI-SWARM Cuantitativo", layout="wide", page_icon="🛡️")

INTELLIGENCE_FILE = "master_intelligence.json"

# =========================================================================
# EXTRACCIÓN DE DATOS
# =========================================================================
@st.cache_data(ttl=60) # Refresca los datos cada 60 segundos si hay cambios
def load_data():
    if not os.path.exists(INTELLIGENCE_FILE):
        return None
    with open(INTELLIGENCE_FILE, "r") as f:
        return json.load(f)

data = load_data()

st.title("🛡️ Centro de Mando: OMNI-SWARM")
st.markdown("Monitor de Inteligencia Artificial y Reglas de Exclusión Dinámicas")

if not data:
    st.error("No se encontró la base de datos (master_intelligence.json). Ejecuta train_models.py primero.")
    st.stop()

engines = data.get("Micro_Engines", {})

# Convertir el JSON a un DataFrame global para la tabla resumen
df_list = []
for engine, stats in engines.items():
    symbol = stats.get("symbol", "N/A")
    wr = stats.get("win_rate", 0) * 100
    status = stats.get("pre_flight_status", "⚪ SIN DATOS")
    trades = stats.get("n_trades", 0)
    df_list.append({
        "Símbolo": symbol,
        "Motor Táctico": engine,
        "Win Rate (%)": round(wr, 1),
        "Trades": trades,
        "Salud Base": status
    })

df_overview = pd.DataFrame(df_list)

# =========================================================================
# BARRA LATERAL (FILTROS)
# =========================================================================
st.sidebar.header("Filtros de Flota")
activos_disponibles = df_overview["Símbolo"].unique().tolist() if not df_overview.empty else []
selected_asset = st.sidebar.selectbox("Filtrar por Activo", ["Todos"] + activos_disponibles)

if selected_asset != "Todos":
    df_overview = df_overview[df_overview["Símbolo"] == selected_asset]

selected_engine = st.sidebar.selectbox("Inspeccionar Motor Específico", df_overview["Motor Táctico"].tolist())

# =========================================================================
# VISTA DE DETALLE (EL MICROSCOPIO)
# =========================================================================
st.divider()
if selected_engine:
    stats = engines[selected_engine]
    st.header(f"⚙️ Análisis de Motor: {selected_engine} ({stats.get('symbol', 'N/A')})")

    # 1. KPIs Globales
    col1, col2, col3 = st.columns(3)
    wr_val = stats.get('win_rate', 0) * 100
    col1.metric("Win Rate Global", f"{wr_val:.1f}%")
    col2.metric("Muestra Histórica", f"{stats.get('n_trades', 0)} trades")

    estado = stats.get('pre_flight_status', 'N/A')
    if "CRÍTICO" in estado:
        col3.error(f"Estatus: {estado}")
    else:
        col3.success(f"Estatus: {estado}")

    # 2. Matriz Condicional (El Mapa de Calor de Regímenes)
    st.subheader("📊 Probabilidad Condicional (Desglose por Régimen)")
    matrix = stats.get("conditional_matrix", {})

    if matrix:
        reg_cols = st.columns(len(matrix))
        for i, (regime, info) in enumerate(matrix.items()):
            with reg_cols[i]:
                health = info.get("regime_health", "")
                reg_wr = info.get("win_rate", 0) * 100
                st.markdown(f"**{regime}**")

                if "HOSTIL" in health:
                    st.error(f"**🚫 HOSTIL**\n\n**WR:** {reg_wr:.1f}%\n\n**Trades:** {info.get('n_trades', 0)}")
                else:
                    st.success(f"**✅ ÓPTIMO**\n\n**WR:** {reg_wr:.1f}%\n\n**Trades:** {info.get('n_trades', 0)}")
    else:
        st.info("No hay suficientes datos segregados por régimen (Mín. 15 trades requeridos).")

    # 3. Prescripción Automática para Middleware
    st.subheader("🛡️ Reglas Activas para el Filtro de Señales")
    toxic_regimes = [reg for reg, info in matrix.items() if "HOSTIL" in info.get("regime_health", "")]

    if toxic_regimes:
        st.warning(f"🚨 **RECHAZAR SEÑALES** de `{selected_engine}` si el mercado entra en: **{', '.join(toxic_regimes)}**")
    else:
        st.info("✅ Sin restricciones operativas. El motor tiene ventaja estadística en todos los regímenes evaluados.")

# =========================================================================
# VISTA PANORÁMICA DE LA FLOTA
# =========================================================================
st.divider()
st.subheader("🌍 Panorama Global de la Flota Activa")
# Colorear la columna de Win Rate según tu límite crítico de supervivencia (65%)
def color_wr(val):
    color = '#ff4b4b' if val < 65.0 else '#00cc96'
    return f'color: {color}'

st.dataframe(df_overview.style.applymap(color_wr, subset=['Win Rate (%)']), use_container_width=True)
