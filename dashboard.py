import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

# =========================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y RUTAS
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
# 2. CARGA DEL DATASET MAESTRO (CACHÉ EN RAM)
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

    return df_master, df_config, kill_switch

df_master, df_config, kill_switch_active = load_data()

# =========================================================================
# 3. FUNCIONES DE DISEÑO (ESTILOS Y GRÁFICAS)
# =========================================================================
def highlight_buckets(val):
    if val == "A": return 'background-color: rgba(0, 200, 83, 0.2); color: #00C853; font-weight: bold;'
    if val == "B": return 'background-color: rgba(255, 214, 0, 0.2); color: #FFD600; font-weight: bold;'
    if val == "C": return 'background-color: rgba(213, 0, 0, 0.2); color: #D50000; font-weight: bold;'
    return ''

def plot_cumulative_hits(df, title):
    if df.empty: return None
    df_closed = df[df['Status'].astype(str).str.contains('WIN|LOSS|CLOSED')].copy()
    if df_closed.empty: return None

    df_closed = df_closed.sort_values('Timestamp')
    df_closed['Hit_Score'] = df_closed['Status'].apply(lambda x: 1 if 'WIN' in str(x) else (-1 if 'LOSS' in str(x) else 0))
    df_closed['Cumulative_Hits'] = df_closed['Hit_Score'].cumsum()

    fig = px.line(df_closed, x='Timestamp', y='Cumulative_Hits', title=title,
                  labels={'Cumulative_Hits': 'Balance de Aciertos Netos', 'Timestamp': 'Fecha'},
                  color_discrete_sequence=['#2962FF'])
    return fig

def render_top_metrics(df_c, title):
    st.markdown(f"### 📊 Rendimiento de Probabilidad Pura: {title}")
    if df_c.empty:
        st.warning("No hay datos de configuración disponibles.")
        return

    total_trades = df_c['Trades'].sum()
    avg_wr = (df_c['WR_Global'] * df_c['Trades']).sum() / total_trades if total_trades > 0 else 0
    total_motores = len(df_c)

    b_a = len(df_c[df_c['Bucket'] == 'A'])
    b_b = len(df_c[df_c['Bucket'] == 'B'])
    b_c = len(df_c[df_c['Bucket'] == 'C'])

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Trades", f"{total_trades}")
    col2.metric("WinRate Global", f"{avg_wr:.1f}%")
    col3.metric("Total Motores", f"{total_motores}")
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
if kill_switch_active:
    st.error("🚨 **ALERTA DE INFRAESTRUCTURA (VÍA B):** La cuenta de fondeo conectada registra un Buying Power de $0. Ejecución física pausada.")
else:
    st.success("✅ **SISTEMA EN LÍNEA:** Cerebro conectado. Flujo de Vía A y Vía B operando con normalidad.")

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

# ---> VISTA 2: MÓDULOS ESPECÍFICOS
elif selected_view.startswith("🔬 Módulo:"):
    module_name = selected_view.split(": ")[1]

    df_master_mod = df_master[df_master['Module'] == module_name] if not df_master.empty else pd.DataFrame()
    df_config_mod = df_config[df_config['Módulo'] == module_name] if not df_config.empty else pd.DataFrame()

    render_top_metrics(df_config_mod, module_name)

    fig = plot_cumulative_hits(df_master_mod, f"Curva de Efectividad - {module_name}")
    if fig: st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"### 🔬 Radiografía Interna: {module_name}")
    render_engine_table(df_config_mod)

# ---> VISTA 3: BITÁCORA CRONOLÓGICA
elif selected_view == "📅 Bitácora Cronológica":
    st.markdown("### 📅 Explorador del Data Lake (Dataset Maestro)")
    st.markdown("Aquí se muestran todos los eventos capturados por la Vía A y el Backtest, ordenados cronológicamente.")

    if not df_master.empty:
        col_filtro, col_metric = st.columns([1, 2])

        with col_filtro:
            # Nuevo diseño: Un checkbox mucho más intuitivo para filtrar
            usar_filtro = st.checkbox("🔍 Filtrar por un día específico")
            if usar_filtro:
                filter_date = st.date_input("Selecciona la fecha:")
            else:
                filter_date = None

        df_log = df_master.copy()

        # Aplicar el filtro de fecha si el checkbox está activado
        if filter_date is not None:
            df_log = df_log[df_log['Timestamp'].dt.date == filter_date]

        # Renderizado de la tabla
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

            # Ordenar del más reciente al más antiguo
            df_log = df_log.sort_values('Timestamp', ascending=False)

            # Columnas seguras
            show_cols = ['Timestamp', 'Module', 'Engine', 'Action', 'Régimen', 'Status']
            show_cols = [c for c in show_cols if c in df_log.columns] # Seguridad anticaídas
            if 'Trade_Exact_PnL' in df_log.columns:
                show_cols.append('Trade_Exact_PnL')

            st.dataframe(df_log[show_cols], use_container_width=True, hide_index=True, height=700)
        else:
            st.warning("No hay registros almacenados para esta fecha en específico.")
    else:
        st.error("El Dataset Maestro está vacío o no se pudo cargar.")
        st.info("💡 Solución: Haz clic en el botón '🔄 Forzar Recarga' en el menú de la izquierda.")