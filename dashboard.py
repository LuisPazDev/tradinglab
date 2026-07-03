import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# =========================================================================
# CONFIGURACIÓN DE PÁGINA Y RUTAS INTELIGENTES
# =========================================================================
st.set_page_config(page_title="TradingLab Quant", layout="wide", page_icon="📈")

def get_file_path(filename):
    """Detecta si está en Streamlit Cloud (raíz) o en PythonAnywhere (~/mysite/)"""
    if os.path.exists(filename):
        return filename
    local_path = os.path.join(os.path.expanduser("~/mysite/"), filename)
    if os.path.exists(local_path):
        return local_path
    return filename

TRADE_FILE = get_file_path("trade_history.csv")
ALPHA_FILE = get_file_path("alpha_dataset.csv")
CONFIG_FILE = get_file_path("engines_config.json")

# =========================================================================
# FUNCIONES DE CARGA DE DATOS
# =========================================================================
@st.cache_data(ttl=60)
def load_data():
    df_trades = pd.DataFrame()
    df_alpha = pd.DataFrame()
    config = {}

    if os.path.exists(TRADE_FILE):
        try:
            df_trades = pd.read_csv(TRADE_FILE, on_bad_lines='skip')
            df_trades['Timestamp'] = pd.to_datetime(df_trades['Timestamp'], errors='coerce')
            df_trades['Trade_Exact_PnL'] = pd.to_numeric(df_trades.get('Trade_Exact_PnL', 0), errors='coerce').fillna(0)
        except: pass

    if os.path.exists(ALPHA_FILE):
        try:
            df_alpha = pd.read_csv(ALPHA_FILE, on_bad_lines='skip')
            df_alpha['Timestamp'] = pd.to_datetime(df_alpha['Timestamp'], errors='coerce')
        except: pass

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except: pass

    return df_trades, df_alpha, config

df_trades, df_alpha, engines_config = load_data()

# =========================================================================
# UI: BARRA LATERAL (FILTROS)
# =========================================================================
st.sidebar.image("https://img.icons8.com/color/96/000000/artificial-intelligence.png", width=60)
st.sidebar.title("Vigilante Quant V12")
st.sidebar.markdown("---")

# Filtro de Activo
symbols = ["TODOS"]
if not df_trades.empty: symbols.extend(df_trades['Symbol'].dropna().unique().tolist())
if not df_alpha.empty: symbols.extend(df_alpha['Symbol'].dropna().unique().tolist())
symbols = list(set(symbols))
selected_symbol = st.sidebar.selectbox("🎯 Instrumento", symbols)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Forzar Recarga de Datos"):
    st.cache_data.clear()
    st.rerun()

# =========================================================================
# FILTRADO DE DATOS GLOBALES
# =========================================================================
df_t = df_trades.copy()
df_a = df_alpha.copy()

if selected_symbol != "TODOS":
    if not df_t.empty: df_t = df_t[df_t['Symbol'] == selected_symbol]
    if not df_a.empty: df_a = df_a[df_a['Symbol'] == selected_symbol]

# =========================================================================
# DETECCIÓN DE KILL SWITCH (ESTADO DE LA CUENTA)
# =========================================================================
st.title("🎛️ Centro de Mando Institucional")

kill_switch_active = False
if not df_t.empty:
    last_trade = df_t.iloc[-1]
    if "REJECTED_ACCOUNT_INACTIVE" in str(last_trade.get('Status', '')):
        kill_switch_active = True

if kill_switch_active:
    st.error("🚨 **SISTEMA EN ESPERA (KILL SWITCH ACTIVADO):** La cuenta de fondeo conectada registra un Poder de Compra (Buying Power) de $0. La Vía B está bloqueada para proteger la telemetría, pero la Vía A sigue recabando datos teóricos.")
else:
    st.success("✅ **SISTEMA EN LÍNEA:** Conexión a Bróker establecida. Cuenta activa con liquidez disponible para atacar.")

# =========================================================================
# TABS PRINCIPALES (LA BIFURCACIÓN)
# =========================================================================
tab_fin, tab_ml = st.tabs(["💰 Realidad Bróker (Finanzas)", "🧠 Salud Sistémica (Machine Learning)"])

# -------------------------------------------------------------------------
# PESTAÑA 1: FINANZAS (CARRIL B)
# -------------------------------------------------------------------------
with tab_fin:
    st.markdown("### 🏦 Rendimiento Físico en la Cuenta de Fondeo")

    if df_t.empty:
        st.warning("No hay datos de ejecución real en el bróker registrados aún.")
    else:
        reales_cerrados = df_t[df_t['Status'].astype(str).str.contains('CLOSED_MANUAL|CLOSED_BY_BRACKET', na=False)].copy()

        if reales_cerrados.empty:
            st.info("Aún no hay operaciones físicas cerradas en el histórico.")
        else:
            reales_cerrados = reales_cerrados.sort_values('Timestamp')
            reales_cerrados['Cumulative_PnL'] = reales_cerrados['Trade_Exact_PnL'].cumsum()

            pnl_neto = reales_cerrados['Trade_Exact_PnL'].sum()
            total_reales = len(reales_cerrados)
            wins = len(reales_cerrados[reales_cerrados['Trade_Exact_PnL'] > 0])
            wr_real = (wins / total_reales) * 100 if total_reales > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("PnL Neto USD", f"${pnl_neto:,.2f}")
            col2.metric("Trades Físicos", f"{total_reales}")
            col3.metric("WinRate Real", f"{wr_real:.1f}%")

            rechazos = len(df_t[df_t['Status'].astype(str).str.contains('REJECTED')])
            col4.metric("Bloqueos por Riesgo", f"{rechazos}")

            st.markdown("#### Curva de Equity (Realidad)")
            fig_equity = px.area(reales_cerrados, x='Timestamp', y='Cumulative_PnL',
                                 title="Crecimiento de Capital Neto",
                                 labels={'Cumulative_PnL':'Capital USD', 'Timestamp':'Fecha'},
                                 color_discrete_sequence=['#00C853'])
            st.plotly_chart(fig_equity, use_container_width=True)

            st.markdown("#### Últimas Ejecuciones Físicas")
            show_cols_fin = ['Timestamp', 'Symbol', 'Action', 'Qty', 'Status', 'Trade_Exact_PnL']
            st.dataframe(reales_cerrados[show_cols_fin].tail(15).sort_values('Timestamp', ascending=False), use_container_width=True)

# -------------------------------------------------------------------------
# PESTAÑA 2: MACHINE LEARNING (CARRIL A & BUCKETS)
# -------------------------------------------------------------------------
with tab_ml:
    st.markdown("### 🧬 Análisis Predictivo y Distribución de Riesgo")

    if not engines_config:
        st.warning("El modelo de Machine Learning aún no ha generado el archivo de configuración (engines_config.json).")
    else:
        config_rows = []
        for eng, data in engines_config.items():
            row = {
                'Engine': eng,
                'Bucket': data.get('bucket', 'B'),
                'WR_Global': data.get('wr', 'N/A'),
                'Trades': data.get('trades', 0),
                'R0': data.get('r0_wr', data.get('r0', 'N/A')),
                'R1': data.get('r1_wr', data.get('r1', 'N/A')),
                'R2': data.get('r2_wr', data.get('r2', 'N/A')),
                'Reason': data.get('reason', '')
            }
            config_rows.append(row)

        df_config = pd.DataFrame(config_rows)

        bucket_counts = df_config['Bucket'].value_counts().to_dict()
        b_a = bucket_counts.get("A", 0)
        b_b = bucket_counts.get("B", 0)
        b_c = bucket_counts.get("C", 0)

        col1, col2, col3 = st.columns(3)
        col1.metric("🟢 BUCKET A (Riesgo Full)", f"{b_a} Motores", "Listos para atacar")
        col2.metric("🟡 BUCKET B (Limitados)", f"{b_b} Motores", "En fase de maduración/fricción", delta_color="off")
        col3.metric("🔴 BUCKET C (Cuarentena)", f"{b_c} Motores", "Freno de emergencia / Decay", delta_color="inverse")

        st.markdown("---")

        fig_buckets = px.pie(names=['Bucket A (Óptimos)', 'Bucket B (Fricción)', 'Bucket C (Cuarentena)'],
                             values=[b_a, b_b, b_c],
                             color_discrete_sequence=['#00C853', '#FFD600', '#D50000'],
                             hole=0.4, title="Distribución de Salud del Ecosistema")

        fig_alpha = go.Figure()
        if not df_a.empty:
            df_a_closed = df_a[df_a['Status'].astype(str).str.contains('ALPHA_CLOSED')].copy()
            if not df_a_closed.empty:
                df_a_closed = df_a_closed.sort_values('Timestamp')

                df_a_closed['Hit_Score'] = df_a_closed['Status'].apply(lambda x: 1 if 'WIN' in str(x) else (-1 if 'LOSS' in str(x) else 0))
                df_a_closed['Cumulative_Hits'] = df_a_closed['Hit_Score'].cumsum()

                fig_alpha = px.line(df_a_closed, x='Timestamp', y='Cumulative_Hits',
                                    title="Curva de Efectividad Pura (Acumulación de Victorias Teóricas)",
                                    labels={'Cumulative_Hits': 'Balance de Aciertos (Hits)', 'Timestamp': 'Fecha'},
                                    color_discrete_sequence=['#2962FF'])

        col_graf1, col_graf2 = st.columns(2)
        with col_graf1: st.plotly_chart(fig_buckets, use_container_width=True)
        with col_graf2: st.plotly_chart(fig_alpha, use_container_width=True)

        st.markdown("#### 🔬 Matriz de Regímenes (Rayos X del Pipeline)")

        def highlight_buckets(val):
            if val == "A": return 'background-color: rgba(0, 200, 83, 0.2); color: #00C853; font-weight: bold;'
            if val == "B": return 'background-color: rgba(255, 214, 0, 0.2); color: #FFD600; font-weight: bold;'
            if val == "C": return 'background-color: rgba(213, 0, 0, 0.2); color: #D50000; font-weight: bold;'
            return ''

        styled_config = df_config.style.map(highlight_buckets, subset=['Bucket'])
        st.dataframe(styled_config, use_container_width=True, height=400)