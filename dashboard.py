# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="OmniSwarm Quant", layout="wide")

# Custom CSS for Minimalist Modern Design & Green SEND Button
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 400; color: #E0E0E0;}
    .stMetric label { font-size: 0.85rem !important; color: #A0A0A0 !important; }
    .stMetric value { font-size: 1.5rem !important; }
    /* Target the primary button to be standard green */
    div.stButton > button[kind="primary"] {
        background-color: #28a745;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: bold;
        width: 150px;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #218838;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# CONFIGURATION & INFRASTRUCTURE
# =========================================================================
VPS_PUBLIC_IP = "103.89.14.117" 
VPS_WEBHOOK_URL = f"http://{VPS_PUBLIC_IP}:80/webhook"
WEBHOOK_PASSPHRASE = "TradingLab_Quant_V15_Secret"

def get_file_path(filename):
    if os.path.exists(filename): return filename
    local_vps_path = os.path.join(r"C:\OmniSwarm_Brain\Data", filename)
    if os.path.exists(local_vps_path): return local_vps_path
    return filename

# =========================================================================
# DATA LOADING (CACHE)
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

    config_rows = [{
        'Module': d.get('module', 'N/A'), 
        'Engine': d.get('engine_name', k), 
        'Bucket': d.get('bucket', 'B'), 
        'Win Rate': d.get('wr', 0.0), 
        'Trades': d.get('trades', 0),
        'Last 5': d.get('last_5', 'N/A'),
        'R0': d.get('regimes_breakdown', {}).get('R0', 'N/A'),
        'R1': d.get('regimes_breakdown', {}).get('R1', 'N/A'),
        'R2': d.get('regimes_breakdown', {}).get('R2', 'N/A'),
        'Diag': d.get('reason', '')
    } for k, d in config.items()]
    
    return df_master, pd.DataFrame(config_rows), risk_data

df_master, df_config, risk_profile = load_data()

# =========================================================================
# REUSABLE UI COMPONENTS
# =========================================================================
def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.1); color: #00C853;'
    if val == "B": return 'background-color: rgba(255, 214, 0, 0.1); color: #FFD600;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.1); color: #D50000;'
    return ''

def render_top_row(df_c):
    if df_c.empty:
        st.warning("No data available.")
        return

    total_trades = df_c['Trades'].sum()
    avg_wr = (df_c['Win Rate'] * df_c['Trades']).sum() / total_trades if total_trades > 0 else 0
    engines_count = len(df_c)
    b_a = len(df_c[df_c['Bucket'] == 'A'])
    b_b = len(df_c[df_c['Bucket'] == 'B'])
    b_c = len(df_c[df_c['Bucket'] == 'C'])
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Trades", total_trades)
    c2.metric("Win Rate", f"{avg_wr:.1f}%")
    c3.metric("Active Engines", engines_count)
    c4.metric("Bucket A", b_a)
    c5.metric("Bucket B", b_b)
    c6.metric("Bucket C", b_c)
    st.markdown("---")

def render_engine_table(df_c):
    if df_c.empty: return
    cols = ['Module', 'Engine', 'Bucket', 'Win Rate', 'Trades', 'Last 5', 'R0', 'R1', 'R2', 'Diag']
    df_display = df_c[cols].sort_values(by='Trades', ascending=False)
    styled = df_display.style.map(highlight_buckets, subset=['Bucket']).format({'Win Rate': "{:.1f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

# =========================================================================
# NAVIGATION (SIDEBAR)
# =========================================================================
st.sidebar.title("OmniSwarm Quant")
st.sidebar.markdown("---")

nav_category = st.sidebar.radio("Navigation", [
    "HOME", 
    "Risk Management", 
    "Trade Log", 
    "Buckets Breakdown", 
    "Regimes Breakdown", 
    "Modules"
])

selected_module = None
if nav_category == "Modules":
    selected_module = st.sidebar.selectbox("Select Module", ["MCL", "MGC", "MES", "MNQ_DAY", "MNQ_NIGHT"])

st.sidebar.markdown("---")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# =========================================================================
# VIEWS RENDERING
# =========================================================================
if nav_category == "HOME":
    st.title("System Overview")
    status = risk_profile.get("account_status", "ACTIVE")
    if status in ["ACTIVE", "DEMO"]: 
        st.success(f"System Online | Status: {status}")
    else: 
        st.error(f"Execution Locked | Status: {status}")
    
    render_top_row(df_config)
    st.markdown("#### Global Engine Registry")
    render_engine_table(df_config)

elif nav_category == "Risk Management":
    st.title("Risk Management")
    st.markdown("Configure core risk parameters. Changes are transmitted directly to the execution server.")
    
    with st.form("risk_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            acc_name = st.text_input("Account Number", value=risk_profile.get("account_name", "PA-01"))
            acc_status = st.selectbox("Account Status", ["ACTIVE", "DEMO", "PAUSED"], index=["ACTIVE", "DEMO", "PAUSED"].index(risk_profile.get("account_status", "ACTIVE")))
        with col2:
            acc_size = st.number_input("Global Target", value=float(risk_profile.get("account_size", 25000.0)), step=1000.0)
            daily_cap = st.number_input("Daily Cap", value=float(risk_profile.get("daily_cap_usd", 500.0)), step=50.0)
            eod_dd = st.number_input("Max EOD Drawdown", value=float(risk_profile.get("eod_drawdown_limit", 1000.0)), step=100.0)
        
        submitted = st.form_submit_button("SEND", type="primary")
        
        if submitted:
            payload = {
                "passphrase": WEBHOOK_PASSPHRASE,
                "event": "UPDATE_RISK",
                "risk_data": {
                    "account_name": acc_name, 
                    "account_status": acc_status, 
                    "account_size": acc_size,
                    "eod_drawdown_limit": eod_dd, 
                    "daily_cap_usd": daily_cap
                }
            }
            try:
                res = requests.post(VPS_WEBHOOK_URL, json=payload, timeout=5)
                if res.status_code == 200: st.success("Parameters updated successfully.")
                else: st.error(f"Server rejected connection: {res.status_code}")
            except Exception as e:
                st.error(f"Connection failed to {VPS_PUBLIC_IP}. Error: {e}")

elif nav_category == "Trade Log":
    st.title("Trade Log")
    time_filter = st.radio("Timeframe", ["Today", "7 Days", "15 Days", "1 Month", "3 Months", "6 Months", "1 Year", "All-Time"], horizontal=True)
    
    if not df_master.empty:
        df_log = df_master[df_master['Engine'] != 'NO_TRADE'].copy()
        
        if time_filter != "All-Time":
            days_map = {"Today": 1, "7 Days": 7, "15 Days": 15, "1 Month": 30, "3 Months": 90, "6 Months": 180, "1 Year": 365}
            cutoff_date = datetime.now() - timedelta(days=days_map[time_filter])
            df_log = df_log[df_log['Timestamp'] >= cutoff_date]
            
        df_log = df_log.sort_values('Timestamp', ascending=False)
        
        if not df_log.empty:
            df_log['Result'] = df_log['Is_Win'].apply(lambda x: "WIN" if x == 1 else "LOSS")
            wins = len(df_log[df_log['Is_Win'] == 1])
            total = len(df_log)
            wr = (wins / total) * 100 if total > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Trades", total)
            col2.metric("Win Rate", f"{wr:.1f}%")
            col3.metric("Net Wins", wins)
            
            show_cols = ['Timestamp', 'Module', 'Engine', 'Action', 'Result', 'Trade_Exact_PnL', 'Macro_Rng_Ratio']
            st.dataframe(df_log[[c for c in show_cols if c in df_log.columns]], use_container_width=True, hide_index=True)
        else: st.warning("No data found for the selected timeframe.")
    else: st.error("Database is empty.")

elif nav_category == "Buckets Breakdown":
    st.title("Buckets Breakdown")
    b_choice = st.radio("Filter Bucket", ["A", "B", "C"], horizontal=True)
    df_b = df_config[df_config['Bucket'] == b_choice]
    render_top_row(df_b)
    render_engine_table(df_b)

elif nav_category == "Regimes Breakdown":
    st.title("Regimes Breakdown")
    r_choice = st.radio("Filter Regime", ["R0", "R1", "R2"], horizontal=True)
    df_r = df_config[df_config[r_choice] != 'N/A']
    render_top_row(df_r)
    render_engine_table(df_r)

elif nav_category == "Modules" and selected_module:
    st.title(f"Module: {selected_module}")
    df_c_mod = df_config[df_config['Module'] == selected_module]
    render_top_row(df_c_mod)
    st.markdown(f"#### {selected_module} Engines")
    render_engine_table(df_c_mod)