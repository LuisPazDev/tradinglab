# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="TradingLab Quant", layout="wide", page_icon="🧬")

# =========================================================================
# 1. CONFIGURACIÓN E INFRAESTRUCTURA
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
# 2. MOTOR DE EXTRACCIÓN (CACHÉ)
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

    config_rows = [{'Módulo': d.get('module', 'N/A'), 'Motor': d.get('engine_name', k), 'Bucket': d.get('bucket', 'B'), 'WR_Global': d.get('wr', 0.0), 'Trades': d.get('trades', 0)} for k, d in config.items()]
    return df_master, pd.DataFrame(config_rows), risk_data

df_master, df_config, risk_profile = load_data()

# =========================================================================
# 3. INTERFAZ Y RUTEO (MENÚ LATERAL)
# =========================================================================
st.sidebar.image("https://img.icons8.com/color/96/000000/artificial-intelligence.png", width=60)
st.sidebar.title("Quant Lab V15")
st.sidebar.markdown("---")

menu_options = [
    "🏠 HOME (Global)", 
    "⚙️ Gestión de Riesgo", 
    "📅 Bitácora Temporal",
    "---",
    "🔬 Módulo: MCL", 
    "🔬 Módulo: MGC", 
    "🔬 Módulo: MES", 
    "🔬 Módulo: MNQ_DAY", 
    "🔬 Módulo: MNQ_NIGHT"
]

selected_view = st.sidebar.radio("Navegación del Sistema", menu_options)
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Sincronizar Datos"):
    st.cache_data.clear()
    st.rerun()

# =========================================================================
# 4. VISTA: GESTIÓN DE RIESGO (COMUNICACIÓN CON VPS)
# =========================================================================
if selected_view == "⚙️ Gestión de Riesgo":
    st.title("⚙️ Sala de Mandos Institucional")
    st.markdown("Los parámetros guardados aquí se envían instantáneamente al VPS de Windows para gobernar las próximas ejecuciones.")
    
    with st.form("risk_form"):
        col1, col2 = st.columns(2)
        with col1:
            acc_name = st.text_input("Nombre de Cuenta", value=risk_profile.get("account_name", "Apex-01"))
            acc_status = st.selectbox("Estado del Sistema", ["ACTIVE", "DEMO", "PAUSED"], index=["ACTIVE", "DEMO", "PAUSED"].index(risk_profile.get("account_status", "ACTIVE")))
            acc_size = st.number_input("Capital Global (Account Size)", value=float(risk_profile.get("account_size", 25000.0)), step=1000.0)
        
        with col2:
            start_bal = st.number_input("Balance Inicial de Hoy", value=float(risk_profile.get("start_of_day_balance", 25000.0)), step=500.0)
            eod_dd = st.number_input("Drawdown Máximo Diario (EOD limit)", value=float(risk_profile.get("eod_drawdown_limit", 1000.0)), step=100.0)
            daily_cap = st.number_input("Daily Cap (Meta Diaria en USD)", value=float(risk_profile.get("daily_cap_usd", 500.0)), step=50.0)
        
        submitted = st.form_submit_button("🛡️ Transmitir al Servidor (VPS)")
        
        if submitted:
            payload = {
                "passphrase": WEBHOOK_PASSPHRASE,
                "event": "UPDATE_RISK",
                "risk_data": {
                    "account_name": acc_name, "account_status": acc_status, "account_size": acc_size,
                    "start_of_day_balance": start_bal, "eod_drawdown_limit": eod_dd, "daily_cap_usd": daily_cap
                }
            }
            try:
                res = requests.post(VPS_WEBHOOK_URL, json=payload, timeout=5)
                if res.status_code == 200: st.success("✅ ¡Orden recibida por el Cerebro en el VPS! Ver Telegram.")
                else: st.error(f"❌ El VPS rechazó la conexión: {res.status_code}")
            except Exception as e:
                st.error(f"❌ No se pudo conectar al VPS en {VPS_PUBLIC_IP}. Error: {e}")

# =========================================================================
# 5. VISTA: BITÁCORA Y FILTROS TEMPORALES
# =========================================================================
elif selected_view == "📅 Bitácora Temporal":
    st.title("📅 Explorador del Data Lake")
    
    time_filter = st.radio("Filtro de Tiempo:", ["Hoy (1D)", "7 Días", "15 Días", "1 Mes", "90 Días", "180 Días", "1 Año", "Histórico"], horizontal=True)
    
    if not df_master.empty:
        df_log = df_master[df_master['Engine'] != 'NO_TRADE'].copy()
        
        if time_filter != "Histórico":
            days_map = {"Hoy (1D)": 1, "7 Días": 7, "15 Días": 15, "1 Mes": 30, "90 Días": 90, "180 Días": 180, "1 Año": 365}
            cutoff_date = datetime.now() - timedelta(days=days_map[time_filter])
            df_log = df_log[df_log['Timestamp'] >= cutoff_date]
            
        df_log = df_log.sort_values('Timestamp', ascending=False)
        
        if not df_log.empty:
            df_log['Resultado'] = df_log['Is_Win'].apply(lambda x: "🟢 WIN" if x == 1 else "🔴 LOSS")
            wins = len(df_log[df_log['Is_Win'] == 1])
            total = len(df_log)
            wr = (wins / total) * 100 if total > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric(f"Trades ({time_filter})", total)
            col2.metric("WinRate", f"{wr:.1f}%")
            col3.metric("Aciertos Netos", wins)
            
            show_cols = ['Timestamp', 'Module', 'Engine', 'Action', 'Resultado', 'Trade_Exact_PnL', 'Macro_Rng_Ratio']
            st.dataframe(df_log[[c for c in show_cols if c in df_log.columns]], use_container_width=True, hide_index=True)
        else: st.warning(f"No hay operaciones en el periodo: {time_filter}")
    else: st.error("No hay base de datos disponible.")

# =========================================================================
# 6. VISTAS: MÓDULOS INDIVIDUALES
# =========================================================================
elif selected_view.startswith("🔬 Módulo:"):
    mod = selected_view.split(": ")[1]
    st.title(f"🔬 Radiografía Aislada: {mod}")
    
    df_mod = df_master[df_master['Module'] == mod] if not df_master.empty else pd.DataFrame()
    df_c_mod = df_config[df_config['Módulo'] == mod] if not df_config.empty else pd.DataFrame()
    
    if not df_c_mod.empty:
        total_trades = df_c_mod['Trades'].sum()
        avg_wr = (df_c_mod['WR_Global'] * df_c_mod['Trades']).sum() / total_trades if total_trades > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Motores Operativos", len(df_c_mod))
        col2.metric("WinRate Promedio", f"{avg_wr:.1f}%")
        col3.metric("🟢 Bucket A (Aprobados)", len(df_c_mod[df_c_mod['Bucket'] == 'A']))
        col4.metric("🔴 Bucket C (Cuarentena)", len(df_c_mod[df_c_mod['Bucket'] == 'C']))
        
        st.dataframe(df_c_mod.sort_values(by=['Bucket', 'WR_Global'], ascending=[True, False]), use_container_width=True, hide_index=True)
    else:
        st.info(f"Aún no hay motores configurados en el JSON para el módulo {mod}.")

# =========================================================================
# 7. VISTA: HOME (GLOBAL)
# =========================================================================
elif selected_view == "🏠 HOME (Global)":
    st.title("🧬 Ecosistema Cuantitativo V15")
    status = risk_profile.get("account_status", "ACTIVE")
    if status in ["ACTIVE", "DEMO"]: st.success(f"✅ Hot-Path en Línea. Riesgo: [{status}]")
    else: st.error(f"🚨 EJECUCIÓN BLOQUEADA. Estatus de Cuenta: [{status}]")
    
    if not df_config.empty:
        st.markdown("### Radiografía Maestra (Todos los Motores)")
        st.dataframe(df_config.sort_values(by=['Bucket', 'WR_Global'], ascending=[True, False]), use_container_width=True, hide_index=True)