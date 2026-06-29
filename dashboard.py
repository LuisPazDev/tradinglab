import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="OMNI-SWARM EMS", layout="wide", page_icon="🛡️")

# =========================================================================
# RUTAS EN LA NUBE (Busca los archivos en el mismo repo)
# =========================================================================
INTELLIGENCE_FILE = "master_intelligence.json"
LIVE_DATA_FILE = "trade_history.csv"

# =========================================================================
# EXTRACCIÓN DE DATOS
# =========================================================================
@st.cache_data(ttl=60)
def load_json():
    if os.path.exists(INTELLIGENCE_FILE):
        with open(INTELLIGENCE_FILE, "r") as f:
            return json.load(f)
    return None

@st.cache_data(ttl=60)
def load_csv():
    if os.path.exists(LIVE_DATA_FILE):
        return pd.read_csv(LIVE_DATA_FILE)
    return pd.DataFrame()

data = load_json()
df_live = load_csv()

st.title("🛡️ OMNI-SWARM: Execution Management System")

# =========================================================================
# NAVEGACIÓN PRINCIPAL
# =========================================================================
tab1, tab2 = st.tabs(["📊 Telemetría en Vivo", "🧠 Inteligencia y Exclusiones"])

# -------------------------------------------------------------------------
# PESTAÑA 1: TELEMETRÍA EN VIVO (PnL y Operaciones de Hoy)
# -------------------------------------------------------------------------
with tab1:
    st.header("Operativa de la Sesión")
    if df_live.empty:
        st.info("No hay datos de operaciones en vivo registrados todavía.")
    else:
        # Limpieza rápida del dataset
        df_live['Timestamp'] = pd.to_datetime(df_live['Timestamp'], errors='coerce')
        df_live = df_live.sort_values(by='Timestamp', ascending=False)
        
        # Filtro de fecha
        fechas_disponibles = df_live['Timestamp'].dt.date.dropna().unique()
        selected_date = st.selectbox("Filtrar Sesión", ["Todas"] + list(fechas_disponibles))
        
        df_filtered = df_live.copy()
        if selected_date != "Todas":
            df_filtered = df_filtered[df_filtered['Timestamp'].dt.date == selected_date]
        
        # KPIs de la sesión
        df_closed = df_filtered[df_filtered['Status'].astype(str).str.contains('CLOSED_')]
        total_trades = len(df_closed)
        wins = len(df_closed[df_closed['Status'].astype(str).str.contains('WIN')])
        losses = total_trades - wins
        wr_session = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Trades Cerrados", f"{total_trades}")
        c2.metric("Win Rate Sesión", f"{wr_session:.1f}%")
        c3.metric("Resultado Crudo", f"{wins}W - {losses}L")
        
        st.subheader("Bitácora de Ejecución")
        # Mostrar el dataframe coloreando los ganadores y perdedores
        def color_status(val):
            if 'WIN' in str(val): return 'color: #00cc96; font-weight: bold;'
            if 'LOSS' in str(val): return 'color: #ff4b4b; font-weight: bold;'
            return ''
        st.dataframe(df_filtered.style.map(color_status, subset=['Status']), use_container_width=True)

# -------------------------------------------------------------------------
# PESTAÑA 2: INTELIGENCIA (El dashboard original)
# -------------------------------------------------------------------------
with tab2:
    if not data:
        st.error("No se encontró master_intelligence.json.")
    else:
        engines = data.get("Micro_Engines", {})
        
        df_list = []
        for engine, stats in engines.items():
            df_list.append({
                "Símbolo": stats.get("symbol", "N/A"), 
                "Motor": engine, 
                "WR (%)": round(stats.get("win_rate", 0) * 100, 1), 
                "Salud": stats.get("pre_flight_status", "N/A")
            })
        df_overview = pd.DataFrame(df_list)
        
        selected_engine = st.selectbox("Inspeccionar Regímenes del Motor", df_overview["Motor"].tolist())
        
        if selected_engine:
            stats = engines[selected_engine]
            matrix = stats.get("conditional_matrix", {})
            if matrix:
                reg_cols = st.columns(len(matrix))
                for i, (regime, info) in enumerate(matrix.items()):
                    with reg_cols[i]:
                        health = info.get("regime_health", "")
                        st.markdown(f"**{regime}**")
                        if "HOSTIL" in health:
                            st.error(f"**🚫 HOSTIL** (WR: {info.get('win_rate',0)*100:.1f}%)")
                        else:
                            st.success(f"**✅ ÓPTIMO** (WR: {info.get('win_rate',0)*100:.1f}%)")
            
            st.divider()
            def color_wr(val):
                return 'color: #ff4b4b' if val < 65.0 else 'color: #00cc96'
            st.dataframe(df_overview.style.map(color_wr, subset=['WR (%)']), use_container_width=True)
