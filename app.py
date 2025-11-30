import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import feedparser
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN VISUAL "TERMINAL PRO" ---
st.set_page_config(layout="wide", page_title="TERMINAL v1.0", page_icon="📈", initial_sidebar_state="collapsed")

# CSS AGRESIVO PARA CAMBIAR TODO EL LOOK A MODO TERMINAL
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
    
    /* FONDO NEGRO PROFUNDO */
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    
    /* TIPOGRAFÍA TÉCNICA */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .mono {
        font-family: 'Roboto Mono', monospace;
    }
    
    /* TICKER TAPE (CINTA DE COTIZACIONES) */
    .ticker-wrap {
        width: 100%;
        overflow: hidden;
        background-color: #161b22;
        border-bottom: 1px solid #30363d;
        white-space: nowrap;
        padding: 8px 0;
        margin-bottom: 20px;
    }
    .ticker {
        display: inline-block;
        animation: marquee 30s linear infinite;
    }
    @keyframes marquee {
        0% { transform: translateX(100%); }
        100% { transform: translateX(-100%); }
    }
    .ticker-item {
        display: inline-block;
        padding: 0 20px;
        font-family: 'Roboto Mono', monospace;
        font-weight: bold;
        font-size: 14px;
    }
    .up { color: #00ff41; }
    .down { color: #ff3b30; }

    /* TARJETAS ESTILO BLOOMBERG */
    .terminal-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 4px; /* Bordes más rectos */
        padding: 20px;
        margin-bottom: 15px;
    }
    .terminal-header {
        border-bottom: 1px solid #30363d;
        padding-bottom: 10px;
        margin-bottom: 15px;
        color: #8b949e;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* METRICAS NEÓN */
    .big-number {
        font-family: 'Roboto Mono', monospace;
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
    }
    .highlight-orange { color: #ff9900; } /* Bloomberg Orange */
    
    /* NOTICIAS TELETYPE */
    .news-item {
        border-left: 2px solid #ff9900;
        padding-left: 10px;
        margin-bottom: 12px;
        font-family: 'Roboto Mono', monospace;
        font-size: 13px;
    }
    .news-time { color: #ff9900; font-weight: bold; margin-right: 5px; }
    
    /* BOTONES INDUSTRIALES */
    .stButton > button {
        background-color: #21262d;
        color: #58a6ff;
        border: 1px solid #30363d;
        border-radius: 4px;
        font-family: 'Roboto Mono', monospace;
        font-weight: bold;
        text-transform: uppercase;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background-color: #30363d;
        border-color: #8b949e;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. LÓGICA DE NEGOCIO (IGUAL DE POTENTE) ---

# Tickers Clave para la cinta
TICKER_TAPE_LIST = ["SPY", "QQQ", "GLD", "BTC-USD", "EURUSD=X", "VWO", "BND"]

ETF_UNIVERSE = {
    'SPY': {'Nombre': 'S&P 500 MARKET', 'Desc': 'US LARGE CAP BLEND'},
    'QQQ': {'Nombre': 'NASDAQ 100', 'Desc': 'US TECH / GROWTH'},
    'GLD': {'Nombre': 'GOLD BULLION', 'Desc': 'COMMODITY / HEDGE'},
    'VWO': {'Nombre': 'EMERGING MKTS', 'Desc': 'HIGH RISK / GROWTH'},
    'VEA': {'Nombre': 'DEVELOPED MKTS', 'Desc': 'EX-US EQUITY'},
    'BND': {'Nombre': 'TOTAL BOND MKT', 'Desc': 'FIXED INCOME'},
    'XLE': {'Nombre': 'ENERGY SELECT', 'Desc': 'OIL & GAS SECTOR'},
    'XLV': {'Nombre': 'HEALTH CARE', 'Desc': 'PHARMA / BIOTECH'}
}

if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'cash' not in st.session_state: st.session_state.cash = 10000.0

@st.cache_data(ttl=300) # Cache 5 min
def get_ticker_tape_data():
    """Datos rápidos para la cinta de arriba"""
    data_str = ""
    try:
        tickers = yf.download(TICKER_TAPE_LIST, period="1d", progress=False)['Close']
        for t in TICKER_TAPE_LIST:
            try:
                price = tickers[t].iloc[-1]
                prev = tickers[t].iloc[0] # Apertura aprox
                delta = ((price - prev)/prev)*100
                color_class = "up" if delta >= 0 else "down"
                symbol = "▲" if delta >= 0 else "▼"
                data_str += f"<span class='ticker-item'>{t} {price:.2f} <span class='{color_class}'>{symbol} {delta:.2f}%</span></span>"
            except: continue
    except: 
        data_str = "<span class='ticker-item'>SYSTEM_OFFLINE_RETRYING...</span>"
    return data_str

@st.cache_data(ttl=3600)
def analyze_market_system():
    """Análisis Técnico de Mercado"""
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="6mo")
        current = hist['Close'].iloc[-1]
        ma_200 = hist['Close'].mean() 
        daily_ret = hist['Close'].pct_change()
        vol = daily_ret.std() * np.sqrt(252) * 100
        
        status = "BULLISH" if current > ma_200 else "BEARISH"
        risk = "HIGH" if vol > 20 else "NORMAL"
        return status, risk, vol
    except: return "N/A", "N/A", 0

@st.cache_data(ttl=3600)
def scan_opportunities():
    data = []
    tickers = list(ETF_UNIVERSE.keys())
    try:
        history = yf.download(tickers, period="3mo", progress=False)['Close']
        for ticker in tickers:
            try:
                prices = history[ticker].dropna()
                if len(prices) < 20: continue
                curr = prices.iloc[-1]
                prev = prices.iloc[-22]
                ret_1m = ((curr - prev) / prev) * 100
                vol = prices.pct_change().std() * np.sqrt(252) * 100
                score = ret_1m / (vol if vol > 0 else 1)
                
                # Generar señal técnica
                signal = "BUY" if ret_1m > 2 else "HOLD" if ret_1m > -2 else "SELL"
                
                data.append({'Ticker': ticker, 'Info': ETF_UNIVERSE[ticker], 'Price': curr, 'Ret': ret_1m, 'Vol': vol, 'Score': score, 'Signal': signal})
            except: continue
        return pd.DataFrame(data).sort_values(by='Score', ascending=False).head(3)
    except: return pd.DataFrame()

def get_terminal_news():
    try:
        rss_url = "https://es.investing.com/rss/news_25.rss"
        feed = feedparser.parse(rss_url)
        return feed.entries[:6]
    except: return []

# --- 3. INTERFAZ TIPO TERMINAL ---

# 1. CINTA DE COTIZACIONES (HEADER)
tape_html = get_ticker_tape_data()
st.markdown(f"""
<div class="ticker-wrap">
    <div class="ticker">
        {tape_html} {tape_html} </div>
</div>
""", unsafe_allow_html=True)

# 2. STATUS BAR (DATOS MACRO)
m_status, m_risk, m_vol = analyze_market_system()
col_sys1, col_sys2, col_sys3, col_sys4 = st.columns(4)

with col_sys1:
    st.markdown(f"""<div style="font-family:'Roboto Mono'; font-size:12px; color:#888;">SYSTEM DATE</div><div style="color:white; font-weight:bold;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>""", unsafe_allow_html=True)
with col_sys2:
    color = "#00ff41" if m_status == "BULLISH" else "#ff3b30"
    st.markdown(f"""<div style="font-family:'Roboto Mono'; font-size:12px; color:#888;">MARKET TREND</div><div style="color:{color}; font-weight:bold;">● {m_status}</div>""", unsafe_allow_html=True)
with col_sys3:
    color = "#ff9900" if m_risk == "HIGH" else "#00ff41"
    st.markdown(f"""<div style="font-family:'Roboto Mono'; font-size:12px; color:#888;">VOLATILITY IDX</div><div style="color:{color}; font-weight:bold;">{m_vol:.2f}% ({m_risk})</div>""", unsafe_allow_html=True)
with col_sys4:
    st.markdown(f"""<div style="font-family:'Roboto Mono'; font-size:12px; color:#888;">USER SESSION</div><div style="color:#58a6ff; font-weight:bold;">GUEST_ADMIN</div>""", unsafe_allow_html=True)

st.markdown("---")

# 3. CUERPO PRINCIPAL (GRID)
col_main, col_news = st.columns([2, 1])

with col_main:
    st.markdown("### ⚡ ALGORITHMIC OPPORTUNITIES (TOP 3)")
    
    top_df = scan_opportunities()
    
    if not top_df.empty:
        for idx, row in top_df.iterrows():
            # Color lógico para terminal
            signal_color = "#00ff41" if row['Signal'] == "BUY" else "#ff9900"
            ret_color = "up" if row['Ret'] >= 0 else "down"
            ret_sym = "+" if row['Ret'] >= 0 else ""
            
            st.markdown(f"""
            <div class="terminal-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span class="big-number highlight-orange">{row['Ticker']}</span>
                        <span style="font-family:'Roboto Mono'; color:#8b949e; margin-left:10px;">{row['Info']['Nombre']}</span>
                    </div>
                    <div style="text-align:right;">
                        <div class="big-number {ret_color}">{ret_sym}{row['Ret']:.2f}%</div>
                        <div style="font-size:11px; color:#888;">1M MOMENTUM</div>
                    </div>
                </div>
                <div style="margin-top:10px; display:flex; justify-content:space-between; border-top:1px solid #30363d; padding-top:10px;">
                    <div style="font-family:'Roboto Mono'; font-size:12px; color:#8b949e;">
                        VOL: {row['Vol']:.2f}% | SCORE: {row['Score']:.2f}
                    </div>
                    <div style="font-family:'Roboto Mono'; font-weight:bold; color:{signal_color}; border:1px solid {signal_color}; padding:2px 8px; border-radius:2px;">
                        SIGNAL: {row['Signal']}
                    </div>
                </div>
                <div style="margin-top:10px; font-size:12px; color:#ccc;">
                    Strategy: {row['Info']['Desc']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Botón de acción integrado en el flujo
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button(f"EXECUTE {row['Ticker']}", key=row['Ticker']):
                    st.toast(f"ORDER SENT: BUY {row['Ticker']} @ MKT PRICE", icon="✅")
                    # Lógica de cartera ficticia aquí
    else:
        st.info("INITIALIZING DATA FEEDS... PLEASE WAIT.")

with col_news:
    st.markdown("### 📰 NEWS WIRE (REAL-TIME)")
    st.markdown("<div class='terminal-card'>", unsafe_allow_html=True)
    
    news = get_terminal_news()
    if news:
        for n in news:
            time_str = datetime(*n.published_parsed[:6]).strftime('%H:%M')
            st.markdown(f"""
            <div class="news-item">
                <span class="news-time">[{time_str}]</span>
                <a href="{n.link}" target="_blank" style="color:#e0e0e0; text-decoration:none;">{n.title}</a>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("NO SIGNAL.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Mini Calculadora Rápida en Sidebar
    st.markdown("### 🧮 QUICK CALC")
    with st.container(border=True):
        inv = st.number_input("CAPITAL", value=10000, label_visibility="collapsed")
        st.caption("EST. ANNUAL YIELD (7%)")
        res = inv * 1.07
        st.markdown(f"<div class='big-number'>{res:,.0f} €</div>", unsafe_allow_html=True)

# 4. FOOTER TÉCNICO
st.markdown("---")
st.markdown("""
<div style="text-align:center; font-family:'Roboto Mono'; font-size:10px; color:#555;">
    TERMINAL ID: W-OS-9921 • LATENCY: 24ms • DATA SOURCE: YFINANCE/RSS • SECURE CONNECTION
</div>
""", unsafe_allow_html=True)
