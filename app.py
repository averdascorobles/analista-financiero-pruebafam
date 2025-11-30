import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import feedparser
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN VISUAL "CLEAN FINTECH" ---
st.set_page_config(layout="wide", page_title="Wealth OS", page_icon="🏛️", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;800&display=swap');
    
    .stApp { background-color: #ffffff; color: #111111; font-family: 'Manrope', sans-serif; }
    
    /* CINTA */
    .ticker-wrap { width: 100%; overflow: hidden; background-color: #f3f4f6; border-bottom: 1px solid #e5e7eb; white-space: nowrap; padding: 10px 0; }
    .ticker-item { display: inline-block; padding: 0 20px; font-weight: bold; font-size: 14px; color: #374151; }
    .up { color: #16a34a; } .down { color: #dc2626; }

    /* TARJETAS */
    .clean-card { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); transition: transform 0.2s; height: 100%; }
    .clean-card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05); }
    
    /* BADGES & SUGERENCIAS */
    .badge { background: #f3f4f6; color: #4b5563; padding: 4px 10px; border-radius: 20px; font-size: 11px; text-transform: uppercase; font-weight: 800; }
    .suggestion-btn {
        background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 12px; padding: 10px; 
        text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 10px;
    }
    .suggestion-btn:hover { border-color: #2563eb; background: #eff6ff; }
    .sug-ticker { font-weight: 800; font-size: 14px; display: block; }
    .sug-name { font-size: 11px; color: #6b7280; }

    /* BOTONES */
    .stButton > button { background-color: #111827; color: white; border: none; border-radius: 8px; font-weight: 600; width: 100%; padding: 12px; }
    .stButton > button:hover { background-color: #374151; }
    
    /* ADD BOX */
    .add-box { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 12px; padding: 20px; }

    /* NOTICIAS */
    .news-item { background: #f9fafb; border-left: 4px solid #2563eb; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .news-title { color: #111; font-weight: 700; text-decoration: none; font-size: 15px; display: block; }
    .news-meta { color: #6b7280; font-size: 11px; text-transform: uppercase; margin-top: 5px; }
    
    /* ONBOARDING */
    .onboarding-box { background: white; padding: 40px; border-radius: 24px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1); max-width: 600px; margin: 50px auto; text-align: center; border: 1px solid #e5e7eb; }
</style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE ESTADO ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'cash' not in st.session_state: st.session_state.cash = 10000.0
if 'profile' not in st.session_state: st.session_state.profile = None
if 'onboarding_complete' not in st.session_state: st.session_state.onboarding_complete = False
# Nuevo: para guardar la búsqueda cuando haces clic en sugerencias
if 'search_query' not in st.session_state: st.session_state.search_query = ""

# --- 3. FUNCIONES ---

@st.cache_data(ttl=300)
def get_ticker_tape():
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
    prompt = f"Analista Financiero Senior. NOTICIAS HOY: {news}. CARTERA: {ptf_str}. LIQUIDEZ: {cash}. Predice 3 escenarios (Corto/Medio/Largo)."
    return model.generate_content(prompt).text

def ai_audit(portfolio, profile, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    return model.generate_content(f"Audita esta cartera: {portfolio} para perfil {profile}. Sé breve y crítico.").text

# --- 4. FLUJO DE APP ---

# === ONBOARDING ===
if not st.session_state.onboarding_complete:
    with st.container():
        st.markdown(f"""<div class="onboarding-box"><h1>🏛️ Wealth OS</h1><p style="color:#6b7280;">Configuración Inicial</p></div>""", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            horizon = st.select_slider("Horizonte", ["Corto (<2 años)", "Medio (5 años)", "Largo (>10 años)"])
            panic = st.radio("Si cae 20%...", ["Vendo todo", "Espero", "Compro más"])
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("COMENZAR"):
                score = 1 if "Vendo" in panic else 2 if "Espero" in panic else 3
                if "Largo" in horizon: score += 1
                st.session_state.profile = "Conservador 🛡️" if score <= 2 else "Equilibrado ⚖️" if score <= 3 else "Agresivo 🔥"
                st.session_state.onboarding_complete = True
                st.rerun()

# === PLATAFORMA PRINCIPAL ===
else:
    tape = get_ticker_tape()
    st.markdown(f"""<div class="ticker-wrap"><div style="display:inline-block; animation:marquee 30s linear infinite;">{tape} {tape} {tape}</div></div><style>@keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}</style>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([3, 1, 1])
    with c1: st.title("Wealth OS")
    with c2: st.metric("Perfil", st.session_state.profile)
    with c3: st.metric("Saldo", f"{st.session_state.cash:,.0f} €")
    
    tab_market, tab_port, tab_search, tab_oracle = st.tabs(["📊 Mercado Hoy", "💼 Mi Cartera", "🔎 Explorador", "🔮 El Oráculo"])

    # --- TAB 1: MERCADO ---
    with tab_market:
        st.markdown("### 🔥 Top 3 Oportunidades")
        top_df = scan_top_opportunities()
        if not top_df.empty:
            num_rows = len(top_df)
            cols = st.columns(num_rows)
            for i, (index, row) in enumerate(top_df.iterrows()):
                color = "#16a34a" if row['Ret'] > 0 else "#dc2626"
                with cols[i]:
                    st.markdown(f"""
                    <div class="clean-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:24px; font-weight:800;">{row['Ticker']}</span>
                            <span class="badge">{row['Name']}</span>
                        </div>
                        <div style="font-size:32px; font-weight:700; color:{color}; margin:10px 0;">{row['Ret']:.2f}%</div>
                        <div style="background:#f3f4f6; padding:8px; border-radius:8px; font-size:12px; font-weight:bold; text-align:center;">💡 {row['Advice']}</div>
                    </div>""", unsafe_allow_html=True)
                    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                    if st.button(f"Comprar {row['Ticker']}", key=f"btn_{row['Ticker']}"):
                        if st.session_state.cash >= row['Price']:
                            st.session_state.portfolio.append({'Ticker': row['Ticker'], 'Shares': 1, 'AvgPrice': row['Price']})
                            st.session_state.cash -= row['Price']
                            st.toast("Orden Completada", icon="✅")
                        else: st.error("Saldo insuficiente")
        else: st.info("Cargando mercado...")
        
        st.markdown("---")
        c_news, c_mood = st.columns([2, 1])
        with c_news:
            st.markdown("### 📰 Noticias")
            news = get_news_rss()
            if news:
                for n in news:
                    st.markdown(f"""<div class="news-item"><a href="{n.link}" target="_blank" class="news-title">{n.title}</a><div class="news-meta">Fuente Oficial</div></div>""", unsafe_allow_html=True)
        with c_mood:
            st.markdown("### 🛡️ Estado")
            spy_ret = top_df.iloc[0]['Ret'] if not top_df.empty else 0
            if spy_ret > 2: st.success("ALCISTA")
            elif spy_ret < -2: st.error("VOLÁTIL")
            else: st.warning("NEUTRO")

    # --- TAB 2: MI CARTERA (MEJORADA) ---
    with tab_port:
        col_view, col_add = st.columns([3, 1])
        
        # IZQUIERDA: VISUALIZACIÓN
        with col_view:
            st.subheader("📊 Resumen de Activos")
            if st.session_state.portfolio:
                df_p = pd.DataFrame(st.session_state.portfolio)
                vals = []
                for p in st.session_state.portfolio:
                    try: curr = yf.Ticker(p['Ticker']).fast_info.last_price
                    except: curr = p['AvgPrice']
                    vals.append(curr * p['Shares'])
                df_p['Valor Actual'] = vals
                
                # KPIs
                k1, k2, k3 = st.columns(3)
                total_val = sum(vals)
                pnl = total_val - sum([p['Shares']*p['AvgPrice'] for p in st.session_state.portfolio])
                k1.metric("Valor Total", f"{total_val:,.2f} €")
                k2.metric("Beneficio/Pérdida", f"{pnl:,.2f} €", delta_color="normal")
                k3.metric("Activos", len(df_p))
                
                st.dataframe(df_p, use_container_width=True)
                fig = go.Figure(data=[go.Pie(labels=df_p['Ticker'], values=df_p['Valor Actual'], hole=.4)])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tu cartera está vacía. Usa el panel de la derecha para añadir activos manualmente.")

        # DERECHA: AÑADIR MANUAL (LO QUE PEDISTE)
        with col_add:
            st.markdown('<div class="add-box">', unsafe_allow_html=True)
            st.markdown("### ➕ Añadir Manual")
            st.caption("Si ya compraste algo en tu banco, regístralo aquí.")
            
            with st.form("manual_add"):
                m_ticker = st.text_input("Ticker (Ej: VOO, SAN.MC)").upper()
                m_qty = st.number_input("Cantidad", 1, 10000, 1)
                m_price = st.number_input("Precio de Compra (€)", 0.0, 100000.0, 100.0)
                
                if st.form_submit_button("Registrar Operación"):
                    st.session_state.portfolio.append({'Ticker': m_ticker, 'Shares': m_qty, 'AvgPrice': m_price})
                    st.toast(f"{m_ticker} añadido manualmente!", icon="📝")
                    st.rerun()
            
            st.divider()
            
            st.markdown("### 🤖 Auditoría IA")
            api_aud = st.text_input("API Key", type="password", key="aud_key")
            if st.button("Auditar Riesgo") and api_aud:
                with st.spinner("Analizando..."):
                    st.info(ai_audit(st.session_state.portfolio, st.session_state.profile, api_aud))
            
            if st.button("🗑️ Borrar Todo"):
                st.session_state.portfolio = []
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 3: EXPLORADOR (MEJORADO CON SUGERENCIAS) ---
    with tab_search:
        st.subheader("🔎 Explorador de Mercado")
        
        # SUGERENCIAS RÁPIDAS (CHIPS)
        st.caption("¿No sabes qué buscar? Prueba estos:")
        c1, c2, c3, c4 = st.columns(4)
        suggestions = {
            "Principales": ["SPY", "QQQ", "DIA"],
            "Dividendos": ["VIG", "SCHD", "VYM"],
            "Global": ["VT", "ACWI", "VEA"],
            "Sectorial": ["XLK", "XLE", "XLV"]
        }
        
        # Lógica de Botones de Sugerencia
        # Usamos columnas para simular "Chips"
        col_sugs = st.columns(6)
        sug_list = [("S&P 500", "SPY"), ("Tecnología", "QQQ"), ("Mundo", "VT"), ("Oro", "GLD"), ("Bonos", "BND"), ("Dividendos", "VIG")]
        
        for i, (label, ticker_sug) in enumerate(sug_list):
            with col_sugs[i]:
                if st.button(label, use_container_width=True):
                    st.session_state.search_query = ticker_sug
        
        # BARRA DE BÚSQUEDA
        search = st.text_input("Escribe el Ticker:", value=st.session_state.search_query).upper()
        
        if search:
            try:
                stock = yf.Ticker(search)
                info = stock.info
                
                # LAYOUT DE RESULTADO
                col_inf, col_chart = st.columns([1, 2])
                
                with col_inf:
                    st.markdown(f"## {search}")
                    st.caption(info.get('shortName'))
                    st.metric("Precio", f"{info.get('currentPrice')} {info.get('currency')}")
                    st.markdown(f"**Sector:** {info.get('sector')}")
                    st.markdown(f"**Beta (Riesgo):** {info.get('beta')}")
                    
                    st.markdown("---")
                    # BOTÓN DE AÑADIR DIRECTO DESDE BUSCADOR
                    if st.button(f"➕ Añadir {search} a Cartera", type="primary"):
                        curr_p = info.get('currentPrice', 0)
                        if st.session_state.cash >= curr_p:
                            st.
