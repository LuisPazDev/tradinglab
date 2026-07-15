# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="OmniSwarm Quant", layout="wide")

# Custom CSS for Minimalist Modern Design, Green SEND Button & Bucket Gradients
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 400; color: #E0E0E0;}
    
    /* Metrics general styling */
    .stMetric label { font-size: 0.85rem !important; color: #A0A0A0 !important; }
    .stMetric value { font-size: 1.5rem !important; }
    
    /* Primary SEND Button */
    div.stButton > button[kind="primary"] {
        background-color: #28a745;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: bold;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #218838;
    }
    
    /* Glassmorphism Gradients for Buckets */
    div[data-testid="column"]:nth-of-type(2) [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(0,200,83,0.15), transparent);
        border-radius: 8px; padding: 10px 15px; border-left: 3px solid #00C853;
    }
    div[data-testid="column"]:nth-of-type(3) [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(200,170,0,0.06), transparent);
        border-radius: 8px; padding: 10px 15px; border-left: 3px solid #B38F00;
    }
    div[data-testid="column"]:nth-of-type(4) [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(213,0,0,0.12), transparent);
        border-radius: 8px; padding: 10px 15px; border-left: 3px solid #D50000;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# CONFIGURATION & INFRASTRUCTURE
# =========================================================================
VPS_PUBLIC_IP = "127.0.0.1" # Como corre en el VPS, local host es la vía más rápida y segura.
VPS_WEBHOOK_URL = f"http://{VPS_PUBLIC_IP}:80/webhook/"
NT8_WEBHOOK_URL = f"http://{VPS_PUBLIC_IP}:8080/webhook/"
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
    if val == "B": return 'background-color: rgba(200, 170, 0, 0.06); color: #CCA700;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.1); color: #D50000;'
    return ''

def render_top_row(df_c, df_m=None):
    if df_c.empty:
        st.warning("No data available.")
        return

    total_trades = df_c['Trades'].sum()
    avg_wr = (df_c['Win Rate'] * df_c['Trades']).sum() / total_trades if total_trades > 0 else 0
    engines_count = len(df_c)
    b_a = len(df_c[df_c['Bucket'] == 'A'])
    b_b = len(df_c[df_c['Bucket'] == 'B'])
    b_c = len(df_c[df_c['Bucket'] == 'C'])
    
    wins = 0
    losses = 0
    max_l_streak = 0
    
    if df_m is not None and not df_m.empty and 'Is_Win' in df_m.columns:
        wins = len(df_m[df_m['Is_Win'] == 1])
        losses = len(df_m[df_m['Is_Win'] == 0])
        df_asc = df_m.sort_values('Timestamp', ascending=True)
        curr_streak = 0
        for val in df_asc['Is_Win']:
            if val == 0:
                curr_streak += 1
                max_l_streak = max(max_l_streak, curr_streak)
            else:
                curr_streak = 0
    else:
        wins = int((avg_wr / 100) * total_trades)
        losses = total_trades - wins

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Trades", total_trades)
    c2.metric("Win Rate", f"{avg_wr:.1f}%")
    c3.metric("Net Wins", wins)
    c4.metric("Net Losses", losses)
    c5.metric("Max L-Streak", max_l_streak)
    
    st.write("") 
    swarm_health = (b_a / engines_count * 100) if engines_count > 0 else 0
    
    c6, c7, c8, c9, c10 = st.columns(5)
    c6.metric("Active Engines", engines_count)
    c7.metric("Bucket A", b_a)
    c8.metric("Bucket B", b_b)
    c9.metric("Bucket C", b_c)
    c10.metric("Swarm Health", f"{swarm_health:.1f}%")
    st.markdown("---")

def render_engine_table(df_c, exclude_cols=None):
    if df_c.empty: return
    df_display = df_c.copy()
    
    def format_diag(row):
        if row['Bucket'] == 'A': return "ÓPTIMO"
        elif row['Bucket'] == 'B':
            if row['Trades'] < 20: return f"({row['Trades']}/20)"
            else: return "FRICCIÓN"
        elif row['Bucket'] == 'C': return "CUARENTENA"
        return str(row.get('Diag', ''))
        
    if 'Diag' in df_display.columns:
        df_display['Diag'] = df_display.apply(format_diag, axis=1)

    if 'Last 5' in df_display.columns:
        df_display['Last 5'] = df_display['Last 5'].apply(lambda x: " - ".join(list(str(x))) if pd.notna(x) and x != 'N/A' else x)
        
    cols = ['Module', 'Engine', 'Bucket', 'Win Rate', 'Trades', 'Last 5', 'R0', 'R1', 'R2', 'Diag']
    if exclude_cols: cols = [c for c in cols if c not in exclude_cols]
        
    df_display = df_display[cols].sort_values(by='Trades', ascending=False)
    styled = df_display.style.map(highlight_buckets, subset=['Bucket'] if 'Bucket' in df_display.columns else []).format({'Win Rate': "{:.1f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

# =========================================================================
# NAVIGATION (SIDEBAR)
# =========================================================================
st.sidebar.title("OmniSwarm Quant")
st.sidebar.markdown("---")

nav_category = st.sidebar.radio("Navigation", ["HOME", "Risk Management", "Trade Log", "Modules"])

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
    if status in ["ACTIVE", "DEMO", "PASSED"]: st.success(f"System Online | Status: {status}")
    else: st.error(f"Execution Locked | Status: {status}")
    
    df_m_valid = df_master[df_master['Engine'] != 'NO_TRADE'] if not df_master.empty else None
    render_top_row(df_config, df_m_valid)
    render_engine_table(df_config)

# -------------------------------------------------------------------------
# NUEVA VISTA ZERO-TRUST: RISK MANAGEMENT
# -------------------------------------------------------------------------
elif nav_category == "Risk Management":
    st.title("Risk Management (Zero-Trust)")
    st.markdown("Consulta en vivo la memoria de NinjaTrader para asignar reglas a la cuenta real.")
    
    # Manejo de estado en RAM para no perder los datos al clickear botones
    if "scanned_accounts" not in st.session_state:
        st.session_state.scanned_accounts = []
    if "active_account" not in st.session_state:
        st.session_state.active_account = risk_profile.get("account_name", "")

    st.markdown("### 1. Escáner de Conexiones Físicas")
    if st.button("🔍 ESCANEAR BROKER (NT8)", use_container_width=True):
        payload = {"passphrase": WEBHOOK_PASSPHRASE, "command": "SCAN_ACCOUNTS"}
        try:
            res = requests.post(NT8_WEBHOOK_URL, json=payload, timeout=5)
            if res.status_code == 200:
                data = res.json()
                st.session_state.scanned_accounts = data.get("accounts", [])
                st.session_state.active_account = data.get("active_account", "")
                st.success("✅ Servidor NinjaTrader interrogado exitosamente.")
            else:
                st.error(f"❌ NT8 rechazó la conexión (Error {res.status_code}).")
        except Exception as e:
            st.error(f"❌ Falló la conexión con NT8 en el puerto 8080. Verifique que OmniSwarmWebhook esté activo. Error: {e}")

    if st.session_state.scanned_accounts:
        st.markdown("---")
        st.markdown("### 2. Selección de Cuenta y Radiografía")
        
        # Generar lista de cuentas encontradas
        account_names = [acc["name"] for acc in st.session_state.scanned_accounts]
        default_index = account_names.index(st.session_state.active_account) if st.session_state.active_account in account_names else 0
        
        selected_acc_name = st.selectbox("Selecciona la cuenta que deseas operar:", account_names, index=default_index)
        acc_data = next((acc for acc in st.session_state.scanned_accounts if acc["name"] == selected_acc_name), None)
        
        if acc_data:
            st.info(f"📊 **Métricas extraídas directamente del servidor para {selected_acc_name}**")
            colA, colB, colC, colD = st.columns(4)
            colA.metric("Net Liquidation", f"${acc_data['net_liq']:,.2f}")
            colB.metric("Cash Value", f"${acc_data['cash_value']:,.2f}")
            colC.metric("PnL Realizado (Hoy)", f"${acc_data['pnl']:,.2f}")
            
            dd_val = acc_data['trailing_dd']
            if dd_val > 0:
                colD.metric("Colchón de Vida (Max DD)", f"${dd_val:,.2f}")
            else:
                colD.metric("Colchón de Vida", "N/A (Sim/Sin Límite)")

            st.markdown("---")
            st.markdown("### 3. Parámetros de Ejecución y Disciplina")
            st.markdown("Estos límites le dictarán a NinjaTrader cuándo colocar el candado por protección.")
            
            c_lim1, c_lim2 = st.columns(2)
            with c_lim1:
                base_risk = st.number_input("Riesgo Base por Trade (Bucket A) - $", value=float(risk_profile.get("base_risk_usd", 500.0)), step=50.0)
                max_contracts = st.number_input("Límite Máximo de Contratos Físicos", value=int(risk_profile.get("max_contracts", 15)), step=1)
            with c_lim2:
                daily_cap = st.number_input("Daily Loss Cap (Bloqueo por Pérdida) - $", value=float(risk_profile.get("daily_cap_usd", 1250.0)), step=50.0)
                profit_target = st.number_input("Profit Target (Bloqueo por Meta) - $", value=float(risk_profile.get("profit_target", 1500.0)), step=100.0)
                
            st.write("")
            if st.button("🚀 ENVIAR AL VPS Y ESTABLECER COMO CUENTA ACTIVA", type="primary", use_container_width=True):
                # El gateway en Python reescribe el risk_profile.json e invoca el HotSwap en C#
                payload_gateway = {
                    "passphrase": WEBHOOK_PASSPHRASE,
                    "event": "UPDATE_RISK",
                    "target_account": selected_acc_name, # Clave: Esto dispara el cambio en NT8
                    "risk_data": {
                        "account_status": "ACTIVE", # Auto-desbloqueo 
                        "account_type": "EVALUATION" if "LTE" in selected_acc_name else "DEMO",
                        "account_name": selected_acc_name, 
                        "account_size": acc_data['net_liq'], # Referencial
                        "profit_target": profit_target,
                        "eod_drawdown_limit": 0.0, # Obsoleto, C# ya usa el del broker, se envía por retrocompatibilidad
                        "daily_cap_usd": daily_cap,
                        "base_risk_usd": base_risk,
                        "max_contracts": max_contracts
                    }
                }
                try:
                    res = requests.post(VPS_WEBHOOK_URL, json=payload_gateway, timeout=5)
                    if res.status_code == 200: 
                        st.success(f"✅ ¡Blindaje Activo! NinjaTrader ahora ejecutará órdenes físicamente en **{selected_acc_name}**.")
                        st.session_state.active_account = selected_acc_name
                    else: 
                        st.error(f"❌ El Gateway de Python rechazó la configuración (Error {res.status_code}).")
                except Exception as e:
                    st.error(f"❌ Falló la conexión con la base de datos (Puerto 80). Error: {e}")

# -------------------------------------------------------------------------
# TRADE LOG Y MODULES QUEDAN INTACTOS
# -------------------------------------------------------------------------
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
            losses = len(df_log[df_log['Is_Win'] == 0])
            total = len(df_log)
            wr = (wins / total) * 100 if total > 0 else 0
            df_asc = df_log.sort_values('Timestamp', ascending=True)
            max_l_streak, curr_streak = 0, 0
            for val in df_asc['Is_Win']:
                if val == 0:
                    curr_streak += 1
                    max_l_streak = max(max_l_streak, curr_streak)
                else: curr_streak = 0
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Trades", total)
            col2.metric("Win Rate", f"{wr:.1f}%")
            col3.metric("Net Wins", wins)
            col4.metric("Net Losses", losses)
            col5.metric("Max L-Streak", max_l_streak)
            show_cols = ['Timestamp', 'Module', 'Engine', 'Action', 'Result']
            st.dataframe(df_log[[c for c in show_cols if c in df_log.columns]], use_container_width=True, hide_index=True)
        else: st.warning("No data found for the selected timeframe.")
    else: st.error("Database is empty.")

elif nav_category == "Modules":
    st.title("Modules Dashboard")
    selected_module = st.selectbox("Select Target Module", ["MCL", "MGC", "MES", "MNQ_DAY", "MNQ_NIGHT"])
    df_c_mod = df_config[df_config['Module'] == selected_module]
    df_m_mod = df_master[(df_master['Module'] == selected_module) & (df_master['Engine'] != 'NO_TRADE')] if not df_master.empty else None
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview (All)", "Buckets Breakdown", "R0 (Low Volatility)", "R1 (Normal)", "R2 (High Volatility)"])
    with tab1:
        render_top_row(df_c_mod, df_m_mod)
        render_engine_table(df_c_mod)
    with tab2:
        b_choice = st.radio("Filter Bucket", ["A", "B", "C"], horizontal=True)
        df_c_b = df_c_mod[df_c_mod['Bucket'] == b_choice]
        df_m_b = df_m_mod[df_m_mod['Engine'].isin(df_c_b['Engine'].tolist())] if df_m_mod is not None else None
        render_top_row(df_c_b, df_m_b)
        render_engine_table(df_c_b, exclude_cols=['Bucket'])
    with tab3:
        df_r0 = df_c_mod[df_c_mod['R0'] != 'N/A']
        render_top_row(df_r0, None)
        render_engine_table(df_r0, exclude_cols=['R1', 'R2'])
    with tab4:
        df_r1 = df_c_mod[df_c_mod['R1'] != 'N/A']
        render_top_row(df_r1, None)
        render_engine_table(df_r1, exclude_cols=['R0', 'R2'])
    with tab5:
        df_r2 = df_c_mod[df_c_mod['R2'] != 'N/A']
        render_top_row(df_r2, None)
        render_engine_table(df_r2, exclude_cols=['R0', 'R1'])
