# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import time
import requests
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="OmniSwarm Quant", layout="wide")

# =========================================================================
# CSS PARA ESTÉTICA, CENTRADO ABSOLUTO Y RESPONSIVIDAD
# =========================================================================
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 400; color: #E0E0E0;}
    
    .stMetric label { font-size: 0.85rem !important; color: #A0A0A0 !important; }
    .stMetric value { font-size: 1.5rem !important; }
    
    div.stButton > button[kind="primary"] { background-color: #28a745; color: white; border: none; border-radius: 4px; font-weight: bold; }
    div.stButton > button[kind="primary"]:hover { background-color: #218838; }
    
    .forecast-card {
        background-color: #1A1C23; border: 1px solid #2D303E; border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 10px;
    }
    .fc-title { font-size: 1rem; color: #A0A0A0; font-weight: 600; margin-bottom: 5px; }
    .fc-data { font-size: 1.1rem; color: #E0E0E0; font-weight: 400; }
    .fc-highlight { color: #00C853; font-weight: 700; }
    .fc-dual { color: #CCA700; font-weight: 700; }
    
    .module-hud {
        background: linear-gradient(90deg, #1A1C23, #15161B); border-left: 4px solid #00C853; padding: 15px; border-radius: 6px; margin-bottom: 20px; color: #E0E0E0; font-size: 1.2rem; font-weight: 500;
    }
    .module-hud-dual { border-left-color: #CCA700; }

    .table-container { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin-top: 10px; margin-bottom: 20px; border-radius: 8px; }
    .custom-table { border-collapse: collapse; width: 100%; min-width: 800px; margin: 0 auto; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 0.85rem; color: #E0E0E0; background-color: #1A1C23; border: 1px solid #2D303E; }
    .custom-table th { background-color: #262730; color: #FAFAFA; font-weight: 600; padding: 10px 12px; text-align: center !important; border-bottom: 1px solid #2D303E; white-space: nowrap; }
    .custom-table td { padding: 8px 12px; text-align: center !important; border-bottom: 1px solid #2D303E; white-space: nowrap; }
    .custom-table tr:hover { background-color: #2D303E; }
    
    .macro-table .custom-table { min-width: 100%; }
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
# FILE SHIELDS (ANTI-COLLISION SYSTEM PARA STREAMLIT)
# =========================================================================
def safe_json_read(filepath, retries=5, delay=0.05):
    for _ in range(retries):
        try:
            if not os.path.exists(filepath): return {}
            with open(filepath, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except (IOError, PermissionError, json.JSONDecodeError):
            time.sleep(delay)
    return {}

def safe_json_write(filepath, data, retries=5, delay=0.05):
    for _ in range(retries):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except (IOError, PermissionError):
            time.sleep(delay)
    return False

risk_profile = safe_json_read(get_file_path("risk_profile.json"))

# =========================================================================
# DATA LOADING & PRE-PROCESSING 
# =========================================================================
@st.cache_data(ttl=30)
def load_data():
    modules = ['MCL', 'MGC', 'MES', 'MNQ_DAY', 'MNQ_NIGHT']
    df_list = []
    macro_dict = {} 
    
    for mod in modules:
        micro_path = get_file_path(f"{mod}_micro_trades.csv")
        macro_path = get_file_path(f"{mod}_macro_history.csv")
        
        if os.path.exists(micro_path) and os.path.exists(macro_path):
            df_micro = pd.read_csv(micro_path)
            df_macro = pd.read_csv(macro_path)
            
            macro_dict[mod] = df_macro.copy() 
            
            if not df_micro.empty and not df_macro.empty and 'Regime_Label' in df_macro.columns:
                df_micro['Date'] = pd.to_datetime(df_micro['Date'], format='mixed', errors='coerce').dt.normalize()
                df_macro['Date'] = pd.to_datetime(df_macro['Date'], format='mixed', errors='coerce').dt.normalize()
                
                df_merged = pd.merge(df_micro, df_macro[['Date', 'Regime_Label']], on='Date', how='inner')
                df_merged['Module'] = mod
                df_list.append(df_merged)

    if df_list:
        df_master = pd.concat(df_list, ignore_index=True)
        if 'Timestamp' in df_master.columns:
            df_master['Timestamp'] = pd.to_datetime(df_master['Timestamp'], format='mixed', errors='coerce')
    else:
        df_master = pd.DataFrame()

    config = safe_json_read(get_file_path("engines_config.json"))
    system_forecast = config.pop("_SYSTEM_FORECAST_", {})

    config_rows = []
    for k, d in config.items():
        if isinstance(d, dict) and 'engine_name' in d:
            config_rows.append({
                'Module': d.get('module', 'N/A'), 
                'Engine': d.get('engine_name', k), 
                'Bucket': d.get('bucket', 'C'),
                
                'Risk Scalar': d.get('risk_scalar', 0.0),
                'EV (R)': d.get('expected_value_r', d.get('expected_value_usd', 0.0)),
                'Bayes WR': d.get('wr_bayes_weighted', 0.0),
                
                'TT Global': d.get('total_trades_global', 0),
                'WR Global': d.get('wr_global', 0.0),
                'Diag': d.get('reason', ''),
                
                'WR R0': d.get('r0_wr', 0.0),
                'TT R0': d.get('r0_trades', 0),
                'Bucket R0': d.get('bucket_r0', 'C'),
                'Diag R0': d.get('reason_r0', ''),
                
                'WR R1': d.get('r1_wr', 0.0),
                'TT R1': d.get('r1_trades', 0),
                'Bucket R1': d.get('bucket_r1', 'C'),
                'Diag R1': d.get('reason_r1', ''),
                
                'WR R2': d.get('r2_wr', 0.0),
                'TT R2': d.get('r2_trades', 0),
                'Bucket R2': d.get('bucket_r2', 'C'),
                'Diag R2': d.get('reason_r2', '') 
            })
    
    return df_master, pd.DataFrame(config_rows), system_forecast, macro_dict

df_master, df_config, system_forecast, macro_data_dict = load_data()

# =========================================================================
# UTILITIES & STRICT HTML FORMATTING
# =========================================================================
def get_streak(df_sub):
    if df_sub is None or df_sub.empty or 'Is_Win' not in df_sub.columns: return 0
    df_asc = df_sub.sort_values('Timestamp', ascending=True)
    c, m = 0, 0
    for v in df_asc['Is_Win']:
        if v == 0:
            c += 1
            m = max(m, c)
        else: c = 0
    return m

def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.1); color: #00C853; font-weight: bold;'
    if val == "B": return 'background-color: rgba(200, 170, 0, 0.06); color: #CCA700; font-weight: bold;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.1); color: #D50000; font-weight: bold;'
    return ''

def render_html_table(df, bucket_cols=None):
    if df.empty: return ""
    if bucket_cols is None: bucket_cols = []
    
    format_dict = {}
    for col in df.columns:
        if 'WR' in col: format_dict[col] = "{:.1f}%"
        elif 'Scalar' in col: format_dict[col] = "{:.2f}"
        elif 'EV' in col: format_dict[col] = "{:.2f}R"

    styled = df.style.set_properties(**{'text-align': 'center'})
    
    for col in bucket_cols:
        if col in df.columns: styled = styled.map(highlight_buckets, subset=[col])
            
    styled = styled.format(format_dict)
    html = styled.hide(axis="index").to_html()
    html = html.replace('<table', '<table class="custom-table"')
    return f'<div class="table-container">{html}</div>'

def get_last_5_string(engine_name, df_m, regime_val=None):
    if df_m is None or df_m.empty: return "N/A"
    trades = df_m[df_m['Engine'] == engine_name]
    if regime_val is not None:
        trades = trades[trades['Regime_Label'] == regime_val]
    trades = trades.sort_values('Timestamp')
    if trades.empty: return "N/A"
    last_5 = trades.tail(5)['Is_Win'].tolist()
    return " - ".join(["W" if x == 1 else "L" for x in last_5])

if not df_config.empty:
    df_m_valid = df_master[df_master['Engine'] != 'NO_TRADE'] if not df_master.empty else None
    df_config['Last 5'] = df_config['Engine'].apply(lambda e: get_last_5_string(e, df_m_valid))
    df_config['Last 5 R0'] = df_config['Engine'].apply(lambda e: get_last_5_string(e, df_m_valid, regime_val=0))
    df_config['Last 5 R1'] = df_config['Engine'].apply(lambda e: get_last_5_string(e, df_m_valid, regime_val=1))
    df_config['Last 5 R2'] = df_config['Engine'].apply(lambda e: get_last_5_string(e, df_m_valid, regime_val=2))

def render_historical_metrics(df_c, df_m):
    if df_c.empty: return
    engines_count = len(df_c)
    
    if df_m is not None and not df_m.empty and 'Is_Win' in df_m.columns:
        total_raw = len(df_m)
        wins_raw = len(df_m[df_m['Is_Win'] == 1])
        losses_raw = len(df_m[df_m['Is_Win'] == 0])
        wr_raw = (wins_raw / total_raw * 100) if total_raw > 0 else 0
        streak_raw = get_streak(df_m)
    else:
        total_raw, wr_raw, wins_raw, losses_raw, streak_raw = 0, 0, 0, 0, 0
            
    st.markdown("#### 🩸 RAW EXECUTION (All Trades)")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Trades", total_raw); c2.metric("Global WR", f"{wr_raw:.1f}%"); c3.metric("Net Wins", wins_raw)
    c4.metric("Net Losses", losses_raw); c5.metric("Max L-Streak", streak_raw); c6.metric("Total Engines", engines_count)
    
    st.markdown("#### 🛡️ ML FILTERED (Buckets A & B Only)")
    if df_m is not None and not df_m.empty and 'Regime_Label' in df_m.columns:
        engine_bucket_map = {}
        for _, row in df_c.iterrows():
            engine_bucket_map[row['Engine']] = {
                0: row.get('Bucket R0', 'C'),
                1: row.get('Bucket R1', 'C'),
                2: row.get('Bucket R2', 'C')
            }
        
        def get_bucket(r):
            if pd.isna(r['Regime_Label']): return "C"
            try: return engine_bucket_map.get(r['Engine'], {}).get(int(r['Regime_Label']), "C")
            except: return "C"
            
        df_m_filt = df_m.copy()
        df_m_filt['Bucket'] = df_m_filt.apply(get_bucket, axis=1)
        df_filt = df_m_filt[df_m_filt['Bucket'].isin(['A', 'B'])]
        
        total_filt = len(df_filt)
        wins_filt = len(df_filt[df_filt['Is_Win'] == 1])
        losses_filt = len(df_filt[df_filt['Is_Win'] == 0])
        wr_filt = (wins_filt / total_filt * 100) if total_filt > 0 else 0
        streak_filt = get_streak(df_filt)
        engines_filt = df_filt['Engine'].nunique() if total_filt > 0 else 0
    else:
        total_filt, wr_filt, wins_filt, losses_filt, streak_filt, engines_filt = 0, 0, 0, 0, 0, 0

    f1, f2, f3, f4, f5, f6 = st.columns(6)
    f1.metric("Total Trades", total_filt); f2.metric("Global WR", f"{wr_filt:.1f}%"); f3.metric("Net Wins", wins_filt)
    f4.metric("Net Losses", losses_filt); f5.metric("Max L-Streak", streak_filt); f6.metric("Filtered Engines", engines_filt)
    st.markdown("---")

def render_regime_metrics(df_c, df_m, regime_id):
    if df_c.empty: return
    tt_col = f'TT R{regime_id}'
    if tt_col not in df_c.columns: return
    
    df_reg_config = df_c[df_c[tt_col] > 0]
    engines_count = len(df_reg_config)
    
    df_m_reg = pd.DataFrame()
    if df_m is not None and not df_m.empty and 'Regime_Label' in df_m.columns:
        df_m_reg = df_m[df_m['Regime_Label'] == regime_id].copy()

    if not df_m_reg.empty and 'Is_Win' in df_m_reg.columns:
        total_raw = len(df_m_reg)
        wins_raw = len(df_m_reg[df_m_reg['Is_Win'] == 1])
        losses_raw = len(df_m_reg[df_m_reg['Is_Win'] == 0])
        wr_raw = (wins_raw / total_raw * 100) if total_raw > 0 else 0
        streak_raw = get_streak(df_m_reg)
    else:
        total_raw, wr_raw, wins_raw, losses_raw, streak_raw = 0, 0, 0, 0, 0

    st.markdown(f"#### 🩸 RAW EXECUTION (Regime {regime_id})")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric(f"TT R{regime_id}", total_raw); c2.metric(f"WR R{regime_id}", f"{wr_raw:.1f}%"); c3.metric("Net Wins", wins_raw)
    c4.metric("Net Losses", losses_raw); c5.metric("Max L-Streak", streak_raw); c6.metric("Total Engines", engines_count)

    st.markdown("#### 🛡️ ML FILTERED (Buckets A & B Only)")
    if not df_m_reg.empty:
        bucket_col = f'Bucket R{regime_id}'
        engine_bucket_map = df_c.set_index('Engine')[bucket_col].to_dict() if bucket_col in df_c.columns else {}
        df_m_reg['Bucket'] = df_m_reg['Engine'].map(engine_bucket_map).fillna('C')
        df_filt = df_m_reg[df_m_reg['Bucket'].isin(['A', 'B'])]
        
        total_filt = len(df_filt)
        wins_filt = len(df_filt[df_filt['Is_Win'] == 1])
        losses_filt = len(df_filt[df_filt['Is_Win'] == 0])
        wr_filt = (wins_filt / total_filt * 100) if total_filt > 0 else 0
        streak_filt = get_streak(df_filt)
        engines_filt = df_filt['Engine'].nunique() if total_filt > 0 else 0
    else:
        total_filt, wr_filt, wins_filt, losses_filt, streak_filt, engines_filt = 0, 0, 0, 0, 0, 0
        
    f1, f2, f3, f4, f5, f6 = st.columns(6)
    f1.metric(f"TT R{regime_id}", total_filt); f2.metric(f"WR R{regime_id}", f"{wr_filt:.1f}%"); f3.metric("Net Wins", wins_filt)
    f4.metric("Net Losses", losses_filt); f5.metric("Max L-Streak", streak_filt); f6.metric("Filtered Engines", engines_filt)
    st.write("")

# =========================================================================
# NAVIGATION & VIEWS
# =========================================================================
st.sidebar.title("OmniSwarm Quant")
st.sidebar.markdown("---")
nav_category = st.sidebar.radio("Navigation", ["HOME", "Risk Management", "Trade Log", "Modules", "Macro Regime"])
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
        st.markdown("### 🔮 Markov Predictive Forecast (V3.4 Quant)")
        cols = st.columns(len(system_forecast))
        for i, (mod, data) in enumerate(system_forecast.items()):
            ftype = data.get("forecast_type", "SINGLE")
            p1 = data.get("probability", 0)
            t1 = data.get("top1", "?")
            t2 = data.get("top2", "?")
            ent = data.get("shannon_entropy", 0.0)
            
            if ftype == "SINGLE":
                cls_color = "fc-highlight"
                r_txt = f"R{t1}"
            else: 
                cls_color = "fc-dual"
                r_txt = f"R{t1} & R{t2} (DUAL)"

            with cols[i]:
                st.markdown(f"""
                <div class="forecast-card">
                    <div class="fc-title">[ {mod} ]</div>
                    <div class="fc-data">TARGET: <span class="{cls_color}">{r_txt}</span> | P1: {p1}% | H: {ent}</div>
                </div>
                """, unsafe_allow_html=True)
        st.write("")
    
    st.markdown("### 🌐 Global Historical Performance")
    if not df_config.empty:
        df_m_valid = df_master[df_master['Engine'] != 'NO_TRADE'] if not df_master.empty else None
        render_historical_metrics(df_config, df_m_valid)
        
        st.markdown("### 📊 The Global Matrix")
        df_home = df_config.copy()
        df_home = df_home.sort_values(by='TT Global', ascending=False)
        
        cols_home = [
            'Module', 'Engine', 'TT Global', 'WR Global', 'Last 5', 
            'TT R0', 'WR R0', 'Bucket R0', 
            'TT R1', 'WR R1', 'Bucket R1', 
            'TT R2', 'WR R2', 'Bucket R2'
        ]
        df_home = df_home[[c for c in cols_home if c in df_home.columns]]
        
        html_home = render_html_table(df_home, bucket_cols=['Bucket R0', 'Bucket R1', 'Bucket R2'])
        st.markdown(html_home, unsafe_allow_html=True)
    else:
        st.warning("No global data available.")

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
        except Exception as e: st.error(f"❌ Connection to NT8 failed. Check IP/Firewall. Error: {e}")

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
                daily_cap = st.number_input("Daily Profit Cap - $", value=float(risk_profile.get("daily_cap_usd", 1250.0)), step=50.0)
                profit_target = st.number_input("Profit Target - $", value=float(risk_profile.get("profit_target", 1500.0)), step=100.0)
                
            st.write("")
            if st.button("🚀 PUSH TO VPS & SET ACTIVE ACCOUNT", type="primary", use_container_width=True):
                new_risk_data = {
                    "account_status": "ACTIVE", 
                    "account_type": acc_type, "account_name": selected_acc_name, 
                    "account_size": acc_data['net_liq'], "profit_target": profit_target,
                    "eod_drawdown_limit": eod_fallback, "daily_cap_usd": daily_cap,
                    "base_risk_usd": base_risk, "max_contracts": max_contracts
                }
                
                if safe_json_write(get_file_path("risk_profile.json"), new_risk_data):
                    payload_gateway = {"passphrase": WEBHOOK_PASSPHRASE, "event": "UPDATE_RISK", "target_account": selected_acc_name, "risk_data": new_risk_data}
                    payload_nt8 = {"passphrase": WEBHOOK_PASSPHRASE, "command": "SYNC_BALANCE", "target_account": selected_acc_name}
                    
                    try: requests.post(VPS_WEBHOOK_URL, json=payload_gateway, timeout=2)
                    except: pass
                    try: requests.post(NT8_WEBHOOK_URL, json=payload_nt8, timeout=2)
                    except: pass

                    st.success(f"✅ Shield Active! NinjaTrader will execute orders on **{selected_acc_name}**.")
                    st.session_state.active_account = selected_acc_name
                    st.cache_data.clear() 
                    st.rerun() 
                else:
                    st.error("❌ Critical Error: Could not write file (Disk Lock). Try again in 1 second.")

elif nav_category == "Trade Log":
    st.title("Trade Log")
    time_filter = st.radio("Timeframe", ["Last Session", "7 Days", "15 Days", "1 Month", "3 Months", "6 Months", "1 Year", "All-Time"], horizontal=True)
    
    if not df_master.empty:
        df_log = df_master[df_master['Engine'] != 'NO_TRADE'].copy()
        
        df_log['Temp_Date'] = df_log['Timestamp'].dt.date
        df_log = df_log.drop_duplicates(subset=['Temp_Date', 'Engine', 'Action', 'Is_Win'], keep='last')
        
        if time_filter == "Last Session":
            if not df_log.empty:
                valid_ts = df_log['Timestamp'].dropna()
                if not valid_ts.empty:
                    last_date = valid_ts.max().date()
                    df_log = df_log[df_log['Timestamp'].dt.date == last_date]
                else:
                    df_log = pd.DataFrame(columns=df_log.columns) 
        elif time_filter != "All-Time":
            days_map = {"7 Days": 7, "15 Days": 15, "1 Month": 30, "3 Months": 90, "6 Months": 180, "1 Year": 365}
            cutoff_date = datetime.now() - timedelta(days=days_map[time_filter])
            df_log = df_log[df_log['Timestamp'] >= cutoff_date]
            
        df_log = df_log.sort_values('Timestamp', ascending=False)
        
        if not df_log.empty:
            def get_trade_bucket(engine, regime_val):
                if pd.isna(regime_val): return "C"
                try:
                    r_id = int(regime_val)
                    engine_data = df_config[df_config['Engine'] == engine]
                    if not engine_data.empty and f'Bucket R{r_id}' in engine_data.columns:
                        return engine_data.iloc[0][f'Bucket R{r_id}']
                except: pass
                return "C"

            df_log['Result'] = df_log['Is_Win'].apply(lambda x: "WIN" if x == 1 else "LOSS")
            
            if 'Regime_Label' in df_log.columns:
                df_log['Regime'] = df_log['Regime_Label'].apply(lambda x: f"R{int(x)}" if pd.notnull(x) else "N/A")
                df_log['Bucket'] = df_log.apply(lambda r: get_trade_bucket(r['Engine'], r['Regime_Label']), axis=1)
            else:
                df_log['Regime'], df_log['Bucket'] = "N/A", "C"
            
            wins_raw = len(df_log[df_log['Is_Win'] == 1])
            losses_raw = len(df_log[df_log['Is_Win'] == 0])
            total_raw = len(df_log)
            wr_raw = (wins_raw / total_raw * 100) if total_raw > 0 else 0
            
            st.markdown(f"#### 🩸 RAW EXECUTION (All Trades)")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Trades", total_raw); c2.metric("Win Rate", f"{wr_raw:.1f}%"); c3.metric("Net Wins", wins_raw); c4.metric("Net Losses", losses_raw); c5.metric("Max L-Streak", get_streak(df_log))
            
            df_filt = df_log[df_log['Bucket'].isin(['A', 'B'])]
            wins_filt = len(df_filt[df_filt['Is_Win'] == 1])
            losses_filt = len(df_filt[df_filt['Is_Win'] == 0])
            total_filt = len(df_filt)
            wr_filt = (wins_filt / total_filt * 100) if total_filt > 0 else 0
            
            st.markdown(f"#### 🛡️ ML FILTERED (Buckets A & B Only)")
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("Total Trades", total_filt); f2.metric("Win Rate", f"{wr_filt:.1f}%"); f3.metric("Net Wins", wins_filt); f4.metric("Net Losses", losses_filt); f5.metric("Max L-Streak", get_streak(df_filt))
            
            st.markdown("---")
            show_cols = ['Timestamp', 'Module', 'Engine', 'Regime', 'Bucket', 'Action', 'Result']
            html_log = render_html_table(df_log[[c for c in show_cols if c in df_log.columns]], bucket_cols=['Bucket'])
            st.markdown(html_log, unsafe_allow_html=True)
        else: 
            st.warning("No data found for the selected timeframe.")
    else: st.error("Database is empty.")

# =========================================================================
# PESTAÑA: MACRO REGIME INTELLIGENCE
# =========================================================================
elif nav_category == "Macro Regime":
    st.title("Macro Regime Intelligence")
    st.markdown("Deep dive into Market Dominance, ML Historical Accuracy, and Markov Probabilities.")

    selected_module = st.selectbox("Select Target Module:", ["MCL", "MGC", "MES", "MNQ_DAY", "MNQ_NIGHT"])
    df_macro = macro_data_dict.get(selected_module, pd.DataFrame())

    if not df_macro.empty:
        df_macro['Date_Obj'] = pd.to_datetime(df_macro['Date'], format='mixed', errors='coerce').dt.date
        df_macro = df_macro.sort_values('Date_Obj').reset_index(drop=True)
        
        if 'Regime_Label' in df_macro.columns:
            regimes_seq = df_macro['Regime_Label'].dropna().astype(int).tolist()
            transitions = np.zeros((3,3))
            for i in range(len(regimes_seq)-1):
                transitions[regimes_seq[i]][regimes_seq[i+1]] += 1
            
            trans_probs = np.zeros((3,3))
            for i in range(3):
                row_sum = np.sum(transitions[i])
                if row_sum > 0: trans_probs[i] = transitions[i] / row_sum
                else: trans_probs[i] = [1/3, 1/3, 1/3]
            
            forecasts = ["N/A"]
            matches = ["N/A"]
            
            for i in range(1, len(regimes_seq)):
                prev_r = regimes_seq[i-1]
                act_r = regimes_seq[i]
                pred_r = int(np.argmax(trans_probs[prev_r]))
                forecasts.append(f"R{pred_r}")
                matches.append("✅" if pred_r == act_r else "❌")
                
            df_macro['Actual Regime'] = df_macro['Regime_Label'].apply(lambda x: f"R{int(x)}")
            df_macro['ML Forecasted Regime'] = forecasts
            df_macro['Match?'] = matches

        tab_dom, tab_hist, tab_markov = st.tabs(["👑 Regime Dominance", "📅 Historical Accuracy", "🔮 Markov Engine"])

        with tab_dom:
            st.markdown("### The Big Picture (All-Time Dominance)")
            
            total_sessions = len(df_macro)
            counts = df_macro['Regime_Label'].value_counts().to_dict()
            c0 = counts.get(0, 0)
            c1 = counts.get(1, 0)
            c2 = counts.get(2, 0)
            
            st.metric("Total Historical Sessions Evaluated", total_sessions)
            st.markdown("---")
            
            if total_sessions > 0:
                c_a, c_b, c_c = st.columns(3)
                c_a.metric("Regime 0 (R0)", f"{(c0/total_sessions*100):.1f}%", f"{c0} Sessions")
                c_b.metric("Regime 1 (R1)", f"{(c1/total_sessions*100):.1f}%", f"{c1} Sessions")
                c_c.metric("Regime 2 (R2)", f"{(c2/total_sessions*100):.1f}%", f"{c2} Sessions")

        with tab_hist:
            st.markdown("### Historical Accuracy (Forecast vs Reality)")
            time_filter = st.radio("Timeframe (Macro)", ["Last Session", "7 Days", "15 Days", "1 Month", "3 Months", "6 Months", "All-Time"], horizontal=True)
            
            df_hist = df_macro.copy()
            if time_filter == "Last Session":
                last_date = df_hist['Date_Obj'].max()
                df_hist = df_hist[df_hist['Date_Obj'] == last_date]
            elif time_filter != "All-Time":
                days_map = {"7 Days": 7, "15 Days": 15, "1 Month": 30, "3 Months": 90, "6 Months": 180}
                cutoff_date = datetime.now().date() - timedelta(days=days_map[time_filter])
                df_hist = df_hist[df_hist['Date_Obj'] >= cutoff_date]
                
            df_hist = df_hist.sort_values('Date_Obj', ascending=False)
            
            if not df_hist.empty:
                valid_preds = df_hist[df_hist['Match?'] != "N/A"]
                if not valid_preds.empty:
                    accuracy = (len(valid_preds[valid_preds['Match?'] == "✅"]) / len(valid_preds)) * 100
                    st.success(f"**Markov Accuracy in selected period:** {accuracy:.1f}%")
                
                cols_hist = ['Date', 'Actual Regime', 'ML Forecasted Regime', 'Match?']
                st.markdown(render_html_table(df_hist[[c for c in cols_hist if c in df_hist.columns]]), unsafe_allow_html=True)
            else:
                st.warning("No macro records found for this timeframe.")

        with tab_markov:
            st.markdown("### Next Session Predictive Matrix")
            f_data = system_forecast.get(selected_module, {})
            
            if f_data:
                today_r = f_data.get('today_regime', '?')
                ftype = f_data.get('forecast_type', 'SINGLE')
                p1 = f_data.get('probability', 0)
                t1 = f_data.get('top1', '?')
                t2 = f_data.get('top2', '?')
                ent = f_data.get('shannon_entropy', 0.0)
                
                if ftype == "SINGLE":
                    hud_style = "module-hud"
                    r_txt = f"<span style='color: #00C853; font-weight: 700;'>R{t1}</span>"
                    status_txt = "Quant Single Lineup (Kelly Sweet Spot &ge; 66.6% or Dominant Majority)"
                else:
                    hud_style = "module-hud module-hud-dual"
                    r_txt = f"<span style='color: #CCA700; font-weight: 700;'>R{t1} & R{t2} (DUAL)</span>"
                    status_txt = "Quant Dual Shield (Intersectional All-Weather Protection)"
                
                st.markdown(f"""
                <div class="{hud_style}">
                    [ MARKET INERTIA ] &nbsp;&nbsp;TODAY: <b>R{today_r}</b> &nbsp;➔&nbsp; FORECAST: {r_txt} (P1: {p1}% | H: {ent})
                    <br><span style="font-size: 0.9rem; font-weight: 400; color:#A0A0A0;">{status_txt}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("#### Top Probabilities for Tomorrow")
                p1_v, p2_v, p3_v = f_data.get('p1', 0), f_data.get('p2', 0), f_data.get('p3', 0)
                t1_v, t2_v, t3_v = f_data.get('top1', 0), f_data.get('top2', 0), f_data.get('top3', 0)
                
                c_p1, c_p2, c_p3 = st.columns(3)
                c_p1.metric(f"Rank 1 (R{t1_v})", f"{p1_v}%")
                c_p2.metric(f"Rank 2 (R{t2_v})", f"{p2_v}%")
                c_p3.metric(f"Rank 3 (R{t3_v})", f"{p3_v}%")
            else:
                st.warning("No Markov forecast data available for this module.")
    else:
        st.error("No Macro Data found for this module. Ensure the ML Auditor has run successfully.")

# =========================================================================
# MODULES DASHBOARD
# =========================================================================
elif nav_category == "Modules":
    st.title("Modules Dashboard")
    selected_module = st.selectbox("Select Target Module:", ["MCL", "MGC", "MES", "MNQ_DAY", "MNQ_NIGHT"])
    df_c_mod = df_config[df_config['Module'] == selected_module].copy()
    
    f_data = system_forecast.get(selected_module, {})
    if f_data:
        ftype = f_data.get('forecast_type', 'SINGLE')
        p1 = f_data.get('probability', 0)
        t1 = f_data.get('top1', 0)
        t2 = f_data.get('top2', 0)
        ent = f_data.get('shannon_entropy', 0.0)
        
        if ftype == "SINGLE":
            hud_style = "module-hud"
            r_txt = f"<span style='color: #00C853; font-weight: 700;'>R{t1}</span>"
        else:
            hud_style = "module-hud module-hud-dual"
            r_txt = f"<span style='color: #CCA700; font-weight: 700;'>R{t1} & R{t2} (DUAL)</span>"

        st.markdown(f"""
        <div class="{hud_style}">
            [ NEXT SESSION FORECAST ] &nbsp;&nbsp;🎯 TARGET: {r_txt} &nbsp;&nbsp;|&nbsp;&nbsp; P1: {p1}% &nbsp;&nbsp;|&nbsp;&nbsp; H: {ent}
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown(f"### 🌐 Historical Performance: {selected_module}")
    df_m_mod = df_master[(df_master['Module'] == selected_module) & (df_master['Engine'] != 'NO_TRADE')] if not df_master.empty else None
    render_historical_metrics(df_c_mod, df_m_mod)
    
    tab1, tab2, tab3 = st.tabs(["🌐 Global Matrix", "🚀 Next Session Line-up", "📊 Regime Breakdown"])
    
    with tab1:
        st.markdown(f"### The Global Matrix ({selected_module})")
        if not df_c_mod.empty:
            df_t1 = df_c_mod.copy().sort_values(by='TT Global', ascending=False)
            cols_t1 = ['Engine', 'TT Global', 'WR Global', 'Last 5', 'TT R0', 'WR R0', 'Bucket R0', 'TT R1', 'WR R1', 'Bucket R1', 'TT R2', 'WR R2', 'Bucket R2']
            st.markdown(render_html_table(df_t1[[c for c in cols_t1 if c in df_t1.columns]], bucket_cols=['Bucket R0', 'Bucket R1', 'Bucket R2']), unsafe_allow_html=True)
    
    with tab2:
        st.markdown("### Tactical Execution Plan (Next Session)")
        if not df_c_mod.empty and f_data:
            df_t2 = df_c_mod.copy()
            df_t2['Bucket_Rank'] = df_t2['Bucket'].map({'A': 1, 'B': 2, 'C': 3}).fillna(3)
            
            if ftype == "SINGLE":
                sort_wr_col = f'WR R{t1}' if f'WR R{t1}' in df_t2.columns else 'WR Global'
                df_t2 = df_t2.sort_values(by=['Bucket_Rank', 'Risk Scalar', sort_wr_col], ascending=[True, False, False])
                if f'Last 5 R{t1}' in df_t2.columns:
                    df_t2['Last 5 Target'] = df_t2[f'Last 5 R{t1}']
                else:
                    df_t2['Last 5 Target'] = df_t2['Last 5']
                cols_t2 = ['Engine', 'Bucket', 'Risk Scalar', 'EV (R)', f'TT R{t1}', f'WR R{t1}', 'Last 5 Target', 'Diag']
            else: 
                sort_wr_col = f'WR R{t1}' if f'WR R{t1}' in df_t2.columns else 'WR Global'
                df_t2 = df_t2.sort_values(by=['Bucket_Rank', 'Risk Scalar', sort_wr_col], ascending=[True, False, False])
                cols_t2 = ['Engine', 'Bucket', 'Risk Scalar', 'EV (R)', f'TT R{t1}', f'WR R{t1}', f'TT R{t2}', f'WR R{t2}', 'Diag']

            st.markdown(render_html_table(df_t2[[c for c in cols_t2 if c in df_t2.columns]], bucket_cols=['Bucket']), unsafe_allow_html=True)
            
    with tab3:
        st.markdown("### Forensic Multi-Regime Analysis")
        t_r0, t_r1, t_r2 = st.tabs(["[ Regime 0 ]", "[ Regime 1 ]", "[ Regime 2 ]"])
        
        def render_sub_bucket_table(df_regime, regime_id, bucket_label, title):
            bucket_col = f'Bucket R{regime_id}'
            if bucket_col not in df_regime.columns: return
            df_sub = df_regime[df_regime[bucket_col] == bucket_label].copy()
            if not df_sub.empty:
                st.markdown(f"#### {title}")
                df_sub['Diag'] = df_sub.get(f'Diag R{regime_id}', '')
                cols_sub = ['Engine', bucket_col, f'TT R{regime_id}', f'WR R{regime_id}', f'Last 5 R{regime_id}', 'Diag']
                sort_col = f'WR R{regime_id}' if f'WR R{regime_id}' in df_sub.columns else 'Engine'
                df_sub = df_sub[[c for c in cols_sub if c in df_sub.columns]].sort_values(by=sort_col, ascending=False)
                st.markdown(render_html_table(df_sub, bucket_cols=[bucket_col]), unsafe_allow_html=True)
        
        for idx, t_tab in enumerate([t_r0, t_r1, t_r2]):
            with t_tab:
                render_regime_metrics(df_c_mod, df_m_mod, idx)
                render_sub_bucket_table(df_c_mod, idx, 'A', "🎯 Bucket A (Snipers)")
                render_sub_bucket_table(df_c_mod, idx, 'B', "⚠️ Bucket B (Friction/New)")
                render_sub_bucket_table(df_c_mod, idx, 'C', "🚫 Bucket C (Quarantine)")