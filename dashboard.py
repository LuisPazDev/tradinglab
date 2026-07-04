import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

# =========================================================================
# CONFIGURACIÓN DE PÁGINA Y RUTAS
# =========================================================================
st.set_page_config(page_title="TradingLab Quant", layout="wide", page_icon="🧬")

def get_file_path(filename):
    if os.path.exists(filename): return filename
    local_path = os.path.join(os.path.expanduser("~/mysite/"), filename)
    if os.path.exists(local_path): return local_path
    return filename

MASTER_FILE = get_file_path("master_ml_dataset.csv")
CONFIG_FILE = get_file_path("engines_config.json")
TRADE_FILE = get_file_path("trade_history.csv")

# =========================================================================
# CARGA DEL DATASET MAESTRO
# =========================================================================
@st.cache_data(ttl=60)
def load_data():
    df_master = pd.DataFrame()
    config = {}
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

    if os.path.exists(TRADE_FILE):
        try:
            df_t = pd.read_csv(TRADE_FILE, on_bad_lines='skip')
            if not df_t.empty and "REJECTED_ACCOUNT_INACTIVE" in str(df_t.iloc[-1].get('Status', '')):
                kill_switch = True
        except: pass

    return df_master, config, kill_switch

df_master, engines_config, kill_switch_active = load_data()

# =========================================================================
# UI: BARRA LATERAL (CASCADA MACRO -> MICRO)
# =========================================================================
st.sidebar.image("https://img.icons8.com/color/96/000000/artificial-intelligence.png", width=60)
st.sidebar.title("Quant Lab V14")
st.sidebar.markdown("---")

modules_list = ["SISTEMA COMPLETO", "MCL", "MGC", "MES", "MNQ_DAY", "MNQ_NIGHT"]
selected_module = st.sidebar.selectbox("🔬 Módulo de Análisis", modules_list)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Forzar Recarga"):
    st.cache_data.clear()
    st.rerun()

# =========================================================================
# CABECERA Y ESTADO DEL SISTEMA
# =========================================================================
st.title("🧬 Ecosistema Cuantitativo Institucional")
if kill_switch_active:
    st.error("🚨 **ALERTA DE INFRAESTRUCTURA (VÍA B):** La cuenta de fondeo conectada registra un Buying Power de $0. Ejecución física pausada.")
else:
    st.success("✅ **SISTEMA EN LÍNEA:** Cerebro conectado. Flujo de Vía A y Vía B operando con normalidad.")

# =========================================================================
# PROCESAMIENTO DEL JSON DE MOTORES
# =========================================================================
config_rows = []
for eng, data in engines_config.items():
    row = {
        'Módulo': data.get('module', 'N/A'),
        'Motor': eng,
        'Últimos_5': data.get('last_5', 'N/A'),
        'Bucket': data.get('bucket', 'B'),
        'WR_Global': data.get('wr', 0.0),
        'Trades': data.get('trades', 0),
        'R0': data.get('regimes_breakdown', {}).get('R0', 'N/A'),
        'R1': data.get('regimes_breakdown', {}).get('R1', 'N/A'),
        'R2': data.get('regimes_breakdown', {}).get('R2', 'N/A'),
        'Decay_Pts': data.get('execution_decay', 0.0),
        'Trades_Vía_B': data.get('decay_samples', 0),
        'Diag': data.get('reason', '')
    }
    config_rows.append(row)

df_config = pd.DataFrame(config_rows)

# =========================================================================
# FILTRADO POR MÓDULO
# =========================================================================
if selected_module != "SISTEMA COMPLETO":
    if not df_master.empty: df_master = df_master[df_master['Module'] == selected_module]
    if not df_config.empty: df_config = df_config[df_config['Módulo'] == selected_module]

# =========================================================================
# MÉTRICAS SUPERIORES
# =========================================================================
st.markdown(f"### 📊 Rendimiento de Probabilidad Pura: {selected_module}")
if not df_config.empty:
    total_trades = df_config['Trades'].sum()
    avg_wr = (df_config['WR_Global'] * df_config['Trades']).sum() / total_trades if total_trades > 0 else 0

    b_a = len(df_config[df_config['Bucket'] == 'A'])
    b_b = len(df_config[df_config['Bucket'] == 'B'])
    b_c = len(df_config[df_config['Bucket'] == 'C'])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Trades Históricos", f"{total_trades}")
    col2.metric("WinRate Promedio", f"{avg_wr:.1f}%")
    col3.metric("🟢 BUCKET A", f"{b_a} Motores")
    col4.metric("🟡 BUCKET B", f"{b_b} Motores")
    col5.metric("🔴 BUCKET C", f"{b_c} Motores")
else:
    st.warning("No hay datos de configuración para este módulo.")

st.markdown("---")

# =========================================================================
# GRÁFICAS DE COMPORTAMIENTO VS TABLA DE MÓDULOS
# =========================================================================
col_g1, col_g2 = st.columns(2)

with col_g1:
    if not df_master.empty:
        df_m_closed = df_master[df_master['Status'].astype(str).str.contains('WIN|LOSS|CLOSED')].copy()
        if not df_m_closed.empty:
            df_m_closed = df_m_closed.sort_values('Timestamp')
            df_m_closed['Hit_Score'] = df_m_closed['Status'].apply(lambda x: 1 if 'WIN' in str(x) else (-1 if 'LOSS' in str(x) else 0))
            df_m_closed['Cumulative_Hits'] = df_m_closed['Hit_Score'].cumsum()

            fig_alpha = px.line(df_m_closed, x='Timestamp', y='Cumulative_Hits',
                                title=f"Curva de Efectividad (Hits Netos) - {selected_module}",
                                labels={'Cumulative_Hits': 'Balance de Aciertos', 'Timestamp': 'Fecha'},
                                color_discrete_sequence=['#2962FF'])
            st.plotly_chart(fig_alpha, use_container_width=True)

with col_g2:
    st.markdown("#### 🏢 Resumen de Módulos (Macro)")
    if not df_config.empty:
        # Calcular Wins estimados para sacar el WinRate real del módulo
        df_config['Wins_Est'] = (df_config['WR_Global'] / 100) * df_config['Trades']
        mod_summary = df_config.groupby('Módulo').agg(
            Trades=('Trades', 'sum'),
            Wins=('Wins_Est', 'sum'),
            Motores=('Motor', 'count')
        ).reset_index()

        mod_summary['WinRate'] = (mod_summary['Wins'] / mod_summary['Trades'] * 100).round(1)
        # Formatear
        mod_summary['WinRate'] = mod_summary['WinRate'].astype(str) + "%"
        mod_summary = mod_summary[['Módulo', 'WinRate', 'Trades', 'Motores']].sort_values('Trades', ascending=False)

        st.dataframe(mod_summary, use_container_width=True, hide_index=True)

# =========================================================================
# MATRIZ CIENTÍFICA (RAYOS X)
# =========================================================================
st.markdown("### 🔬 Radiografía de Motores y Execution Decay")
if not df_config.empty:
    def highlight_buckets(val):
        if val == "A": return 'background-color: rgba(0, 200, 83, 0.2); color: #00C853; font-weight: bold;'
        if val == "B": return 'background-color: rgba(255, 214, 0, 0.2); color: #FFD600; font-weight: bold;'
        if val == "C": return 'background-color: rgba(213, 0, 0, 0.2); color: #D50000; font-weight: bold;'
        return ''

    display_cols = ['Módulo', 'Motor', 'Últimos_5', 'Bucket', 'WR_Global', 'Trades', 'R0', 'R1', 'R2', 'Decay_Pts', 'Trades_Vía_B', 'Diag']
    df_display = df_config[display_cols].sort_values(by=['Bucket', 'WR_Global'], ascending=[True, False])

    styled_config = df_display.style.map(highlight_buckets, subset=['Bucket'])\
                                    .format({'Decay_Pts': "{:.2f}", 'WR_Global': "{:.1f}%"})

    st.dataframe(styled_config, use_container_width=True, height=600)