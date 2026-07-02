"""
ia_service.py — Classifieur expert agricole à 8 features / 7 classes
===================================================================

Entrées (8 features) :
  Capteurs ESP32 temps réel :
    temperature (°C), humidite_air (%), humidite_sol (%), vitesse_vent (km/h)
  Prévisions OpenWeather :
    pluie_prevue_3h (mm), temperature_future (°C), humidite_future (%), vent_future (km/h)

Classes prédites (priorité décroissante) :
  2 → 🌧️ Alerte Drainage         (pluie prévue > 15 mm)
  1 → 🏜️ Alerte Sécheresse       (sol < HUM_SOL_MIN)
  4 → 💧 Alerte Saturation       (sol > HUM_SOL_MAX)
  5 → ❄️ Alerte Gel / Froid      (temp < TEMP_MIN ou prévue < TEMP_MIN)
  3 → ☀️ Alerte Évapotranspiration (prévue > TEMP_MAX et vent prévu > VENT_MAX et hum prévue < HUM_AIR_MIN)
  6 → 🍄 Alerte Risque de Maladies (hum prévue > HUM_AIR_MAX et 18 <= temp prévue <= 26)
  0 → ✅ Conditions Optimales
"""

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

CONSEILS_DETAILLES = {
    0: "Les conditions actuelles et les prévisions à venir sont optimales pour vos cultures.",
    1: "L'humidité du sol est basse et aucune pluie n'est prévue. Un arrosage est recommandé tôt le matin ou en soirée.",
    2: "Précipitations abondantes attendues par météo. Pensez à vérifier le drainage de vos champs et suspendez l'arrosage.",
    3: "la meteo prévoit de fortes températures, du vent et un air très sec. Risque d'un dessèchement accéléré, surveillez vos cultures.",
    4: "Le sol est saturé en eau. Risque d'asphyxie des racines. Suspendez toute irrigation.",
    5: "Baisse critique des températures prévue par la meteo ou mesurée par les capteurs. Risque de gel pour vos cultures.",
    6: "la meteo prévoit une humidité de l'air très élevée combinée à des températures douces. Risque important de développement de maladies (champignons, mildiou). Inspectez le feuillage."
}

FEATURES = [
    "temperature",
    "humidite_air",
    "humidite_sol",
    "vitesse_vent",
    "pluie_prevue_3h",
    "temperature_future",
    "humidite_future",
    "vent_future",
]


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
    culture: str = "Tomate",
    seuils: dict = None
) -> dict:
    """
    Prédit la recommandation à partir des 8 features en utilisant le système expert.
    """
    if seuils is None:
        try:
            from firebase_service import get_seuils_culture
            seuils = get_seuils_culture(culture)
        except Exception:
            try:
                from firebase_service import DEFAULT_CULTURES_SEUILS
                seuils = DEFAULT_CULTURES_SEUILS.get(culture, DEFAULT_CULTURES_SEUILS["Tomate"])
            except Exception:
                # Fallback ultime au cas où
                seuils = {
                    "HUM_SOL_MIN": 40.0,
                    "HUM_SOL_MAX": 70.0,
                    "TEMP_AIR_MIN": 15.0,
                    "TEMP_AIR_MAX": 30.0,
                    "HUM_AIR_MIN": 50.0,
                    "HUM_AIR_MAX": 85.0,
                    "VENT_MAX": 25.0
                }

    hum_sol_min = float(seuils.get("HUM_SOL_MIN", 40.0))
    hum_sol_max = float(seuils.get("HUM_SOL_MAX", 70.0))
    temp_air_min = float(seuils.get("TEMP_AIR_MIN", 15.0))
    temp_air_max = float(seuils.get("TEMP_AIR_MAX", 30.0))
    hum_air_min = float(seuils.get("HUM_AIR_MIN", 50.0))
    hum_air_max = float(seuils.get("HUM_AIR_MAX", 85.0))
    vent_max = float(seuils.get("VENT_MAX", 25.0))

    # Température future : si la valeur est 0 (pas de données OW), on utilise la temp actuelle
    # pour éviter de déclencher faussement une alerte gel
    tf_effective = temperature_future if temperature_future > 0.0 else temperature
    hf_effective = humidite_future   if humidite_future   > 0.0 else humidite_air
    vf_effective = vent_future        if vent_future        > 0.0 else vitesse_vent

    # LOGIQUE DÉCISIONNELLE DE L'ARBRE (PAR ORDRE DE PRIORITÉ)
    # 1. Si api_pluie_prevue > 15 mm -> Code 2 (Alerte Drainage)
    if pluie_prevue_3h > 15.0:
        idx = 2
    # 2. Sinon, si hum_sol < HUM_SOL_MIN -> Code 1 (Alerte Sécheresse)
    elif humidite_sol < hum_sol_min:
        idx = 1
    # 3. Sinon, si hum_sol > HUM_SOL_MAX -> Code 4 (Alerte Saturation)
    elif humidite_sol > hum_sol_max:
        idx = 4
    # 4. Alerte Gel : temp capteur OU temp prévue (effective) < seuil min
    elif temperature < temp_air_min or tf_effective < temp_air_min:
        idx = 5
    # 5. Sinon, si api_temp > TEMP_AIR_MAX AND api_vent > VENT_MAX AND api_hum < HUM_AIR_MIN -> Code 3 (Evapotranspiration)
    elif tf_effective > temp_air_max and vf_effective > vent_max and hf_effective < hum_air_min:
        idx = 3
    # 6. Sinon, si api_hum > HUM_AIR_MAX AND (18 <= api_temp <= 26) -> Code 6 (Risque phytosanitaire)
    elif hf_effective > hum_air_max and (18.0 <= tf_effective <= 26.0):
        idx = 6
    # 7. Sinon -> Code 0 (Conditions Optimales)
    else:
        idx = 0

    return {
        "label_idx": idx,
        "label":     LABELS[idx],
        "emoji":     EMOJIS[idx],
        "conseil":   CONSEILS_DETAILLES[idx],
        "confiance": 1.0,
        "source":    "Système Expert",
    }


def get_source_modele() -> str:
    """Retourne la source du modèle : toujours 'Système Expert'."""
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
    """
    Fusionne historique capteurs Firebase + données OpenWeather historique.
    Chaque mesure capteur est jointe à l'entrée OpenWeather la plus proche par date.
    Sans labellisation (traçabilité brute sans label).
    """
    from firebase_service import get_historique, get_openweather_historique

    capteurs    = get_historique(station_id, limit=2000)
    openweather = get_openweather_historique(station_id)

    # Construire un dictionnaire date -> données OW pour jointure rapide
    # Les entrées OW sont triées par date YYYY-MM-DD
    ow_par_date = {}
    for ow in openweather:
        if not isinstance(ow, dict):
            continue
        ts = ow.get("timestamp", "")
        if ts:
            date_cle = ts[:10]  # YYYY-MM-DD
            ow_par_date[date_cle] = ow

    # Trier les dates disponibles pour la recherche par proximité
    dates_ow = sorted(ow_par_date.keys())

    def trouver_ow_proche(timestamp_mesure: str) -> dict:
        """Trouve l'entrée OW la plus proche par date."""
        if not dates_ow:
            return {}
        date_mesure = timestamp_mesure[:10] if timestamp_mesure else ""
        if not date_mesure:
            return ow_par_date.get(dates_ow[-1], {})
        # Chercher la date exacte d'abord
        if date_mesure in ow_par_date:
            return ow_par_date[date_mesure]
        # Sinon prendre la date OW la plus proche (inférieure ou égale)
        prev_date = None
        for d in dates_ow:
            if d <= date_mesure:
                prev_date = d
            else:
                break
        if prev_date:
            return ow_par_date[prev_date]
        # Sinon prendre le plus ancien disponible
        return ow_par_date.get(dates_ow[0], {})

    dataset = []
    for mesure in capteurs:
        if not isinstance(mesure, dict):
            continue
        t   = safe_float(mesure.get("temperature"),  0.0)
        ha  = safe_float(mesure.get("humidite_air"), 0.0)
        hs  = safe_float(mesure.get("humidite_sol"), 0.0)
        vv  = safe_float(mesure.get("vitesse_vent"), 0.0)
        ts_mesure = mesure.get("timestamp", "")

        # Trouver l'entrée OW la plus proche par date
        prev = trouver_ow_proche(ts_mesure)

        p  = safe_float(prev.get("pluie_prevue_3h"),    0.0)
        tf = safe_float(prev.get("temperature_future"), t)
        hf = safe_float(prev.get("humidite_future"),    ha)
        vf = safe_float(prev.get("vent_future"),        0.0)

        dataset.append({
            "temperature":        t,
            "humidite_air":       ha,
            "humidite_sol":       hs,
            "vitesse_vent":       vv,
            "pluie_prevue_3h":    p,
            "temperature_future": tf,
            "humidite_future":    hf,
            "vent_future":        vf,
            "timestamp":          ts_mesure,
        })

    return dataset


def generer_dataset_sur_firebase(station_id: str) -> dict:
    """
    Génère le dataset fusionné depuis Firebase et l'écrit dans
    stations/{station_id}/dataset.
    """
    from firebase_service import sauvegarder_dataset

    dataset = construire_dataset(station_id)
    if not dataset:
        return {
            "succes": False,
            "message": "Aucun dataset à sauvegarder — historique ou OpenWeather vide.",
            "nb_entrees": 0,
        }

    sauvegarder_dataset(station_id, dataset)
    return {
        "succes": True,
        "message": "Dataset fusionné sauvegardé dans Firebase.",
        "nb_entrees": len(dataset),
    }


# ── Ré-entraînement depuis Firebase (Mocké pour Système Expert) ───────────────

def predire_depuis_firebase(station_id: str, region: str = "Kaolack") -> dict:
    """
    Prédit la recommandation pour demain en prenant :
      - la DERNIÈRE mesure réelle ESP32 depuis Firebase
      - les prévisions OpenWeather actuelles
    """
    from firebase_service import get_historique, get_station_culture
    import weather_service

    # 1. Dernière mesure capteurs (ESP32)
    historique = get_historique(station_id, limit=1)
    if not historique:
        return {
            "erreur": f"Aucune mesure capteur disponible pour {station_id}",
            "succes": False,
        }
    derniere = historique[0]

    t   = safe_float(derniere.get("temperature"),  0.0)
    ha  = safe_float(derniere.get("humidite_air"), 0.0)
    hs  = safe_float(derniere.get("humidite_sol"), 0.0)
    vv  = safe_float(derniere.get("vitesse_vent"), 0.0)

    # 2. Prévisions OpenWeather (prochain créneau 3h)
    try:
        snap = weather_service.snapshot_openweather_ia(region=region)
        p    = safe_float(snap.get("pluie_prevue_3h"),    0.0)
        tf   = safe_float(snap.get("temperature_future"), t)
        hf   = safe_float(snap.get("humidite_future"),    ha)
        vf   = safe_float(snap.get("vent_future"),        0.0)
    except Exception:
        p, tf, hf, vf = 0.0, t, ha, vv

    # 3. Récupérer la culture
    culture = get_station_culture(station_id)

    # 4. Prédiction immédiate via Système Expert
    reco = get_recommandation(t, ha, hs, vv, p, tf, hf, vf, culture=culture)

    return {
        "succes": True,
        "station_id": station_id,
        "culture": culture,
        "capteurs": {
            "temperature":  t,
            "humidite_air": ha,
            "humidite_sol": hs,
            "vitesse_vent": vv,
        },
        "previsions_meteo": {
            "pluie_prevue_3h":    p,
            "temperature_future": tf,
            "humidite_future":    hf,
            "vent_future":        vf,
        },
        **reco,
    }


def reentainer_modele(station_id: str) -> dict:
    """
    (Mocké pour le Système Expert)
    Génère le dataset brute fusionné et le stocke.
    """
    dataset = construire_dataset(station_id)

    try:
        from firebase_service import sauvegarder_dataset
        if dataset:
            sauvegarder_dataset(station_id, dataset)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder le dataset complet pour {station_id} : {e}")

    return {
        "statut": "firebase",
        "message": "Système expert configuré avec succès et dataset mis à jour.",
        "nb_entrees": len(dataset),
        "score": 1.0
    }


# ── Message vocal agriculteur ────────────────────────────────────────────────

def get_message_vocal(
    nom: str,
    region: str,
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
    pluie_prevue_3h: float = 0.0,
    temperature_future: float = 0.0,
    humidite_future: float = 0.0,
    vent_future: float = 0.0,
    culture: str = "Tomate",
) -> str:
    """Génère un message vocal adapté aux agriculteurs peu alphabétisés."""
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
