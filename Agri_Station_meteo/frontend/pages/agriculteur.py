"""
agriculteur.py — Dashboard Agriculteur (Streamlit)
Style : Sidebar vert foncé Station_meteo
"""

import streamlit as st
import requests
import time
from datetime import datetime


import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from components.charts       import graphique_historique, graphique_jauge, graphique_tous_capteurs
from components.weather_card import afficher_previsions, afficher_alerte_meteo, afficher_meteo_actuelle
from components.auth         import deconnexion

BACKEND = "https://agri-station-meteo.onrender.com"

REGIONS = [
    "Dakar", "Thiès", "Kaolack", "Saint-Louis", "Fatick",
    "Diourbel", "Ziguinchor", "Tambacounda", "Louga", "Matam",
    "Kaffrine", "Kédougou", "Kolda", "Sédhiou",
]


def _get(endpoint, default=None):
    try:
        r = requests.get(f"{BACKEND}{endpoint}", timeout=60)
        return r.json() if r.status_code == 200 else default
    except Exception:
        return default


def _post(endpoint, body, default=None):
    try:
        r = requests.post(f"{BACKEND}{endpoint}", json=body, timeout=60)
        return r.json() if r.status_code == 200 else default
    except Exception:
        return default

import streamlit as st
import requests

# CSS responsive — dashboard agriculteur uniquement
st.markdown("""
<style>

/* ===== CARD METEO ACTUELLE ===== */
.meteo-now-card{
    background: linear-gradient(135deg, #16351c, #1f4d2c);
    border-radius: 18px;
    padding: 20px;
    color: white;
    box-shadow: 0 6px 22px rgba(0,0,0,0.25);
    border: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 18px;
}
.meteo-now-top{ display:flex; align-items:center; gap:18px; }
.meteo-now-icon{ font-size:3.2rem; line-height:1; }
.meteo-now-temp{ font-size:2rem; font-weight:800; line-height:1; }
.meteo-now-desc{ font-size:0.95rem; opacity:0.85; margin-top:4px; }
.meteo-now-ville{ margin-top:18px; font-size:0.9rem; opacity:0.9; }
.meteo-now-infos{ margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08); font-size:0.88rem; opacity:0.92; }

/* ===== RESPONSIVE MOBILE ===== */
@media(max-width:768px){

    /* Empêcher le scroll horizontal */
    .stApp, .block-container, [data-testid="stAppViewBlockContainer"]{
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }

    /* Container */
    .block-container{
        padding: 0.5rem 0.5rem 1rem !important;
        padding-top: 3.5rem !important;
    }

    /* Cacher le bouton natif Streamlit */
    [data-testid="collapsedControl"]{ display: none !important; }

    /* Sidebar mobile */
    section[data-testid="stSidebar"]{
        width: 80vw !important;
        max-width: 300px !important;
        min-width: 240px !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        height: 100vh !important; height: 100dvh !important;
        z-index: 9998 !important;
        box-shadow: 6px 0 28px rgba(0,0,0,0.6) !important;
        transition: transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94) !important;
    }

    /* Colonnes : 4 colonnes (layout desktop) */
    [data-testid="stHorizontalBlock"]{
        display: grid !important;
        grid-template-columns: repeat(4, 1fr) !important;
        gap: 6px !important;
    }
    [data-testid="stHorizontalBlock"] > *{ min-width:0 !important; width:100% !important; }
    [data-testid="stMetric"]{ min-height:60px !important; padding:8px 7px !important; }
    [data-testid="stMetricValue"]{ font-size:0.95rem !important; }
    [data-testid="stMetricLabel"]{ font-size:0.52rem !important; }

    /* Cartes prévisions */
    .meteo-card{ min-height:100px !important; padding:6px !important; }
    .meteo-card .temp{ font-size:0.95rem !important; }
    .meteo-card .jour{ font-size:0.58rem !important; }
    .meteo-card .desc{ font-size:0.65rem !important; }

    /* Titres */
    h1{ font-size:1.15rem !important; }
    .entete h1, .entete-admin h1, .page-header h1{ font-size:1.15rem !important; }
    .entete, .entete-admin, .page-header{ padding:12px 14px !important; border-radius:14px !important; }
    .sous-titre{ font-size:0.68rem !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab"]{ font-size:0.68rem !important; padding:5px 7px !important; }

    /* Boutons */
    .stButton > button{ font-size:0.78rem !important; padding:8px !important; }

    /* Reco card */
    .reco-card{ padding:12px 14px !important; }
    .reco-icon{ font-size:1.5rem !important; }
    .reco-titre{ font-size:0.88rem !important; }
    .reco-desc{ font-size:0.75rem !important; }

    /* Météo card */
    .meteo-now-card{ padding:12px !important; }
    .meteo-now-icon{ font-size:2rem !important; }
    .meteo-now-temp{ font-size:1.3rem !important; }
    .meteo-now-desc{ font-size:0.75rem !important; }
}
</style>
""", unsafe_allow_html=True)

def _calculer_alertes(mesures, seuils):
    alertes = []
    temp    = mesures.get("temperature")
    hum_sol = mesures.get("humidite_sol")
    vent    = mesures.get("vitesse_vent")
    if temp    and temp    > seuils.get("temp_max",    40): alertes.append(f"🌡️ Température critique : {temp:.1f}°C (seuil : {seuils['temp_max']}°C)")
    if temp    and temp    < seuils.get("temp_min",    15): alertes.append(f"❄️ Température trop basse : {temp:.1f}°C (seuil : {seuils['temp_min']}°C)")
    if hum_sol and hum_sol < seuils.get("hum_sol_min", 25): alertes.append(f"🌱 Sol trop sec : {hum_sol:.1f}% (seuil : {seuils['hum_sol_min']}%)")
    if vent    and vent    > seuils.get("vent_max",    45): alertes.append(f"💨 Vent dangereux : {vent:.1f} km/h (seuil : {seuils['vent_max']} km/h)")
    return alertes


# ── Pages ─────────────────────────────────────────────────────────────────────

def _render_metric_html(label, value, emoji, alert=False):
    """Rendu HTML d'une carte métrique — indépendant de st.columns."""
    border_color = "#E53E3E" if alert else "#1B7F2A"
    badge = '<span style="background:#E53E3E;color:white;font-size:0.6rem;padding:2px 6px;border-radius:8px;margin-left:6px;">⚠️</span>' if alert else ""
    return f"""
    <div style="background:rgba(255,255,255,0.97);border-radius:16px;padding:14px 12px;
                border-top:4px solid {border_color};
                box-shadow:0 4px 14px rgba(0,0,0,0.14);flex:1;min-width:0;">
        <div style="color:#2F5233;font-size:0.65rem;font-weight:800;text-transform:uppercase;
                    letter-spacing:0.8px;margin-bottom:8px;">{emoji} {label}{badge}</div>
        <div style="color:#062B0D;font-size:1.4rem;font-weight:900;line-height:1;
                    font-family:'Roboto Mono',monospace;">{value}</div>
    </div>
    """

def _page_accueil(station_id, nom, station_nom, region):
    # ── En-tête HTML flex (pas de st.columns → tient sur mobile) ──
    meteo = _get(f"/meteo-actuelle?region={region}", default={"ok": False})
    _emoji_meteo = {"01":"☀️","02":"⛅","03":"☁️","04":"☁️","09":"🌧️","10":"🌦️","11":"⛈️","13":"❄️","50":"🌫️"}
    m_emoji = _emoji_meteo.get((meteo.get("icone","01d"))[:2], "🌡️") if meteo.get("ok") else "🌡️"

    meteo_html = ""
    if meteo.get("ok"):
        meteo_html = f"""
        <div style="background:linear-gradient(135deg,#16351c,#1f4d2c);border-radius:16px;
                    padding:16px 18px;color:white;box-shadow:0 6px 18px rgba(0,0,0,0.28);
                    border:1px solid rgba(255,255,255,0.08);min-width:200px;flex-shrink:0;">
            <div style="display:flex;align-items:center;gap:12px;">
                <div style="font-size:2.4rem;">{m_emoji}</div>
                <div>
                    <div style="font-size:1.8rem;font-weight:900;line-height:1;">{meteo.get('temp','--')}°C</div>
                    <div style="font-size:0.82rem;opacity:0.85;">{meteo.get('description','')}</div>
                </div>
            </div>
            <div style="margin-top:10px;font-size:0.8rem;opacity:0.9;">📍 {meteo.get('ville','')}</div>
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.12);
                        font-size:0.78rem;display:flex;gap:12px;flex-wrap:wrap;">
                <span>💧 {meteo.get('humidite','--')}%</span>
                <span>💨 {meteo.get('vent','--')} km/h</span>
                <span>🌡️ Ressenti {meteo.get('ressenti','--')}°C</span>
            </div>
        </div>
        """

    st.markdown(f"""
    <div style="display:flex;gap:16px;align-items:stretch;margin-bottom:18px;flex-wrap:wrap;">
        <div class="entete fade-in" style="flex:1;min-width:200px;">
            <h1>🌾 Bonjour, {nom}</h1>
            <div class="sous-titre">
                <span class="live-dot"></span>
                {station_nom} &nbsp;·&nbsp; 📍 {region} &nbsp;·&nbsp; {datetime.now().strftime('%H:%M:%S')}
            </div>
        </div>
        {meteo_html}
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Chargement des données..."):
        mesures    = _get(f"/mesures/{station_id}", default={})
        historique = _get(f"/historique/{station_id}?limit=48", default={}).get("historique", [])
        previsions = _get(f"/previsions/{station_id}?region={region}", default={"ok": False})
        seuils     = _get("/seuils", default={"temp_max": 40, "temp_min": 15, "hum_sol_min": 25, "vent_max": 45})

    if not mesures:
        st.error("❌ Impossible de récupérer les mesures. Vérifiez que le backend est démarré.")
        return

    temp    = mesures.get("temperature",  "--")
    hum_air = mesures.get("humidite_air", "--")
    hum_sol = mesures.get("humidite_sol", "--")
    vent    = mesures.get("vitesse_vent", "--")
    ts      = mesures.get("timestamp",    "N/A")

    alertes = _calculer_alertes(mesures, seuils) + afficher_alerte_meteo(previsions)
    if alertes:
        with st.expander(f"🚨 {len(alertes)} alerte(s) active(s)", expanded=True):
            for al in alertes: st.warning(al)

    # ── Métriques HTML 4 colonnes (pas de st.columns → tient sur mobile) ──
    st.markdown("")
    st.markdown("#### 📡 Mesures en temps réel")
    alert_temp = isinstance(temp, (int,float)) and temp > seuils.get("temp_max", 40)
    alert_sol  = isinstance(hum_sol, (int,float)) and hum_sol < seuils.get("hum_sol_min", 25)

    temp_val    = f"{temp}°C"    if isinstance(temp,    (int, float)) else str(temp)
    hum_air_val = f"{hum_air}%" if isinstance(hum_air, (int, float)) else str(hum_air)
    hum_sol_val = f"{hum_sol}%" if isinstance(hum_sol, (int, float)) else str(hum_sol)
    vent_val    = f"{vent} km/h" if isinstance(vent,    (int, float)) else str(vent)

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:8px;">
        {_render_metric_html("Température",  temp_val,    "🌡️", alert_temp)}
        {_render_metric_html("Humidité air", hum_air_val, "💧")}
        {_render_metric_html("Humidité sol", hum_sol_val, "🌱", alert_sol)}
        {_render_metric_html("Vent",         vent_val,    "💨")}
    </div>
    <div style="font-size:0.75rem;color:rgba(255,255,255,0.55);margin-bottom:12px;">🕐 Dernière mesure : {ts}</div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🎯 Niveaux actuels")
    # 2 colonnes × 2 lignes — plus lisible sur mobile que 4 d'affilée
    jc1, jc2 = st.columns(2)
    jc3, jc4 = st.columns(2)
    for capteur, val, col in [("temperature", temp, jc1), ("humidite_air", hum_air, jc2),
                               ("humidite_sol", hum_sol, jc3), ("vitesse_vent", vent, jc4)]:
        if isinstance(val, (int, float)):
            with col:
                st.plotly_chart(graphique_jauge(val, capteur,
                    seuil_min=seuils.get("hum_sol_min") if capteur == "humidite_sol" else None,
                    seuil_max=seuils.get("temp_max")    if capteur == "temperature"  else
                              seuils.get("vent_max")    if capteur == "vitesse_vent" else None),
                    width='stretch', config={"displayModeBar": False})

    st.markdown("---")
    st.markdown("#### 🤖 Conseil de votre assistant agricole IA")
    if all(isinstance(v, (int, float)) for v in [temp, hum_air, hum_sol, vent]):
        reco = _post("/recommandation", {"temperature": temp, "humidite_air": hum_air,
                                         "humidite_sol": hum_sol, "vitesse_vent": vent,
                                         "nom": nom, "region": region})
        if reco:
            col_reco, col_tts = st.columns([3, 1])
            with col_reco:
                st.markdown(f"""
                <div class="reco-card fade-in">
                    <span class="reco-icon">{reco.get('emoji', '✅')}</span>
                    <div class="reco-titre">{reco.get('label', '')}</div>
                    <div class="reco-desc">{reco.get('conseil', '')}</div>
                    <div style="margin-top:10px;color:#4A5568;font-size:0.78rem;font-weight:700;">
                        Confiance du modèle : {int(reco.get('confiance', 0) * 100)}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_tts:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("🔊 Écouter le conseil", width='stretch', key="btn_tts"):
                    try:
                        resp = requests.post(f"{BACKEND}/tts", json={"texte": reco.get("message_vocal", reco.get("conseil", "")), "lent": False}, timeout=15)
                        if resp.status_code == 200: st.audio(resp.content, format="audio/mp3")
                        else: st.error("Erreur lors de la génération audio")
                    except Exception as e: st.error(f"Service vocal indisponible : {e}")
        else:
            st.info("Recommandation IA indisponible — vérifiez le backend.")
    else:
        st.info("Données capteurs insuffisantes pour générer une recommandation.")

    st.markdown("---")
    st.markdown("#### 📈 Historique des mesures")
    if historique:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🌡️ Température", "💧 Humidité air", "🌱 Humidité sol", "💨 Vent", "📊 Vue globale"])
        with tab1: st.plotly_chart(graphique_historique(historique, "temperature"),  width='stretch', config={"displayModeBar": False})
        with tab2: st.plotly_chart(graphique_historique(historique, "humidite_air"), width='stretch', config={"displayModeBar": False})
        with tab3: st.plotly_chart(graphique_historique(historique, "humidite_sol"), width='stretch', config={"displayModeBar": False})
        with tab4: st.plotly_chart(graphique_historique(historique, "vitesse_vent"), width='stretch', config={"displayModeBar": False})
        with tab5: st.plotly_chart(graphique_tous_capteurs(historique),              width='stretch', config={"displayModeBar": False})
    else:
        st.info("Aucun historique disponible pour le moment.")

    st.markdown("---")
    st.markdown("#### 🌤️ Prévisions météo — 5 prochains jours")
    afficher_previsions(previsions)

    st.markdown('<div class="footer">Station Météo Agricole · Réseau IoT Sénégal · USSEIN</div>', unsafe_allow_html=True)


def _page_historique(station_id):
    st.markdown("#### 📋 Historique complet")
    historique = _get(f"/historique/{station_id}?limit=200", default={}).get("historique", [])
    if not historique:
        st.info("Aucun historique disponible."); return
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🌡️ Température", "💧 Humidité air", "🌱 Humidité sol", "💨 Vent", "📊 Vue globale"])
    with tab1: st.plotly_chart(graphique_historique(historique, "temperature"),  width='stretch', config={"displayModeBar": False})
    with tab2: st.plotly_chart(graphique_historique(historique, "humidite_air"), width='stretch', config={"displayModeBar": False})
    with tab3: st.plotly_chart(graphique_historique(historique, "humidite_sol"), width='stretch', config={"displayModeBar": False})
    with tab4: st.plotly_chart(graphique_historique(historique, "vitesse_vent"), width='stretch', config={"displayModeBar": False})
    with tab5: st.plotly_chart(graphique_tous_capteurs(historique),              width='stretch', config={"displayModeBar": False})


def _page_previsions(station_id, region):
    st.markdown("#### 🌤️ Prévisions météo — 5 prochains jours")
    previsions = _get(f"/previsions/{station_id}?region={region}", default={"ok": False})
    afficher_previsions(previsions)


# ── Page principale avec sidebar ──────────────────────────────────────────────

def page_agriculteur():
    station_id  = st.session_state.get("station_id",  "ST002")
    nom         = st.session_state.get("nom",          "Agriculteur")
    station_nom = st.session_state.get("station_nom",  station_id)
    region      = st.session_state.get("region",       "Kaolack")
    
    # Forcer la sidebar ouverte si demandé
    """if st.session_state.get("sidebar_ouverte"):
        st.session_state["sidebar_ouverte"] = False
        st.set_page_config(
            page_title="Station Météo Agricole",
            page_icon="🌾",
            layout="wide",
            initial_sidebar_state="expanded"
        )"""
    # ══════════════════════════════════════════
    #  SIDEBAR — style Station_meteo
    # ══════════════════════════════════════════
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center; padding:18px 0 12px;">
            <div style="font-size:2.8rem;
                        filter:drop-shadow(0 0 8px rgba(255,255,255,0.35));">🌾</div>
            <div style="font-family:'Sora',sans-serif; font-weight:900;
                        font-size:1.05rem; margin-top:4px;">{nom}</div>
            <div style="font-size:0.78rem; opacity:0.65;">Agriculteur</div>
            <div style="font-size:0.70rem; opacity:0.50; margin-top:3px;">
                📡 {station_nom}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        page = st.radio("Navigation", [
            "🏠 Accueil",
            "📋 Historique",
            "🌤️ Prévisions",
        ], label_visibility="collapsed")

        st.markdown("---")

        
        st.markdown("**📍 Ma région**")
        region_sel = st.selectbox("Région", REGIONS,
                                  index=REGIONS.index(region) if region in REGIONS else 0,
                                  label_visibility="collapsed", key="agri_region_sel")
        st.session_state["region"] = region_sel

        st.markdown("---")

        auto = st.checkbox("🔄 Actualisation auto (30s)", value=False)
        if auto:
            st.info("🔄 Actualisation dans 30s…")
            time.sleep(30)
            st.rerun()

        st.markdown("---")

        st.markdown(f"""
        <div class="sidebar-box">
            <div style="font-weight:800; font-size:0.82rem; margin-bottom:6px;">📊 Ma Station</div>
            <div style="font-size:0.80rem; opacity:0.85;">🛰️ ID : {station_id}</div>
            <div style="font-size:0.80rem; opacity:0.85;">📍 {region_sel}</div>
            <div style="font-size:0.72rem; opacity:0.55; margin-top:4px;">ESP32 + SIM7600 + Firebase</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        if st.button("🚪 Se déconnecter", width='stretch', key="btn_deco_agri"):
            deconnexion()

        st.markdown("""
        <div style="font-size:0.68rem; opacity:0.45; text-align:center; margin-top:10px;">
            Projet IoT Agricole · USSEIN Sénégal
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════
    #  ROUTING
    # ══════════════════════════════════════════
    if "Accueil"    in page: _page_accueil(station_id, nom, station_nom, region_sel)
    elif "Historique" in page: _page_historique(station_id)
    elif "Prévisions" in page: _page_previsions(station_id, region_sel)