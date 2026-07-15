# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import requests
import re
from datetime import datetime, timedelta

# =========================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y RUTAS
# =========================================================================
st.set_page_config(page_title="TradingLab Quant", layout="wide", page_icon="🧬")

# Custom CSS for Modern Design & Green SEND Button
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 400; color: #E0E0E0;}
    
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
    </style>
""", unsafe_allow_html=True)

# ----------------- CREDENCIALES DEL VPS -----------------
VPS_PUBLIC_IP = "103.89.14.117" 
VPS_WEBHOOK_URL = f"http://{VPS_PUBLIC_IP}:80/webhook"
WEBHOOK_PASSPHRASE = "TradingLab_Quant_V15_Secret"

def get_file_path(filename):
    if os.path.exists(filename): return filename
    local_path = os.path.join(os.path.expanduser("~/mysite/"), filename)
    if os.path.exists(local_path): return local_path
    return filename

MASTER_FILE = get_file_path("master_ml_dataset.csv")
CONFIG_FILE = get_file_path("engines_config.json")
TRADE_FILE = get_file_path("trade_history.csv")
RISK_FILE = get_file_path("risk_profile.json")

# =========================================================================
# 2. CARGA DEL DATASET MAESTRO (CACHÉ EN RAM)
# =========================================================================
@st.cache_data(ttl=60)
def load_data():
    df_master = pd.DataFrame()
    config = {}
    risk_data = {}
    kill_switch = False

    if os.path.exists(MASTER_FILE):
        try:
            df_master = pd.read_csv(MASTER_FILE, on_bad_lines='skip')
            if 'Timestamp' in df_master.columns:
                df_master['Timestamp'] = pd.to_datetime(df_master['Timestamp'], errors='coerce')
        except: pass

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f: config = json.load(f)
        except: pass
        
    if os.path.exists(RISK_FILE):
        try:
            with open(RISK_FILE, "r", encoding="utf-8-sig") as f: risk_data = json.load(f)
        except: pass

    if os.path.exists(TRADE_FILE):
        try:
            df_t = pd.read_csv(TRADE_FILE, on_bad_lines='skip')
            if not df_t.empty and 'Status' in df_t.columns and "REJECTED_ACCOUNT_INACTIVE" in str(df_t.iloc[-1].get('Status', '')):
                kill_switch = True
        except: pass

    # Convertir JSON a DataFrame una sola vez
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
            'Decay_Pts': data.get('execution_decay', 0.0),
            'Diag': data.get('reason', '')
        }
        config_rows.append(row)
    df_config = pd.DataFrame(config_rows)

    return df_master, df_config, risk_data, kill_switch

df_master, df_config, risk_profile, kill_switch_active = load_data()

# =========================================================================
# 3. FUNCIONES DE DISEÑO (ESTILOS Y GRÁFICAS BLINDADAS)
# =========================================================================
def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.2); color: #00C853; font-weight: bold;'
    if val == "B": return 'background-color: rgba(255, 214, 0, 0.2); color: #FFD600; font-weight: bold;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.2); color: #D50000; font-weight: bold;'
    return ''

def plot_cumulative_hits(df, title):
    """Función de gráfica blindada para buscar Status o Is_Win"""
    if df.empty: return None
    df_closed = df.copy()

    # Si la base de datos trae la columna 'Status'
    if 'Status' in df_closed.columns:
        df_closed = df_closed[df_closed['Status'].astype(str).str.contains('WIN|LOSS|CLOSED', case=False, na=False)].copy()
        if df_closed.empty: return None
        df_closed['Hit_Score'] = df_closed['Status'].apply(lambda x: 1 if 'WIN' in str(x).upper() else (-1 if 'LOSS' in str(x).upper() else 0))
    
    # Si en cambio trae la columna numérica 'Is_Win' (Formato anterior)
    elif 'Is_Win' in df_closed.columns:
        df_closed = df_closed.dropna(subset=['Is_Win']).copy()
        if df_closed.empty: return None
        df_closed['Hit_Score'] = df_closed['Is_Win'].apply(lambda x: 1 if float(x) == 1.0 else -1)
    
    # Si no hay ninguna columna válida, abortamos la gráfica en lugar de romper la app
    else:
        return None

    df_closed = df_closed.sort_values('Timestamp')
    df_closed['Cumulative_Hits'] = df_closed['Hit_Score'].cumsum()

    fig = px.line(df_closed, x='Timestamp', y='Cumulative_Hits', title=title,
                  labels={'Cumulative_Hits': 'Balance de Aciertos Netos', 'Timestamp': 'Fecha'},
                  color_discrete_sequence=['#2962FF'])
    return fig

def render_top_metrics(df_c, title):
    st.markdown(f"### 📊 Rendimiento de Probabilidad Pura: {title}")
    if df_c.empty:
        st.warning("No hay datos disponibles.")
        return

    total_trades = df_c['Trades'].sum()
    avg_wr = (df_c['WR_Global'] * df_c['Trades']).sum() / total_trades if total_trades > 0 else 0
    total_motores = len(df_c)

    b_a = len(df_c[df_c['Bucket'] == 'A'])
    b_b = len(df_c[df_c['Bucket'] == 'B'])
    b_c = len(df_c[df_c['Bucket'] == 'C'])

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Trades", f"{total_trades}")
    col2.metric("WinRate Promedio", f"{avg_wr:.1f}%")
    col3.metric("Motores en Vista", f"{total_motores}")
    col4.metric("🟢 BUCKET A", f"{b_a}")
    col5.metric("🟡 BUCKET B", f"{b_b}")
    col6.metric("🔴 BUCKET C", f"{b_c}")
    st.markdown("---")

def render_engine_table(df_c):
    if df_c.empty: return
    display_cols = ['Módulo', 'Motor', 'Últimos_5', 'Bucket', 'WR_Global', 'Trades', 'R0', 'R1', 'R2', 'Decay_Pts', 'Diag']
    df_display = df_c[display_cols].sort_values(by=['Bucket', 'WR_Global'], ascending=[True, False])

    styled_config = df_display.style.map(highlight_buckets, subset=['Bucket'])\
                                    .format({'Decay_Pts': "{:.2f}", 'WR_Global': "{:.1f}%"})

    st.dataframe(styled_config, use_container_width=True, height=600)

# =========================================================================
# 4. RUTEO DE VISTAS (MENÚ LATERAL)
# =========================================================================
st.sidebar.image("https://img.icons8.com/color/96/000000/artificial-intelligence.png", width=60)
st.sidebar.title("Quant Lab V15")
st.sidebar.markdown("---")

menu_options = [
    "🏠 HOME (Visión Global)",
    "⚙️ Risk Management (Vía B)",
    "🗂️ Visión por Buckets",
    "🌤️ Visión por Regímenes",
    "🔬 Módulo: MCL",
    "🔬 Módulo: MGC",
    "🔬 Módulo: MES",
    "🔬 Módulo: MNQ_DAY",
    "🔬 Módulo: MNQ_NIGHT",
    "📅 Bitácora Cronológica"
]
selected_view = st.sidebar.radio("Navegación del Sistema", menu_options)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Forzar Recarga"):
    st.cache_data.clear()
    st.rerun()

# =========================================================================
# 5. CABECERA GLOBAL
# =========================================================================
st.title("🧬 Ecosistema Cuantitativo Institucional")
status = risk_profile.get("account_status", "ACTIVE")
if status in ["ACTIVE", "DEMO", "PASSED"] and not kill_switch_active: 
    st.success(f"✅ **SISTEMA EN LÍNEA:** Flujo de Vía A y Vía B operando con normalidad. Estado: {status}")
else: 
    st.error(f"🚨 **ALERTA DE INFRAESTRUCTURA:** Ejecución física bloqueada por Risk Management. Estado actual: {status}")

# =========================================================================
# 6. RENDERIZADO CONDICIONAL DE VISTAS
# =========================================================================

# ---> VISTA 1: HOME (VISIÓN GLOBAL)
if selected_view == "🏠 HOME (Visión Global)":
    render_top_metrics(df_config, "SISTEMA COMPLETO")

    fig = plot_cumulative_hits(df_master, "Curva de Efectividad Global (Todos los Módulos)")
    if fig: st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🔬 Radiografía Maestra (Todos los Motores)")
    render_engine_table(df_config)

# ---> VISTA 2: RISK MANAGEMENT
elif selected_view == "⚙️ Risk Management (Vía B)":
    st.markdown("### ⚙️ Risk Management (Gatekeeper)")
    st.markdown("Configura los parámetros de riesgo. Estos datos viajan en tiempo real al VPS para gobernar las decisiones de NT8.")
    
    with st.container():
        current_type = risk_profile.get("account_type", "DEMO").upper()
        acc_type = st.radio("Account Type", ["DEMO", "FUNDED", "EVALUATION"], index=["DEMO", "FUNDED", "EVALUATION"].index(current_type) if current_type in ["DEMO", "FUNDED", "EVALUATION"] else 0, horizontal=True)
        
        if acc_type == "DEMO":
            st.info("🟢 Modo Simulación: Todo el flujo se enruta a la cuenta Sim101. Límites de riesgo diarios desactivados.")
            acc_name = "Sim101"
            base_risk = float(risk_profile.get("base_risk_usd", 500.0))
            max_contracts = int(risk_profile.get("max_contracts", 15))
            acc_size = float(risk_profile.get("account_size", 25000.0))
            profit_target = 0.0
            daily_cap = float(risk_profile.get("daily_cap_usd", 500.0))
            eod_dd = float(risk_profile.get("eod_drawdown_limit", 1000.0))
            
        else:
            col1, col2 = st.columns(2)
            with col1:
                acc_name = st.text_input("Account Number", value=risk_profile.get("account_name", "LTE02571085060001"))
                acc_size = st.number_input("Account Size ($)", value=float(risk_profile.get("account_size", 25000.0)), step=1000.0)
                base_risk = st.number_input("Base Risk Bucket A ($)", value=float(risk_profile.get("base_risk_usd", 500.0)), step=50.0)
                max_contracts = st.number_input("Max Contracts Limit", value=int(risk_profile.get("max_contracts", 15)), step=1)
                
            with col2:
                profit_target = st.number_input("Profit Target ($)", value=float(risk_profile.get("profit_target", 1500.0)), step=100.0)
                daily_cap = st.number_input("Daily Cap ($)", value=float(risk_profile.get("daily_cap_usd", 1250.0)), step=50.0)
                eod_dd = st.number_input("Max EOD Drawdown ($)", value=float(risk_profile.get("eod_drawdown_limit", 1500.0)), step=100.0)
        
        st.write("")
        c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 2])
        with c_btn1:
            submitted = st.button("SEND TO VPS", type="primary", use_container_width=True)
        with c_btn2:
            force_sync = st.button("🔄 FORCE VPS SYNC", use_container_width=True)
            
        if submitted:
            payload = {
                "passphrase": WEBHOOK_PASSPHRASE,
                "event": "UPDATE_RISK",
                "risk_data": {
                    "account_type": acc_type,
                    "account_name": acc_name, 
                    "account_size": acc_size,
                    "profit_target": profit_target,
                    "eod_drawdown_limit": eod_dd, 
                    "daily_cap_usd": daily_cap,
                    "base_risk_usd": base_risk,
                    "max_contracts": max_contracts
                }
            }
            try:
                res = requests.post(VPS_WEBHOOK_URL, json=payload, timeout=5)
                if res.status_code == 200: st.success(f"✅ Éxito: Parámetros transmitidos correctamente al VPS ({VPS_PUBLIC_IP}).")
                else: st.error(f"❌ El Gateway del VPS rechazó la conexión (Error {res.status_code}).")
            except Exception as e:
                st.error(f"❌ Falla de red: No se pudo conectar al VPS. Verifique que el servicio Python esté activo. Error: {e}")
                
        if force_sync:
            payload = {"passphrase": WEBHOOK_PASSPHRASE, "command": "SYNC_BALANCE"}
            try:
                res = requests.post(VPS_WEBHOOK_URL, json=payload, timeout=5)
                if res.status_code == 200: st.success("✅ Comando de sincronización enviado directamente a NinjaTrader.")
                else: st.error(f"❌ NinjaTrader rechazó la conexión (Error {res.status_code}).")
            except Exception as e:
                st.error(f"❌ Falló el enlace de sincronización. Error: {e}")

# ---> VISTA 3: VISIÓN POR BUCKETS
elif selected_view == "🗂️ Visión por Buckets":
    st.markdown("### 🗂️ Radiografía por Buckets de Riesgo")

    bucket_map = {
        "🟢 BUCKET A (Full Riesgo)": "A",
        "🟡 BUCKET B (Limitados)": "B",
        "🔴 BUCKET C (Cuarentena)": "C"
    }
    bucket_choice = st.radio("Filtro de Riesgo Institucional:", list(bucket_map.keys()), horizontal=True)
    b_target = bucket_map[bucket_choice]

    df_bucket = df_config[df_config['Bucket'] == b_target].copy()

    if not df_bucket.empty:
        render_top_metrics(df_bucket, f"Aislamiento de Motores en Bucket {b_target}")
        st.markdown(f"#### 📋 Lista de Motores ({bucket_choice})")
        render_engine_table(df_bucket)
    else:
        st.info(f"No hay motores asignados actualmente al Bucket {b_target}.")

# ---> VISTA 4: VISIÓN POR REGÍMENES
elif selected_view == "🌤️ Visión por Regímenes":
    st.markdown("### 🌤️ Rendimiento Aislado por Clima Macroeconómico")

    regime_choice = st.radio("Selecciona el Régimen Macro:", ["R0", "R1", "R2"], horizontal=True)

    df_reg = df_config[df_config[regime_choice] != 'N/A'].copy()

    if not df_reg.empty:
        st.info(f"Mostrando **{len(df_reg)}** motores que tienen exposición histórica comprobada (5+ trades) en el Régimen **{regime_choice}**.")
        df_reg['Sort_Key'] = df_reg[regime_choice].str.extract(r'([\d\.]+)%').astype(float)
        display_cols = ['Módulo', 'Motor', regime_choice, 'Bucket', 'WR_Global', 'Trades', 'Últimos_5']
        df_display = df_reg.sort_values(by=['Sort_Key', 'Trades'], ascending=[False, False])[display_cols]
        styled_config = df_display.style.map(highlight_buckets, subset=['Bucket']).format({'WR_Global': "{:.1f}%"})
        st.dataframe(styled_config, use_container_width=True, height=600)
    else:
        st.warning(f"Ningún motor tiene suficientes datos recopilados en el Régimen {regime_choice}.")

# ---> VISTA 5: MÓDULOS ESPECÍFICOS
elif selected_view.startswith("🔬 Módulo:"):
    module_name = selected_view.split(": ")[1]

    df_master_mod = df_master[df_master['Module'] == module_name] if not df_master.empty else pd.DataFrame()
    df_config_mod = df_config[df_config['Módulo'] == module_name] if not df_config.empty else pd.DataFrame()

    render_top_metrics(df_config_mod, module_name)

    fig = plot_cumulative_hits(df_master_mod, f"Curva de Efectividad - {module_name}")
    if fig: st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"### 🔬 Radiografía Interna: {module_name}")
    render_engine_table(df_config_mod)

# ---> VISTA 6: BITÁCORA CRONOLÓGICA
elif selected_view == "📅 Bitácora Cronológica":
    st.markdown("### 📅 Explorador del Data Lake (Dataset Maestro)")
    st.markdown("Aquí se muestran todos los eventos capturados por la Vía A y el Backtest, ordenados cronológicamente.")

    if not df_master.empty:
        col_filtro, col_metric = st.columns([1, 2])

        with col_filtro:
            usar_filtro = st.checkbox("🔍 Filtrar por un día específico")
            if usar_filtro:
                filter_date = st.date_input("Selecciona la fecha:")
            else:
                filter_date = None

        df_log = df_master.copy()

        if filter_date is not None:
            df_log = df_log[df_log['Timestamp'].dt.date == filter_date]

        if not df_log.empty:
            with col_metric:
                if usar_filtro:
                    st.info(f"Mostrando **{len(df_log)}** registros para el {filter_date.strftime('%Y-%m-%d')}.")
                else:
                    st.info(f"Mostrando el historial completo: **{len(df_log)}** registros.")

            if 'Unified_Regime' in df_log.columns:
                df_log['Régimen'] = df_log['Unified_Regime'].apply(lambda x: f"R{int(x)}" if pd.notnull(x) else "N/A")
            else:
                df_log['Régimen'] = "N/A"

            df_log = df_log.sort_values('Timestamp', ascending=False)

            show_cols = ['Timestamp', 'Module', 'Engine', 'Action', 'Régimen', 'Status']
            show_cols = [c for c in show_cols if c in df_log.columns]
            if 'Trade_Exact_PnL' in df_log.columns:
                show_cols.append('Trade_Exact_PnL')

            st.dataframe(df_log[show_cols], use_container_width=True, hide_index=True, height=700)
        else:
            st.warning("No hay registros almacenados para esta fecha en específico.")
    else:
        st.error("El Dataset Maestro está vacío o no se pudo cargar.")
        st.info("💡 Solución: Haz clic en el botón '🔄 Forzar Recarga' en el menú de la izquierda.")
