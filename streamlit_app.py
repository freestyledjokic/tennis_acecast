import streamlit as st
import os
from ui import profiles, match, tournament

# Page configuration
st.set_page_config(
    page_title="AceCast - Tennis Match Prediction AI",
    page_icon="🎾",
    layout="wide"
)

# -----------------------------
# Custom CSS - Night Court / Hardcourt Neon Theme
# -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg: #0a0e27;           /* deep navy night */
  --panel: #0f1629;        /* card background */
  --border: #1a2332;       /* subtle borders */
  --text: #e2e8f0;         /* clean white */
  --muted: #94a3b8;        /* muted gray */
  --accent: #00d4ff;       /* electric cyan */
  --accent-glow: #00b8d4;  /* deeper cyan */
  --lime: #39ff14;         /* neon lime highlight */
}

* { font-family: 'Inter', sans-serif; }
html, body, .block-container { 
  background: var(--bg) !important; 
  color: var(--text); 
}

/* Ensure full viewport coverage */
html, body {
  min-height: 100vh;
  background: var(--bg) !important;
}

.main .block-container {
  min-height: 100vh;
  background: var(--bg) !important;
}

/* HERO SECTION */
.hero {
  position: relative;
  border-radius: 16px;
  padding: 2.5rem 2rem;
  background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%);
  border: 1px solid var(--border);
  box-shadow: 0 8px 32px rgba(0, 212, 255, 0.1);
  overflow: hidden;
  margin-bottom: 2.5rem;
}

.hero::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -10%;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.15) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.hero h1 { 
  margin: 0; 
  font-size: 2.5rem; 
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent) 0%, var(--lime) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero .subtitle { 
  color: var(--muted); 
  margin-top: 0.5rem; 
  font-size: 1.1rem;
  font-weight: 400;
}

.hero .badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 50px;
  font-size: 0.85rem;
  font-weight: 600;
  background: rgba(0, 212, 255, 0.1);
  color: var(--accent);
  border: 1px solid rgba(0, 212, 255, 0.3);
  margin-top: 1rem;
}

/* CARD GRID - 3 COLUMNS */
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin-top: 2rem;
}

@media (max-width: 1200px) {
  .card-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 768px) {
  .card-grid { grid-template-columns: 1fr; }
}

/* FEATURE CARDS */
.feature-card {
  position: relative;
  background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 2rem;
  height: 280px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.feature-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.feature-card:hover {
  transform: translateY(-6px);
  border-color: var(--accent);
  box-shadow: 0 12px 40px rgba(0, 212, 255, 0.2);
}

.feature-card:hover::before {
  opacity: 1;
}

.feature-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.3);
  font-size: 1.75rem;
  margin-bottom: 1rem;
}

.feature-card h3 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.75rem;
}

.feature-card p {
  color: var(--muted);
  font-size: 0.95rem;
  line-height: 1.6;
  margin: 0;
  flex-grow: 1;
}

/* BUTTONS */
.stButton > button {
  width: 100%;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-glow) 100%);
  color: #0a0e27;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.3px;
  box-shadow: 0 4px 16px rgba(0, 212, 255, 0.3);
  transition: all 0.2s ease;
  margin-top: 1rem;
}

.stButton > button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(0, 212, 255, 0.4);
  background: linear-gradient(135deg, var(--lime) 0%, var(--accent) 100%);
}

.stButton > button:active {
  transform: translateY(0);
}

/* STATS SECTION */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin-top: 3rem;
}

.stat-card {
  background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  text-align: center;
}

.stat-number {
  font-size: 2.5rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent) 0%, var(--lime) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0;
}

.stat-label {
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 0.5rem;
}

/* SIDEBAR */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0a0e27 0%, #0f1629 100%);
}

[data-testid="stSidebar"] h3 {
  color: var(--text);
  font-size: 1.5rem;
  font-weight: 700;
  text-align: center;
  margin-bottom: 0.5rem;
}

[data-testid="stSidebar"] .stRadio > label {
  color: var(--text);
  font-weight: 600;
}

[data-testid="stSidebar"] .stRadio > div {
  background: rgba(255, 255, 255, 0.05);
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid var(--border);
}

/* COMING SOON PAGE */
.coming-soon {
  background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%);
  padding: 4rem 2rem;
  border-radius: 16px;
  text-align: center;
  border: 1px solid var(--border);
  margin: 2rem 0;
}

.coming-soon h2 {
  font-size: 2.5rem;
  margin: 0 0 1rem 0;
  background: linear-gradient(135deg, var(--accent) 0%, var(--lime) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.coming-soon p {
  font-size: 1.1rem;
  color: var(--muted);
  margin: 0.5rem 0;
}

/* PAGE TITLE */
.page-title {
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 2rem;
  background: linear-gradient(135deg, var(--accent) 0%, var(--lime) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Force background on all containers */
.stApp {
  background: var(--bg) !important;
}

[data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
}

[data-testid="stHeader"] {
  background: transparent !important;
}

.main {
  background: var(--bg) !important;
}

@media (max-width: 768px) {
  .hero h1 { font-size: 2rem; }
  .stats-row { grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Session state
# -----------------------------
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# -----------------------------
# Model loading
# -----------------------------
@st.cache_resource
def load_elo_model():
    try:
        from elo_system import EloSystem
        import glob
        
        elo_system = EloSystem()
        csv_files = glob.glob("data/*.csv")
        
        if csv_files:
            success = elo_system.load_data(csv_files)
            if success:
                return elo_system, len(csv_files)
            else:
                return None, 0
        else:
            return None, 0
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, 0

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("### 🎾 AceCast")
    st.markdown("<p style='color: #94a3b8; text-align: center; font-size: 0.85rem;'>Tennis Intelligence Platform</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ['🏠 Home', '👤 Player Profiles', '⚔️ Match Prediction', '🏆 Tournament Simulator'],
        key='nav_radio'
    )
    
    if page == '🏠 Home':
        st.session_state.page = 'home'
    elif page == '👤 Player Profiles':
        st.session_state.page = 'players'
    elif page == '⚔️ Match Prediction':
        st.session_state.page = 'predict'
    elif page == '🏆 Tournament Simulator':
        st.session_state.page = 'simulate'
    
    st.markdown("---")
    
    elo_model, file_count = load_elo_model()
    if elo_model:
        st.success(f"✅ {file_count} files loaded")
    else:
        st.error("❌ Data loading failed")
    
    st.markdown("---")
    st.markdown("""
    <p style='color: #64748b; text-align: center; font-size: 0.75rem;'>
        Powered by Amazon Bedrock<br>
        v1.0.0 Beta
    </p>
    """, unsafe_allow_html=True)

# -----------------------------
# Homepage
# -----------------------------
def show_homepage():
    # Hero Section
    st.markdown("""
    <div class="hero">
      <h1>🎾 AceCast</h1>
      <div class="subtitle">Tennis Match Prediction AI</div>
      <div class="subtitle">Elo ratings • Match Predictions • Tournament simulations • AI-powered insights</div>
      <div class="badge">Powered by <b>Amazon Bedrock</b></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Feature Cards - 3 columns (no buttons)
    col1, col2, col3 = st.columns(3, gap="large")
    
    with col1:
        st.markdown("""
        <div class="feature-card">
          <div>
            <div class="feature-icon">👤</div>
            <h3>Player Profiles</h3>
            <p>Explore detailed player statistics, Elo ratings across different surfaces, recent form, and head-to-head records</p>
          </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
          <div>
            <div class="feature-icon">⚔️</div>
            <h3>Match Prediction</h3>
            <p>Predict outcomes between any two players with AI-powered analysis, win probabilities, and tactical insights</p>
          </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
          <div>
            <div class="feature-icon">🏆</div>
            <h3>Tournament Simulator</h3>
            <p>Simulate custom 16-player tournaments with tournament analysis and comprehensive bracket visualization</p>
          </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style='text-align: center; margin-top: 3rem; padding: 2rem; 
                background: linear-gradient(135deg, #0f1629 0%, #1a2332 100%);
                border-radius: 12px; border: 1px solid #1a2332;'>
        <h3 style='color: #00d4ff; margin: 0;'>📍 Use the sidebar to navigate</h3>
        <p style='color: #94a3b8; margin-top: 1rem;'>
            Select from Player Profiles, Match Prediction, or Tournament Simulator in the sidebar menu.
        </p>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------
# Configuration
# -----------------------------
DEFAULT_SURFACE = "Hard"
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
REGION = "us-east-1"
SHOW_CONTEXT = True

# -----------------------------
# Main
# -----------------------------
def main():
    elo_model, _ = load_elo_model()
    
    if st.session_state.page == 'home':
        show_homepage()
    elif st.session_state.page == 'players':
        profiles.render(elo_model, DEFAULT_SURFACE)
    elif st.session_state.page == 'predict':
        match.render(elo_model, DEFAULT_SURFACE, MODEL_ID, REGION, SHOW_CONTEXT)
    elif st.session_state.page == 'simulate':
        tournament.render(elo_model, DEFAULT_SURFACE, MODEL_ID, REGION, SHOW_CONTEXT)

if __name__ == "__main__":
    main()