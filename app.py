import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import feedparser
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Wealth OS", page_icon="✨", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1d1d1f;
        background-color: #fbfbfd;
    }
    
    /* PANEL DE CONTROL */
    .control-panel {
        background-color: white;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border: 1px solid #e5e5e5;
        margin-bottom: 30px;
    }
    
    /* BOTONES */
    .stButton > button {
        background-color: #000000;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 15px 30px;
        font-weight: 500;
        width: 100%;
        transition: transform 0.1s;
    }
    .stButton > button:hover {
        background-color: #333333;
        transform: scale(1.01);
    }
    
    /* NOTICIAS */
    .news-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #ff7700; /* Naranja Investing */
        margin-bottom: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .news-card:hover { transform: translateX(5px); }
    .news-source { font-size: 10px; color: #888; text-transform: uppercase; font-weight: bold; }
    .news-title { font-size: 15px; font-weight: 600; color: #111; margin: 6px 0; line-height: 1.4; }
    .news-link { text-decoration: none; color: #007AFF; font-size: 12px; font-weight: 500; }
    
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
    'GLD': 'Oro Físico', 'VWO': 'Emergentes', 'VEA': 'Europa/Pacífico',
    'XLE': 'Energía', 'XLF': 'Financiero', 'XLV': 'Salud',
    'SMH': 'Semiconductores', 'VIG': 'Dividendos', 'ARKK': 'Innovación',
    'TLT': 'Bonos 20+ Años', 'IWM': 'Small Caps'
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
    """Escaneo Matemático con RED DE SEGURIDAD (Validación de Datos)"""
    data = []
    tickers = list(SATELLITE_UNIVERSE.keys())
    
    try:
        # Descarga masiva
        history = yf.download(tickers, period="6mo", progress=False)['Close']
        
        # FILTRO 1: ¿Ha fallado la descarga masiva?
        if history.empty:
            st.error("Error de conexión con Yahoo Finance. Reintentando...")
            return pd.DataFrame() # Devolvemos vacío para no romper la app

        for ticker in tickers:
            try:
                # Extraemos la serie de precios de este ticker concreto
                # Usamos .dropna() para eliminar días festivos o huecos
                prices = history[ticker].dropna()
                
                # FILTRO 2: ¿Tenemos suficientes datos históricos?
                # Necesitamos al menos 30 días para calcular medias y volatilidad fiables
                if len(prices) < 30:
                    continue # Saltamos este activo, no es fiable

                # FILTRO 3: Validación de Precio Lógico
                current = prices.iloc[-1]
                prev_month = prices.iloc[-22] if len(prices) >= 22 else prices.iloc[0]
                
                if current <= 0 or prev_month <= 0:
                    continue # Precio corrupto (cero o negativo), saltamos
                
                # --- CÁLCULOS MATEMÁTICOS (Solo si pasan los filtros) ---
                ret_1m = ((current - prev_month) / prev_month) * 100
                daily_ret = prices.pct_change().dropna()
                vol = daily_ret.std() * np.sqrt(252) * 100
                
                # Clasificación de Riesgo
                risk_label = "Equilibrado"
                if vol < 12: risk_label = "Conservador"
                elif vol > 25: risk_label = "Agresivo"
                
                # Score (Evitamos división por cero)
                score = ret_1m / vol if vol > 0.1 else 0
                
                data.append({
                    'Ticker': ticker,
                    'Nombre': SATELLITE_UNIVERSE[ticker],
                    'Precio': current,
                    'Retorno 1M': ret_1m,
                    'Volatilidad': vol,
                    'Perfil': risk_label,
                    'Score': score
                })
                
            except Exception as e:
                # Si falla UN ticker específico, lo ignoramos y seguimos con los demás
                continue 

    except Exception as e:
        st.error(f"Error crítico en el escaneo: {e}")
        return pd.DataFrame()
        
    # Devolvemos la lista limpia y ordenada
    return pd.DataFrame(data).sort_values(by='Score', ascending=False)

def get_rss_news():
    """Obtiene noticias en ESPAÑOL desde RSS Oficiales (Infalible)"""
    rss_urls = [
        "https://es.investing.com/rss/news_25.rss", # Mercado de Valores
        "https://es.investing.com/rss/news_285.rss" # Noticias Populares
    ]
    
    news_feed = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # 5 noticias de cada fuente
                news_feed.append({
                    'Title': entry.title,
                    'Link': entry.link,
                    'Publisher': "Investing.com España",
                    # Intentamos parsear la fecha, si falla ponemos 'Hoy'
                    'Time': entry.published_parsed if hasattr(entry, 'published_parsed') else datetime.now()
                })
        except: continue
    
    # Ordenar por fecha (más reciente primero) y devolver top 10
    return sorted(news_feed, key=lambda x: x['Time'], reverse=True)[:10]

def generate_advisor_report(profile, custom_core, top_satellites, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    instructions = load_instructions()
    satellites_txt = top_satellites[['Ticker', 'Nombre', 'Retorno 1M', 'Perfil']].to_string(index=False)
    prompt = f"{instructions}\nPERFIL: {profile}\nCORE ELEGIDO: {custom_core['Ticker']}\nTOP SATÉLITES:\n{satellites_txt}\nGenera estrategia."
    return model.generate_content(prompt).text

# --- 4. INTERFAZ ---

st.title(f"Wealth OS")
st.caption(f"Panel de Inteligencia | {datetime.now().strftime('%d/%m/%Y')}")

# PANEL DE CONTROL EXPANDIBLE
with st.expander("👤 Configuración de Inversor", expanded=True):
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    col_key, col_prof = st.columns([2, 1])
    with col_key:
        api_key = st.text_input("🔑 Google API Key", type="password")
    with col_prof:
        risk_profile = st.selectbox("Perfil Riesgo", ["Conservador", "Equilibrado", "Agresivo"], index=1)
    
    st.markdown("---")
    st.markdown("**🎯 Activo Base (Núcleo)**")
    col_rad, col_sel = st.columns([1, 2])
    with col_rad:
        core_mode = st.radio("Modo:", ["Automático (IA)", "Manual"], label_visibility="collapsed")
    selected_core = None
    with col_sel:
        if core_mode == "Automático (IA)":
            suggestion = DEFAULT_CORES[risk_profile]
            st.info(f"Recomendado: **{suggestion['Ticker']}** - {suggestion['Nombre']}")
            selected_core = suggestion
        else:
            manual_choice = st.selectbox("Elige tu fondo:", list(POPULAR_MANUAL_CORES.keys()))
            manual_ticker = POPULAR_MANUAL_CORES[manual_choice]
            selected_core = {"Ticker": manual_ticker, "Nombre": manual_choice, "Riesgo": "Manual"}
    st.markdown('</div>', unsafe_allow_html=True)

# TABS
tab1, tab2, tab3 = st.tabs(["📊 Estrategia", "🔮 Calculadora", "📰 Noticias (ES)"])

# TAB 1: ESTRATEGIA
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 GENERAR PLAN DE INVERSIÓN", type="primary"):
        if not api_key:
            st.error("⚠️ Introduce la API Key arriba.")
        else:
            with st.spinner(f"Diseñando estrategia para {selected_core['Ticker']}..."):
                df_market = scan_satellites()
                if risk_profile == "Conservador":
                    df_filtered = df_market[df_market['Perfil'].isin(["Conservador", "Equilibrado"])]
                else:
                    df_filtered = df_market
                top_3 = df_filtered.head(3)
                report = generate_advisor_report(risk_profile, selected_core, top_3, api_key)
            
            # Resultados
            col_core, col_txt = st.columns([1, 3])
            with col_core:
                st.metric("Tu Base", selected_core['Ticker'], "Núcleo")
            with col_txt:
                st.success(f"Plan generado para perfil **{risk_profile}**.")

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

# TAB 2: CALCULADORA
with tab2:
    col_inp, col_graph = st.columns([1, 2])
    with col_inp:
        ini = st.number_input("Capital Inicial (€)", 1000, 100000, 5000)
        mon = st.number_input("Mensual (€)", 100, 5000, 300)
        yrs = st.slider("Años", 5, 30, 15)
        r = st.slider("Interés (%)", 2.0, 12.0, 7.0)
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

# TAB 3: NOTICIAS (NUEVO CÓDIGO RSS)
with tab3:
    st.markdown("### 🇪🇸 Noticias de Mercado (En Español)")
    st.caption("Fuente: Investing.com España (Tiempo Real)")
    
    if st.button("🔄 Actualizar Noticias"):
        with st.spinner("Descargando titulares..."):
            news = get_rss_news()
            
            if not news:
                st.warning("No se pudieron cargar noticias.")
            else:
                col1, col2 = st.columns(2)
                for idx, n in enumerate(news):
                    with col1 if idx % 2 == 0 else col2:
                        st.markdown(f"""
                        <div class="news-card">
                            <div class="news-source">{n['Publisher']}</div>
                            <div class="news-title">{n['Title']}</div>
                            <a href="{n['Link']}" target="_blank" class="news-link">Leer noticia completa ↗</a>
                        </div>
                        """, unsafe_allow_html=True)
