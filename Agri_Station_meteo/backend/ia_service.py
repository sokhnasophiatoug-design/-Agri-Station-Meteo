"""
ia_service.py — Classifieur expert agricole à 7 classes
=========================================================

Sources de données :
  Capteurs ESP32 temps réel (mesures actuelles) :
    temperature (°C), humidite_air (%), humidite_sol (%), vitesse_vent (km/h)
  OpenWeather (prévisions) :
    pluie_prevue_3h (mm) — seule donnée sans capteur ESP32

Classes prédites (priorité décroissante) :
  2 -> Alerte Drainage         (pluie prevue > PLUIE_MAX)
  1 -> Alerte Secheresse       (sol < HUM_SOL_MIN ET pluie < PLUIE_MIN)
  4 -> Alerte Saturation       (sol > HUM_SOL_MAX)
  5 -> Alerte Gel / Froid      (temp ESP32 < TEMP_MIN OU temp future < TEMP_MIN)
  3 -> Alerte Evapotranspiration (temp ESP32 > TEMP_MAX ET vent > VENT_MAX ET hum_air < HUM_AIR_MIN)
  6 -> Alerte Risque de Maladies (hum_air > HUM_AIR_MAX ET TEMP_MIN <= temp <= TEMP_MAX)
  0 -> Conditions Optimales
"""

from datetime import datetime

# ── Métadonnées des 7 classes ────────────────────────────────────────────────

LABELS = {
    0: "Conditions Optimales",
    1: "Alerte Sécheresse",
    2: "Alerte Drainage",
    3: "Alerte Évapotranspiration",
    4: "Alerte Saturation",
    5: "Alerte Gel / Froid",
    6: "Alerte Risque de Maladies"
}

EMOJIS = {
    0: "✅",
    1: "🏜️",
    2: "🌧️",
    3: "☀️",
    4: "💧",
    5: "❄️",
    6: "🍄"
}

FEATURES = [
    "temperature", "humidite_air", "humidite_sol", "vitesse_vent",
    "pluie_prevue_3h", "temperature_future", "humidite_future", "vent_future",
]


# ── Génération des conseils dynamiques ───────────────────────────────────────

def _conseil_dynamique(
    idx: int,
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
    pluie_prevue_3h: float,
    pluie_min: float,
    temp_air_min: float,
    heure_creneau: str = None,
    mode: str = "maintenant"
) -> str:
    """
    Génère un conseil agronomique concret adapté à la situation.
    mode='maintenant' -> situation actuelle ESP32, action adaptée à l'heure
    mode='planning'   -> créneau futur de la journée
    """
    h = datetime.now().hour

    def _action_irrigation() -> str:
        """Action d'irrigation précise selon l'heure actuelle."""
        if 5 <= h < 10:
            return "Ouvrez les vannes d'irrigation maintenant (goutte-à-goutte ou rigoles) pour gorger le sol avant la chaleur."
        elif 10 <= h < 17:
            return "N'irriguez pas maintenant : la chaleur evaporerait l'eau et brulerait les feuilles. Attendez 17h30."
        elif 17 <= h < 21:
            return "Ouvrez les vannes maintenant : l'eau penetrera sans s'evaporer, parfait pour la nuit."
        else:
            return "Planifiez un arrosage manuel ou automatique dès l'aube pour hydrater les plants."

    # ── Index 2 : Alerte Drainage ─────────────────────────────────────────────
    if idx == 2:
        if mode == "planning":
            return (
                f"{pluie_prevue_3h:.0f} mm de pluie prevus avant {heure_creneau}. "
                f"Debouchez vos canaux et creusez des sillons entre les rangs "
                f"pour que l'eau puisse s'ecouler librement hors de la parcelle. "
                f"Un sol gorge asphyxie les racines et lessive les nutriments."
            )
        return (
            f"Fortes pluies prevues ({pluie_prevue_3h:.0f} mm). "
            f"Agissez maintenant : debouchez vos canaux d'ecoulement, "
            f"creusez des sillons entre les rangs si l'eau stagne, "
            f"et ouvrez les sorties d'eau en bordure de parcelle. "
            f"Un sol gorge d'eau asphyxie les racines."
        )

    # ── Index 1 : Alerte Secheresse ───────────────────────────────────────────
    elif idx == 1:
        if pluie_prevue_3h > 0:
            if mode == "planning":
                return (
                    f"Sol sec a {heure_creneau}, pluie prevue ({pluie_prevue_3h:.1f} mm) "
                    f"insuffisante (besoin : {pluie_min:.0f} mm). "
                    f"Planifiez un arrosage copieux a l'aube pour eviter le stress hydrique."
                )
            return (
                f"La pluie prevue ({pluie_prevue_3h:.1f} mm) ne suffira pas (besoin : {pluie_min:.0f} mm). "
                f"La secheresse bloque la photosynthese. {_action_irrigation()}"
            )
        else:
            if mode == "planning":
                return (
                    f"Sol sec prevu a {heure_creneau}, aucune pluie attendue. "
                    f"Programmez un arrosage copieux en debut de matinée ou en soirée "
                    f"pour eviter que les feuilles ne fanent."
                )
            return (
                f"Sol trop sec, aucune pluie prevue (stress hydrique : photosynthese ralentie, feuilles fanees). "
                f"{_action_irrigation()}"
            )

    # ── Index 4 : Alerte Saturation ───────────────────────────────────────────
    elif idx == 4:
        if mode == "planning":
            return (
                f"Sol encore sature a {heure_creneau}. "
                f"Coupez tout systeme d'arrosage automatique."
            )
        return (
            "Sol gorge d'eau (risque d'asphyxie des racines) : fermez immediatement vos vannes d'arrosage. "
            "Evacuez l'eau stagnante et laissez la surface du sol secher avant toute nouvelle intervention."
        )

    # ── Index 5 : Alerte Gel / Froid ──────────────────────────────────────────
    elif idx == 5:
        if mode == "planning":
            return (
                f"Temperature froide ({temperature:.0f}°C) prevue a {heure_creneau} (seuil min : {temp_air_min:.0f}°C). "
                f"Préparez et installez des voiles d'hivernage, de la paille ou des baches plastiques."
            )
        if h >= 17 or h < 8:
            return (
                f"Froid critique ({temperature:.0f}°C). Le gel bloque la photosynthese. "
                f"Couvrez d'urgence vos cultures (baches, paille au sol) et arretez les arrosages de nuit."
            )
        return (
            f"Froid critique ({temperature:.0f}°C). Préparez des couvertures thermiques ou du paillage "
            f"a installer sur vos plants avant la fin de l'apres-midi."
        )

    # ── Index 3 : Alerte Evapotranspiration ───────────────────────────────────
    elif idx == 3:
        if mode == "planning":
            return (
                f"Chaleur, vent ({vitesse_vent:.0f} km/h) et air sec prevus a {heure_creneau}. "
                f"Evaporation maximale : ne lancez pas d'arrosage en plein champ et reportez les traitements."
            )
        return (
            f"Fort dessèchement en cours (vent fort {vitesse_vent:.0f} km/h). "
            f"N'arrosez pas par aspersion (utilisez uniquement le goutte-à-goutte sous paillage si urgent). "
            f"Ne pulverisez aucun traitement (le vent derive les produits hors de la parcelle)."
        )

    # ── Index 6 : Alerte Risque de Maladies ───────────────────────────────────
    elif idx == 6:
        if mode == "planning":
            return (
                f"Risque de maladies fongiques a {heure_creneau} (humidite de l'air > 80%). "
                f"Espacez les plants pour ameliorer l'aeration et preparez une inspection visuelle."
            )
        if h >= 16:
            return (
                "Humidite propice au mildiou/champignons : examinez le dessous des feuilles. "
                "Retirez les feuilles tachees et appliquez un traitement preventif (bio ou cuivre) ce soir."
            )
        return (
            "Humidite de l'air tres elevee. Inspectez le feuillage aujourd'hui : en cas de taches ou duvet blanc, "
            "coupez les parties malades pour stopper la propagation."
        )

    # ── Index 0 : Conditions Optimales ────────────────────────────────────────
    else:
        if mode == "planning":
            return f"Conditions ideales a {heure_creneau}."
        return (
            "Meteo parfaite (sol, air, vent dans les normes). Profitez-en pour biner et desherber "
            "ou pour realiser vos pulverisations d'engrais et de traitements en toute securite."
        )



# ── Moteur de décision principal ─────────────────────────────────────────────

def _appliquer_regles(
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
    pluie_prevue_3h: float,
    temperature_future: float,
    hum_sol_min: float,
    hum_sol_max: float,
    temp_air_min: float,
    temp_air_max: float,
    hum_air_min: float,
    hum_air_max: float,
    vent_max: float,
    pluie_max: float,
    pluie_min: float,
) -> int:
    """Applique les règles dans l'ordre de priorité et retourne l'index."""
    # 1. Pluie abondante -> Drainage
    if pluie_prevue_3h > pluie_max:
        return 2
    # 2. Sol sec + pluie insuffisante -> Secheresse / Irrigation
    if humidite_sol < hum_sol_min and pluie_prevue_3h < pluie_min:
        return 1
    # 3. Sol gorge -> Saturation
    if humidite_sol > hum_sol_max:
        return 4
    # 4. Froid : ESP32 OU prevision OpenWeather (risque nocturne)
    if temperature < temp_air_min or temperature_future < temp_air_min:
        return 5
    # 5. Chaleur + vent + air sec -> Evapotranspiration (ESP32 temps reel)
    if temperature > temp_air_max and vitesse_vent > vent_max and humidite_air < hum_air_min:
        return 3
    # 6. Air sature + temperature dans plage optimale culture -> Maladies (ESP32)
    if humidite_air > hum_air_max and (temp_air_min <= temperature <= temp_air_max):
        return 6
    # 7. Tout va bien
    return 0


# ── API publique ─────────────────────────────────────────────────────────────

def get_recommandation(
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
    pluie_prevue_3h: float = 0.0,
    temperature_future: float = 0.0,
    humidite_future: float = 0.0,
    vent_future: float = 0.0,
    culture: str = "Manioc",
    seuils: dict = None
) -> dict:
    """Predit la recommandation en mode temps reel (ESP32 + pluie OpenWeather)."""
    if seuils is None:
        try:
            from firebase_service import get_seuils_culture
            seuils = get_seuils_culture(culture)
        except Exception:
            try:
                from firebase_service import DEFAULT_CULTURES_SEUILS
                seuils = DEFAULT_CULTURES_SEUILS.get(culture, DEFAULT_CULTURES_SEUILS["Manioc"])
            except Exception:
                seuils = {
                    "HUM_SOL_MIN": 40.0, "HUM_SOL_MAX": 70.0,
                    "TEMP_AIR_MIN": 15.0, "TEMP_AIR_MAX": 30.0,
                    "HUM_AIR_MIN": 50.0, "HUM_AIR_MAX": 85.0,
                    "VENT_MAX": 25.0, "PLUIE_MAX": 15.0, "PLUIE_MIN": 5.0
                }

    hum_sol_min  = float(seuils.get("HUM_SOL_MIN",  40.0))
    hum_sol_max  = float(seuils.get("HUM_SOL_MAX",  70.0))
    temp_air_min = float(seuils.get("TEMP_AIR_MIN", 15.0))
    temp_air_max = float(seuils.get("TEMP_AIR_MAX", 30.0))
    hum_air_min  = float(seuils.get("HUM_AIR_MIN",  50.0))
    hum_air_max  = float(seuils.get("HUM_AIR_MAX",  85.0))
    vent_max     = float(seuils.get("VENT_MAX",      25.0))
    pluie_max    = float(seuils.get("PLUIE_MAX",     15.0))
    pluie_min    = float(seuils.get("PLUIE_MIN",      5.0))

    idx = _appliquer_regles(
        temperature, humidite_air, humidite_sol, vitesse_vent,
        pluie_prevue_3h, temperature_future,
        hum_sol_min, hum_sol_max, temp_air_min, temp_air_max,
        hum_air_min, hum_air_max, vent_max, pluie_max, pluie_min
    )

    conseil = _conseil_dynamique(
        idx, temperature, humidite_air, humidite_sol, vitesse_vent,
        pluie_prevue_3h, pluie_min, temp_air_min, mode="maintenant"
    )

    return {
        "label_idx": idx,
        "label":     LABELS[idx],
        "emoji":     EMOJIS[idx],
        "conseil":   conseil,
        "confiance": 1.0,
        "source":    "Système Expert",
    }


# ── Planning journée — 8 créneaux de 3h ──────────────────────────────────────

def planning_journee(
    station_id: str,
    region: str = "Kaolack",
    seuils: dict = None,
    humidite_sol_actuelle: float = 50.0,
) -> list:
    """
    Génère les recommandations pour les 8 créneaux de 3h de la journée en cours.
    - temperature, humidite_air, vitesse_vent, pluie : valeurs OpenWeather (prévisions)
    - humidite_sol : dernière valeur ESP32 connue (pas de capteur futur)
    Retourne une liste de dicts : heure + recommandation IA + conseil dynamique.
    """
    import weather_service

    try:
        raw = weather_service.get_crenaux_journee(region=region)
        if not raw.get("ok"):
            return []
        crenaux = raw.get("crenaux", [])
    except Exception:
        return []

    if seuils is None:
        try:
            from firebase_service import get_seuils_culture, get_station_culture
            culture = get_station_culture(station_id)
            seuils = get_seuils_culture(culture)
        except Exception:
            seuils = {
                "HUM_SOL_MIN": 40.0, "HUM_SOL_MAX": 70.0,
                "TEMP_AIR_MIN": 15.0, "TEMP_AIR_MAX": 30.0,
                "HUM_AIR_MIN": 50.0, "HUM_AIR_MAX": 85.0,
                "VENT_MAX": 25.0, "PLUIE_MAX": 15.0, "PLUIE_MIN": 5.0
            }

    hum_sol_min  = float(seuils.get("HUM_SOL_MIN",  40.0))
    hum_sol_max  = float(seuils.get("HUM_SOL_MAX",  70.0))
    temp_air_min = float(seuils.get("TEMP_AIR_MIN", 15.0))
    temp_air_max = float(seuils.get("TEMP_AIR_MAX", 30.0))
    hum_air_min  = float(seuils.get("HUM_AIR_MIN",  50.0))
    hum_air_max  = float(seuils.get("HUM_AIR_MAX",  85.0))
    vent_max     = float(seuils.get("VENT_MAX",      25.0))
    pluie_max    = float(seuils.get("PLUIE_MAX",     15.0))
    pluie_min    = float(seuils.get("PLUIE_MIN",      5.0))

    planning = []
    heure_actuelle = datetime.now().hour

    for creneau in crenaux:
        temp      = float(creneau.get("temperature", 25.0))
        hum_air   = float(creneau.get("humidite",    60.0))
        vent      = float(creneau.get("vent",        10.0))
        pluie     = float(creneau.get("pluie",        0.0))
        heure_str = creneau.get("heure", "00h00")

        # Pour le gel, temperature future = temperature du creneau
        idx = _appliquer_regles(
            temperature=temp, humidite_air=hum_air,
            humidite_sol=humidite_sol_actuelle, vitesse_vent=vent,
            pluie_prevue_3h=pluie, temperature_future=temp,
            hum_sol_min=hum_sol_min, hum_sol_max=hum_sol_max,
            temp_air_min=temp_air_min, temp_air_max=temp_air_max,
            hum_air_min=hum_air_min, hum_air_max=hum_air_max,
            vent_max=vent_max, pluie_max=pluie_max, pluie_min=pluie_min
        )

        conseil = _conseil_dynamique(
            idx, temp, hum_air, humidite_sol_actuelle, vent,
            pluie, pluie_min, temp_air_min,
            heure_creneau=heure_str, mode="planning"
        )

        # Créneau passé si son heure < heure actuelle
        try:
            heure_num = int(heure_str[:2])
        except Exception:
            heure_num = 0

        planning.append({
            "heure":        heure_str,
            "passe":        heure_num < heure_actuelle,
            "label_idx":    idx,
            "label":        LABELS[idx],
            "emoji":        EMOJIS[idx],
            "conseil":      conseil,
            "temperature":  temp,
            "humidite_air": hum_air,
            "vitesse_vent": vent,
            "pluie":        pluie,
        })

    return planning


def get_source_modele() -> str:
    return "Système Expert"


def safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ── Construction du dataset depuis Firebase ──────────────────────────────────

def construire_dataset(station_id: str) -> list:
    from firebase_service import get_historique, get_openweather_historique

    capteurs    = get_historique(station_id, limit=2000)
    openweather = get_openweather_historique(station_id)

    ow_par_date = {}
    for ow in openweather:
        if not isinstance(ow, dict):
            continue
        ts = ow.get("timestamp", "")
        if ts:
            ow_par_date[ts[:10]] = ow

    dates_ow = sorted(ow_par_date.keys())

    def trouver_ow_proche(ts_mesure: str) -> dict:
        if not dates_ow:
            return {}
        date_mesure = ts_mesure[:10] if ts_mesure else ""
        if not date_mesure:
            return ow_par_date.get(dates_ow[-1], {})
        if date_mesure in ow_par_date:
            return ow_par_date[date_mesure]
        prev = None
        for d in dates_ow:
            if d <= date_mesure:
                prev = d
            else:
                break
        return ow_par_date.get(prev or dates_ow[0], {})

    dataset = []
    for mesure in capteurs:
        if not isinstance(mesure, dict):
            continue
        t   = safe_float(mesure.get("temperature"),  0.0)
        ha  = safe_float(mesure.get("humidite_air"), 0.0)
        hs  = safe_float(mesure.get("humidite_sol"), 0.0)
        vv  = safe_float(mesure.get("vitesse_vent"), 0.0)
        ts_mesure = mesure.get("timestamp", "")
        prev = trouver_ow_proche(ts_mesure)
        dataset.append({
            "temperature":        t,
            "humidite_air":       ha,
            "humidite_sol":       hs,
            "vitesse_vent":       vv,
            "pluie_prevue_3h":    safe_float(prev.get("pluie_prevue_3h"),    0.0),
            "temperature_future": safe_float(prev.get("temperature_future"), t),
            "humidite_future":    safe_float(prev.get("humidite_future"),    ha),
            "vent_future":        safe_float(prev.get("vent_future"),        0.0),
            "timestamp":          ts_mesure,
        })

    return dataset


def generer_dataset_sur_firebase(station_id: str) -> dict:
    from firebase_service import sauvegarder_dataset
    dataset = construire_dataset(station_id)
    if not dataset:
        return {"succes": False, "message": "Historique ou OpenWeather vide.", "nb_entrees": 0}
    sauvegarder_dataset(station_id, dataset)
    return {"succes": True, "message": "Dataset fusionné sauvegardé.", "nb_entrees": len(dataset)}


def predire_depuis_firebase(station_id: str, region: str = "Kaolack") -> dict:
    from firebase_service import get_historique, get_station_culture
    import weather_service

    historique = get_historique(station_id, limit=1)
    if not historique:
        return {"erreur": f"Aucune mesure capteur pour {station_id}", "succes": False}
    d = historique[0]
    t   = safe_float(d.get("temperature"),  0.0)
    ha  = safe_float(d.get("humidite_air"), 0.0)
    hs  = safe_float(d.get("humidite_sol"), 0.0)
    vv  = safe_float(d.get("vitesse_vent"), 0.0)

    try:
        snap = weather_service.snapshot_openweather_ia(region=region)
        p  = safe_float(snap.get("pluie_prevue_3h"),    0.0)
        tf = safe_float(snap.get("temperature_future"), t)
        hf = safe_float(snap.get("humidite_future"),    ha)
        vf = safe_float(snap.get("vent_future"),        0.0)
    except Exception:
        p, tf, hf, vf = 0.0, t, ha, vv

    culture = get_station_culture(station_id)
    reco = get_recommandation(t, ha, hs, vv, p, tf, hf, vf, culture=culture)
    return {
        "succes": True, "station_id": station_id, "culture": culture,
        "capteurs": {"temperature": t, "humidite_air": ha, "humidite_sol": hs, "vitesse_vent": vv},
        "previsions_meteo": {"pluie_prevue_3h": p, "temperature_future": tf, "humidite_future": hf, "vent_future": vf},
        **reco,
    }


def reentainer_modele(station_id: str) -> dict:
    dataset = construire_dataset(station_id)
    try:
        from firebase_service import sauvegarder_dataset
        if dataset:
            sauvegarder_dataset(station_id, dataset)
    except Exception as e:
        print(f"Impossible de sauvegarder dataset pour {station_id} : {e}")
    return {
        "statut": "firebase",
        "message": "Système expert configuré et dataset mis à jour.",
        "nb_entrees": len(dataset),
        "score": 1.0
    }


# ── Message vocal agriculteur ─────────────────────────────────────────────────

def get_message_vocal(
    nom: str, region: str,
    temperature: float, humidite_air: float,
    humidite_sol: float, vitesse_vent: float,
    pluie_prevue_3h: float = 0.0,
    temperature_future: float = 0.0,
    humidite_future: float = 0.0,
    vent_future: float = 0.0,
    culture: str = "Manioc",
) -> str:
    reco = get_recommandation(
        temperature, humidite_air, humidite_sol, vitesse_vent,
        pluie_prevue_3h, temperature_future, humidite_future, vent_future,
        culture=culture
    )
    pluie_str = f"Pluie prévue : {pluie_prevue_3h:.0f} mm. " if pluie_prevue_3h > 0 else ""
    return (
        f"Bonjour {nom}, voici vos informations pour la région {region} sur votre culture de {culture}. "
        f"Température : {temperature:.0f} degrés. "
        f"Humidité du sol : {humidite_sol:.0f} pour cent. "
        f"{pluie_str}"
        f"Conseil : {reco['conseil']} "
        f"Bonne journée !"
    )
