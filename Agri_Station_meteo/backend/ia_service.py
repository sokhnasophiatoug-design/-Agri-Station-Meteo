"""
ia_service.py — Arbre de décision agricole (scikit-learn)
Recommandations automatiques basées sur les mesures des capteurs.
Adapté au contexte sénégalais (Kaolack, Thiès, Saint-Louis...).
"""

import os
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split


# ── Labels de recommandation ─────────────────────────────────────────────────

LABELS = [
    "Conditions favorables — surveiller régulièrement",
    "Arroser les cultures — humidité du sol insuffisante",
    "URGENCE — Stress hydrique sévère, arroser immédiatement",
    "Risque fongique — envisager un traitement fongicide",
    "Vent fort — protéger les cultures fragiles",
]

EMOJIS = ["✅", "💧", "🚨", "🍄", "💨"]

CONSEILS_DETAILLES = [
    "Les conditions sont bonnes. Continuez à surveiller vos cultures et vérifiez l'état du sol toutes les 6 heures.",
    "L'humidité du sol est faible. Activez l'irrigation pendant 30 à 45 minutes, de préférence tôt le matin pour limiter l'évaporation.",
    "Situation critique ! Le sol est très sec et la chaleur est élevée. Arrosez immédiatement et abondamment. Vérifiez vos canalisations d'irrigation.",
    "L'humidité de l'air est élevée avec une température chaude : risque de développement de maladies fongiques. Inspectez vos plants et appliquez un fongicide préventif si nécessaire.",
    "Le vent souffle fort. Protégez les jeunes plants avec des filets brise-vent. Évitez de pulvériser des produits par ce vent.",
]


# ── Chargement du dataset CSV ────────────────────────────────────────────────

# Chemin du fichier CSV (même dossier que ce script)
_CSV_PATH = os.path.join(os.path.dirname(__file__), "dataset_agricole.csv")

def _charger_dataset():
    """
    Charge le dataset depuis dataset_agricole.csv.
    Colonnes attendues : temperature, humidite_air, humidite_sol, vitesse_vent, label
    """
    if not os.path.isfile(_CSV_PATH):
        raise FileNotFoundError(
            f"Dataset introuvable : {_CSV_PATH}\n"
            "Assurez-vous que 'dataset_agricole.csv' est présent dans le dossier backend."
        )
    df = pd.read_csv(_CSV_PATH)
    X = df[["temperature", "humidite_air", "humidite_sol", "vitesse_vent"]].values
    y = df["label"].values
    return X, y


# ── Entraînement du modèle ───────────────────────────────────────────────────

def _entrainer_modele():
    X, y = _charger_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    modele = DecisionTreeClassifier(max_depth=7, random_state=42)
    modele.fit(X_train, y_train)
    score = modele.score(X_test, y_test)
    print(f"[IA] Modèle entraîné — précision : {score:.2%}")
    return modele


def _regles(
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
) -> int:
    """Calcule un label basé sur des règles simples pour le dataset de réentrainement."""
    if vitesse_vent >= 45:
        return 4
    if humidite_sol <= 20:
        return 2 if temperature >= 30 else 1
    if humidite_air >= 80 and temperature >= 28:
        return 3
    return 0


# Entraînement au démarrage du module
_modele = _entrainer_modele()


# ── API publique ─────────────────────────────────────────────────────────────

def get_recommandation(
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
) -> dict:
    """
    Retourne la recommandation IA pour les valeurs capteurs données.

    Returns:
        dict avec clés :
            - label      : texte court de la recommandation
            - emoji      : emoji associé
            - conseil    : texte long explicatif
            - label_idx  : index numérique (0-4)
            - confiance  : probabilité max (0-1)
    """
    X = np.array([[temperature, humidite_air, humidite_sol, vitesse_vent]])
    idx = int(_modele.predict(X)[0])
    proba = _modele.predict_proba(X)[0]

    return {
        "label_idx":  idx,
        "label":      LABELS[idx],
        "emoji":      EMOJIS[idx],
        "conseil":    CONSEILS_DETAILLES[idx],
        "confiance":  round(float(proba[idx]), 3),
    }

def construire_dataset(station_id: str) -> list:
    """Fusionne historique capteurs + OpenWeather + calcule le label."""
    from firebase_service import get_historique, get_openweather_historique

    capteurs    = get_historique(station_id, limit=1000)
    openweather = get_openweather_historique(station_id)

    dataset = []
    for mesure in capteurs:
        # Prendre la première prévision disponible (simplification)
        prev = openweather[0] if openweather else {}

        label = _regles(
            mesure.get("temperature",  0),
            mesure.get("humidite_air", 0),
            mesure.get("humidite_sol", 0),
            mesure.get("vitesse_vent", 0),
        )

        dataset.append({
            "temperature"       : mesure.get("temperature",  0),
            "humidite_air"      : mesure.get("humidite_air", 0),
            "humidite_sol"      : mesure.get("humidite_sol", 0),
            "vitesse_vent"      : mesure.get("vitesse_vent", 0),
            "pluie_prevue_3h"   : prev.get("pluie_prevue_3h",    0),
            "temperature_future": prev.get("temperature_future",  0),
            "humidite_future"   : prev.get("humidite_future",     0),
            "vent_future"       : prev.get("vent_future",         0),
            "label"             : label,
        })
    return dataset


def reentainer_modele(station_id: str):
    """Re-entraîne le modèle avec les données réelles si suffisantes."""
    global _modele
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.model_selection import train_test_split
    import pandas as pd

    dataset = construire_dataset(station_id)

    if len(dataset) < 100:
        print(f"[IA] Dataset trop petit ({len(dataset)} entrées) — modèle synthétique conservé")
        return

    df = pd.DataFrame(dataset)
    X  = df[["temperature", "humidite_air", "humidite_sol", "vitesse_vent",
             "pluie_prevue_3h", "temperature_future", "humidite_future", "vent_future"]]
    y  = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    nouveau_modele = DecisionTreeClassifier(max_depth=7, random_state=42)
    nouveau_modele.fit(X_train, y_train)
    score = nouveau_modele.score(X_test, y_test)

    _modele = nouveau_modele
    print(f"[IA] Re-entraîné sur données réelles — précision : {score:.2%} ({len(dataset)} entrées)")

def get_message_vocal(
    nom: str,
    region: str,
    temperature: float,
    humidite_air: float,
    humidite_sol: float,
    vitesse_vent: float,
) -> str:
    """Génère un message vocal adapté aux agriculteurs peu alphabétisés."""
    reco = get_recommandation(temperature, humidite_air, humidite_sol, vitesse_vent)
    return (
        f"Bonjour {nom}, voici vos informations météo pour la région {region}. "
        f"Température : {temperature:.0f} degrés. "
        f"Humidité du sol : {humidite_sol:.0f} pour cent. "
        f"Conseil : {reco['conseil']} "
        f"Bonne journée !"
    )
