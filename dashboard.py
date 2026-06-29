import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="OMNI-SWARM EMS", layout="wide", page_icon="🛡️")

# =========================================================================
# RUTAS EN LA NUBE
# =========================================================================
INTELLIGENCE_FILE = "master_intelligence.json"
LIVE_DATA_FILE = "trade_history.csv"
DATA_LAKE_DIR = "data_lake"

# =========================================================================
# EXTRACCIÓN DE DATOS Y MAPEO DINÁMICO
# =========================================================================
@st.cache_data(ttl=30)
def load_json():
    if os.path.exists(INTELLIGENCE_FILE):
        with open(INTELLIGENCE_FILE, "r") as f:
            return json.load(f)
    return None

@st.cache_data(ttl=30)
def load_live_csv():
    if os.path.exists(LIVE_DATA_FILE):
        return pd.read_csv(LIVE_DATA_FILE)
    return pd.DataFrame()

def get_datalake_files():
    if os.path.exists(DATA_LAKE_DIR):
        return [f for f in os.listdir(DATA_LAKE_DIR) if f.endswith(".csv")]
    return []

@st.cache_data(ttl=3600)
def build_engine_to_asset_map():
    mapping = {}
    if os.path.exists(DATA_LAKE_DIR):
        for file in os.listdir(DATA_LAKE_DIR):
            if file.endswith(".csv"):
                symbol = file.replace('_historical_clean.csv', '').replace('_clean.csv', '').upper()
                try:
                    df = pd.read_csv(os.path.join(DATA_LAKE_DIR, file), usecols=['Engine'])
                    for engine in df['Engine'].dropna().unique():
                        mapping[engine] = symbol
                except: pass
    return mapping

def resolve_symbol(engine_name, stats_dict, dynamic_map):
    for key in ['symbol', 'Symbol', 'asset', 'Asset']:
        if key in stats_dict and stats_dict[key]: return str(stats_dict[key]).upper()
    if engine_name in dynamic_map: return dynamic_map[engine_name]
    
    engine_clean = str(engine_name).strip().lower()
    if 'asia' in engine_clean or 'bullet' in engine_clean: return 'MCL'
    if 'gc' in engine_clean or 'gold' in engine_clean: return 'MGC'
    if 'mes' in engine_clean or 'spy' in engine_clean: return 'MES'
    return '⚠️ REVISAR'

# =========================================================================
# MICRO-ETL: EXTRACCIÓN DE INERCIA (ÚLTIMOS 5 TRADES)
# =========================================================================
def get_recent_sequence(engine, asset, df_live):
    seq = []
    
    # 1. Buscar primero en la sesión en vivo (Lo más reciente)
    if not df_live.empty and 'Engine' in df_live.columns:
        live_trades = df_live[(df_live['Engine'] == engine) & (df_live['Status'].astype(str).str.contains('CLOSED_'))]
        live_trades = live_trades.sort_values(by='Timestamp', ascending=False)
        for status in live_trades['Status'].head(5):
            seq.append('🟩' if 'WIN' in str(status) else '🟥')

    # 2. Rellenar con histórico si faltan trades para completar los 5
    if len(seq) < 5 and asset != '⚠️ REVISAR':
        hist_file = os.path.join(DATA_LAKE_DIR, f"{asset.lower()}_historical_clean.csv")
        if os.path.exists(hist_file):
            try:
                df_hist = pd.read_csv(hist_file, usecols=['Engine', 'Status'])
                hist_trades = df_hist[df_hist['Engine'] == engine]
                # Tomamos la cola (los más recientes del histórico) y los invertimos
                for status in hist_trades['Status'].tail(5 - len(seq)).iloc[::-1]:
                    seq.append('🟩' if 'WIN' in str(status) else '🟥')
            except: pass

    # 3. Rellenar con bloques vacíos si el motor es ultra nuevo
    while len(seq) < 5:
        seq.append('⬜')

    # Invertir la lista final para que se lea cronológicamente (Izquierda = Más Antiguo, Derecha = Último Trade)
    seq.reverse()
    return " ".join(seq)

data = load_json()
df_live = load_live_csv()
datalake_files = get_datalake_files()
dynamic_asset_map = build_engine_to_asset_map()

st.title("🛡️ OMNI-SWARM: Execution Management System")

# =========================================================================
# BARRA LATERAL
# =========================================================================
st.sidebar.header("Gobernanza del Sistema")
if st.sidebar.button("🔄 Forzar Recarga Completa (Limpiar Caché)"):
    st.cache_data.clear()
    st.rerun()

# =========================================================================
# NAVEGACIÓN PRINCIPAL
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
        
        enrichment_ratio = 0.0
        if 'Regime_Dist' in df_closed.columns:
            df_closed['Regime_Dist'] = df_closed['Regime_Dist'].replace(['None', 'nan', ''], pd.NA)
            enriched_count = df_closed['Regime_Dist'].notna().sum()
            enrichment_ratio = (enriched_count / total_trades * 100) if total_trades > 0 else 0.0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Trades Cerrados", f"{total_trades}")
        c2.metric("Win Rate Sesión", f"{wr_session:.1f}%")
        c3.metric("Resultado Crudo", f"{wins}W - {losses}L")
        
        if enrichment_ratio == 100:
            c4.metric("Salud de Datos (ETL)", f"{enrichment_ratio:.0f}%", "Óptimo")
        else:
            c4.metric("Salud de Datos (ETL)", f"{enrichment_ratio:.0f}%", "-Faltan Datos", delta_color="inverse")
        
        st.subheader("Bitácora de Ejecución (Enriquecida)")
        
        def color_status(val):
            if 'WIN' in str(val): return 'color: #00cc96; font-weight: bold;'
            if 'LOSS' in str(val): return 'color: #ff4b4b; font-weight: bold;'
            return ''
            
        column_order = [c for c in df_filtered.columns if c not in ['Regime_Dist', 'Session_Range', 'Session_Volume']]
        macro_cols = [c for c in ['Regime_Dist', 'Session_Range', 'Session_Volume'] if c in df_filtered.columns]
        
        if 'Status' in column_order:
            idx = column_order.index('Status') + 1
            final_order = column_order[:idx] + macro_cols + column_order[idx:]
        else:
            final_order = column_order + macro_cols
            
        st.dataframe(df_filtered[final_order].style.map(color_status, subset=['Status']), use_container_width=True)

# -------------------------------------------------------------------------
# PESTAÑA 2: INTELIGENCIA Y EXCLUSIONES (MATRIZ EXPANDIDA)
# -------------------------------------------------------------------------
with tab2:
    if not data:
        st.error("No se encontró master_intelligence.json.")
    else:
        engines = data.get("Micro_Engines", {})
        df_list = []
        for engine, stats in engines.items():
            resolved_asset = resolve_symbol(engine, stats, dynamic_asset_map)
            
            # Variables Críticas
            n_trades = stats.get("n_trades", 0)
            wr = round(stats.get("win_rate", 0) * 100, 1)
            
            # Clasificación de Tiers Autónoma
            tier = stats.get("tier", None)
            if not tier:
                if wr >= 65.0 and n_trades >= 30:
                    tier = "Tier 1 (Core)"
                elif wr >= 65.0 and n_trades < 30:
                    tier = "Tier 2 (Incubadora)"
                else:
                    tier = "Tier 3 (Observación)"
            
            # Inercia Reciente
            recent_seq = get_recent_sequence(engine, resolved_asset, df_live)
            
            df_list.append({
                "Símbolo": resolved_asset, 
                "Motor Táctico": engine, 
                "Tier": tier,
                "Trades": n_trades,
                "WR (%)": wr,
                "Últimos 5": recent_seq,
                "Salud Actual": stats.get("pre_flight_status", "⚪ SIN DATOS")
            })
            
        df_overview = pd.DataFrame(df_list)
        
        st.header("🚨 Monitoreo de Pérdida de Ventaja (Decay System)")
        df_decay = df_overview[df_overview["Salud Actual"].astype(str).str.contains("CRÍTICO|ADVERTENCIA", na=False)]
        
        if not df_decay.empty:
            st.error(f"⚠️ ATENCIÓN: Se han detectado {len(df_decay)} motores operando fuera de sus parámetros estadísticos base.")
            st.dataframe(df_decay, use_container_width=True)
        else:
            st.success("✅ OPTIMAL STATUS: Todos los motores de la flota se encuentran estables o en rendimiento Alpha.")
        
        st.divider()
        
        st.header("🔍 Inspección Analítica por Motor")
        selected_engine = st.selectbox("Seleccionar Motor para ver su matriz de regímenes", df_overview["Motor Táctico"].tolist())
        
        if selected_engine:
            stats = engines[selected_engine]
            matrix = stats.get("conditional_matrix", {})
            if matrix:
                st.subheader(f"Desglose de Probabilidad Condicional: {selected_engine}")
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
            st.subheader("🌍 Panorama General de la Flota Activa")
            
            # Colorear condicionalmente la columna de Win Rate
            def color_wr(val):
                return 'color: #ff4b4b' if val < 65.0 else 'color: #00cc96'
                
            st.dataframe(df_overview.style.map(color_wr, subset=['WR (%)']), use_container_width=True)

# -------------------------------------------------------------------------
# PESTAÑA 3: DATA LAKE
# -------------------------------------------------------------------------
with tab3:
    st.header("🗄️ Explorador de Backtests (Data Lake)")
    if not datalake_files:
        st.warning("Esperando inicialización de archivos...")
    else:
        selected_file = st.selectbox("Seleccionar Activo / Dataset", datalake_files)
        if selected_file:
            file_path = os.path.join(DATA_LAKE_DIR, selected_file)
            df_hist = pd.read_csv(file_path)
            motores_disponibles = df_hist['Engine'].unique() if 'Engine' in df_hist.columns else []
            selected_hist_engine = st.selectbox("Filtrar por Motor Táctico", ["Todos"] + list(motores_disponibles))
            
            if selected_hist_engine != "Todos":
                df_hist = df_hist[df_hist['Engine'] == selected_hist_engine]
            
            st.subheader(f"Métricas Históricas: {selected_file.replace('_historical_clean.csv', '').upper()}")
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
