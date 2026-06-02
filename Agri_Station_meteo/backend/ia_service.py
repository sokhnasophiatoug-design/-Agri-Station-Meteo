"""
ia_service.py — Classifieur agricole à 8 features / 6 classes
===============================================================

Flux de fonctionnement :
  1. Au démarrage  → _ClassifieurRegles actif (règles directes, zéro dépendance)
  2. Dès que Firebase accumule ≥ 100 mesures réelles →
     POST /ia/reentainer/{id} → étiquetage des vraies données → sklearn actif

Entrées (8 features) :
  Capteurs ESP32 temps réel :
    temperature (°C), humidite_air (%), humidite_sol (%), vitesse_vent (km/h)
  Prévisions OpenWeather :
    pluie_prevue_3h (mm), temperature_future (°C), humidite_future (%), vent_future (km/h)

Classes prédites (priorité décroissante) :
  4 → 💨 Reporter pulvérisation  (vent ≥ 45 km/h OU prévu ≥ 40)
  5 → 🌧️ Attendre la pluie      (pluie ≥ 3 mm ET sol < 60 %)
  2 → 🚨 Urgence hydrique        (sol ≤ 20 % ET temp ≥ 30 °C)
  1 → 💧 Arroser                 (sol ≤ 25 % ET pas de pluie prévue)
  3 → 🍄 Risque fongique         (humidité air ≥ 80 % ET temp ≥ 28 °C)
  0 → ✅ Conditions favorables
"""

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split


# ── Métadonnées des 6 classes ────────────────────────────────────────────────

LABELS = [
    "Conditions favorables — surveiller régulièrement",             # 0
    "Arroser les cultures — humidité du sol insuffisante",          # 1
    "URGENCE — Stress hydrique sévère, arroser immédiatement",      # 2
    "Risque fongique — envisager un traitement fongicide",          # 3
    "Reporter pulvérisation — vent trop fort",                      # 4
    "Attendre la pluie prévue — irrigation non nécessaire",         # 5
]

EMOJIS = ["✅", "💧", "🚨", "🍄", "💨", "🌧️"]

CONSEILS_DETAILLES = [
    "Les conditions sont bonnes. Continuez à surveiller vos cultures et vérifiez l'état du sol toutes les 6 heures.",
    "L'humidité du sol est faible. Activez l'irrigation pendant 30 à 45 minutes, de préférence tôt le matin pour limiter l'évaporation.",
    "Situation critique ! Le sol est très sec et la chaleur est élevée. Arrosez immédiatement et abondamment. Vérifiez vos canalisations d'irrigation.",
    "L'humidité de l'air est élevée avec une température chaude : risque de maladies fongiques. Inspectez vos plants et appliquez un fongicide préventif si nécessaire.",
    "Le vent souffle trop fort pour pulvériser des produits. Reportez toute pulvérisation et protégez les jeunes plants avec des filets brise-vent.",
    "De la pluie est prévue dans les prochaines heures. Évitez d'arroser maintenant. Profitez-en pour vérifier vos équipements d'irrigation.",
]

# Ordre fixe des features — respecté partout
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


# ── Règles métier (arbre de décision explicite) ──────────────────────────────

def _regles(
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
    pluie_prevue_3h: float = 0.0,
    temperature_future: float = 0.0,
    humidite_future: float = 0.0,
    vent_future: float = 0.0,
) -> int:
    """
    Arbre de décision prioritaire à 6 classes.
    Utilisé directement au démarrage ET pour étiqueter les données Firebase
    avant ré-entraînement sklearn.
    """
    if vitesse_vent >= 45 or vent_future >= 40:
        return 4
    if pluie_prevue_3h >= 3.0 and humidite_sol < 60:
        return 5
    if humidite_sol <= 20 and temperature >= 30:
        return 2
    if humidite_sol <= 25 and pluie_prevue_3h < 3.0:
        return 1
    if humidite_air >= 80 and temperature >= 28:
        return 3
    return 0


# ── Classifieurs ─────────────────────────────────────────────────────────────

class _ClassifieurRegles:
    """
    Classifieur basé sur les règles métier.
    Actif au démarrage — aucune dépendance fichier / Firebase.
    """
    source = "Règles"

    def predict(self, features: list) -> int:
        return _regles(*features)

    def confiance(self, idx: int) -> float:
        # Les règles sont déterministes : confiance = 1.0
        return 1.0


class _ClassifieurSklearn:
    """
    Classifieur sklearn (DecisionTreeClassifier) entraîné sur données Firebase.
    Remplace _ClassifieurRegles après ré-entraînement.
    """
    source = "Firebase"

    def __init__(self, modele: DecisionTreeClassifier):
        self._modele = modele

    def predict(self, features: list) -> int:
        X = np.array([features])
        return int(self._modele.predict(X)[0])

    def confiance(self, features: list, idx: int) -> float:
        X = np.array([features])
        proba = self._modele.predict_proba(X)[0]
        # predict_proba retourne les probas dans l'ordre des classes vues
        classes = list(self._modele.classes_)
        if idx in classes:
            return round(float(proba[classes.index(idx)]), 3)
        return 1.0


# Classifieur actif au démarrage = règles directes
_classifieur: _ClassifieurRegles | _ClassifieurSklearn = _ClassifieurRegles()
print("[IA] Classifieur démarré — mode : Règles (8 features, 6 classes)")


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
) -> dict:
    """
    Prédit la recommandation à partir des 8 features.

    Retourne :
      label_idx  : indice classe (0-5)
      label      : texte court
      emoji      : emoji associé
      conseil    : texte long explicatif
      confiance  : certitude (0-1)
      source     : 'Règles' | 'Firebase'
    """
    features = [
        temperature, humidite_air, humidite_sol, vitesse_vent,
        pluie_prevue_3h, temperature_future, humidite_future, vent_future,
    ]

    idx = _classifieur.predict(features)
    idx = min(max(idx, 0), len(LABELS) - 1)  # garde-fou

    # Calcul confiance selon le type de classifieur
    if isinstance(_classifieur, _ClassifieurSklearn):
        conf = _classifieur.confiance(features, idx)
    else:
        conf = 1.0  # règles déterministes

    return {
        "label_idx": idx,
        "label":     LABELS[idx],
        "emoji":     EMOJIS[idx],
        "conseil":   CONSEILS_DETAILLES[idx],
        "confiance": conf,
        "source":    _classifieur.source,
    }


def get_source_modele() -> str:
    """Retourne la source du classifieur actif : 'Règles' ou 'Firebase'."""
    return _classifieur.source


# ── Construction du dataset depuis Firebase ──────────────────────────────────

def construire_dataset(station_id: str) -> list:
    """
    Fusionne historique capteurs Firebase + données OpenWeather historique.
    Chaque mesure est étiquetée automatiquement via _regles().
    """
    from firebase_service import get_historique, get_openweather_historique

    capteurs    = get_historique(station_id, limit=2000)
    openweather = get_openweather_historique(station_id)

    prev_defaut = openweather[0] if openweather else {}

    dataset = []
    for mesure in capteurs:
        t   = float(mesure.get("temperature",  0))
        ha  = float(mesure.get("humidite_air", 0))
        hs  = float(mesure.get("humidite_sol", 0))
        vv  = float(mesure.get("vitesse_vent", 0))

        prev = prev_defaut
        p    = float(prev.get("pluie_prevue_3h",    prev.get("pluie_future",   0)))
        tf   = float(prev.get("temperature_future", prev.get("temp_future",    t)))
        hf   = float(prev.get("humidite_future",    prev.get("hum_future",     ha)))
        vf   = float(prev.get("vent_future",        prev.get("vent_futur",     0)))

        label = _regles(t, ha, hs, vv, p, tf, hf, vf)

        dataset.append({
            "temperature":        t,
            "humidite_air":       ha,
            "humidite_sol":       hs,
            "vitesse_vent":       vv,
            "pluie_prevue_3h":    p,
            "temperature_future": tf,
            "humidite_future":    hf,
            "vent_future":        vf,
            "label":              label,
        })

    return dataset


# ── Ré-entraînement depuis Firebase ─────────────────────────────────────────

def predire_depuis_firebase(station_id: str, region: str = "Kaolack") -> dict:
    """
    Prédit la recommandation pour demain en prenant :
      - la DERNIÈRE mesure réelle ESP32 depuis Firebase
      - les prévisions OpenWeather actuelles

    Fonctionne dès la première mesure reçue — aucune attente.
    """
    from firebase_service import get_historique
    import weather_service

    # 1. Dernière mesure capteurs (ESP32)
    historique = get_historique(station_id, limit=1)
    if not historique:
        return {
            "erreur": f"Aucune mesure capteur disponible pour {station_id}",
            "succes": False,
        }
    derniere = historique[0]

    t   = float(derniere.get("temperature",  0))
    ha  = float(derniere.get("humidite_air", 0))
    hs  = float(derniere.get("humidite_sol", 0))
    vv  = float(derniere.get("vitesse_vent", 0))

    # 2. Prévisions OpenWeather (prochain créneau 3h)
    try:
        snap = weather_service.snapshot_openweather_ia(region=region)
        p    = float(snap.get("pluie_future",       0))
        tf   = float(snap.get("temperature_future", t))
        hf   = float(snap.get("humidite_future",    ha))
        vf   = float(snap.get("vent_future",        0))
    except Exception:
        # Si OpenWeather indisponible : on prédit sans données météo futures
        p, tf, hf, vf = 0.0, t, ha, vv

    # 3. Prédiction immédiate (règles ou sklearn selon classifieur actif)
    reco = get_recommandation(t, ha, hs, vv, p, tf, hf, vf)

    return {
        "succes": True,
        "station_id": station_id,
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
    (Optionnel — amélioration progressive)
    Entraîne sklearn sur les données RÉELLES Firebase étiquetées par _regles().
    Fonctionne dès 5 entrées. Plus on a de données, meilleure est la précision.
    Remplace _ClassifieurRegles par _ClassifieurSklearn une fois entraîné.
    """
    global _classifieur

    dataset = construire_dataset(station_id)

    if len(dataset) < 5:
        msg = (
            f"Données insuffisantes ({len(dataset)} mesures, minimum 5) "
            "— classifieur Règles conservé"
        )
        print(f"[IA] {msg}")
        return {"succes": False, "message": msg, "nb_entrees": len(dataset)}

    df = pd.DataFrame(dataset)
    X  = df[FEATURES].values
    y  = df["label"].values

    # Avec peu de données : pas de split train/test
    if len(dataset) >= 20:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42,
            stratify=y if len(set(y)) > 1 else None
        )
        modele = DecisionTreeClassifier(max_depth=8, random_state=42)
        modele.fit(X_train, y_train)
        score = modele.score(X_test, y_test)
        score_str = f", précision : {score:.1%}"
    else:
        modele = DecisionTreeClassifier(max_depth=8, random_state=42)
        modele.fit(X, y)
        score_str = " (trop peu de données pour évaluer la précision)"

    _classifieur = _ClassifieurSklearn(modele)
    msg = (
        f"Modèle sklearn entraîné sur données Firebase réelles "
        f"({len(dataset)} mesures{score_str})"
    )
    print(f"[IA] {msg}")
    return {"succes": True, "message": msg, "nb_entrees": len(dataset)}


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
) -> str:
    """Génère un message vocal adapté aux agriculteurs peu alphabétisés."""
    reco = get_recommandation(
        temperature, humidite_air, humidite_sol, vitesse_vent,
        pluie_prevue_3h, temperature_future, humidite_future, vent_future,
    )
    pluie_str = f"Pluie prévue : {pluie_prevue_3h:.0f} mm. " if pluie_prevue_3h > 0 else ""
    return (
        f"Bonjour {nom}, voici vos informations pour la région {region}. "
        f"Température : {temperature:.0f} degrés. "
        f"Humidité du sol : {humidite_sol:.0f} pour cent. "
        f"{pluie_str}"
        f"Conseil : {reco['conseil']} "
        f"Bonne journée !"
    )
