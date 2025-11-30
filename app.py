import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import feedparser
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN VISUAL "PRO FINTECH" (OSCURO & LIMPIO) ---
st.set_page_config(layout="wide", page_title="Wealth OS Pro", page_icon="🏛️", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;800&family=Roboto+Mono:wght@400;700&display=swap');
    
    /* FONDO Y TEXTO GENERAL */
    .stApp {
        background-color: #0e1117; /* Negro Profundo */
        color: #e0e0e0;
        font-family: 'Manrope', sans-serif;
    }
    
    /* TICKER TAPE (CINTA) */
    .ticker-wrap {
        width: 100%; overflow: hidden; background-color: #161b22;
        border-bottom: 1px solid #30363d; white-space: nowrap; padding: 10px 0;
    }
    .ticker-item {
        display: inline-block; padding: 0 20px; font-family: 'Roboto Mono', monospace;
        font-weight: bold; font-size: 14px; color: #8b949e;
    }
    .up { color: #3fb950; } .down { color: #f85149; }

    /* TARJETAS (CARDS) */
    .pro-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .pro-card:hover { border-color: #58a6ff; transform: translateY(-2px); }
    
    /* BADGES */
    .risk-badge {
        background: #21262d; color: #8b949e; padding: 4px 8px;
        border-radius: 4px; font-size: 11px; text-transform: uppercase; font-weight: bold;
        font-family: 'Roboto Mono', monospace;
    }
    
    /* TOP 3 HIGHLIGHT */
    .top-score { font-size: 28px; font-weight: 800; font-family: 'Roboto Mono'; }
    
    /* BOTONES */
    .stButton > button {
        background-color: #238636; /* Verde GitHub */
        color: white; border: none; border-radius: 6px; font-weight: 600;
        width: 100%; padding: 10px;
    }
    .stButton > button:hover { background-color: #2ea043; }
    
    /* NOTICIAS */
    .news-item {
        border-left: 3px solid #f78166; padding-left: 15px; margin-bottom: 15px;
    }
    .news-title { color: #e0e0e0; font-weight: 600; text-decoration: none; font-size: 15px; }
    .news-meta { color: #8b949e; font-size: 11px; text-transform: uppercase; margin-top: 4px; }
    
    /* ONBOARDING */
    .onboarding-box {
        background: #161b22; padding: 40px; border-radius: 20px;
        border: 1px solid #30363d; max-width: 600px; margin: 0 auto; text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE ESTADO ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'cash' not in st.session_state: st.session_state.cash = 10000.0
if 'profile' not in st.session_state: st.session_state.profile = None
if 'onboarding_complete' not in st.session_state: st.session_state.onboarding_complete = False

# --- 3. FUNCIONES DE DATOS ---

@st.cache_data(ttl=300)
def get_ticker_tape():
    tickers = ["SPY", "QQQ", "BTC-USD", "GLD", "EURUSD=X"]
    html = ""
    try:
        data = yf.download(tickers, period="1d", progress=False)['Close']
        for t in tickers:
            curr = data[t].iloc[-1]
            prev = data[t].iloc[0]
            delta = ((curr-prev)/prev)*100
            color = "up" if delta >=0 else "down"
            sym = "▲" if delta >=0 else "▼"
            html += f"<span class='ticker-item'>{t} {curr:.2f} <span class='{color}'>{sym} {delta:.2f}%</span></span>"
    except: html = "MARKET DATA OFFLINE"
    return html

@st.cache_data(ttl=3600)
def scan_top_opportunities():
    # Universo de ETFs seguros para novatos
    UNIVERSE = {
        'SPY': 'S&P 500', 'QQQ': 'Nasdaq 100', 'GLD': 'Oro', 
        'VWO': 'Emergentes', 'BND': 'Bonos', 'XLE': 'Energía'
    }
    data = []
    try:
        hist = yf.download(list(UNIVERSE.keys()), period="3mo", progress=False)['Close']
        for t in UNIVERSE:
            try:
                prices = hist[t].dropna()
                if len(prices) < 20: continue
                curr = prices.iloc[-1]
                prev = prices.iloc[-22]
                ret = ((curr-prev)/prev)*100
                vol = prices.pct_change().std() * np.sqrt(252)*100
                score = ret / (vol if vol > 0 else 1)
                
                # Consejo automático
                advice = "MOMENTUM ALCISTA" if ret > 3 else "ESTABLE/REFUGIO" if vol < 10 else "ALTA VOLATILIDAD"
                
                data.append({'Ticker': t, 'Name': UNIVERSE[t], 'Price': curr, 'Ret': ret, 'Vol': vol, 'Score': score, 'Advice': advice})
            except: continue
        return pd.DataFrame(data).sort_values(by='Score', ascending=False).head(3)
    except: return pd.DataFrame()

def get_news_rss():
    try:
        d = feedparser.parse("https://es.investing.com/rss/news_25.rss")
        return d.entries[:5]
    except: return []

def ai_oracle(portfolio, cash, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Contexto real
    news = [e.title for e in get_news_rss()[:3]]
    ptf_str = str(portfolio) if portfolio else "Sin inversiones"
    
    prompt = f"""
    Actúa como un Analista de Riesgos Senior (Stress Test).
    NOTICIAS DE HOY: {news}
    CARTERA USUARIO: {ptf_str}
    LIQUIDEZ: {cash}
    
    Genera 3 escenarios (Corto, Medio, Largo Plazo) en formato Markdown.
    Sé serio y realista.
    """
    return model.generate_content(prompt).text

def ai_audit(portfolio, profile, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    return model.generate_content(f"Audita esta cartera: {portfolio} para un perfil {profile}. Sé crítico.").text

# --- 4. FLUJO DE APLICACIÓN ---

# === FASE 1: ONBOARDING (TEST INICIAL) ===
if not st.session_state.onboarding_complete:
    st.markdown("<br><br>", unsafe_allow_html=True)
    with st.container():
        st.markdown(f"""
        <div class="onboarding-box">
            <h1>🏛️ Wealth OS Setup</h1>
            <p style="color:#8b949e;">Configurando terminal para nuevo inversor.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Preguntas simples
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown("### 1. Horizonte Temporal")
            horizon = st.select_slider("", ["Corto Plazo (<2 años)", "Medio (5 años)", "Largo (>10 años)"])
            
            st.markdown("### 2. Reacción ante caídas (-15%)")
            panic = st.radio("", ["Vendo todo (Stop Loss)", "Mantengo la calma", "Compro más (Oportunidad)"])
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("INICIAR SISTEMA"):
                score = 1 if "Vendo" in panic else 2 if "Mantengo" in panic else 3
                if "Largo" in horizon: score += 1
                
                st.session_state.profile = "Conservador 🛡️" if score <= 2 else "Equilibrado ⚖️" if score <= 3 else "Agresivo 🔥"
                st.session_state.onboarding_complete = True
                st.rerun()

# === FASE 2: PLATAFORMA PRINCIPAL ===
else:
    # HEADER: CINTA DE COTIZACIONES
    tape = get_ticker_tape()
    st.markdown(f"""
    <div class="ticker-wrap">
        <div style="display:inline-block; animation:marquee 30s linear infinite;">
            {tape} {tape} {tape}
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <style>
    @keyframes marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
    </style>
    """, unsafe_allow_html=True)

    # BARRA SUPERIOR
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1: st.title("Wealth OS Pro")
    with c2: st.metric("Perfil", st.session_state.profile)
    with c3: st.metric("Liquidez (Sim)", f"{st.session_state.cash:,.0f} €")
    
    # NAVEGACIÓN
    tab_market, tab_port, tab_search, tab_oracle = st.tabs(["📊 Mercado Hoy", "💼 Mi Cartera", "🔎 Explorador", "🔮 El Oráculo"])

    # --- PESTAÑA 1: DASHBOARD (LO QUE PIDES: TOP 3 + NOTICIAS) ---
    with tab_market:
        st.markdown("### ⚡ Oportunidades del Día (Algoritmo)")
        
        top_df = scan_top_opportunities()
        if not top_df.empty:
            cols = st.columns(3)
            for idx, row in top_df.iterrows():
                color = "#3fb950" if row['Ret'] > 0 else "#f85149"
                with cols[idx]:
                    st.markdown(f"""
                    <div class="pro-card">
                        <div style="display:flex; justify-content:space-between;">
                            <span style="font-size:20px; font-weight:bold;">{row['Ticker']}</span>
                            <span class="risk-badge">{row['Name']}</span>
                        </div>
                        <div class="top-score" style="color:{color}">{row['Ret']:.2f}%</div>
                        <div style="font-size:12px; color:#8b949e;">Momentum (1 Mes)</div>
                        <hr style="border-color:#30363d;">
                        <div style="font-size:13px; color:#e0e0e0;">💡 {row['Advice']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Simular Compra {row['Ticker']}", key=row['Ticker']):
                        if st.session_state.cash >= row['Price']:
                            st.session_state.portfolio.append({'Ticker': row['Ticker'], 'Shares': 1, 'AvgPrice': row['Price']})
                            st.session_state.cash -= row['Price']
                            st.toast(f"Orden Ejecutada: {row['Ticker']}", icon="✅")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("Saldo insuficiente")
        
        st.markdown("---")
        c_news, c_mood = st.columns([2, 1])
        
        with c_news:
            st.markdown("### 📰 Noticias Relevantes (Investing.com)")
            news = get_news_rss()
            if news:
                for n in news:
                    st.markdown(f"""
                    <div class="news-item">
                        <a href="{n.link}" target="_blank" class="news-title">{n.title}</a>
                        <div class="news-meta">FUENTE: INVESTING.COM • {datetime.now().strftime('%H:%M')}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info("Sin noticias recientes.")
            
        with c_mood:
            st.markdown("### 🛡️ Estado del Mercado")
            # Lógica simple de semáforo
            spy_ret = top_df.iloc[0]['Ret'] if not top_df.empty else 0
            if spy_ret > 2:
                st.success("MERCADO ALCISTA: Las condiciones son favorables para la inversión.")
            elif spy_ret < -2:
                st.error("ALTA VOLATILIDAD: Se recomienda precaución extrema.")
            else:
                st.warning("MERCADO LATERAL: Buscar oportunidades selectivas.")

    # --- PESTAÑA 2: SIMULADOR DE CARTERA ---
    with tab_port:
        c1, c2 = st.columns([2,1])
        with c1:
            st.markdown("### Tus Posiciones")
            if st.session_state.portfolio:
                df_p = pd.DataFrame(st.session_state.portfolio)
                # Cálculo de valor actual
                current_vals = []
                for p in st.session_state.portfolio:
                    try: 
                        curr = yf.Ticker(p['Ticker']).fast_info.last_price
                        current_vals.append(curr * p['Shares'])
                    except: current_vals.append(p['AvgPrice'] * p['Shares'])
                
                df_p['Valor Actual'] = current_vals
                st.dataframe(df_p, use_container_width=True)
                
                # Gráfico
                fig = go.Figure(data=[go.Pie(labels=df_p['Ticker'], values=df_p['Valor Actual'], hole=.3)])
                fig.update_layout(paper_bgcolor="#0e1117", font={'color': "white"})
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Cartera vacía. Ve al Mercado para comprar.")
            
        with c2:
            st.markdown("### Auditoría IA")
            api = st.text_input("API Key (Para Auditoría)", type="password")
            if st.button("Analizar Riesgos") and api:
                with st.spinner("Auditando..."):
                    res = ai_audit(st.session_state.portfolio, st.session_state.profile, api)
                    st.info(res)
            
            if st.button("🔴 Reiniciar Cartera"):
                st.session_state.portfolio = []
                st.session_state.cash = 10000.0
                st.rerun()

    # --- PESTAÑA 3: EXPLORADOR (BUSCADOR) ---
    with tab_search:
        st.markdown("### 🔎 Analizador de Activos")
        search = st.text_input("Ticker (Ej: TSLA, AAPL, SPY)", "").upper()
        if search:
            try:
                stock = yf.Ticker(search)
                info = stock.info
                st.metric(f"{info.get('shortName')}", f"{info.get('currentPrice')} {info.get('currency')}")
                st.line_chart(stock.history(period="1y")['Close'])
                st.write(info.get('longBusinessSummary'))
            except: st.error("Activo no encontrado")

    # --- PESTAÑA 4: EL ORÁCULO (PREDICCIONES) ---
    with tab_oracle:
        st.markdown("### 🔮 Simulador de Escenarios")
        st.caption("Proyección basada en noticias en tiempo real.")
        
        col_o1, col_o2 = st.columns([1, 2])
        with col_o1:
            api_oracle = st.text_input("API Key (Google)", type="password", key="oracle_key")
            if st.button("Ejecutar Simulación"):
                if not api_oracle: st.error("Falta API Key")
                else:
                    with st.spinner("Leyendo noticias y proyectando..."):
                        with col_o2:
                            res = ai_oracle(st.session_state.portfolio, st.session_state.cash, api_oracle)
                            st.markdown(res)
