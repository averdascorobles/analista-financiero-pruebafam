import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import feedparser
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN Y ESTÉTICA "NEOBANK" ---
st.set_page_config(layout="centered", page_title="Wealth OS", page_icon="🛡️", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1d1d1f;
        background-color: #ffffff;
    }
    
    /* BARRA DE PROGRESO GAMIFICADA */
    .stProgress > div > div > div > div {
        background-color: #00C805;
    }

    /* EL ESCUDO (SHIELD) */
    .shield-container {
        padding: 20px;
        border-radius: 20px;
        margin-bottom: 20px;
        text-align: center;
        transition: transform 0.3s;
    }
    .shield-safe { background: linear-gradient(135deg, #e0fddf 0%, #ffffff 100%); border: 2px solid #00C805; }
    .shield-warn { background: linear-gradient(135deg, #fff4e0 0%, #ffffff 100%); border: 2px solid #ffaa00; }
    
    /* TARJETAS NIVEL */
    .level-badge {
        background-color: #1d1d1f;
        color: white;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 12px;
        font-weight: bold;
        text-transform: uppercase;
    }

    /* BOTONES GRANDES (TAP AREA) */
    .stButton > button {
        border-radius: 16px;
        height: 55px;
        font-weight: 600;
        border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: all 0.2s;
    }
    .stButton > button:hover { transform: scale(1.02); }
    
    /* INPUTS CUESTIONARIO */
    .stRadio > div {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE ESTADO (MEMORIA DE LA APP) ---
if 'step' not in st.session_state: st.session_state.step = 1 # Paso del onboarding
if 'user_profile' not in st.session_state: st.session_state.user_profile = None # Perfil detectado
if 'user_xp' not in st.session_state: st.session_state.user_xp = 350 # Puntos de experiencia (Demo)
if 'streak' not in st.session_state: st.session_state.streak = 3 # Racha de días
if 'api_key' not in st.session_state: st.session_state.api_key = "" 

# --- 3. FUNCIONES LÓGICAS (BACKEND) ---

def load_instructions():
    try:
        with open("Instrucciones.md", "r", encoding="utf-8") as f: return f.read()
    except: return "Actúa como asesor experto."

@st.cache_data(ttl=3600)
def scan_satellites():
    # SIMULACIÓN DE ESCANEO PARA LA DEMO (Para que vaya rápido en la prueba UX)
    # En producción, aquí va tu código completo de yfinance
    return pd.DataFrame([
        {'Ticker': 'GLD', 'Nombre': 'Oro Físico', 'Retorno 1M': 4.2, 'Volatilidad': 11, 'Perfil': 'Conservador', 'Score': 2.5},
        {'Ticker': 'QQQ', 'Nombre': 'Nasdaq 100', 'Retorno 1M': 1.8, 'Volatilidad': 18, 'Perfil': 'Agresivo', 'Score': 1.9},
        {'Ticker': 'VWO', 'Nombre': 'Emergentes', 'Retorno 1M': -0.5, 'Volatilidad': 15, 'Perfil': 'Agresivo', 'Score': 0},
    ])

def calculate_profile(age, goal, panic):
    """Algoritmo invisible de perfilado"""
    score = 0
    # Edad
    if age < 35: score += 3
    elif age < 55: score += 2
    else: score += 1
    
    # Meta
    if goal == "Lambo (Riqueza Máxima)": score += 3
    elif goal == "Jubilación Tranquila": score += 1
    
    # Reacción al miedo (Lo más importante)
    if panic == "Vendo todo": score -= 5 # Penalización fuerte
    elif panic == "No hago nada": score += 2
    elif panic == "Compro más (Ofertas)": score += 5
    
    if score <= 2: return "Conservador"
    elif score <= 6: return "Equilibrado"
    else: return "Agresivo"

def generate_simple_advice(profile, api_key):
    """Versión simplificada del prompt para el usuario novato"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    Actúa como un mentor financiero amigable (Estilo Duolingo/Headspace).
    El usuario es perfil: {profile}.
    
    Dame 3 consejos MUY CORTOS (1 frase cada uno) y motivadores para hoy.
    Usa emojis. No uses jerga técnica.
    """
    return model.generate_content(prompt).text

# --- 4. FLUJO DE LA APLICACIÓN ---

# A) PANTALLA DE BIENVENIDA (ONBOARDING)
if st.session_state.user_profile is None:
    st.markdown("### 👋 Hola, vamos a configurar tu plan")
    progress = (st.session_state.step / 4) * 100
    st.progress(int(progress))
    
    # Paso 1: Edad
    if st.session_state.step == 1:
        st.header("¿Cuál es tu edad?")
        st.caption("Para ajustar el horizonte temporal.")
        age = st.radio("Selecciona:", ["Menos de 30", "30 - 50", "Más de 50"], label_visibility="collapsed")
        if st.button("Continuar ➔"):
            st.session_state.age_input = 25 if age == "Menos de 30" else 40 if age == "30 - 50" else 60
            st.session_state.step = 2
            st.rerun()

    # Paso 2: Meta
    elif st.session_state.step == 2:
        st.header("¿Para qué es este dinero?")
        st.caption("Sé honesto, aquí no juzgamos.")
        goal = st.radio("Objetivo:", ["Jubilación Tranquila", "Comprarme una casa", "Lambo (Riqueza Máxima)"], label_visibility="collapsed")
        if st.button("Continuar ➔"):
            st.session_state.goal_input = goal
            st.session_state.step = 3
            st.rerun()
            
    # Paso 3: Test de Estrés (Invisible)
    elif st.session_state.step == 3:
        st.header("😱 ¡El mercado cae un 20% mañana!")
        st.subheader("¿Qué haces?")
        panic = st.radio("Reacción:", ["Vendo todo para no perder más", "No hago nada, espero", "Compro más (Ofertas)"], label_visibility="collapsed")
        if st.button("Analizar mi Perfil ➔"):
            # CÁLCULO DEL PERFIL
            profile = calculate_profile(st.session_state.age_input, st.session_state.goal_input, panic)
            st.session_state.user_profile = profile
            st.success(f"¡Perfil Detectado: {profile}!")
            time.sleep(1.5)
            st.rerun()

# B) PANTALLA PRINCIPAL (DASHBOARD GAMIFICADO)
else:
    # --- HEADER GAMIFICADO ---
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.markdown(f"🔥 **{st.session_state.streak} Días**")
    with c3:
        level = "Novato" if st.session_state.user_xp < 500 else "Estratega"
        st.markdown(f"<span class='level-badge'>Nivel: {level}</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # --- EL ESCUDO (SEMÁFORO) ---
    # Lógica simple: Si mercado volátil y perfil conservador -> Aviso
    market_status = "Safe" # Esto vendría de tu scan_satellites() real
    
    if market_status == "Safe":
        st.markdown(f"""
        <div class="shield-container shield-safe">
            <h1 style="margin:0;">🛡️ Escudo Activo</h1>
            <p style="color:#666;">Tu cartera <b>{st.session_state.user_profile}</b> está equilibrada.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="shield-container shield-warn">
            <h1 style="margin:0;">⚠️ Atención</h1>
            <p>Hemos detectado volatilidad. Revisa tus satélites.</p>
        </div>
        """, unsafe_allow_html=True)

    # --- MENÚ PRINCIPAL SIMPLIFICADO ---
    
    # Aquí escondemos la complejidad. Solo mostramos "Qué hacer hoy".
    st.subheader("🎯 Tu Misión de Hoy")
    
    with st.expander("Ver Análisis Inteligente (Requiere API Key)", expanded=True):
        api_key_input = st.text_input("Tu Llave Maestra (Google API Key):", type="password", value=st.session_state.api_key)
        
        if st.button("✨ Generar Consejo Diario"):
            if not api_key_input:
                st.error("Necesitamos tu llave para despertar a la IA.")
            else:
                st.session_state.api_key = api_key_input # Guardamos para la sesión
                with st.spinner("Consultando al Mentor..."):
                    advice = generate_simple_advice(st.session_state.user_profile, api_key_input)
                    st.info(advice)
                    
                    # GAMIFICACIÓN: DAR PUNTOS
                    st.balloons()
                    st.session_state.user_xp += 50
                    st.toast(f"+50 XP Ganados! (Total: {st.session_state.user_xp})")

    # --- PESTAÑAS OCULTAS (PARA EL QUE QUIERA MÁS) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("HERRAMIENTAS AVANZADAS")
    
    tab1, tab2 = st.tabs(["🚀 Oportunidades", "💰 Calculadora"])
    
    with tab1:
        st.markdown("Aquí iría tu escáner de satélites (código anterior).")
        # Aquí puedes llamar a tu función scan_satellites() real
        df = scan_satellites()
        st.dataframe(df)
    
    with tab2:
        st.markdown("Aquí iría tu calculadora de interés compuesto.")
        
    # BOTÓN DE RESET (PARA PROBAR OTRA VEZ)
    if st.button("🔄 Reiniciar Perfil (Debug)"):
        st.session_state.user_profile = None
        st.session_state.step = 1
        st.rerun()
