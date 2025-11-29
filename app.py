import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Scanner de Inversión Mensual", page_icon="🔭")

# Estilos visuales
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .winner-card { border: 2px solid #00C805; padding: 20px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- EL UNIVERSO DE INVERSIÓN (MODIFICA ESTA LISTA A TU GUSTO) ---
# Hemos puesto los ETFs más líquidos y fiables del mundo
ETF_UNIVERSE = {
    'SPY': 'S&P 500 (EEUU)',
    'QQQ': 'Nasdaq 100 (Tech)',
    'VEA': 'Desarrollados (Ex-USA)',
    'VWO': 'Emergentes',
    'VIG': 'Dividendos Crecientes',
    'GLD': 'Oro Físico',
    'BND': 'Bonos Totales EEUU',
    'TLT': 'Bonos Largo Plazo',
    'XLE': 'Energía',
    'XLV': 'Salud',
    'XLF': 'Financiero'
}

# --- FUNCIONES DE CÁLCULO ---
def load_instructions():
    try:
        with open("Instrucciones.md", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Actúa como asesor financiero."

def scan_market(tickers):
    """Descarga datos de TODOS los ETFs y calcula cuál es el mejor hoy"""
    data = []
    
    # Descarga masiva para ir rápido
    tickers_list = list(tickers.keys())
    # Descargamos 6 meses de historia para ver tendencias
    history = yf.download(tickers_list, period="6mo", progress=False)['Close']
    
    for ticker in tickers_list:
        try:
            prices = history[ticker]
            if prices.empty: continue
            
            # 1. Precio Actual
            current_price = prices.iloc[-1]
            
            # 2. Rentabilidad Mensual (Momentum Corto)
            price_1mo_ago = prices.iloc[-22] # Aprox 22 días de trading
            mom_1m = ((current_price - price_1mo_ago) / price_1mo_ago) * 100
            
            # 3. Tendencia (Precio vs Media Móvil 50 días)
            sma_50 = prices.tail(50).mean()
            trend_score = (current_price / sma_50) - 1 # Positivo = Alcista
            
            # 4. Volatilidad (Riesgo)
            daily_ret = prices.pct_change().dropna()
            volatility = daily_ret.std() * np.sqrt(252) * 100
            
            # 5. PUNTUACIÓN FINAL (Score)
            # Premiamos Momentum y penalizamos Volatilidad
            # Score = Rentabilidad Mensual / (Volatilidad * 0.5)
            # Esto busca subidas "limpias" sin demasiados sustos
            score = mom_1m / (volatility if volatility > 0 else 1)
            
            data.append({
                'Ticker': ticker,
                'Nombre': tickers[ticker],
                'Precio': current_price,
                'Retorno 1M (%)': mom_1m,
                'Volatilidad (%)': volatility,
                'Score': score,
                'Tendencia': "Alcista 🟢" if trend_score > 0 else "Bajista 🔴"
            })
            
        except Exception as e:
            continue
            
    # Crear Tabla y Ordenar por Score (Los mejores arriba)
    df = pd.DataFrame(data)
    df = df.sort_values(by='Score', ascending=False)
    return df

def generate_monthly_plan(top_3_df, api_key):
    """Envía los ganadores a la IA para que haga el plan"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    instructions = load_instructions()
    
    # Convertimos los datos de los 3 mejores a texto
    candidates_text = top_3_df.to_string(index=False)
    
    prompt = f"""
    {instructions}
    
    CONTEXTO: He escaneado el mercado y estos son los 3 ETFs con mejor comportamiento ajustado al riesgo este mes:
    
    {candidates_text}
    
    Por favor, genera el informe mensual de inversión basado en estos datos.
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- INTERFAZ ---
with st.sidebar:
    st.header("🔭 Configuración")
    api_key = st.text_input("Google API Key", type="password")
    st.info("Escanea Momentum y Volatilidad para seleccionar los mejores activos.")

st.title("📅 Scanner de Asignación Mensual")
st.markdown("Esta herramienta analiza el **Universo de ETFs** y selecciona los 3 candidatos matemáticamente más fuertes para tu aportación de este mes.")

if st.button("🚀 Escanear Mercado y Generar Plan", type="primary"):
    if not api_key:
        st.error("Por favor, introduce tu API Key.")
    else:
        with st.spinner('Analizando tendencias, volatilidad y momentum de todos los activos...'):
            # 1. Escaneo Matemático
            ranking_df = scan_market(ETF_UNIVERSE)
            
            # Seleccionar Top 3
            top_3 = ranking_df.head(3)
            
            # 2. Análisis IA
            plan_ia = generate_monthly_plan(top_3, api_key)
            
        # --- RESULTADOS ---
        
        # 1. MOSTRAR EL PODIO (TOP 3)
        st.subheader("🏆 Los 3 Ganadores del Mes")
        cols = st.columns(3)
        
        for index, (i, row) in enumerate(top_3.iterrows()):
            with cols[index]:
                st.markdown(f"""
                <div class="winner-card">
                    <h3 style="text-align:center;">#{index+1} {row['Ticker']}</h3>
                    <p style="text-align:center; color:gray;">{row['Nombre']}</p>
                    <h2 style="text-align:center; color:{'green' if row['Retorno 1M (%)'] > 0 else 'red'}">
                        {row['Retorno 1M (%)']:.2f}%
                    </h2>
                    <p style="text-align:center;">Retorno (1 Mes)</p>
                    <hr>
                    <p><b>Volatilidad:</b> {row['Volatilidad (%)']:.1f}%</p>
                    <p><b>Tendencia:</b> {row['Tendencia']}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # 2. INFORME DE ESTRATEGIA
        st.markdown("---")
        st.markdown("### 📝 Estrategia de Inversión (IA)")
        with st.container(border=True):
            st.markdown(plan_ia)
            
        # 3. TABLA COMPLETA (Para los curiosos)
        with st.expander("Ver Ranking Completo del Mercado"):
            st.dataframe(ranking_df.style.format({
                'Precio': '{:.2f}',
                'Retorno 1M (%)': '{:.2f}%', 
                'Volatilidad (%)': '{:.2f}%',
                'Score': '{:.2f}'
            }))
