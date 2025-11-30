import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import feedparser
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN VISUAL "CLEAN FINTECH" (BLANCO) ---
st.set_page_config(layout="wide", page_title="Wealth OS", page_icon="🏛️", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;800&display=swap');
    
    /* RESET GENERAL A MODO CLARO */
    .stApp {
        background-color: #ffffff;
        color: #111111;
        font-family: 'Manrope', sans-serif;
    }
    
    /* CINTA DE COTIZACIONES (Ticker Tape) */
    .ticker-wrap {
        width: 100%; overflow: hidden; background-color: #f3f4f6;
        border-bottom: 1px solid #e5e7eb; white-space: nowrap; padding: 10px 0;
    }
    .ticker-item {
        display: inline-block; padding: 0 20px; font-weight: bold; font-size: 14px; color: #374151;
    }
    .up { color: #16a34a; } .down { color: #dc2626; }

    /* TARJETAS (CARDS) CON SOMBRA SUAVE */
    .clean-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
        height: 100%;
    }
    .clean-card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05); }
    
    /* BADGES */
    .badge {
        background: #f3f4f6; color: #4b5563; padding: 4px 10px;
        border-radius: 20px; font-size: 11px; text-transform: uppercase; font-weight: 800;
        letter-spacing: 0.5px;
    }
    
    /* BOTONES */
    .stButton > button {
        background-color: #111827; /* Negro casi puro */
        color: white; border: none; border-radius: 8px; font-weight: 600;
        width: 100%; padding: 12px;
    }
    .stButton > button:hover { background-color: #374151; }
    
    /* NOTICIAS */
    .news-item {
        background: #f9fafb; border-left: 4px solid #2563eb;
        padding: 15px; border-radius: 8px; margin-bottom: 10px;
    }
    .news-title { color: #111; font-weight: 700; text-decoration: none; font-size: 15px; display: block; }
    .news-meta { color: #6b7280; font-size: 11px; text-transform: uppercase; margin-top: 5px; }
    
    /* ONBOARDING CENTRADO */
    .onboarding-box {
        background: white; padding: 40px; border-radius: 24px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        max-width: 600px; margin: 50px auto; text-align: center; border: 1px solid #e5e7eb;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE ESTADO ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'cash' not in st.session_state: st.session_state.cash = 10000.0
if 'profile' not in st.session_state: st.session_state.profile = None
if 'onboarding_complete' not in st.session_state: st.session_state.onboarding_complete = False

# --- 3. FUNCIONES ---

@st.cache_data(ttl=300)
def get_ticker_tape():
    """Cinta de cotizaciones rápida"""
    tickers = ["SPY", "QQQ", "BTC-USD", "GLD", "EURUSD=X"]
    html = ""
    try:
        data = yf.download(tickers, period="1d", progress=False)['Close']
        for t in tickers:
            try:
                curr = data[t].iloc[-1]
                prev = data[t].iloc[0]
                delta = ((curr-prev)/prev)*100
                color = "up" if delta >=0 else "down"
                sym = "▲" if delta >=0 else "▼"
                html += f"<span class='ticker-item'>{t} {curr:.2f} <span class='{color}'>{sym} {delta:.2f}%</span></span>"
            except: continue
    except: html = "<span class='ticker-item'>Conectando mercados...</span>"
    return html

@st.cache_data(ttl=3600)
def scan_top_opportunities():
    """Escáner robusto (Filtra errores para evitar el IndexError)"""
    UNIVERSE = {
        'SPY': 'S&P 500', 'QQQ': 'Nasdaq 100', 'GLD': 'Oro', 
        'VWO': 'Emergentes', 'BND': 'Bonos', 'XLE': 'Energía', 'XLV': 'Salud'
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
                
                advice = "ALCISTA" if ret > 2 else "REFUGIO" if vol < 10 else "VOLÁTIL"
                
                data.append({'Ticker': t, 'Name': UNIVERSE[t], 'Price': curr, 'Ret': ret, 'Vol': vol, 'Score': score, 'Advice': advice})
            except: continue
        
        # Devolver Top 3 asegurado
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()
        return df.sort_values(by='Score', ascending=False).head(3)
    except: return pd.DataFrame()

def get_news_rss():
    try:
        d = feedparser.parse("https://es.investing.com/rss/news_25.rss")
        return d.entries[:4]
    except: return []

def ai_oracle(portfolio, cash, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    news = [e.title for e in get_news_rss()[:3]]
    ptf_str = str(portfolio) if portfolio else "Cartera Vacía"
    prompt = f"Actúa como Analista Financiero. NOTICIAS: {news}. CARTERA: {ptf_str}. LIQUIDEZ: {cash}. Predice 3 escenarios (Corto/Medio/Largo plazo)."
    return model.generate_content(prompt).text

def ai_audit(portfolio, profile, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    return model.generate_content(f"Audita esta cartera: {portfolio} para perfil {profile}. Sé breve y crítico.").text

# --- 4. FLUJO DE APP ---

# === ONBOARDING (TEST INICIAL) ===
if not st.session_state.onboarding_complete:
    with st.container():
        st.markdown(f"""
        <div class="onboarding-box">
            <h1>🏛️ Configuración Inicial</h1>
            <p style="color:#6b7280;">Bienvenido a Wealth OS. Calibremos tu perfil.</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            # Preguntas
            st.markdown("##### 1. ¿Cuándo necesitarás el dinero?")
            horizon = st.select_slider("", ["Pronto (<2 años)", "Medio (5 años)", "Jubilación (>10 años)"])
            
            st.markdown("##### 2. Si la bolsa cae un 20% mañana...")
            panic = st.radio("", ["Vendo todo (Miedo)", "Espero quieto", "Compro más (Oportunidad)"])
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("CREAR PERFIL"):
                score = 1 if "Vendo" in panic else 2 if "Espero" in panic else 3
                if "Jubilación" in horizon: score += 1
                
                st.session_state.profile = "Conservador 🛡️" if score <= 2 else "Equilibrado ⚖️" if score <= 3 else "Agresivo 🔥"
                st.session_state.onboarding_complete = True
                st.rerun()

# === PLATAFORMA PRINCIPAL ===
else:
    # 1. CINTA DE PRECIOS
    tape = get_ticker_tape()
    st.markdown(f"""
    <div class="ticker-wrap">
        <div style="display:inline-block; animation:marquee 30s linear infinite;">
            {tape} {tape} {tape}
        </div>
    </div>
    <style>@keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}</style>
    """, unsafe_allow_html=True)

    # 2. CABECERA
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1: st.title("Wealth OS")
    with c2: st.metric("Perfil", st.session_state.profile)
    with c3: st.metric("Saldo (Sim)", f"{st.session_state.cash:,.0f} €")
    
    # 3. PESTAÑAS (TABS)
    tab_market, tab_port, tab_search, tab_oracle = st.tabs(["📊 Mercado Hoy", "💼 Mi Cartera", "🔎 Explorador", "🔮 El Oráculo"])

    # --- TAB 1: DASHBOARD ---
    with tab_market:
        st.markdown("### 🔥 Top 3 Oportunidades del Día")
        st.caption(f"Activos con mejor momentum para perfil {st.session_state.profile}")
        
        top_df = scan_top_opportunities()
        
        if not top_df.empty:
            # --- CORRECCIÓN DEL ERROR DE COLUMNAS ---
            # Creamos tantas columnas como filas tengamos (máximo 3)
            num_rows = len(top_df)
            cols = st.columns(num_rows)
            
            for i, (index, row) in enumerate(top_df.iterrows()):
                # Usamos 'i' (0, 1, 2) para acceder a la columna correcta
                color = "#16a34a" if row['Ret'] > 0 else "#dc2626"
                
                with cols[i]:
                    st.markdown(f"""
                    <div class="clean-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:24px; font-weight:800;">{row['Ticker']}</span>
                            <span class="badge">{row['Name']}</span>
                        </div>
                        <div style="font-size:32px; font-weight:700; color:{color}; margin:10px 0;">
                            {row['Ret']:.2f}%
                        </div>
                        <div style="color:#6b7280; font-size:12px; margin-bottom:15px;">Momentum (1 Mes)</div>
                        <div style="background:#f3f4f6; padding:8px; border-radius:8px; font-size:12px; font-weight:bold; text-align:center;">
                            💡 {row['Advice']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                    if st.button(f"Comprar {row['Ticker']}", key=f"btn_{row['Ticker']}"):
                        if st.session_state.cash >= row['Price']:
                            st.session_state.portfolio.append({'Ticker': row['Ticker'], 'Shares': 1, 'AvgPrice': row['Price']})
                            st.session_state.cash -= row['Price']
                            st.toast("Orden Completada", icon="✅")
                        else: st.error("Saldo insuficiente")
        else:
            st.info("Cargando datos de mercado... espera unos segundos.")
        
        st.markdown("---")
        
        # NOTICIAS
        c_news, c_mood = st.columns([2, 1])
        with c_news:
            st.markdown("### 📰 Noticias (Investing.com)")
            news = get_news_rss()
            if news:
                for n in news:
                    st.markdown(f"""
                    <div class="news-item">
                        <a href="{n.link}" target="_blank" class="news-title">{n.title}</a>
                        <div class="news-meta">Hace poco • Fuente Oficial</div>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info("Sin noticias RSS disponibles.")
            
        with c_mood:
            st.markdown("### 🛡️ Estado")
            spy_ret = top_df.iloc[0]['Ret'] if not top_df.empty else 0
            if spy_ret > 2:
                st.success("MERCADO FUERTE: Tendencia alcista clara.")
            elif spy_ret < -2:
                st.error("ALTA VOLATILIDAD: Precaución.")
            else:
                st.warning("MERCADO NEUTRO: Sin tendencia clara.")

    # --- TAB 2: CARTERA ---
    with tab_port:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Mis Posiciones")
            if st.session_state.portfolio:
                df_p = pd.DataFrame(st.session_state.portfolio)
                # Valoración en tiempo real
                vals = []
                for p in st.session_state.portfolio:
                    try: 
                        curr = yf.Ticker(p['Ticker']).fast_info.last_price
                        vals.append(curr * p['Shares'])
                    except: vals.append(p['AvgPrice'] * p['Shares'])
                df_p['Valor Actual'] = vals
                st.dataframe(df_p, use_container_width=True)
                
                # Gráfico
                fig = go.Figure(data=[go.Pie(labels=df_p['Ticker'], values=df_p['Valor Actual'], hole=.4)])
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Cartera vacía. Ve a 'Mercado Hoy' para comprar.")
            
        with c2:
            st.subheader("Auditor")
            api = st.text_input("API Key (Auditoría)", type="password")
            if st.button("Analizar Riesgos") and api:
                with st.spinner("Auditando..."):
                    res = ai_audit(st.session_state.portfolio, st.session_state.profile, api)
                    st.info(res)
            if st.button("Resetear Todo"):
                st.session_state.portfolio = []
                st.session_state.cash = 10000.0
                st.rerun()

    # --- TAB 3: EXPLORADOR ---
    with tab_search:
        st.subheader("Buscador de Activos")
        search = st.text_input("Ticker (Ej: AAPL, TSLA)", "").upper()
        if search:
            try:
                stock = yf.Ticker(search)
                info = stock.info
                st.metric(info.get('shortName'), f"{info.get('currentPrice')} {info.get('currency')}")
                st.line_chart(stock.history(period="6mo")['Close'])
                st.write(info.get('longBusinessSummary'))
            except: st.error("No encontrado")

    # --- TAB 4: ORÁCULO ---
    with tab_oracle:
        st.subheader("Predicción de Escenarios")
        st.caption("Basado en noticias reales de hoy.")
        api_oracle = st.text_input("API Key (Google)", type="password", key="oracle")
        if st.button("Simular Futuro") and api_oracle:
            with st.spinner("Consultando oráculo..."):
                res = ai_oracle(st.session_state.portfolio, st.session_state.cash, api_oracle)
                st.markdown(res)
