"""
agriculteur.py — Dashboard Agriculteur (Streamlit)
Style : Sidebar vert foncé Station_meteo
"""

import streamlit as st
import requests
from components.http import http_get, http_post
import time
from datetime import datetime


import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from components.charts       import graphique_historique, graphique_jauge, graphique_tous_capteurs
from components.weather_card import (
    afficher_previsions, afficher_alerte_meteo, afficher_meteo_actuelle,
    html_meteo_entete, html_meteo_carte_ia,
)
from components.html_render  import esc, render_html
from components.auth         import deconnexion
from components.map_component import afficher_carte_parcelle, afficher_carte_stations

BACKEND = "https://agri-station-meteo.onrender.com"

REGIONS = [
    "Kaolack",
    "Dakar",
    "Thiès",
    "Diourbel",
    "Fatick",
    "Kaffrine",
    "Kédougou",
    "Kolda",
    "Louga",
    "Matam",
    "Saint-Louis",
    "Sédhiou",
    "Tambacounda",
    "Ziguinchor",
]


def _get(endpoint, default=None):
    try:
        r = http_get(f"{BACKEND}{endpoint}", timeout=60)
        return r.json() if r.status_code == 200 else default
    except Exception:
        return default


def _post(endpoint, body, default=None):
    try:
        r = http_post(f"{BACKEND}{endpoint}", json=body, timeout=60)
        return r.json() if r.status_code == 200 else default
    except Exception:
        return default


def _calculer_alertes(mesures, seuils):
    alertes = []
    temp    = mesures.get("temperature")
    hum_sol = mesures.get("humidite_sol")
    vent    = mesures.get("vitesse_vent")
    
    # Support both global seuils format (lowercase) and culture seuils format (uppercase)
    temp_max = seuils.get("TEMP_AIR_MAX") or seuils.get("temp_max") or 40.0
    temp_min = seuils.get("TEMP_AIR_MIN") or seuils.get("temp_min") or 15.0
    hum_sol_min = seuils.get("HUM_SOL_MIN") or seuils.get("hum_sol_min") or 25.0
    vent_max = seuils.get("VENT_MAX") or seuils.get("vent_max") or 45.0
    
    if temp    and temp    > temp_max: alertes.append(f"Temperature critique : {temp:.1f}C (seuil : {temp_max}C)")
    if temp    and temp    < temp_min: alertes.append(f"Temperature trop basse : {temp:.1f}C (seuil : {temp_min}C)")
    if hum_sol and hum_sol < hum_sol_min: alertes.append(f"Sol trop sec : {hum_sol:.1f}% (seuil : {hum_sol_min}%)")
    if vent    and vent    > vent_max: alertes.append(f"Vent dangereux : {vent:.1f} km/h (seuil : {vent_max} km/h)")
    return alertes


# ── Pages ─────────────────────────────────────────────────────────────────────

def _page_accueil(station_id, nom, station_nom, region):
    culture = st.session_state.get("culture", "Manioc")
    
    # ── Chargement de toutes les données en premier ──
    with st.spinner("Chargement des données..."):
        meteo      = _get(f"/meteo-actuelle?region={region}", default={"ok": False})
        mesures    = _get(f"/mesures/{station_id}", default={})
        previsions = _get(f"/previsions/{station_id}?region={region}", default={"ok": False})
        seuils     = _get(f"/seuils/culture/{culture}", default={
            "HUM_SOL_MIN": 40.0, "HUM_SOL_MAX": 70.0,
            "TEMP_AIR_MIN": 15.0, "TEMP_AIR_MAX": 30.0,
            "HUM_AIR_MIN": 50.0, "HUM_AIR_MAX": 85.0,
            "VENT_MAX": 25.0
        })

    if not mesures:
        st.error(" Impossible de récupérer les mesures. Vérifiez que le backend est démarré.")
        return

    temp    = mesures.get("temperature",  "--")
    hum_air = mesures.get("humidite_air", "--")
    hum_sol = mesures.get("humidite_sol", "--")
    vent    = mesures.get("vitesse_vent", "--")
    ts      = mesures.get("timestamp",    "N/A")

    # ── Alertes calculées avant l'entête ──
    alertes = _calculer_alertes(mesures, seuils) + afficher_alerte_meteo(previsions)
    if alertes:
        alertes_items = "".join(
            "<div style='"
            "display:flex;align-items:flex-start;gap:8px;"
            "background:rgba(255,80,80,0.12);border-left:3px solid #ff5252;"
            "border-radius:6px;padding:6px 10px;margin-bottom:5px;"
            "font-size:0.75rem;line-height:1.4;color:#ffe0e0;'"
            ">" + esc(al) + "</div>"
            for al in alertes
        )
        bloc_alertes = (
            "<div style='display:flex;flex-direction:column;gap:0;'>"
            "<div style='font-size:0.72rem;font-weight:800;letter-spacing:0.05em;"
            "color:#ff6b6b;margin-bottom:6px;display:flex;align-items:center;gap:6px;'>"
            "<span style='display:inline-block;width:8px;height:8px;border-radius:50%;"
            "background:#ff5252;box-shadow:0 0 6px #ff5252;animation:pulse 1.2s infinite;'></span>"
            + str(len(alertes)) + " ALERTE" + ("S" if len(alertes) > 1 else "") + " ACTIVE" + ("S" if len(alertes) > 1 else "") +
            "</div>"
            + alertes_items +
            "</div>"
        )
    else:
        bloc_alertes = (
            "<div style='display:flex;align-items:center;gap:8px;"
            "background:rgba(0,217,126,0.1);border-left:3px solid #00d97e;"
            "border-radius:6px;padding:8px 12px;font-size:0.78rem;color:#b0f4d8;'>"
            "<span style='font-size:1rem;'></span> Aucune alerte active"
            "</div>"
        )

    # ── Entête avec alertes intégrées à droite ──
    heure      = datetime.now().strftime('%H:%M:%S')
    meteo_bloc = html_meteo_entete(meteo)

    html_entete = (
        "<div class='entete fade-in' style='display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;'>"
        # Colonne gauche
        "<div style='flex:1;min-width:220px;'>"
        "<h1> Bonjour, " + esc(nom) + "</h1>"
        "<div class='sous-titre'>"
        "<span class='live-dot'></span>"
        + esc(station_nom) + " &nbsp;·&nbsp; " + esc(region) + " &nbsp;·&nbsp; " + heure
        + "</div>"
        + meteo_bloc
        + "</div>"
        # Colonne droite — alertes
        "<div style='min-width:220px;max-width:340px;flex:0 0 auto;'>"
        + bloc_alertes +
        "</div>"
        "</div>"
    )
    render_html(html_entete)
    st.markdown("#### Mesures en temps reel")
    
    # Dynamic thresholds for UI metrics
    temp_max_val = seuils.get("TEMP_AIR_MAX") or seuils.get("temp_max") or 30.0
    hum_sol_min_val = seuils.get("HUM_SOL_MIN") or seuils.get("hum_sol_min") or 40.0
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Temperature",  f"{temp}C"    if isinstance(temp,    (int, float)) else temp,    delta="Eleve" if isinstance(temp, float) and temp > temp_max_val else None)
    with c2: st.metric("Humidite air", f"{hum_air}%"  if isinstance(hum_air, (int, float)) else hum_air)
    with c3: st.metric("Humidite sol", f"{hum_sol}%"  if isinstance(hum_sol, (int, float)) else hum_sol, delta="Sec" if isinstance(hum_sol, float) and hum_sol < hum_sol_min_val else None)
    with c4: st.metric("Vent",         f"{vent} km/h" if isinstance(vent,    (int, float)) else vent)
    st.caption(f"Derniere mesure : {ts} &nbsp;·&nbsp; Culture : **{culture}**")


    # ── Recommandation IA + Timeline Planning ────────────────────────────────
    st.markdown("#### 🤖 Assistant Agricole IA")

    if all(isinstance(v, (int, float)) for v in [temp, hum_air, hum_sol, vent]):
        # --- PARTIE 1 : Situation actuelle (ESP32) ---
        reco = _post("/recommandation", {
            "temperature": temp, "humidite_air": hum_air,
            "humidite_sol": hum_sol, "vitesse_vent": vent,
            "nom": nom, "region": region, "culture": culture
        })

        # --- PARTIE 2 : Planning du jour (OpenWeather) ---
        planning_data = _get(f"/ia/planning/{station_id}?region={region}", default={"planning": []})
        planning = planning_data.get("planning", [])

        # --- Couleur selon index ---
        COULEURS = {
            0: ("#00d97e", "#003d20", "rgba(0,217,126,0.1)"),
            1: ("#f5a623", "#3d2800", "rgba(245,166,35,0.12)"),
            2: ("#4fc3f7", "#003952", "rgba(79,195,247,0.12)"),
            3: ("#ff7043", "#3d1400", "rgba(255,112,67,0.12)"),
            4: ("#29b6f6", "#003952", "rgba(41,182,246,0.12)"),
            5: ("#b0bec5", "#1a2a30", "rgba(176,190,197,0.12)"),
            6: ("#ce93d8", "#2d003d", "rgba(206,147,216,0.12)"),
        }

        if reco:
            idx_now  = reco.get("label_idx", 0)
            c_now    = COULEURS.get(idx_now, COULEURS[0])

            # Trouver la prédiction du créneau actuel pour confirmation
            heure_now = datetime.now().hour
            pred_idx  = idx_now  # par défaut pas de créneau futur trouvé
            statut_confirmation = None
            for c in planning:
                try:
                    h = int(c["heure"][:2])
                except Exception:
                    h = -1
                if h <= heure_now:
                    pred_idx = c["label_idx"]
                    break

            if pred_idx == idx_now:
                if idx_now == 0:
                    statut_confirmation = ("🟢", "#00d97e", "CONFIRMÉ", "ESP32 et météo indiquent des conditions optimales")
                else:
                    statut_confirmation = ("🔴", "#ff5252", "ALERTE RENFORCÉE", "ESP32 et météo signalent le même problème")
            else:
                if idx_now == 0 and pred_idx != 0:
                    statut_confirmation = ("🟡", "#f5a623", "DIVERGENCE", "Capteurs OK mais la météo prévoit un risque")
                else:
                    statut_confirmation = ("🟡", "#f5a623", "SURVEILLANCE", "Situation évolutive — restez attentif")

            # Bloc situation actuelle
            badge_confirm = ""
            if statut_confirmation:
                ic, col, lab, desc = statut_confirmation
                badge_confirm = (
                    f"<div style='display:flex;align-items:center;gap:8px;"
                    f"background:rgba(255,255,255,0.05);border-radius:8px;"
                    f"padding:6px 12px;margin-top:10px;'>"
                    f"<span style='font-size:1.1rem'>{ic}</span>"
                    f"<span style='color:{col};font-weight:800;font-size:0.8rem'>{lab}</span>"
                    f"<span style='color:#a0aec0;font-size:0.75rem'>— {esc(desc)}</span>"
                    f"</div>"
                )

            render_html(
                f"<div style='background:{c_now[2]};border-left:4px solid {c_now[0]};"
                f"border-radius:12px;padding:16px 18px;margin-bottom:12px;'>"
                f"<div style='font-size:0.72rem;color:{c_now[0]};font-weight:800;"
                f"letter-spacing:0.08em;margin-bottom:6px'>📡 MAINTENANT — {datetime.now().strftime('%H:%M')}</div>"
                f"<div style='font-size:1.1rem;font-weight:800;color:#fff;margin-bottom:4px'>"
                f"{esc(reco.get('emoji',''))} {esc(reco.get('label',''))}</div>"
                f"<div style='color:#cbd5e0;font-size:0.85rem;line-height:1.5'>{esc(reco.get('conseil',''))}</div>"
                + badge_confirm +
                f"</div>"
            )

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🔊 Écouter le conseil", width='stretch', key="btn_tts"):
                    try:
                        resp = http_post(f"{BACKEND}/tts",
                                     json={"texte": reco.get("message_vocal", reco.get("conseil", "")),
                                         "lent": False}, timeout=15)
                        if resp.status_code == 200:
                            st.audio(resp.content, format="audio/mp3")
                        else:
                            st.error("Erreur lors de la generation audio")
                    except Exception as e:
                        st.error(f"Service vocal indisponible : {e}")

        else:
            st.info("Recommandation IA indisponible — vérifiez le backend.")

        # --- PARTIE 2 : Timeline du jour ---
        if planning:
            st.markdown("#### 📅 Planning de la Journée")
            heure_now = datetime.now().hour

            html_timeline = "<div style='display:flex;flex-direction:column;gap:6px;'>"
            for creneau in planning:
                idx_c   = creneau.get("label_idx", 0)
                c_col   = COULEURS.get(idx_c, COULEURS[0])
                passe   = creneau.get("passe", False)
                heure_c = creneau.get("heure", "")
                # Créneau en cours
                try:
                    h_c = int(heure_c[:2])
                    en_cours = (h_c <= heure_now < h_c + 3)
                except Exception:
                    en_cours = False

                opacity   = "0.4" if passe else "1"
                border_w  = "3px" if en_cours else "2px"
                bg_extra  = f"border:2px solid {c_col[0]};" if en_cours else ""

                html_timeline += (
                    f"<div style='display:flex;align-items:flex-start;gap:12px;"
                    f"opacity:{opacity};padding:10px 14px;"
                    f"background:{c_col[2]};border-left:{border_w} solid {c_col[0]};"
                    f"border-radius:10px;{bg_extra}'>"
                    # Heure
                    f"<div style='min-width:52px;font-size:0.82rem;font-weight:800;"
                    f"color:{c_col[0]};padding-top:2px'>{esc(heure_c)}"
                    + (" <span style='font-size:0.6rem'>▶</span>" if en_cours else "") +
                    f"</div>"
                    # Contenu
                    f"<div style='flex:1'>"
                    f"<div style='font-size:0.88rem;font-weight:700;color:#e2e8f0;margin-bottom:2px'>"
                    f"{esc(creneau.get('emoji',''))} {esc(creneau.get('label',''))}</div>"
                    f"<div style='font-size:0.78rem;color:#a0aec0;line-height:1.4'>{esc(creneau.get('conseil',''))}</div>"
                    f"</div>"
                    # Mini données météo
                    f"<div style='text-align:right;font-size:0.7rem;color:#718096;white-space:nowrap'>"
                    f"🌡️ {creneau.get('temperature','--')}°C<br>"
                    f"💨 {creneau.get('vitesse_vent','--')} km/h<br>"
                    f"🌧️ {creneau.get('pluie','--')} mm"
                    f"</div>"
                    f"</div>"
                )
            html_timeline += "</div>"
            render_html(html_timeline)
        else:
            st.info("Planning du jour indisponible — OpenWeather inaccessible.")

    else:
        st.info("Données capteurs insuffisantes pour générer une recommandation.")

    render_html("<div class='footer'>Station Meteo Agricole · Reseau IoT Senegal · USSEIN</div>")


def _page_gps(station_id, mesures):
    """Page dediee a la carte GPS de la station."""
    st.markdown("#### Localisation de la Parcelle")
    # Charger les mesures en temps réel pour l'affichage de la carte
    mesures_reelles = _get(f"/mesures/{station_id}", default={})
    gps_data = _get(f"/stations/{station_id}/gps", default={"latitude": None, "longitude": None})
    lat = gps_data.get("latitude")
    lon = gps_data.get("longitude")
    if lat and lon:
        stations_dict = {
            station_id: {
                "gps":     {"latitude": lat, "longitude": lon},
                "mesures": mesures_reelles,
            }
        }
        afficher_carte_stations(stations_dict)
    else:
        st.info("Calibrage GPS en cours. La localisation sera bientot disponible.")


def _page_historique(station_id):
    st.markdown("#### Historique complet")
    historique = _get(f"/historique/{station_id}?limit=200", default={}).get("historique", [])
    if not historique:
        st.info("Aucun historique disponible."); return
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Temperature", "Humidite air", "Humidite sol", "Vent", "Vue globale"])
    with tab1: st.plotly_chart(graphique_historique(historique, "temperature"),  width='stretch', config={"displayModeBar": False})
    with tab2: st.plotly_chart(graphique_historique(historique, "humidite_air"), width='stretch', config={"displayModeBar": False})
    with tab3: st.plotly_chart(graphique_historique(historique, "humidite_sol"), width='stretch', config={"displayModeBar": False})
    with tab4: st.plotly_chart(graphique_historique(historique, "vitesse_vent"), width='stretch', config={"displayModeBar": False})
    with tab5: st.plotly_chart(graphique_tous_capteurs(historique),              width='stretch', config={"displayModeBar": False})


def _page_previsions(station_id, region):
    st.markdown("####  Prévisions météo — 5 prochains jours")
    previsions = _get(f"/previsions/{station_id}?region={region}", default={"ok": False})
    afficher_previsions(previsions)


# ── Page principale avec sidebar ──────────────────────────────────────────────

def page_agriculteur():
    st.markdown("""
    <style>
    /* ===== CARD METEO ACTUELLE ===== */
    .meteo-now-card{ background:linear-gradient(135deg,#16351c,#1f4d2c); border-radius:18px; padding:20px; color:white; box-shadow:0 6px 22px rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.08); margin-bottom:18px; }
    .meteo-now-top{ display:flex; align-items:center; gap:18px; }
    .meteo-now-icon{ font-size:3.2rem; line-height:1; }
    .meteo-now-temp{ font-size:2rem; font-weight:800; line-height:1; }
    .meteo-now-desc{ font-size:0.95rem; opacity:0.85; margin-top:4px; }
    .meteo-now-ville{ margin-top:18px; font-size:0.9rem; opacity:0.9; }
    .meteo-now-infos{ margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08); font-size:0.88rem; opacity:0.92; }

    /* ===== MÉTÉO COMPACTE DANS L'ENTÊTE ===== */
    .meteo-entete{
        display:inline-flex;
        align-items:center;
        gap:6px;
        margin-top:7px;
        background:rgba(255,255,255,0.10);
        border:1px solid rgba(255,255,255,0.18);
        border-radius:20px;
        padding:4px 12px;
        font-size:0.78rem;
        font-weight:700;
        color:white;
        backdrop-filter:blur(4px);
        flex-wrap:wrap;
    }
    .meteo-entete strong{ font-size:0.90rem; }
    .meteo-entete-sep{ opacity:0.45; margin:0 2px; }

    /* ===== COLONNE MÉTÉO DROITE (bloc IA) — masquée sur mobile ===== */
    .ia-meteo-desktop{ display:block; }
    @media(max-width:768px){
        .ia-meteo-desktop{ display:none !important; }
    }

    /* ===== GRILLE PREVISIONS ===== */
    .previsions-grid{
        display:grid;
        grid-template-columns:repeat(5,1fr);
        gap:8px;
        width:100%;
    }

    /* ===== BLOC IA : reco à gauche, météo à droite ===== */
    .ia-flex-row{
        display:flex;
        gap:16px;
        align-items:flex-start;
        flex-wrap:nowrap;
    }
    .ia-reco-col{ flex:3; min-width:0; }
    .ia-meteo-col{ flex:2; min-width:180px; }

    /* ===== RESPONSIVE MOBILE ===== */
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
            gap: 5px !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{
            flex: 0 0 calc(48% - 3px) !important;
            max-width: calc(48% - 3px) !important;
            min-width: 0 !important;
            width: calc(48% - 3px) !important;
            box-sizing: border-box !important;
        }

        [data-testid="stMetric"]{
            min-height:58px !important;
            padding:7px 5px !important;
        }
        [data-testid="stMetricValue"]{ font-size:0.85rem !important; }
        [data-testid="stMetricLabel"]{ font-size:0.48rem !important; letter-spacing:0 !important; }

        .previsions-grid{ grid-template-columns:repeat(2,1fr) !important; gap:6px !important; }

        .meteo-card{ min-height:unset !important; padding:8px 6px !important; }
        .meteo-card .temp{ font-size:0.88rem !important; }
        .meteo-card .jour{ font-size:0.58rem !important; }
        .meteo-card .desc{ font-size:0.60rem !important; }

        .meteo-now-card{ max-width:100% !important; padding:10px !important; }
        .meteo-now-icon{ font-size:1.8rem !important; }
        .meteo-now-temp{ font-size:1.2rem !important; }
        .meteo-now-desc{ font-size:0.72rem !important; }

        .ia-flex-row{
            flex-direction:column !important;
            flex-wrap:wrap !important;
        }
        .ia-reco-col, .ia-meteo-col{
            flex:unset !important;
            width:100% !important;
            min-width:0 !important;
        }

        [data-testid="stHorizontalBlock"]:has(.reco-card) > [data-testid="stColumn"]:last-child{
            flex: 0 0 0 !important;
            max-width: 0 !important;
            overflow: hidden !important;
            padding: 0 !important;
        }
        [data-testid="stHorizontalBlock"]:has(.reco-card) > [data-testid="stColumn"]:first-child{
            flex: 0 0 100% !important;
            max-width: 100% !important;
            width: 100% !important;
        }

        h1{ font-size:1.1rem !important; }
        .entete h1,.entete-admin h1,.page-header h1{ font-size:1.1rem !important; }
        .entete,.entete-admin,.page-header{
            padding:10px 12px !important;
            border-radius:14px !important;
            margin-bottom:10px !important;
        }
        .sous-titre{ font-size:0.66rem !important; }

        .stTabs [data-baseweb="tab"]{ font-size:0.63rem !important; padding:4px 5px !important; }

        .stButton>button{ font-size:0.76rem !important; padding:8px !important; }

        .reco-card{ padding:12px 14px !important; }
        .reco-icon{ font-size:1.4rem !important; }
        .reco-titre{ font-size:0.85rem !important; }
        .reco-desc{ font-size:0.74rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    station_id  = st.session_state.get("station_id",  "ST002")
    nom         = st.session_state.get("nom",          "Agriculteur")
    station_nom = st.session_state.get("station_nom",  station_id)
    region      = st.session_state.get("region",       "Kaolack")

    # ══════════════════════════════════════════
    #  SIDEBAR — style Station_meteo
    # ══════════════════════════════════════════
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center;padding:18px 0 12px;'>"
            "<div style='font-size:2.8rem;filter:drop-shadow(0 0 8px rgba(255,255,255,0.35));'></div>"
            "<div style='font-family:Sora,sans-serif;font-weight:900;font-size:1.05rem;margin-top:4px;'>" + nom + "</div>"
            "<div style='font-size:0.78rem;opacity:0.65;'>Agriculteur</div>"
            "<div style='font-size:0.70rem;opacity:0.50;margin-top:3px;'> " + station_nom + "</div>"
            "</div>",
            unsafe_allow_html=True
        )

        st.markdown("---")

        page = st.radio("Navigation", [
            "Accueil",
            "Localisation GPS",
            "Historique",
            "Previsions",
        ], label_visibility="collapsed", key="agri_nav_radio")

        # Dès que l'utilisateur change d'onglet, forcer un rerun propre
        # pour effacer complètement le contenu de la page précédente
        if st.session_state.get("_agri_prev_page") != page:
            st.session_state["_agri_prev_page"] = page
            st.rerun()

        st.markdown("---")

        st.markdown("**Culture de la Station**")
        with st.spinner("Récupération de la culture..."):
            culture_info = _get(f"/stations/{station_id}/culture", default={"culture": "Manioc"})
            culture_active = culture_info.get("culture", "Manioc")

        cultures_list = ["Manioc", "Tomate", "Poivron", "Aubergine", "Oignon"]
        if culture_active not in cultures_list:
            cultures_list.append(culture_active)
        culture_index = cultures_list.index(culture_active) if culture_active in cultures_list else 0
        culture_sel = st.selectbox("Culture", cultures_list, index=culture_index, label_visibility="collapsed", key="agri_culture_sel")

        if culture_sel != culture_active:
            with st.spinner("Mise à jour de la culture..."):
                _post(f"/stations/{station_id}/culture", {"culture": culture_sel})
            st.rerun()

        st.session_state["culture"] = culture_sel

        st.markdown("**Région**")
        region_sel = st.selectbox("Région", REGIONS,
                                  index=REGIONS.index(region) if region in REGIONS else 0,
                                  label_visibility="collapsed", key="agri_region_sel")
        st.session_state["region"] = region_sel

        st.markdown("---")

        auto = st.checkbox("Actualisation auto (30 min)", value=True)

        st.markdown("---")

        st.markdown(
            "<div class='sidebar-box'>"
            "<div style='font-weight:800;font-size:0.82rem;margin-bottom:6px;'> Ma Station</div>"
            "<div style='font-size:0.80rem;opacity:0.85;'> ID : " + station_id + "</div>"
            "<div style='font-size:0.80rem;opacity:0.85;'> " + region_sel + "</div>"
            "<div style='font-size:0.72rem;opacity:0.55;margin-top:4px;'>ESP32 + SIM7600 + Firebase</div>"
            "</div>",
            unsafe_allow_html=True
        )

        st.markdown("---")

        if st.button("Se deconnecter", width='stretch', key="btn_deco_agri"):
            deconnexion()

        st.markdown(
            "<div style='font-size:0.68rem;opacity:0.45;text-align:center;margin-top:10px;'>"
            "Projet IoT Agricole · USSEIN Sénégal"
            "</div>",
            unsafe_allow_html=True
        )

    # ══════════════════════════════════════════
    #  ROUTING
    # ══════════════════════════════════════════
    if "Accueil"          in page: _page_accueil(station_id, nom, station_nom, region_sel)
    elif "Localisation GPS" in page: _page_gps(station_id, {})
    elif "Historique"     in page: _page_historique(station_id)
    elif "Previsions"     in page: _page_previsions(station_id, region_sel)

    # Actualisation automatique via refresh navigateur (pas de time.sleep = pas de ghost)
    if auto:
        st.markdown('<meta http-equiv="refresh" content="1800">', unsafe_allow_html=True)
        st.sidebar.info("Actualisation dans 30 min...")