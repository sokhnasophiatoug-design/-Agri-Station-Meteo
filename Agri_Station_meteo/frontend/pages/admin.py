"""
admin.py — Dashboard Administrateur (Streamlit)
Style : Sidebar vert foncé Station_meteo
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from components.map_component import afficher_carte_stations
from components.auth          import deconnexion

BACKEND = "https://agri-station-meteo.onrender.com"


def _get(endpoint, default=None):
    try:
        r = requests.get(f"{BACKEND}{endpoint}", timeout=60)
        return r.json() if r.status_code == 200 else default
    except Exception:
        return default


def _post(endpoint, body):
    try:
        r = requests.post(f"{BACKEND}{endpoint}", json=body, timeout=60)
        return r.status_code == 200, r.json()
    except Exception as e:
        return False, {"detail": str(e)}


# ── Pages ─────────────────────────────────────────────────────────────────────

def _page_tableau(stations, agriculteurs):
    st.markdown(f"""
    <div class="entete-admin fade-in">
        <div>
            <h1>🛰️ Tableau de Bord Administrateur</h1>
            <div class="sous-titre">
                <span class="live-dot"></span>
                Supervision globale — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    nb_stations      = len(stations)
    nb_agriculteurs  = len(agriculteurs)
    stations_actives = sum(1 for s in stations.values() if s.get("mesures"))

    _CARD = (
        'background:#ffffff;border-radius:18px;padding:20px 24px;'
        'box-shadow:0 6px 20px rgba(0,0,0,0.14);'
        'border-top:4px solid {color};flex:1;min-width:150px;text-align:center;'
    )
    _VAL  = 'font-size:2.4rem;font-weight:900;color:{color};line-height:1;font-family:"Sora",sans-serif;'
    _LBL  = 'font-size:0.82rem;font-weight:700;color:#4A5568;margin-top:8px;'

    html_kpi = (
        '<div style="display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap;">'

        f'<div style="{_CARD.format(color="#1B5E20")}">'
        f'<div style="{_VAL.format(color="#1B5E20")}">{nb_stations}</div>'
        f'<div style="{_LBL}">📡 Stations totales</div>'
        '</div>'

        f'<div style="{_CARD.format(color="#43A047")}">'
        f'<div style="{_VAL.format(color="#43A047")}">{stations_actives}</div>'
        f'<div style="{_LBL}">✅ Stations actives</div>'
        '</div>'

        f'<div style="{_CARD.format(color="#00695C")}">'
        f'<div style="{_VAL.format(color="#00695C")}">{nb_agriculteurs}</div>'
        f'<div style="{_LBL}">👨‍🌾 Agriculteurs</div>'
        '</div>'

        '</div>'
    )
    st.markdown(html_kpi, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🗺️ Carte interactive des stations météo")
    if stations:
        afficher_carte_stations(stations)
    else:
        st.info("Aucune station disponible dans Firebase pour le moment.")

    alertes_globales = []
    for st_id, data in stations.items():
        m = data.get("mesures", {})
        s = data.get("seuils", {"temp_max": 40, "hum_sol_min": 25, "vent_max": 45})
        t, hs, v = m.get("temperature"), m.get("humidite_sol"), m.get("vitesse_vent")
        if t  and isinstance(t,  (int, float)) and t  > s.get("temp_max",    40): alertes_globales.append(f"🌡️ [{st_id}] Température critique : {t:.1f}°C")
        if hs and isinstance(hs, (int, float)) and hs < s.get("hum_sol_min", 25): alertes_globales.append(f"🌱 [{st_id}] Sol très sec : {hs:.1f}%")
        if v  and isinstance(v,  (int, float)) and v  > s.get("vent_max",    45): alertes_globales.append(f"💨 [{st_id}] Vent fort : {v:.1f} km/h")
    if alertes_globales:
        with st.expander(f"🚨 {len(alertes_globales)} alerte(s) réseau", expanded=True):
            for al in alertes_globales: st.warning(al)


def _page_donnees(stations):
    st.markdown("#### 📊 Mesures actuelles de toutes les stations")
    if not stations:
        st.info("Aucune donnée disponible."); return
    rows = []
    for st_id, data in stations.items():
        m = data.get("mesures", {})
        rows.append({"Station ID": st_id, "Température (°C)": m.get("temperature", "N/A"),
                     "Humidité air (%)": m.get("humidite_air", "N/A"), "Humidité sol (%)": m.get("humidite_sol", "N/A"),
                     "Vent (km/h)": m.get("vitesse_vent", "N/A"), "Dernière mesure": m.get("timestamp", "N/A")})
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)


def _page_agriculteurs(agriculteurs):
    st.markdown("#### 👨‍🌾 Liste des agriculteurs enregistrés")
    if not agriculteurs:
        st.info("Aucun agriculteur enregistré."); return
    rows = []
    for uid, info in agriculteurs.items():
        rows.append({"UID": uid[:12] + "...", "Nom": info.get("nom", "N/A"), "Email": info.get("email", "N/A"),
                     "Région": info.get("region", "N/A"), "Station": info.get("station_id", "N/A"),
                     "Station nom": info.get("station_nom", "N/A"), "Téléphone": info.get("telephone", "N/A"),
                     "Actif": "✅" if info.get("actif", True) else "❌",
                     "Créé le": info.get("date_creation", "N/A")[:10] if info.get("date_creation") else "N/A"})
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)


def _page_seuils(stations):
    st.markdown("#### ⚙️ Seuils d'alerte globaux")
    st.info("ℹ️ Ces seuils s'appliquent à toutes les stations du réseau.")

    seuils_actuels = _get("/seuils", default={"temp_max": 40.0, "temp_min": 15.0, "hum_sol_min": 25.0, "vent_max": 45.0})

    with st.form("form_seuils"):
        sc1, sc2 = st.columns(2)
        with sc1:
            temp_max    = st.number_input("🌡️ Temp. max (°C)",    value=float(seuils_actuels.get("temp_max",    40.0)), step=0.5)
            hum_sol_min = st.number_input("🌱 Hum. sol min (%)", value=float(seuils_actuels.get("hum_sol_min", 25.0)), step=1.0)
        with sc2:
            temp_min = st.number_input("❄️ Temp. min (°C)",   value=float(seuils_actuels.get("temp_min",   15.0)), step=0.5)
            vent_max = st.number_input("💨 Vent max (km/h)",  value=float(seuils_actuels.get("vent_max",   45.0)), step=1.0)
        submitted = st.form_submit_button("💾 Enregistrer les seuils globaux", width='stretch')

    if submitted:
        ok, resp = _post("/seuils", {"station_id": "", "temp_max": temp_max,
                                      "temp_min": temp_min, "hum_sol_min": hum_sol_min, "vent_max": vent_max})
        if ok: st.success("✅ Seuils globaux mis à jour pour toutes les stations")
        else:  st.error(f"❌ Erreur : {resp.get('detail', 'Inconnue')}")
        
# ── Page principale avec sidebar ──────────────────────────────────────────────

def page_admin():
    # CSS responsive mobile — injecté ici pour ne pas affecter la page login
    st.markdown("""
    <style>
    @media(max-width:768px){
        .stApp,.block-container,[data-testid="stAppViewBlockContainer"]{
            overflow-x:hidden !important;
            max-width:100vw !important;
        }
        .block-container{
            padding:0.5rem 0.4rem 1rem !important;
            padding-top:3.8rem !important;
        }
        [data-testid="collapsedControl"]{ display:none !important; }
        section[data-testid="stSidebar"]{
            width:82vw !important;
            max-width:300px !important;
            min-width:240px !important;
            position:fixed !important;
            top:0 !important; left:0 !important;
            height:100vh !important;
            z-index:9998 !important;
            box-shadow:6px 0 28px rgba(0,0,0,0.6) !important;
            transition:transform 0.3s ease !important;
        }
        [data-testid="stHorizontalBlock"]{
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{
            flex: 0 0 calc(50% - 4px) !important;
            max-width: calc(50% - 4px) !important;
            min-width: 0 !important;
            width: calc(50% - 4px) !important;
            box-sizing: border-box !important;
        }
        h1{ font-size:1.1rem !important; }
        .entete h1,.entete-admin h1,.page-header h1{ font-size:1.1rem !important; }
        .entete,.entete-admin,.page-header{
            padding:10px 12px !important;
            border-radius:14px !important;
            margin-bottom:10px !important;
        }
        .sous-titre{ font-size:0.66rem !important; }
        .stTabs [data-baseweb="tab"]{ font-size:0.65rem !important; padding:5px 6px !important; }
        .stButton>button{ font-size:0.76rem !important; padding:8px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    with st.spinner("Chargement des données..."):
        stations_resp  = _get("/stations",     default={"stations": {}})
        agriculteurs_r = _get("/agriculteurs", default={"agriculteurs": {}})

    stations     = stations_resp.get("stations", {})
    agriculteurs = agriculteurs_r.get("agriculteurs", {})
    nb_actives   = sum(1 for s in stations.values() if s.get("mesures"))
    nb_panne     = len(stations) - nb_actives

    # ══════════════════════════════════════════
    #  SIDEBAR — style Station_meteo
    # ══════════════════════════════════════════
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:18px 0 12px;">
            <div style="font-size:2.8rem;
                        filter:drop-shadow(0 0 8px rgba(255,255,255,0.40));">🛰️</div>
            <div style="font-family:'Sora',sans-serif; font-weight:900;
                        font-size:1.05rem; margin-top:4px;">Station Météo</div>
            <div style="font-size:0.75rem; opacity:0.65;">Interface Administrateur</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        section = st.radio("Navigation", [
            "🏠 Tableau de Bord",
            "📊 Données Temps Réel",
            "👨‍🌾 Gestion Agriculteurs",
            "⚙️ Seuils d'Alerte",
        ], label_visibility="collapsed")

        st.markdown("---")

        st.markdown("**📍 Filtrer par Région**")
        regions_dispo = ["Toutes"] + sorted({
            data.get("region", "") for data in stations.values() if data.get("region")
        })
        filtre_region = st.selectbox("Région", regions_dispo,
                                     label_visibility="collapsed", key="admin_filtre_region")

        st.markdown("---")

        st.markdown(f"""
        <div class="sidebar-box">
            <div style="font-weight:800; font-size:0.82rem; margin-bottom:8px;">📊 Réseau en Temps Réel</div>
            <div style="font-size:0.82rem;">🛰️ {len(stations)} station(s) totale(s)</div>
            <div style="font-size:0.82rem; color:#A5D6A7;">🟢 {nb_actives} active(s)</div>
            <div style="font-size:0.82rem; color:#EF9A9A;">🔴 {nb_panne} en panne</div>
            <div style="font-size:0.82rem; opacity:0.70; margin-top:4px;">👨‍🌾 {len(agriculteurs)} agriculteur(s)</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        if st.button("🚪 Se déconnecter", width='stretch', key="btn_deco_admin"):
            deconnexion()

        st.markdown("""
        <div style="font-size:0.68rem; opacity:0.45; text-align:center; margin-top:10px;">
            ESP32 + SIM7600 + Firebase<br>Projet IoT Agricole
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════
    #  ROUTING
    # ══════════════════════════════════════════
    stations_aff = {k: v for k, v in stations.items() if v.get("region") == filtre_region} \
                   if filtre_region != "Toutes" else stations

    if   "Tableau de Bord"       in section: _page_tableau(stations_aff, agriculteurs)
    elif "Données Temps Réel"    in section: _page_donnees(stations_aff)
    elif "Gestion Agriculteurs"  in section: _page_agriculteurs(agriculteurs)
    elif "Seuils"                in section: _page_seuils(stations_aff)