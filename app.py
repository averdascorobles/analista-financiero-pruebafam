import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURACIÓN Y ESTÉTICA (APPLE STYLE) ---
# initial_sidebar_state="collapsed" -> Oculta la barra lateral por defecto para no liar
st.set_page_config(layout="wide", page_title="Wealth OS", page_icon="✨", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1d1d1f;
        background-color: #fbfbfd; /* Fondo gris Apple muy suave */
    }
    
    h1, h2, h3 { font-weight: 600; letter-spacing: -0.5px; }
    
    /* PANEL DE CONTROL (NUEVO) */
    .control-panel {
        background-color: white;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border: 1px solid #e5e5e5;
        margin-bottom: 30px;
    }
    
    /* Tarjetas de Métricas */
    .stMetric {
        background-color: #ffffff;
        border: 1px solid #e5e5e5;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.02);
    }
    
    /* Botón Principal Grande */
    .stButton > button {
        background-color: #000000;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 15px 30px;
        font-size: 16px;
        font-weight: 500;
        width: 100%;
        transition: transform 0.1s;
    }
    .stButton > button:hover {
        background-color: #333333;
        transform: scale(1.01);
    }
    
    /* Inputs más bonitos */
    .stSelectbox > div > div {
        background-color: #f5f5f7;
        border-radius: 8px;
        border: none;
    }
    .stTextInput > div > div > input {
        background-color: #f5f5f7;
        border-radius: 8px;
        border: none;
    }

    /* Noticias */
    .news-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1d1d1f;
        margin-bottom: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .news-source { font-size: 10px; color: #888; text-transform: uppercase; font-weight: bold; }
    .news-title { font-size: 15px; font-weight: 600; color: #111; margin: 6px 0; }
    .news-link { text-decoration: none; color: #007AFF; font-size: 12px; }
    
    .card-container {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. DATOS MAESTROS ---

DEFAULT_CORES = {
    "Conservador": {"Ticker": "BND", "Nombre": "Bonos Globales (Vanguard)", "Riesgo": "Bajo"},
    "Equilibrado": {"Ticker": "VTI", "Nombre": "Total Stock Market (Vanguard)", "Riesgo": "Medio"},
    "Agresivo": {"Ticker": "QQQ", "Nombre": "Nasdaq 100 (Tech)", "Riesgo": "Alto"}
}

POPULAR_MANUAL_CORES = {
    "S&P 500 (SPY)": "SPY",
    "MSCI World (URTH)": "URTH",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Euro Stoxx 50 (FEZ)": "FEZ",
    "Bonos Globales (BND)": "BND",
    "Oro Físico (GLD)": "GLD"
}

SATELLITE_UNIVERSE = {
    'GLD': 'Oro Físico',
    'VWO': 'Emergentes',
    'VEA': 'Europa/Pacífico',
    'XLE': 'Energía',
    'XLF': 'Financiero',
    'XLV': 'Salud',
    'SMH': 'Semiconductores',
    'VIG': 'Dividendos',
    'ARKK': 'Innovación',
    'TLT': 'Bonos 20+ Años',
    'IWM': 'Small Caps'
}

# --- 3. FUNCIONES LÓGICAS ---

def load_instructions():
    try:
        with open("Instrucciones.md", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Actúa como asesor financiero experto."

@st.cache_data(ttl=3600)
def scan_satellites():
    data = []
    tickers = list(SATELLITE_UNIVERSE.keys())
    history = yf.download(tickers, period="6mo", progress=False)['Close']
    
    for ticker in tickers:
        try:
            prices = history[ticker]
            if prices.empty: continue
            current = prices.iloc[-1]
            ret_1m = ((current - prices.iloc[-22]) / prices.iloc[-22]) * 100
            daily_ret = prices.pct_change().dropna()
            vol = daily_ret.std() * np.sqrt(252) * 100
            
            risk = "Equilibrado"
            if vol < 12: risk = "Conservador"
            elif vol > 25: risk = "Agresivo"
            
            score = ret_1m / vol if vol > 0 else 0
            
            data.append({
                'Ticker': ticker, 'Nombre': SATELLITE_UNIVERSE[ticker],
                'Precio': current, 'Retorno 1M': ret_1m,
                'Volatilidad': vol, 'Perfil': risk, 'Score': score
            })
        except: continue
    return pd.DataFrame(data).sort_values(by='Score', ascending=False)

def get_general_news():
    sources = ["SPY", "XLF", "^IXIC"] 
    news_feed = []
    seen = set()
    for t in sources:
        try:
            stock = yf.Ticker(t)
            latest = stock.news[:3]
            for n in latest:
                if n['link'] not in seen:
                    news_feed.append({'Title': n['title'], 'Link': n['link'], 'Publisher': n['publisher'], 'Time': n['providerPublishTime']})
                    seen.add(n['link'])
        except: continue
    return sorted(news_feed, key=lambda x: x['Time'], reverse=True)

def generate_advisor_report(profile, custom_core, top_satellites, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    instructions = load_instructions()
    satellites_txt = top_satellites[['Ticker', 'Nombre', 'Retorno 1M', 'Perfil']].to_string(index=False)
    prompt = f"{instructions}\nPERFIL: {profile}\nCORE ELEGIDO: {custom_core['Ticker']}\nTOP SATÉLITES:\n{satellites_txt}\nGenera estrategia."
    return model.generate_content(prompt).text

# --- 4. INTERFAZ PRINCIPAL (EL CAMBIO GRANDE) ---

st.title(f"Wealth OS")
st.caption(f"Inteligencia Financiera | {datetime.now().strftime('%d %B %Y')}")

# --- CONTENEDOR DE CONFIGURACIÓN (VISIBLE SIEMPRE) ---
# Usamos un expander que está ABIERTO por defecto la primera vez
with st.expander("👤 Configuración de Inversor (Haz clic para editar)", expanded=True):
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    
    col_key, col_prof = st.columns([2, 1])
    with col_key:
        api_key = st.text_input("🔑 Tu Clave de Acceso (Google API Key)", type="password", placeholder="Pega aquí tu sk-...")
    with col_prof:
        risk_profile = st.selectbox("Nivel de Riesgo", ["Conservador", "Equilibrado", "Agresivo"], index=1)
        
    st.markdown("---")
    st.markdown("**🎯 Tu Activo Base (Núcleo)**")
    
    col_rad, col_sel = st.columns([1, 2])
    with col_rad:
        core_mode = st.radio("Selección:", ["Automático (IA)", "Manual (Lista)"], label_visibility="collapsed")
    
    selected_core = None
    with col_sel:
        if core_mode == "Automático (IA)":
            suggestion = DEFAULT_CORES[risk_profile]
            st.info(f"Recomendado: **{suggestion['Ticker']}** - {suggestion['Nombre']}")
            selected_core = suggestion
        else:
            manual_choice = st.selectbox("Elige tu fondo actual:", list(POPULAR_MANUAL_CORES.keys()))
            manual_ticker = POPULAR_MANUAL_CORES[manual_choice]
            selected_core = {"Ticker": manual_ticker, "Nombre": manual_choice, "Riesgo": "Manual"}
            
    st.markdown('</div>', unsafe_allow_html=True)

# --- PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["📊 Estrategia", "🔮 Calculadora", "📰 Noticias"])

# --- PESTAÑA 1: ESTRATEGIA ---
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    # BOTÓN GRANDE Y CENTRAL
    if st.button("🚀 GENERAR PLAN DE INVERSIÓN AHORA", type="primary"):
        if not api_key:
            st.error("⚠️ Por favor, introduce la API Key en el panel de arriba.")
        else:
            with st.spinner(f"Analizando mercado para complementar {selected_core['Ticker']}..."):
                df_market = scan_satellites()
                if risk_profile == "Conservador":
                    df_filtered = df_market[df_market['Perfil'].isin(["Conservador", "Equilibrado"])]
                else:
                    df_filtered = df_market
                top_3 = df_filtered.head(3)
                report = generate_advisor_report(risk_profile, selected_core, top_3, api_key)
            
            # RESULTADOS
            col_core, col_txt = st.columns([1, 3])
            with col_core:
                st.metric("Tu Base", selected_core['Ticker'], "Núcleo")
            with col_txt:
                st.success(f"Estrategia generada para perfil **{risk_profile}**.")

            st.markdown("#### Oportunidades Satélite (Mes)")
            c1, c2, c3 = st.columns(3)
            for idx, (i, row) in enumerate(top_3.iterrows()):
                color = "#00C805" if row['Retorno 1M'] > 0 else "#FF3B30"
                with [c1, c2, c3][idx]:
                    st.markdown(f"""
                    <div class="card-container" style="border-top: 4px solid {color}; padding:15px; text-align:center;">
                        <h3>{row['Ticker']}</h3>
                        <p style="font-size:12px; color:#666;">{row['Nombre']}</p>
                        <h2 style="color:{color};">{row['Retorno 1M']:.1f}%</h2>
                    </div>
                    """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown(report)

# --- PESTAÑA 2: CALCULADORA ---
with tab2:
    col_inp, col_graph = st.columns([1, 2])
    with col_inp:
        ini = st.number_input("Capital Inicial (€)", 1000, 100000, 5000)
        mon = st.number_input("Aportación Mensual (€)", 100, 5000, 300)
        yrs = st.slider("Años", 5, 30, 15)
        r = st.slider("Interés Anual (%)", 2.0, 12.0, 7.0)
    with col_graph:
        months = yrs * 12
        val = [ini]
        for i in range(months):
            val.append(val[-1] * (1 + r/100/12) + mon)
        profit = val[-1] - (ini + mon*months)
        st.metric("Patrimonio Futuro", f"{val[-1]:,.0f} €", f"+{profit:,.0f} € Ganancia")
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=val, fill='tozeroy', line_color='#1d1d1f'))
        fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

# --- PESTAÑA 3: NOTICIAS ---
with tab3:
    st.caption("Titulares en tiempo real")
    if st.button("Actualizar Noticias"):
        news = get_general_news()
        col1, col2 = st.columns(2)
        for idx, n in enumerate(news):
            with col1 if idx % 2 == 0 else col2:
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-source">{n['Publisher']}</div>
                    <div class="news-title">{n['Title']}</div>
                    <a href="{n['Link']}" target="_blank" class="news-link">Leer más ↗</a>
                </div>
                """, unsafe_allow_html=True)
