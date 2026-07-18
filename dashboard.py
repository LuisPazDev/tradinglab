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
    
    /* Global Metrics Styling */
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

    /* Force Table Centering in Streamlit HTML */
    div[data-testid="stDataFrame"] table {
        margin: 0 auto;
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
# DATA LOADING & PRE-PROCESSING
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
# UTILITIES & STRICT FORMATTING
# =========================================================================
def get_historical_bucket(trades, wr):
    """Calculates Bucket dynamically for historical regimes"""
    if trades < 5: return "B"
    if wr >= 62.5: return "A"
    return "C"

def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.1); color: #00C853; font-weight: bold;'
    if val == "B": return 'background-color: rgba(200, 170, 0, 0.06); color: #CCA700; font-weight: bold;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.1); color: #D50000; font-weight: bold;'
    return ''

def style_dataframe(df, bucket_cols=None):
    """Applies strict absolute centering to headers and cells, plus coloring"""
    if bucket_cols is None: bucket_cols = []
    format_dict = {col: "{:.1f}%" for col in df.columns if 'WR' in col}
    
    # Pandas Styler rules for absolute centering
    styles = [
        dict(selector="th", props=[("text-align", "center")]),
        dict(selector="td", props=[("text-align", "center")])
    ]
    
    styled = df.style.set_properties(**{'text-align': 'center'}) \
                     .set_table_styles(styles) \
                     .format(format_dict)
    
    for col in bucket_cols:
        if col in df.columns:
            styled = styled.map(highlight_buckets, subset=[col])
    return styled

def get_last_5_string(engine_name, df_m):
    if df_m is None or df_m.empty: return "N/A"
    trades = df_m[df_m['Engine'] == engine_name].sort_values('Timestamp')
    if trades.empty: return "N/A"
    last_5 = trades.tail(5)['Is_Win'].tolist()
    return " - ".join(["W" if x == 1 else "L" for x in last_5])

# Inject Last 5 and Historical Buckets into df_config
if not df_config.empty:
    df_m_valid = df_master[df_master['Engine'] != 'NO_TRADE'] if not df_master.empty else None
    df_config['Last 5'] = df_config['Engine'].apply(lambda e: get_last_5_string(e, df_m_valid))
    df_config['Bucket R0'] = df_config.apply(lambda r: get_historical_bucket(r['TT R0'], r['WR R0']), axis=1)
    df_config['Bucket R1'] = df_config.apply(lambda r: get_historical_bucket(r['TT R1'], r['WR R1']), axis=1)
    df_config['Bucket R2'] = df_config.apply(lambda r: get_historical_bucket(r['TT R2'], r['WR R2']), axis=1)

def render_historical_metrics(df_c, df_m):
    """Renders the top 5 historical metrics"""
    if df_c.empty: return
    total_trades = df_c['TT Global'].sum()
    avg_wr = (df_c['WR Global'] * df_c['TT Global']).sum() / total_trades if total_trades > 0 else 0
    
    wins = 0; losses = 0; max_l_streak = 0
    if df_m is not None and not df_m.empty and 'Is_Win' in df_m.columns:
        wins = len(df_m[df_m['Is_Win'] == 1])
        losses = len(df_m[df_m['Is_Win'] == 0])
        df_asc = df_m.sort_values('Timestamp', ascending=True)
        curr_streak = 0
        for val in df_asc['Is_Win']:
            if val == 0:
                curr_streak += 1
                max_l_streak = max(max_l_streak, curr_streak)
            else: curr_streak = 0
            
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Trades", total_trades)
    c2.metric("Global WR", f"{avg_wr:.1f}%")
    c3.metric("Net Wins", wins)
    c4.metric("Net Losses", losses)
    c5.metric("Max L-Streak", max_l_streak)
    st.markdown("---")

# =========================================================================
# NAVIGATION
# =========================================================================
st.sidebar.title("OmniSwarm Quant")
st.sidebar.markdown("---")
nav_category = st.sidebar.radio("Navigation", ["HOME", "Risk Management", "Trade Log", "Modules"])
st.sidebar.markdown("---")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# =========================================================================
# VIEW: HOME
# =========================================================================
if nav_category == "HOME":
    st.title("System Overview")
    status = risk_profile.get("account_status", "ACTIVE")
    if status in ["ACTIVE", "DEMO", "PASSED"]: st.success(f"System Online | Status: {status}")
    else: st.error(f"Execution Locked | Status: {status}")
    
    # --- BLOCK 1: Markov Predictive Forecast ---
    if system_forecast:
        st.markdown("### 🔮 Markov Predictive Forecast")
        cols = st.columns(len(system_forecast))
        for i, (mod, data) in enumerate(system_forecast.items()):
            pred_r = data.get("predicted_regime_tomorrow", "?")
            prob = data.get("probability", 0)
            with cols[i]:
                st.markdown(f"""
                <div class="forecast-card">
                    <div class="fc-title">[ {mod} ]</div>
                    <div class="fc-data">TARGET: <span class="fc-highlight">R{pred_r}</span> | PROB: {prob}%</div>
                </div>
                """, unsafe_allow_html=True)
        st.write("")
    
    # --- BLOCK 2: Global Historical Performance ---
    st.markdown("### 🌐 Global Historical Performance")
    if not df_config.empty:
        df_m_valid = df_master[df_master['Engine'] != 'NO_TRADE'] if not df_master.empty else None
        render_historical_metrics(df_config, df_m_valid)
        
        # --- BLOCK 3: The Global Matrix ---
        st.markdown("### 📊 The Global Matrix")
        df_home = df_config.copy()
        df_home = df_home.sort_values(by='TT Global', ascending=False)
        
        cols_home = [
            'Module', 'Engine', 'TT Global', 'WR Global', 'Last 5', 
            'TT R0', 'WR R0', 'Bucket R0', 
            'TT R1', 'WR R1', 'Bucket R1', 
            'TT R2', 'WR R2', 'Bucket R2'
        ]
        df_home = df_home[cols_home]
        
        styled_home = style_dataframe(df_home, bucket_cols=['Bucket R0', 'Bucket R1', 'Bucket R2'])
        st.dataframe(styled_home, use_container_width=True, hide_index=True)
    else:
        st.warning("No global data available.")

# =========================================================================
# VIEW: RISK MANAGEMENT (Zero-Trust)
# =========================================================================
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
        except Exception as e: st.error(f"❌ Connection to NT8 failed on port 8080. Check IP/Firewall. Error: {e}")

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

# =========================================================================
# VIEW: TRADE LOG
# =========================================================================
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
            
            show_cols = ['Timestamp', 'Module', 'Engine', 'Action', 'Result']
            df_log_display = df_log[[c for c in show_cols if c in df_log.columns]]
            styled_log = style_dataframe(df_log_display)
            st.dataframe(styled_log, use_container_width=True, hide_index=True)
        else: st.warning("No data found for the selected timeframe.")
    else: st.error("Database is empty.")

# =========================================================================
# VIEW: MODULES
# =========================================================================
elif nav_category == "Modules":
    st.title("Modules Dashboard")
    
    # --- BLOCK 1: Module Selector ---
    selected_module = st.selectbox("Select Target Module:", ["MCL", "MGC", "MES", "MNQ_DAY", "MNQ_NIGHT"])
    df_c_mod = df_config[df_config['Module'] == selected_module].copy()
    
    # --- BLOCK 2: Module Intelligence Header (HUD) ---
    f_data = system_forecast.get(selected_module, {})
    if f_data:
        pred_r = f_data.get('predicted_regime_tomorrow', '?')
        prob = f_data.get('probability', 0)
        st.markdown(f"""
        <div class="module-hud">
            [ NEXT SESSION FORECAST ] &nbsp;&nbsp;🎯 TARGET: <span style='color: #00C853; font-weight: 700;'>R{pred_r}</span> &nbsp;&nbsp;|&nbsp;&nbsp; PROB: {prob}%
        </div>
        """, unsafe_allow_html=True)
        
    # --- BLOCK 3: Module Historical Performance ---
    st.markdown(f"### 🌐 Historical Performance: {selected_module}")
    df_m_mod = df_master[(df_master['Module'] == selected_module) & (df_master['Engine'] != 'NO_TRADE')] if not df_master.empty else None
    render_historical_metrics(df_c_mod, df_m_mod)
    
    # --- BLOCK 4: The Analytical Tabs ---
    tab1, tab2, tab3 = st.tabs(["🌐 Global Matrix", "🚀 Next Session Line-up", "📊 Regime Breakdown"])
    
    # TAB 1: Global Matrix (Specific to this Module)
    with tab1:
        st.markdown(f"### The Global Matrix ({selected_module})")
        if not df_c_mod.empty:
            df_t1 = df_c_mod.copy()
            df_t1 = df_t1.sort_values(by='TT Global', ascending=False)
            
            cols_t1 = [
                'Engine', 'TT Global', 'WR Global', 'Last 5', 
                'TT R0', 'WR R0', 'Bucket R0', 
                'TT R1', 'WR R1', 'Bucket R1', 
                'TT R2', 'WR R2', 'Bucket R2'
            ]
            df_t1 = df_t1[cols_t1]
            
            styled_t1 = style_dataframe(df_t1, bucket_cols=['Bucket R0', 'Bucket R1', 'Bucket R2'])
            st.dataframe(styled_t1, use_container_width=True, hide_index=True)
    
    # TAB 2: Next Session Line-up
    with tab2:
        st.markdown("### Execution Plan (Target Regime Only)")
        if not df_c_mod.empty:
            df_t2 = df_c_mod.copy()
            df_t2['Bucket_Rank'] = df_t2['Bucket'].map({'A': 1, 'B': 2, 'C': 3})
            df_t2 = df_t2.sort_values(by=['Bucket_Rank', 'WR Target'], ascending=[True, False])
            
            cols_t2 = ['Engine', 'Bucket', 'TT Target', 'WR Target', 'TT Global', 'WR Global', 'Diag']
            df_t2 = df_t2[cols_t2]
            
            styled_t2 = style_dataframe(df_t2, bucket_cols=['Bucket'])
            st.dataframe(styled_t2, use_container_width=True, hide_index=True)
            
    # TAB 3: Regime Breakdown (Forensic Lab)
    with tab3:
        st.markdown("### Forensic Multi-Regime Analysis")
        t_r0, t_r1, t_r2 = st.tabs(["[ Regime 0 ]", "[ Regime 1 ]", "[ Regime 2 ]"])
        
        def render_sub_bucket_table(df_regime, regime_id, bucket_label, title):
            df_sub = df_regime[df_regime[f'Bucket R{regime_id}'] == bucket_label]
            if not df_sub.empty:
                st.markdown(f"#### {title}")
                cols_sub = ['Engine', f'Bucket R{regime_id}', f'TT R{regime_id}', f'WR R{regime_id}', 'TT Global', 'WR Global']
                df_sub = df_sub[cols_sub].sort_values(by=f'WR R{regime_id}', ascending=False)
                styled_sub = style_dataframe(df_sub, bucket_cols=[f'Bucket R{regime_id}'])
                st.dataframe(styled_sub, use_container_width=True, hide_index=True)
        
        with t_r0:
            render_sub_bucket_table(df_c_mod, 0, 'A', "🎯 Bucket A (Snipers)")
            render_sub_bucket_table(df_c_mod, 0, 'B', "⚠️ Bucket B (Friction/New)")
            render_sub_bucket_table(df_c_mod, 0, 'C', "🚫 Bucket C (Quarantine)")
            
        with t_r1:
            render_sub_bucket_table(df_c_mod, 1, 'A', "🎯 Bucket A (Snipers)")
            render_sub_bucket_table(df_c_mod, 1, 'B', "⚠️ Bucket B (Friction/New)")
            render_sub_bucket_table(df_c_mod, 1, 'C', "🚫 Bucket C (Quarantine)")
            
        with t_r2:
            render_sub_bucket_table(df_c_mod, 2, 'A', "🎯 Bucket A (Snipers)")
            render_sub_bucket_table(df_c_mod, 2, 'B', "⚠️ Bucket B (Friction/New)")
            render_sub_bucket_table(df_c_mod, 2, 'C', "🚫 Bucket C (Quarantine)")
