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
