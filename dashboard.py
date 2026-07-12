# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="OmniSwarm Quant", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 400; color: #E0E0E0;}
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
# UI COMPONENTS
# =========================================================================
def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.1); color: #00C853;'
    if val == "B": return 'background-color: rgba(255, 214, 0, 0.1); color: #FFD600;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.1); color: #D50000;'
    return ''

def render_top_row(df_c):
    if df_c.empty: return
    total_trades = df_c['Trades'].sum()
    avg_wr = (df_c['Win Rate'] * df_c['Trades']).sum() / total_trades if total_trades > 0 else 0
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Trades", total_trades)
    c2.metric("Win Rate", f"{avg_wr:.1f}%")
    c3.metric("Active Engines", len(df_c))
    c4.metric("Bucket A", len(df_c[df_c['Bucket'] == 'A']))
    c5.metric("Bucket B", len(df_c[df_c['Bucket'] == 'B']))
    c6.metric("Bucket C", len(df_c[df_c['Bucket'] == 'C']))
    st.markdown("---")

# =========================================================================
# NAVIGATION & RENDER
# =========================================================================
st.sidebar.title("OmniSwarm Quant")
nav_category = st.sidebar.radio("Navigation", ["HOME", "Risk Management", "Trade Log", "Buckets Breakdown"])

if nav_category == "HOME":
    st.title("System Overview")
    render_top_row(df_config)
    
    # Tabla de Motores
    cols = ['Module', 'Engine', 'Bucket', 'Win Rate', 'Trades', 'Last 5', 'Diag']
    df_display = df_config[cols].sort_values(by='Trades', ascending=False)
    styled = df_display.style.map(highlight_buckets, subset=['Bucket']).format({'Win Rate': "{:.1f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

elif nav_category == "Risk Management":
    st.title("Risk Management")
    with st.form("risk_form"):
        col1, col2 = st.columns(2)
        with col1:
            acc_name = st.text_input("Account Number", value=risk_profile.get("account_name", "PA-01"))
            acc_status = st.selectbox("Status", ["ACTIVE", "DEMO", "PAUSED"], index=["ACTIVE", "DEMO", "PAUSED"].index(risk_profile.get("account_status", "ACTIVE")))
            # NUEVO: Riesgo Base y Límite de Contratos
            base_risk = st.number_input("Base Risk Bucket A ($)", value=float(risk_profile.get("base_risk_usd", 500.0)), step=50.0)
            max_contracts = st.number_input("Max Contracts Limit", value=int(risk_profile.get("max_contracts", 15)), step=1)
        with col2:
            acc_size = st.number_input("Global Target", value=float(risk_profile.get("account_size", 25000.0)), step=1000.0)
            daily_cap = st.number_input("Daily Cap", value=float(risk_profile.get("daily_cap_usd", 500.0)), step=50.0)
            eod_dd = st.number_input("Max EOD Drawdown", value=float(risk_profile.get("eod_drawdown_limit", 1000.0)), step=100.0)
        
        if st.form_submit_button("SEND", type="primary"):
            payload = {
                "passphrase": WEBHOOK_PASSPHRASE,
                "event": "UPDATE_RISK",
                "risk_data": {
                    "account_name": acc_name, 
                    "account_status": acc_status, 
                    "account_size": acc_size,
                    "eod_drawdown_limit": eod_dd, 
                    "daily_cap_usd": daily_cap,
                    "base_risk_usd": base_risk,
                    "max_contracts": max_contracts
                }
            }
            try:
                res = requests.post(VPS_WEBHOOK_URL, json=payload, timeout=5)
                st.success("Configuración enviada al servidor.")
            except Exception as e:
                st.error(f"Error de conexión: {e}")