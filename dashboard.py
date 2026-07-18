# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="OmniSwarm Quant", layout="wide")

# =========================================================================
# CSS PARA ESTÉTICA Y CENTRADO ABSOLUTO
# =========================================================================
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 400; color: #E0E0E0;}
    
    /* Metrics general styling */
    .stMetric label { font-size: 0.85rem !important; color: #A0A0A0 !important; }
    .stMetric value { font-size: 1.5rem !important; }
    
    /* Buttons */
    div.stButton > button[kind="primary"] { background-color: #28a745; color: white; border: none; border-radius: 4px; font-weight: bold; }
    div.stButton > button[kind="primary"]:hover { background-color: #218838; }
    
    /* Minimalist Forecast Cards */
    .forecast-card {
        background-color: #1A1C23;
        border: 1px solid #2D303E;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        margin-bottom: 10px;
    }
    .fc-title { font-size: 1rem; color: #A0A0A0; font-weight: 600; margin-bottom: 5px; }
    .fc-data { font-size: 1.1rem; color: #E0E0E0; font-weight: 400; }
    .fc-highlight { color: #00C853; font-weight: 700; }
    
    .module-hud {
        background: linear-gradient(90deg, #1A1C23, #15161B);
        border-left: 4px solid #00C853;
        padding: 15px;
        border-radius: 6px;
        margin-bottom: 20px;
        color: #E0E0E0;
        font-size: 1.2rem;
        font-weight: 500;
    }

    /* Absolute HTML Table Centering & Styling */
    .table-container {
        width: 100%;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        margin-top: 10px;
        margin-bottom: 20px;
        border-radius: 8px;
    }
    .custom-table {
        border-collapse: collapse;
        width: 100%;
        min-width: 800px;
        margin: 0 auto;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 0.85rem;
        color: #E0E0E0;
        background-color: #1A1C23;
        border: 1px solid #2D303E;
    }
    .custom-table th {
        background-color: #262730;
        color: #FAFAFA;
        font-weight: 600;
        padding: 10px 12px;
        text-align: center !important;
        border-bottom: 1px solid #2D303E;
        white-space: nowrap;
    }
    .custom-table td {
        padding: 8px 12px;
        text-align: center !important;
        border-bottom: 1px solid #2D303E;
        white-space: nowrap;
    }
    .custom-table tr:hover {
        background-color: #2D303E;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# CONFIGURATION
# =========================================================================
VPS_PUBLIC_IP = "103.89.14.117"
VPS_WEBHOOK_URL = f"http://{VPS_PUBLIC_IP}:80/webhook"
NT8_WEBHOOK_URL = f"http://{VPS_PUBLIC_IP}:8080/webhook"
WEBHOOK_PASSPHRASE = "TradingLab_Quant_V15_Secret"

def get_file_path(filename):
    if os.path.exists(filename): return filename
    local_vps_path = os.path.join(r"C:\OmniSwarm_Brain\Data", filename)
    if os.path.exists(local_vps_path): return local_vps_path
    return filename

# =========================================================================
# DATA LOADING
# =========================================================================
@st.cache_data(ttl=30)
def load_data():
    df_master = pd.read_csv(get_file_path("master_ml_dataset.csv"), on_bad_lines='skip') if os.path.exists(get_file_path("master_ml_dataset.csv")) else pd.DataFrame()
    if not df_master.empty and 'Timestamp' in df_master.columns:
        df_master['Timestamp'] = pd.to_datetime(df_master['Timestamp'], errors='coerce')

    config = {}
    if os.path.exists(get_file_path("engines_config.json")):
        with open(get_file_path("engines_config.json"), "r") as f: config = json.load(f)

    risk_data = {}
    if os.path.exists(get_file_path("risk_profile.json")):
        with open(get_file_path("risk_profile.json"), "r", encoding="utf-8-sig") as f: risk_data = json.load(f)

    system_forecast = config.pop("_SYSTEM_FORECAST_", {})

    config_rows = []
    for k, d in config.items():
        if isinstance(d, dict) and 'engine_name' in d:
            config_rows.append({
                'Module': d.get('module', 'N/A'), 
                'Engine': d.get('engine_name', k), 
                'Bucket': d.get('bucket', 'B'), 
                'Target Regime': f"R{d.get('predicted_regime_evaluated', '?')}",
                'WR Target': d.get('wr_predicted_regime', 0.0),
                'WR Global': d.get('wr_global', 0.0),
                'TT Target': d.get('total_trades_in_regime', 0),
                'TT Global': d.get('total_trades_global', 0),
                'Diag': d.get('reason', ''),
                'WR R0': d.get('r0_wr', 0.0),
                'TT R0': d.get('r0_trades', 0),
                'WR R1': d.get('r1_wr', 0.0),
                'TT R1': d.get('r1_trades', 0),
                'WR R2': d.get('r2_wr', 0.0),
                'TT R2': d.get('r2_trades', 0)
            })
    
    return df_master, pd.DataFrame(config_rows), risk_data, system_forecast

df_master, df_config, risk_profile, system_forecast = load_data()

# =========================================================================
# UTILITIES
# =========================================================================
def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.1); color: #00C853; font-weight: bold;'
    if val == "B": return 'background-color: rgba(200, 170, 0, 0.06); color: #CCA700; font-weight: bold;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.1); color: #D50000; font-weight: bold;'
    return ''

def render_html_table(df, bucket_cols=None):
    if df.empty: return ""
    if bucket_cols is None: bucket_cols = []
    format_dict = {col: "{:.1f}%" for col in df.columns if 'WR' in col}
    styled = df.style.set_properties(**{'text-align': 'center'})
    for col in bucket_cols:
        if col in df.columns: styled = styled.map(highlight_buckets, subset=[col])
    styled = styled.format(format_dict)
    html = styled.hide(axis="index").to_html().replace('<table', '<table class="custom-table"')
    return f'<div class="table-container">{html}</div>'

def render_historical_metrics(df_c, df_m):
    if df_c.empty: return
    total_trades = df_c['TT Global'].sum() if 'TT Global' in df_c.columns else 0
    avg_wr = (df_c['WR Global'] * df_c['TT Global']).sum() / total_trades if total_trades > 0 else 0
    engines_count = len(df_c)
    wins = 0; losses = 0; max_l_streak = 0
    if df_m is not None and not df_m.empty and 'Is_Win' in df_m.columns:
        wins = len(df_m[df_m['Is_Win'] == 1]); losses = len(df_m[df_m['Is_Win'] == 0])
        df_asc = df_m.sort_values('Timestamp', ascending=True)
        curr = 0
        for val in df_asc['Is_Win']:
            if val == 0: curr += 1; max_l_streak = max(max_l_streak, curr)
            else: curr = 0
    else: wins = int((avg_wr / 100) * total_trades); losses = total_trades - wins
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Trades", total_trades)
    c2.metric("Global WR", f"{avg_wr:.1f}%")
    c3.metric("Net Wins", wins); c4.metric("Net Losses", losses)
    c5.metric("Max L-Streak", max_l_streak); c6.metric("Total Engines", engines_count)
    st.markdown("---")

# =========================================================================
# NAVIGATION
# =========================================================================
st.sidebar.title("OmniSwarm Quant")
nav_category = st.sidebar.radio("Navigation", ["HOME", "Risk Management", "Trade Log", "Modules"])
if st.sidebar.button("Refresh Data"): st.cache_data.clear(); st.rerun()

# =========================================================================
# HOME & MODULES
# =========================================================================
if nav_category == "HOME":
    st.title("System Overview")
    if system_forecast:
        st.markdown("### 🔮 Markov Predictive Forecast")
        cols = st.columns(len(system_forecast))
        for i, (mod, data) in enumerate(system_forecast.items()):
            with cols[i]:
                st.markdown(f'<div class="forecast-card"><div class="fc-title">[{mod}]</div><div class="fc-data">TARGET: <span class="fc-highlight">R{data.get("predicted_regime_tomorrow")}</span> | PROB: {data.get("probability")}%</div></div>', unsafe_allow_html=True)
    st.markdown("### 🌐 Global Historical Performance")
    render_historical_metrics(df_config, df_master[df_master['Engine'] != 'NO_TRADE'] if not df_master.empty else None)
    st.markdown("### 📊 The Global Matrix")
    df_home = df_config.sort_values(by='TT Global', ascending=False)
    cols_home = ['Module', 'Engine', 'TT Global', 'WR Global', 'Last 5', 'TT R0', 'WR R0', 'Bucket R0', 'TT R1', 'WR R1', 'Bucket R1', 'TT R2', 'WR R2', 'Bucket R2']
    st.markdown(render_html_table(df_home[cols_home], bucket_cols=['Bucket R0', 'Bucket R1', 'Bucket R2']), unsafe_allow_html=True)

# =========================================================================
# TRADE LOG
# =========================================================================
elif nav_category == "Trade Log":
    st.title("Trade Log")
    time_filter = st.radio("Timeframe", ["Last Session", "7 Days", "15 Days", "All-Time"], horizontal=True)
    if not df_master.empty:
        df_log = df_master[df_master['Engine'] != 'NO_TRADE'].copy()
        if time_filter == "Last Session":
            last_date = df_log['Timestamp'].dt.date.max()
            df_log = df_log[df_log['Timestamp'].dt.date == last_date]
        elif time_filter != "All-Time":
            days = {"7 Days": 7, "15 Days": 15}[time_filter]
            df_log = df_log[df_log['Timestamp'] >= (datetime.now() - timedelta(days=days))]
        
        df_log = df_log.sort_values('Timestamp', ascending=False)
        df_log['Result'] = df_log['Is_Win'].apply(lambda x: "WIN" if x == 1 else "LOSS")
        
        # Nueva columna Regime (asumiendo que viene del dataset)
        show_cols = ['Timestamp', 'Module', 'Engine', 'Regime', 'Action', 'Result']
        st.markdown(render_html_table(df_log[[c for c in show_cols if c in df_log.columns]]), unsafe_allow_html=True)
    else: st.error("Database is empty.")

elif nav_category == "Modules":
    st.title("Modules Dashboard")
    selected_module = st.selectbox("Select Target Module:", ["MCL", "MGC", "MES", "MNQ_DAY", "MNQ_NIGHT"])
    df_c_mod = df_config[df_config['Module'] == selected_module].copy()
    st.markdown(f"### 🌐 Performance: {selected_module}")
    render_historical_metrics(df_c_mod, df_master[(df_master['Module'] == selected_module) & (df_master['Engine'] != 'NO_TRADE')])
    
    t1, t2, t3 = st.tabs(["Global Matrix", "Next Session Plan", "Regime Breakdown"])
    with t1: st.markdown(render_html_table(df_c_mod.sort_values(by='TT Global', ascending=False), bucket_cols=['Bucket R0', 'Bucket R1', 'Bucket R2']), unsafe_allow_html=True)
    with t2: st.markdown(render_html_table(df_c_mod.sort_values(by=['Bucket', 'WR Target']), bucket_cols=['Bucket']), unsafe_allow_html=True)
    with t3:
        for r_id in [0, 1, 2]:
            st.markdown(f"#### Regime {r_id}")
            render_regime_metrics(df_c_mod, df_master[df_master['Module'] == selected_module], r_id)
            for b in ['A', 'B', 'C']:
                df_sub = df_c_mod[df_c_mod[f'Bucket R{r_id}'] == b]
                if not df_sub.empty:
                    st.markdown(f"**Bucket {b}**")
                    st.markdown(render_html_table(df_sub[[f'Engine', f'TT R{r_id}', f'WR R{r_id}']], bucket_cols=[f'Bucket R{r_id}']), unsafe_allow_html=True)
