import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURACIÓN Y ESTÉTICA PREMIUM ---
st.set_page_config(layout="wide", page_title="Wealth OS", page_icon="✨")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1d1d1f;
    }
    
    /* Títulos y Cabeceras */
    h1, h2, h3 { font-weight: 600; letter-spacing: -0.5px; }
    
    /* Tarjetas de Métricas */
    .stMetric {
        background-color: #ffffff;
        border: 1px solid #e5e5e5;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    
    /* Botones Premium */
    .stButton > button {
        background-color: #000000;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: #333333;
        transform: scale(1.01);
    }
    
    /* Tarjetas de Noticias (Nuevo) */
    .news-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #007AFF;
        margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .news-source { font-size: 11px; color: #888; text-transform: uppercase; font-weight: bold; }
    .news-title { font-size: 15px; font-weight: 600; color: #333; margin: 5px 0; }
    .news-link { text-decoration: none; color: #007AFF; font-size: 12px; }
    
    /* Contenedores de Activos */
    .card-container {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
    }
    .risk-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        background: #f5f5f7;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. UNIVERSO DE DATOS ---

CORE_ASSETS = {
    "Conservador": {"Ticker": "BND", "Nombre": "Bonos Totales (Vanguard)", "Riesgo": "Bajo"},
    "Equilibrado": {"Ticker": "VTI", "Nombre": "Total Stock Market (Vanguard)", "Riesgo": "Medio"},
    "Agresivo": {"Ticker": "QQQ", "Nombre": "Nasdaq 100 (Invesco)", "Riesgo": "Alto"}
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
    'SPY': 'S&P 500',
    'DIA': 'Dow Jones'
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
    """Escaneo para Estrategia (Mensual)"""
    data = []
    tickers = list(SATELLITE_UNIVERSE.keys())
    # Descargamos historial para volatilidad
    history = yf.download(tickers, period="6mo", progress=False)['Close']
    
    for ticker in tickers:
        try:
            prices = history[ticker]
            if prices.empty: continue
            
            current_price = prices.iloc[-1]
            ret_1m = ((current_price - prices.iloc[-22]) / prices.iloc[-22]) * 100
            
            daily_ret = prices.pct_change().dropna()
            vol = daily_ret.std() * np.sqrt(252) * 100
            
            risk_label = "Equilibrado"
            if vol < 12: risk_label = "Conservador"
            elif vol > 25: risk_label = "Agresivo"
            
            score = ret_1m / vol if vol > 0 else 0
            
            data.append({
                'Ticker': ticker,
                'Nombre': SATELLITE_UNIVERSE[ticker],
                'Precio': current_price,
                'Retorno 1M': ret_1m,
                'Volatilidad': vol,
                'Perfil': risk_label,
                'Score': score
            })
        except: continue
        
    return pd.DataFrame(data).sort_values(by='Score', ascending=False)

def get_market_pulse():
    """Escaneo Rápido para Dashboard (Diario)"""
    tickers = list(SATELLITE_UNIVERSE.keys())
    # Descargamos solo últimos 5 días para ver la tendencia inmediata
    data = yf.download(tickers, period="5d", progress=False)['Close']
    
    pulse_data = []
    for ticker in tickers:
        try:
            prices = data[ticker]
            if prices.empty: continue
            
            current = prices.iloc[-1]
            prev = prices.iloc[-2]
            change_pct = ((current - prev) / prev) * 100
            
            pulse_data.append({
                'Ticker': ticker,
                'Nombre': SATELLITE_UNIVERSE[ticker],
                'Precio': current,
                'Cambio Diario': change_pct
            })
        except: continue
        
    return pd.DataFrame(pulse_data).sort_values(by='Cambio Diario', ascending=False)

def get_top_news(tickers_list):
    """Busca noticias SOLO de los tickers Top"""
    news_feed = []
    for t in tickers_list:
        try:
            stock = yf.Ticker(t)
            latest = stock.news[:2] # Cogemos las 2 más recientes de cada uno
            for n in latest:
                news_feed.append({
                    'Ticker': t,
                    'Title': n['title'],
                    'Link': n['link'],
                    'Publisher': n['publisher'],
                    'Time': n['providerPublishTime']
                })
        except: continue
    return news_feed

def generate_advisor_report(profile, portfolio, core_asset, top_satellites, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    instructions = load_instructions()
    
    satellites_txt = top_satellites[['Ticker', 'Nombre', 'Retorno 1M', 'Perfil']].to_string(index=False)
    
    prompt = f"""
    {instructions}
    PERFIL: {profile} | CARTERA ACTUAL: {portfolio}
    CORE SUGERIDO: {core_asset['Ticker']}
    OPORTUNIDADES:
    {satellites_txt}
    Genera informe markdown.
    """
    return model.generate_content(prompt).text

# --- 4. INTERFAZ SIDEBAR ---

with st.sidebar:
    st.header("Wealth OS")
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    st.subheader("Configuración Personal")
    risk_profile = st.selectbox("Perfil de Riesgo", ["Conservador", "Equilibrado", "Agresivo"], index=1)
    
    current_portfolio = st.multiselect(
        "¿Qué tienes ya en cartera?",
        list(CORE_ASSETS.keys()) + list(SATELLITE_UNIVERSE.keys()) + ["S&P500", "Bitcoin"],
        default=[]
    )
    st.info("El sistema usará estos datos para personalizar tu estrategia.")

# --- 5. CUERPO PRINCIPAL (TABS) ---

st.title(f"Panel de Control")
st.markdown(f"**{datetime.now().strftime('%d %B %Y')}**")

# AÑADIMOS LA TERCERA PESTAÑA AQUÍ
tab1, tab2, tab3 = st.tabs(["📊 Estrategia Personal", "🔮 Calculadora", "⚡ Radar de Mercado"])

# --- PESTAÑA 1: ESTRATEGIA (CORE & SATELLITE) ---
with tab1:
    st.markdown("### Generador de Estrategia Activa")
    if st.button("🧠 Analizar Cartera", use_container_width=True, type="primary"):
        if not api_key:
            st.error("Falta API Key")
        else:
            with st.spinner("Procesando datos de mercado..."):
                my_core = CORE_ASSETS[risk_profile]
                df_market = scan_satellites()
                
                # Filtro de seguridad
                if risk_profile == "Conservador":
                    df_filtered = df_market[df_market['Perfil'].isin(["Conservador", "Equilibrado"])]
                else:
                    df_filtered = df_market
                
                top_3 = df_filtered.head(3)
                report = generate_advisor_report(risk_profile, current_portfolio, my_core, top_3, api_key)
            
            # MOSTRAR RESULTADOS
            col_core, col_txt = st.columns([1, 3])
            with col_core:
                st.metric("Tu Base (Core)", my_core['Ticker'], "Seguridad")
            with col_txt:
                st.info(f"**{my_core['Nombre']}**: {my_core['Riesgo']}. Base sólida para tu perfil.")

            st.markdown("#### Oportunidades Satélite (Mes)")
            c1, c2, c3 = st.columns(3)
            for idx, (i, row) in enumerate(top_3.iterrows()):
                color = "#00C805" if row['Retorno 1M'] > 0 else "#FF3B30"
                with [c1, c2, c3][idx]:
                    st.markdown(f"""
                    <div class="card-container" style="border-top: 4px solid {color}; padding:15px;">
                        <h4>{row['Ticker']}</h4>
                        <p style="font-size:12px; color:#666;">{row['Nombre']}</p>
                        <h2 style="color:{color};">{row['Retorno 1M']:.1f}%</h2>
                    </div>
                    """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown(report)

# --- PESTAÑA 2: CALCULADORA ---
with tab2:
    st.header("Simulador de Interés Compuesto")
    col_inp, col_graph = st.columns([1, 2])
    
    with col_inp:
        ini = st.number_input("Capital Inicial", 1000, 100000, 5000)
        mon = st.number_input("Aportación Mensual", 100, 5000, 300)
        yrs = st.slider("Años", 5, 30, 15)
        r = st.slider("Interés Anual (%)", 2.0, 12.0, 7.0)
    
    with col_graph:
        months = yrs * 12
        val = [ini]
        for i in range(months):
            val.append(val[-1] * (1 + r/100/12) + mon)
        
        profit = val[-1] - (ini + mon*months)
        st.metric("Patrimonio Futuro", f"{val[-1]:,.0f} €", f"+{profit:,.0f} € Beneficio")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=val, fill='tozeroy', line_color='#007AFF', name='Capital Total'))
        fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

# --- PESTAÑA 3: RADAR DE MERCADO (NUEVO) ---
with tab3:
    st.markdown("### 🔥 Top Movers (Tiempo Real)")
    st.caption("Los ETFs de tu universo que mejor se están comportando HOY.")
    
    # Lógica del Dashboard
    if not api_key:
        st.warning("Introduce tu API Key para ver el radar.")
    else:
        with st.spinner("Escaneando movimientos diarios..."):
            # 1. Obtener Datos
            daily_df = get_market_pulse()
            top_movers = daily_df.head(4) # Los 4 mejores
            
            # 2. Mostrar Tarjetas Top
            cols = st.columns(4)
            for idx, (i, row) in enumerate(top_movers.iterrows()):
                delta = row['Cambio Diario']
                color = "normal" if delta > 0 else "inverse"
                cols[idx].metric(row['Ticker'], f"{row['Precio']:.2f}", f"{delta:.2f}%", delta_color=color)
            
            st.markdown("---")
            st.markdown("### 📰 Noticias Relevantes (Fuentes Fiables)")
            
            # 3. Obtener Noticias de esos Top Movers
            news = get_top_news(top_movers['Ticker'].tolist())
            
            # Mostrar Noticias estilo Feed
            for n in news:
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-source">{n['Publisher']} • {n['Ticker']}</div>
                    <div class="news-title">{n['Title']}</div>
                    <a href="{n['Link']}" target="_blank" class="news-link">Leer noticia completa en fuente original ↗</a>
                </div>
                """, unsafe_allow_html=True)
            
            if not news:
                st.info("No hay noticias urgentes en las últimas horas para estos activos.")
