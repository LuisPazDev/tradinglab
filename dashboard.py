# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

st.set_page_config(page_title="OmniSwarm Quant", layout="wide", page_icon="🧬")

# =========================================================================
# RUTAS HÍBRIDAS (NUBE VS LOCAL)
# =========================================================================
def get_file_path(filename):
    # 1. Si está en la misma carpeta (GitHub / Streamlit Cloud)
    if os.path.exists(filename): return filename
    # 2. Si está en el VPS de Windows
    local_vps_path = os.path.join(r"C:\OmniSwarm_Brain\Data", filename)
    if os.path.exists(local_vps_path): return local_vps_path
    return filename

MASTER_FILE = get_file_path("master_ml_dataset.csv")
CONFIG_FILE = get_file_path("engines_config.json")
RISK_FILE = get_file_path("risk_profile.json")

# =========================================================================
# CARGA DE DATOS
# =========================================================================
@st.cache_data(ttl=60)
def load_data():
    df_master = pd.DataFrame()
    config = {}
    kill_switch = False
    risk_status = "ACTIVE"

    if os.path.exists(RISK_FILE):
        try:
            with open(RISK_FILE, "r", encoding="utf-8-sig") as f:
                risk_data = json.load(f)
                risk_status = risk_data.get("account_status", "ACTIVE")
                if risk_status not in ["ACTIVE", "DEMO"]: kill_switch = True
        except: pass

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f: config = json.load(f)
        except: pass

    if os.path.exists(MASTER_FILE):
        try:
            df_master = pd.read_csv(MASTER_FILE, on_bad_lines='skip')
            if 'Timestamp' in df_master.columns:
                df_master['Timestamp'] = pd.to_datetime(df_master['Timestamp'], errors='coerce')
        except: pass

    config_rows = []
    for unique_key, data in config.items():
        row = {
            'Módulo': data.get('module', 'N/A'),
            'Motor': data.get('engine_name', unique_key),
            'Últimos_5': data.get('last_5', 'N/A'),
            'Bucket': data.get('bucket', 'B'),
            'WR_Global': data.get('wr', 0.0),
            'Trades': data.get('trades', 0),
            'R0': data.get('regimes_breakdown', {}).get('R0', 'N/A'),
            'R1': data.get('regimes_breakdown', {}).get('R1', 'N/A'),
            'R2': data.get('regimes_breakdown', {}).get('R2', 'N/A'),
            'Diag': data.get('reason', '')
        }
        config_rows.append(row)
    
    return df_master, pd.DataFrame(config_rows), kill_switch, risk_status

df_master, df_config, kill_switch_active, current_risk_status = load_data()

# =========================================================================
# VISTAS Y GRÁFICOS (Mismo código de interfaz que ya tienes)
# =========================================================================
def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.2); color: #00C853; font-weight: bold;'
    if val == "B": return 'background-color: rgba(255, 214, 0, 0.2); color: #FFD600; font-weight: bold;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.2); color: #D50000; font-weight: bold;'
    return ''

def plot_cumulative_hits(df, title):
    if df.empty: return None
    df_trades = df[df['Engine'] != 'NO_TRADE'].copy()
    if df_trades.empty: return None
    df_trades = df_trades.sort_values('Timestamp')
    df_trades['Hit_Score'] = df_trades['Is_Win'].apply(lambda x: 1 if x == 1 else -1)
    df_trades['Cumulative_Hits'] = df_trades['Hit_Score'].cumsum()
    fig = px.line(df_trades, x='Timestamp', y='Cumulative_Hits', title=title, color_discrete_sequence=['#00E676'])
    return fig

def render_top_metrics(df_c, title):
    st.markdown(f"### 📊 Rendimiento: {title}")
    if df_c.empty: return st.warning("No hay datos disponibles.")
    total_trades = df_c['Trades'].sum()
    avg_wr = (df_c['WR_Global'] * df_c['Trades']).sum() / total_trades if total_trades > 0 else 0
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Trades", f"{total_trades}")
    col2.metric("WinRate Promedio", f"{avg_wr:.1f}%")
    col3.metric("🟢 BUCKET A", f"{len(df_c[df_c['Bucket']=='A'])}")
    col4.metric("🟡 BUCKET B", f"{len(df_c[df_c['Bucket']=='B'])}")
    col5.metric("🔴 BUCKET C", f"{len(df_c[df_c['Bucket']=='C'])}")

def render_engine_table(df_c):
    if df_c.empty: return
    display_cols = ['Módulo', 'Motor', 'Últimos_5', 'Bucket', 'WR_Global', 'Trades', 'R0', 'R1', 'R2', 'Diag']
    df_display = df_c[display_cols].sort_values(by=['Bucket', 'WR_Global'], ascending=[True, False])
    st.dataframe(df_display.style.map(highlight_buckets, subset=['Bucket']).format({'WR_Global': "{:.1f}%"}), use_container_width=True)

st.sidebar.title("OmniSwarm V6.5")
selected_view = st.sidebar.radio("Navegación", ["🏠 HOME", "🗂️ Buckets", "🌤️ Regímenes", "📅 Bitácora"])

st.title("🧬 Ecosistema Cuantitativo")
if kill_switch_active: st.error(f"🚨 EJECUCIÓN FÍSICA BLOQUEADA. Estatus: [{current_risk_status}]")
else: st.success(f"✅ SISTEMA ARMADO. Riesgo: [{current_risk_status}]")

if selected_view == "🏠 HOME":
    render_top_metrics(df_config, "SISTEMA COMPLETO")
    fig = plot_cumulative_hits(df_master, "Curva de Efectividad Global")
    if fig: st.plotly_chart(fig, use_container_width=True)
    render_engine_table(df_config)

elif selected_view == "🗂️ Buckets":
    b_choice = st.radio("Filtro:", ["A", "B", "C"], horizontal=True)
    df_b = df_config[df_config['Bucket'] == b_choice]
    render_top_metrics(df_b, f"Bucket {b_choice}")
    render_engine_table(df_b)

elif selected_view == "🌤️ Regímenes":
    r_choice = st.radio("Régimen:", ["R0", "R1", "R2"], horizontal=True)
    df_r = df_config[df_config[r_choice] != 'N/A']
    render_engine_table(df_r)

elif selected_view == "📅 Bitácora":
    if not df_master.empty:
        df_log = df_master[df_master['Engine'] != 'NO_TRADE'].sort_values('Timestamp', ascending=False)
        st.dataframe(df_log[['Timestamp', 'Module', 'Engine', 'Action', 'Is_Win', 'Macro_Rng_Ratio', 'Macro_VIX']], use_container_width=True)