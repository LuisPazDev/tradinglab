# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="OmniSwarm Quant", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 400; color: #E0E0E0;}
    .stMetric label { font-size: 0.85rem !important; color: #A0A0A0 !important; }
    .stMetric value { font-size: 1.5rem !important; }
    div.stButton > button[kind="primary"] { background-color: #28a745; color: white; border: none; border-radius: 4px; font-weight: bold; }
    div.stButton > button[kind="primary"]:hover { background-color: #218838; }
    div[data-testid="column"]:nth-of-type(2) [data-testid="stMetric"] { background: linear-gradient(135deg, rgba(0,200,83,0.15), transparent); border-radius: 8px; padding: 10px 15px; border-left: 3px solid #00C853; }
    div[data-testid="column"]:nth-of-type(3) [data-testid="stMetric"] { background: linear-gradient(135deg, rgba(200,170,0,0.06), transparent); border-radius: 8px; padding: 10px 15px; border-left: 3px solid #B38F00; }
    div[data-testid="column"]:nth-of-type(4) [data-testid="stMetric"] { background: linear-gradient(135deg, rgba(213,0,0,0.12), transparent); border-radius: 8px; padding: 10px 15px; border-left: 3px solid #D50000; }
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
                'WR (Target)': d.get('wr_predicted_regime', 0.0),
                'WR (Global)': d.get('wr_global', 0.0),
                'Trades (Target)': d.get('total_trades_in_regime', 0),
                'Trades (Global)': d.get('total_trades_global', 0),
                'Diag': d.get('reason', ''),
                'R0 WR': d.get('r0_wr', 0.0),
                'R0 Trades': d.get('r0_trades', 0),
                'R1 WR': d.get('r1_wr', 0.0),
                'R1 Trades': d.get('r1_trades', 0),
                'R2 WR': d.get('r2_wr', 0.0),
                'R2 Trades': d.get('r2_trades', 0)
            })
    
    return df_master, pd.DataFrame(config_rows), risk_data, system_forecast

df_master, df_config, risk_profile, system_forecast = load_data()

# =========================================================================
# UI COMPONENTS & RENDERING
# =========================================================================
def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.1); color: #00C853;'
    if val == "B": return 'background-color: rgba(200, 170, 0, 0.06); color: #CCA700;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.1); color: #D50000;'
    return ''

def classify_historical_bucket(row, r_id):
    """Dynamic Bucketing for Historical Terrains"""
    wr = row[f'R{r_id} WR']
    trades = row[f'R{r_id} Trades']
    if trades < 5: return "B" # Friction/New
    if wr >= 62.5: return "A" # Sniper
    return "C" # Toxic/Quarantine

def render_module_hud(module_name, forecast_dict):
    f_data = forecast_dict.get(module_name, {})
    if not f_data: return
    
    today_r = f_data.get('today_regime', '?')
    pred_r = f_data.get('predicted_regime_tomorrow', '?')
    prob = f_data.get('probability', 0)
    
    hist = f_data.get('historical_sessions', {})
    hist_r0 = hist.get('0', hist.get(0, 0))
    hist_r1 = hist.get('1', hist.get(1, 0))
    hist_r2 = hist.get('2', hist.get(2, 0))
    
    st.markdown("### 🧠 Module Intelligence Header")
    c1, c2, c3 = st.columns(3)
    c1.metric("Last Session", f"Regime {today_r}")
    c2.metric("Next Session Target", f"Regime {pred_r}", f"{prob}% Prob")
    c3.metric("Historical Distribution", f"{hist_r0} (R0) | {hist_r1} (R1) | {hist_r2} (R2)")
    st.markdown("---")

def render_global_table(df_c):
    """Wide table for Global Overview (Home & Module Tab 1)"""
    if df_c.empty: return
    df_display = df_c.copy()
    
    # Sort first
    df_display = df_display.sort_values(by=['Bucket', 'WR (Global)'], ascending=[True, False])
    
    # Select cols
    cols = ['Module', 'Engine', 'Bucket', 'WR (Global)', 'Trades (Global)', 'R0 WR', 'R0 Trades', 'R1 WR', 'R1 Trades', 'R2 WR', 'R2 Trades']
    valid_cols = [c for c in cols if c in df_display.columns]
    df_display = df_display[valid_cols]
    
    format_dict = {'WR (Global)': "{:.1f}%", 'R0 WR': "{:.1f}%", 'R1 WR': "{:.1f}%", 'R2 WR': "{:.1f}%"}
    styled = df_display.style.map(highlight_buckets, subset=['Bucket'] if 'Bucket' in df_display.columns else [])\
                             .format(format_dict)
    st.dataframe(styled, use_container_width=True, hide_index=True)

def render_lineup_table(df_c):
    """Action table for Next Session (Module Tab 2)"""
    if df_c.empty: return
    df_display = df_c.copy()
    
    df_display = df_display.sort_values(by=['Bucket', 'WR (Target)'], ascending=[True, False])
    cols = ['Module', 'Engine', 'Bucket', 'Target Regime', 'WR (Target)', 'Trades (Target)', 'Diag']
    valid_cols = [c for c in cols if c in df_display.columns]
    df_display = df_display[valid_cols]
    
    styled = df_display.style.map(highlight_buckets, subset=['Bucket'] if 'Bucket' in df_display.columns else [])\
                             .format({'WR (Target)': "{:.1f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

def render_regime_historical_table(df_c, regime_id):
    """Deep forensic table for specific regimes (Module Tabs 3,4,5)"""
    if df_c.empty: return
    df_display = df_c.copy()
    
    wr_col = f'R{regime_id} WR'
    trades_col = f'R{regime_id} Trades'
    
    df_display = df_display.sort_values(by=[wr_col], ascending=[False])
    cols = ['Module', 'Engine', 'Hist_Bucket', wr_col, trades_col, 'WR (Global)', 'Trades (Global)']
    valid_cols = [c for c in cols if c in df_display.columns]
    df_display = df_display[valid_cols]
    
    styled = df_display.style.map(highlight_buckets, subset=['Hist_Bucket'] if 'Hist_Bucket' in df_display.columns else [])\
                             .format({wr_col: "{:.1f}%", 'WR (Global)': "{:.1f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

# =========================================================================
# NAVIGATION & ROUTING
# =========================================================================
st.sidebar.title("OmniSwarm Quant")
st.sidebar.markdown("---")
nav_category = st.sidebar.radio("Navigation", ["HOME", "Risk Management", "Trade Log", "Modules"])
st.sidebar.markdown("---")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

if nav_category == "HOME":
    st.title("System Overview")
    status = risk_profile.get("account_status", "ACTIVE")
    if status in ["ACTIVE", "DEMO", "PASSED"]: st.success(f"System Online | Status: {status}")
    else: st.error(f"Execution Locked | Status: {status}")
    
    if system_forecast:
        st.markdown("### 🔮 Markov Predictive Forecast (Target For Tomorrow)")
        cols = st.columns(len(system_forecast))
        for i, (mod, data) in enumerate(system_forecast.items()):
            with cols[i]:
                prob = data.get("probability", 0)
                pred_r = data.get("predicted_regime_tomorrow", "?")
                delta_color = "normal" if prob > 50 else "off"
                st.metric(f"Module: {mod}", f"Regime {pred_r}", f"{prob}% Prob", delta_color=delta_color)
        st.markdown("---")
    
    st.markdown("### 🌐 Global Swarm Authorization (All Modules)")
    render_global_table(df_config)

elif nav_category == "Risk Management":
    st.title("Risk Management (Zero-Trust)")
    st.markdown("Live scan from NinjaTrader memory to assign rules to real account.")
    
    if "scanned_accounts" not in st.session_state: st.session_state.scanned_accounts = []
    if "active_account" not in st.session_state: st.session_state.active_account = risk_profile.get("account_name", "")

    st.markdown("### 1. Physical Connections Scanner")
    if st.button("🔍 SCAN BROKER (NT8)", use_container_width=True):
        payload = {"passphrase": WEBHOOK_PASSPHRASE, "command": "SCAN_ACCOUNTS"}
        try:
            res = requests.post(NT8_WEBHOOK_URL, json=payload, timeout=5)
            if res.status_code == 200:
                data = res.json()
                st.session_state.scanned_accounts = data.get("accounts", [])
                st.session_state.active_account = data.get("active_account", "")
                st.success("✅ NinjaTrader Server successfully interrogated.")
            else: st.error(f"❌ NT8 Rejected connection (Error {res.status_code}).")
        except Exception as e: st.error(f"❌ Connection to NT8 failed on port 8080. Error: {e}")

    if st.session_state.scanned_accounts:
        st.markdown("---")
        st.markdown("### 2. Account Selection & Telemetry")
        
        account_names = [acc["name"] for acc in st.session_state.scanned_accounts]
        default_index = account_names.index(st.session_state.active_account) if st.session_state.active_account in account_names else 0
        
        selected_acc_name = st.selectbox("Select Target Account:", account_names, index=default_index)
        acc_data = next((acc for acc in st.session_state.scanned_accounts if acc["name"] == selected_acc_name), None)
        
        if acc_data:
            st.info(f"📊 **Live Metrics for {selected_acc_name}**")
            colA, colB, colC, colD = st.columns(4)
            colA.metric("Net Liquidation", f"${acc_data['net_liq']:,.2f}")
            colB.metric("Cash Value", f"${acc_data['cash_value']:,.2f}")
            colC.metric("Realized PnL (Today)", f"${acc_data['pnl']:,.2f}")
            
            dd_val = acc_data['trailing_dd']
            if dd_val > 0: colD.metric("Drawdown Cushion (Max DD)", f"${dd_val:,.2f}")
            else: colD.metric("Drawdown Cushion", "N/A (Sim/No Limit)")

            st.markdown("---")
            st.markdown("### 3. Execution Parameters & Discipline")
            
            c_type, c_lim1, c_lim2 = st.columns([1, 1, 1])
            with c_type:
                acc_type = st.selectbox("Account Type", ["EVALUATION", "FUNDED", "DEMO"], index=0)
                eod_fallback = st.number_input("Math Drawdown (Fallback) - $", value=float(risk_profile.get("eod_drawdown_limit", 1500.0)), step=100.0)

            with c_lim1:
                base_risk = st.number_input("Base Risk per Trade (Bucket A) - $", value=float(risk_profile.get("base_risk_usd", 500.0)), step=50.0)
                max_contracts = st.number_input("Max Physical Contracts", value=int(risk_profile.get("max_contracts", 15)), step=1)
            
            with c_lim2:
                daily_cap = st.number_input("Daily Loss Cap - $", value=float(risk_profile.get("daily_cap_usd", 1250.0)), step=50.0)
                profit_target = st.number_input("Profit Target - $", value=float(risk_profile.get("profit_target", 1500.0)), step=100.0)
                
            st.write("")
            if st.button("🚀 PUSH TO VPS & SET ACTIVE ACCOUNT", type="primary", use_container_width=True):
                payload_gateway = {
                    "passphrase": WEBHOOK_PASSPHRASE,
                    "event": "UPDATE_RISK",
                    "target_account": selected_acc_name, 
                    "risk_data": {
                        "account_status": "ACTIVE", 
                        "account_type": acc_type,
                        "account_name": selected_acc_name, 
                        "account_size": acc_data['net_liq'], 
                        "profit_target": profit_target,
                        "eod_drawdown_limit": eod_fallback,
                        "daily_cap_usd": daily_cap,
                        "base_risk_usd": base_risk,
                        "max_contracts": max_contracts
                    }
                }
                try:
                    res = requests.post(VPS_WEBHOOK_URL, json=payload_gateway, timeout=5)
                    if res.status_code == 200: 
                        st.success(f"✅ Shield Active! NinjaTrader will execute orders on **{selected_acc_name}**.")
                        st.session_state.active_account = selected_acc_name
                    else: st.error(f"❌ Gateway rejected configuration (Error {res.status_code}).")
                except Exception as e: st.error(f"❌ Connection failed. Check IP/Firewall. Error: {e}")

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
    df_c_mod = df_config[df_config['Module'] == selected_module].copy()
    
    # Render HUD
    render_module_hud(selected_module, system_forecast)
    
    # TABS
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🌐 Global Overview", 
        "🚀 Next Session Line-up", 
        "📊 Regime 0 Historical", 
        "📊 Regime 1 Historical", 
        "📊 Regime 2 Historical"
    ])
    
    with tab1:
        render_global_table(df_c_mod)
        
    with tab2:
        pred_regime = system_forecast.get(selected_module, {}).get("predicted_regime_tomorrow", "?")
        st.info(f"🚀 Execution logic and buckets strictly optimized for predicted **Regime {pred_regime}**")
        render_lineup_table(df_c_mod)
        
    with tab3:
        st.markdown("### Regime 0 Forensic Analysis")
        if not df_c_mod.empty:
            df_c_mod['Hist_Bucket'] = df_c_mod.apply(lambda r: classify_historical_bucket(r, 0), axis=1)
            t3_a, t3_b, t3_c = st.tabs(["Bucket A (Snipers)", "Bucket B (Friction/New)", "Bucket C (Quarantine)"])
            with t3_a: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'A'], 0)
            with t3_b: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'B'], 0)
            with t3_c: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'C'], 0)
            
    with tab4:
        st.markdown("### Regime 1 Forensic Analysis")
        if not df_c_mod.empty:
            df_c_mod['Hist_Bucket'] = df_c_mod.apply(lambda r: classify_historical_bucket(r, 1), axis=1)
            t4_a, t4_b, t4_c = st.tabs(["Bucket A (Snipers)", "Bucket B (Friction/New)", "Bucket C (Quarantine)"])
            with t4_a: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'A'], 1)
            with t4_b: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'B'], 1)
            with t4_c: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'C'], 1)
            
    with tab5:
        st.markdown("### Regime 2 Forensic Analysis")
        if not df_c_mod.empty:
            df_c_mod['Hist_Bucket'] = df_c_mod.apply(lambda r: classify_historical_bucket(r, 2), axis=1)
            t5_a, t5_b, t5_c = st.tabs(["Bucket A (Snipers)", "Bucket B (Friction/New)", "Bucket C (Quarantine)"])
            with t5_a: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'A'], 2)
            with t5_b: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'B'], 2)
            with t5_c: render_regime_historical_table(df_c_mod[df_c_mod['Hist_Bucket'] == 'C'], 2)