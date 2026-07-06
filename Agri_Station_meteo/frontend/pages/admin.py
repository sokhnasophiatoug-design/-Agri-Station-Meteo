"""
admin.py — Dashboard Administrateur (Streamlit)
Style : Sidebar vert foncé Station_meteo
"""

import streamlit as st
import requests
from components.http import http_get, http_post
import pandas as pd
from datetime import datetime
import time

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from components.map_component import afficher_carte_stations
from components.auth          import deconnexion

BACKEND = "https://agri-station-meteo.onrender.com"


def _get(endpoint, default=None):
    try:
        r = http_get(f"{BACKEND}{endpoint}", timeout=60)
        return r.json() if r.status_code == 200 else default
    except Exception:
        return default


def _post(endpoint, body):
    try:
        r = http_post(f"{BACKEND}{endpoint}", json=body, timeout=60)
        if r.status_code == 200:
            try:
                return True, r.json()
            except Exception:
                return False, {"detail": "Le serveur a retourné une réponse invalide."}
        else:
            try:
                err_data = r.json()
                detail = err_data.get("detail", f"Erreur {r.status_code}")
                return False, {"detail": detail}
            except Exception:
                return False, {"detail": f"Erreur serveur (code {r.status_code})"}
    except Exception as e:
        return False, {"detail": str(e)}


# ── Pages ─────────────────────────────────────────────────────────────────────

def _page_tableau(stations, agriculteurs):
    st.markdown(f"""
    <div class="entete-admin fade-in">
        <div>
            <h1> Tableau de Bord Administrateur</h1>
            <div class="sous-titre">
                <span class="live-dot"></span>
                Supervision globale — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("####  Carte GPS")
    if stations:
        afficher_carte_stations(stations)
    else:
        st.info("Aucune station disponible dans Firebase pour le moment.")

    alertes_globales = []
    for st_id, data in stations.items():
        m = data.get("mesures", {})
        s = data.get("seuils", {"temp_max": 40, "hum_sol_min": 25, "vent_max": 45})
        t, hs, v = m.get("temperature"), m.get("humidite_sol"), m.get("vitesse_vent")
        if t  and isinstance(t,  (int, float)) and t  > s.get("temp_max",    40): alertes_globales.append(f" [{st_id}] Température critique : {t:.1f}°C")
        if hs and isinstance(hs, (int, float)) and hs < s.get("hum_sol_min", 25): alertes_globales.append(f" [{st_id}] Sol très sec : {hs:.1f}%")
        if v  and isinstance(v,  (int, float)) and v  > s.get("vent_max",    45): alertes_globales.append(f" [{st_id}] Vent fort : {v:.1f} km/h")
    if alertes_globales:
        with st.expander(f" {len(alertes_globales)} alerte(s) réseau", expanded=True):
            for al in alertes_globales: st.warning(al)


def _page_donnees(stations):
    st.markdown("####  Mesures actuelles de toutes les stations")
    if not stations:
        st.info("Aucune donnée disponible."); return
    rows = []
    for st_id, data in stations.items():
        m = data.get("mesures", {})
        rows.append({"Station ID": st_id, 
                     "Culture": data.get("culture", "Tomate"),
                     "Température (°C)": m.get("temperature", "N/A"),
                     "Humidité air (%)": m.get("humidite_air", "N/A"), "Humidité sol (%)": m.get("humidite_sol", "N/A"),
                     "Vent (km/h)": m.get("vitesse_vent", "N/A"), "Dernière mesure": m.get("timestamp", "N/A")})
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)


def _page_agriculteurs(agriculteurs):
    st.markdown("####  Liste des agriculteurs enregistrés")
    if not agriculteurs:
        st.info("Aucun agriculteur enregistré.")
    else:
        rows = []
        for uid, info in agriculteurs.items():
            rows.append({"UID": uid[:12] + "...", "Nom": info.get("nom", "N/A"), "Email": info.get("email", "N/A"),
                         "Région": info.get("region", "N/A"), "Station": info.get("station_id", "N/A"),
                         "Station nom": info.get("station_nom", "N/A"), "Téléphone": info.get("telephone", "N/A"),
                         "Actif": "" if info.get("actif", True) else "",
                         "Créé le": info.get("date_creation", "N/A")[:10] if info.get("date_creation") else "N/A"})
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    st.markdown("---")
    st.markdown("####  Ajouter un agriculteur")
    REGIONS_SN = [
        "Kaolack", "Dakar", "Thiès", "Diourbel", "Fatick", "Kaffrine",
        "Kédougou", "Kolda", "Louga", "Matam", "Saint-Louis",
        "Sédhiou", "Tambacounda", "Ziguinchor",
    ]
    with st.form("form_ajout_agriculteur", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nom_agri    = st.text_input(" Nom complet", placeholder="Ex : Ablaye DIOP")
            email_agri  = st.text_input(" Email", placeholder="Ex : ablaye@mail.com")
            tel_agri    = st.text_input(" Téléphone", placeholder="Ex : +221770130572")
        with c2:
            station_agri  = st.text_input(" ID Station associée", placeholder="Ex : ST002")
            station_nom_a = st.text_input(" Nom de la station", placeholder="Ex : Station Kaolack Centre")
            region_agri   = st.selectbox(" Région", REGIONS_SN)
        submitted_agri = st.form_submit_button(" Enregistrer l'agriculteur", use_container_width=True)

    if submitted_agri:
        if not nom_agri or not email_agri or not station_agri:
            st.warning("Veuillez remplir au minimum : Nom, Email et ID Station.")
        else:
            ok, resp = _post("/agriculteurs", {
                "nom":         nom_agri,
                "email":       email_agri,
                "telephone":   tel_agri,
                "station_id":  station_agri,
                "station_nom": station_nom_a or station_agri,
                "region":      region_agri,
                "actif":       True,
            })
            if ok:
                st.success(resp.get("message", f"Agriculteur {nom_agri} ajouté avec succès !"))
                time.sleep(5)
                st.rerun()
            else:
                st.error(f" Erreur : {resp.get('detail', 'Inconnue')}")


def _page_seuils(stations):
    st.markdown("####  Seuils d'alerte par Culture")
    st.info(" Définissez dynamiquement les seuils agronomiques pour chaque type de culture.")

    cultures_list = ["Tomate", "Poivron", "Aubergine", "Mais", "Oignon"]
    selected_culture = st.selectbox("Sélectionnez la culture à configurer", cultures_list)

    # Récupérer les seuils actuels de cette culture
    seuils_actuels = _get(f"/seuils/culture/{selected_culture}", default={
        "HUM_SOL_MIN": 40.0, "HUM_SOL_MAX": 70.0,
        "TEMP_AIR_MIN": 15.0, "TEMP_AIR_MAX": 30.0,
        "HUM_AIR_MIN": 50.0, "HUM_AIR_MAX": 85.0,
        "VENT_MAX": 25.0
    })

    with st.form("form_seuils_culture"):
        sc1, sc2 = st.columns(2)
        with sc1:
            hum_sol_min = st.number_input(" Humidité sol min (%)", value=float(seuils_actuels.get("HUM_SOL_MIN", 40.0)), step=1.0)
            hum_sol_max = st.number_input(" Humidité sol max (%)", value=float(seuils_actuels.get("HUM_SOL_MAX", 70.0)), step=1.0)
            temp_min = st.number_input("❄️ Température min air (°C)", value=float(seuils_actuels.get("TEMP_AIR_MIN", 15.0)), step=0.5)
            temp_max = st.number_input(" Température max air (°C)", value=float(seuils_actuels.get("TEMP_AIR_MAX", 30.0)), step=0.5)
        with sc2:
            hum_air_min = st.number_input(" Humidité air min (%)", value=float(seuils_actuels.get("HUM_AIR_MIN", 50.0)), step=1.0)
            hum_air_max = st.number_input(" Humidité air max (%)", value=float(seuils_actuels.get("HUM_AIR_MAX", 85.0)), step=1.0)
            vent_max = st.number_input(" Vitesse vent max (km/h)", value=float(seuils_actuels.get("VENT_MAX", 25.0)), step=1.0)
            
        submitted = st.form_submit_button(f" Enregistrer les seuils pour : {selected_culture}", width='stretch')

    if submitted:
        ok, resp = _post(f"/seuils/culture/{selected_culture}", {
            "hum_sol_min": hum_sol_min,
            "hum_sol_max": hum_sol_max,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "hum_air_min": hum_air_min,
            "hum_air_max": hum_air_max,
            "vent_max": vent_max
        })
        if ok: st.success(f" Seuils pour la culture {selected_culture} mis à jour avec succès !")
        else:  st.error(f" Erreur : {resp.get('detail', 'Inconnue')}")


# Page Système Expert supprimée (les mises à jour de dataset se font automatiquement)


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
        st.markdown(
            "<div style='text-align:center;padding:18px 0 12px;'>"
            "<div style='font-size:2.8rem;filter:drop-shadow(0 0 8px rgba(255,255,255,0.40));'></div>"
            "<div style='font-family:Sora,sans-serif;font-weight:900;font-size:1.05rem;margin-top:4px;'>Station Météo</div>"
            "<div style='font-size:0.75rem;opacity:0.65;'>Interface Administrateur</div>"
            "</div>",
            unsafe_allow_html=True
        )

        section = st.radio("Navigation", [
            " Tableau de Bord",
            " Données Temps Réel",
            " Gestion Agriculteurs",
            " Seuils d'Alerte",
        ], label_visibility="collapsed")

        st.markdown("** Filtrer par Région**")
        regions_dispo = ["Toutes"] + sorted({
            data.get("region", "") for data in stations.values() if data.get("region")
        })
        filtre_region = st.selectbox("Région", regions_dispo,
                                     label_visibility="collapsed", key="admin_filtre_region")

        st.markdown("---")

        auto = st.checkbox("Actualisation auto (30 min)", value=True)

        st.markdown("---")

        if st.button(" Se déconnecter", width='stretch', key="btn_deco_admin"):
            deconnexion()

        st.markdown(
            "<div style='font-size:0.68rem;opacity:0.45;text-align:center;margin-top:10px;'>"
            "ESP32 + SIM7600 + Firebase<br>Projet IoT Agricole"
            "</div>",
            unsafe_allow_html=True
        )

    # ══════════════════════════════════════════
    #  ROUTING
    # ══════════════════════════════════════════
    stations_aff = {k: v for k, v in stations.items() if v.get("region") == filtre_region} \
                  if filtre_region != "Toutes" else stations

    if   "Tableau de Bord"       in section: _page_tableau(stations_aff, agriculteurs)
    elif "Données Temps Réel"    in section: _page_donnees(stations_aff)
    elif "Gestion Agriculteurs"  in section: _page_agriculteurs(agriculteurs)
    elif "Seuils"                in section: _page_seuils(stations_aff)

    # Actualisation automatique à la toute fin pour permettre l'affichage complet de la page
    if auto:
        st.sidebar.info("Actualisation dans 30 min...")
        time.sleep(1800)
        st.rerun()