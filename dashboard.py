import streamlit as st
import json
import os
import glob
import pandas as pd

st.set_page_config(page_title="OMNI-SWARM EMS", layout="wide", page_icon="🛡️")

# =========================================================================
# RUTAS EN LA NUBE
# =========================================================================
INTELLIGENCE_FILE = "master_intelligence.json"
LIVE_DATA_FILE = "trade_history.csv"
DATA_LAKE_DIR = "data_lake"

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
def load_live_csv():
    if os.path.exists(LIVE_DATA_FILE):
        return pd.read_csv(LIVE_DATA_FILE)
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_datalake_files():
    if os.path.exists(DATA_LAKE_DIR):
        return [f for f in os.listdir(DATA_LAKE_DIR) if f.endswith("_clean.csv")]
    return []

data = load_json()
df_live = load_live_csv()
datalake_files = get_datalake_files()

st.title("🛡️ OMNI-SWARM: Execution Management System")

# =========================================================================
# NAVEGACIÓN PRINCIPAL (3 PESTAÑAS)
# =========================================================================
tab1, tab2, tab3 = st.tabs(["📊 Telemetría en Vivo", "🧠 Inteligencia y Exclusiones", "🗄️ Data Lake (Históricos)"])

# -------------------------------------------------------------------------
# PESTAÑA 1: TELEMETRÍA EN VIVO 
# -------------------------------------------------------------------------
with tab1:
    st.header("Operativa de la Sesión")
    if df_live.empty:
        st.info("No hay datos de operaciones en vivo registrados todavía.")
    else:
        df_live['Timestamp'] = pd.to_datetime(df_live['Timestamp'], errors='coerce')
        df_live = df_live.sort_values(by='Timestamp', ascending=False)
        
        fechas_disponibles = df_live['Timestamp'].dt.date.dropna().unique()
        selected_date = st.selectbox("Filtrar Sesión", ["Todas"] + list(fechas_disponibles))
        
        df_filtered = df_live.copy()
        if selected_date != "Todas":
            df_filtered = df_filtered[df_filtered['Timestamp'].dt.date == selected_date]
        
        df_closed = df_filtered[df_filtered['Status'].astype(str).str.contains('CLOSED_')]
        total_trades = len(df_closed)
        wins = len(df_closed[df_closed['Status'].astype(str).str.contains('WIN')])
        losses = total_trades - wins
        wr_session = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Trades Cerrados", f"{total_trades}")
        c2.metric("Win Rate Sesión", f"{wr_session:.1f}%")
        c3.metric("Resultado Crudo", f"{wins}W - {losses}L")
        
        def color_status(val):
            if 'WIN' in str(val): return 'color: #00cc96; font-weight: bold;'
            if 'LOSS' in str(val): return 'color: #ff4b4b; font-weight: bold;'
            return ''
        st.dataframe(df_filtered.style.map(color_status, subset=['Status']), use_container_width=True)

# -------------------------------------------------------------------------
# PESTAÑA 2: INTELIGENCIA 
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

# -------------------------------------------------------------------------
# PESTAÑA 3: DATA LAKE (EL HISTÓRICO)
# -------------------------------------------------------------------------
with tab3:
    st.header("🗄️ Explorador de Backtests (Data Lake)")
    
    if not datalake_files:
        st.warning("No se encontraron archivos de backtest en la carpeta 'data_lake'.")
    else:
        # Selector de activo
        selected_file = st.selectbox("Seleccionar Activo / Dataset", datalake_files)
        
        if selected_file:
            file_path = os.path.join(DATA_LAKE_DIR, selected_file)
            df_hist = pd.read_csv(file_path)
            
            # Selector secundario de motor dentro del archivo
            motores_disponibles = df_hist['Engine'].unique() if 'Engine' in df_hist.columns else []
            selected_hist_engine = st.selectbox("Filtrar por Motor Táctico", ["Todos"] + list(motores_disponibles))
            
            if selected_hist_engine != "Todos":
                df_hist = df_hist[df_hist['Engine'] == selected_hist_engine]
            
            # Cálculo de métricas históricas
            st.subheader(f"Métricas Históricas: {selected_file.replace('_clean.csv', '')}")
            
            if 'Status' in df_hist.columns:
                df_hist['Is_Win'] = df_hist['Status'].astype(str).str.contains('WIN').astype(int)
                total_hist = len(df_hist)
                wins_hist = df_hist['Is_Win'].sum()
                wr_hist = (wins_hist / total_hist * 100) if total_hist > 0 else 0
                
                hc1, hc2, hc3 = st.columns(3)
                hc1.metric("Muestra Total", f"{total_hist} trades")
                hc2.metric("Win Rate Histórico", f"{wr_hist:.1f}%")
                
                if 'Trade_Duration_Mins' in df_hist.columns:
                    avg_dur = df_hist['Trade_Duration_Mins'].mean()
                    hc3.metric("Duración Promedio", f"{avg_dur:.1f} mins")
            
            st.dataframe(df_hist, use_container_width=True)
