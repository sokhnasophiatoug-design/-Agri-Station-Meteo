"""
tts_service.py — Synthèse vocale (gTTS)
Génère un fichier MP3 en mémoire depuis un texte en français.
"""

import io
from gtts import gTTS


def generer_audio(texte: str, lang: str = "fr", lent: bool = False) -> bytes:
    """
    Convertit un texte en audio MP3 (bytes).

    Args:
        texte : Le texte à prononcer.
        lang  : Langue (fr par défaut).
        lent  : Si True, parole plus lente (utile pour les seniors).

    Returns:
        bytes du fichier MP3.
    """
    tts = gTTS(text=texte, lang=lang, slow=lent)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    return buffer.read()


def construire_message_agriculteur(
    nom: str,
    station_nom: str,
    region: str,
    temp: float,
    hum_air: float,
    hum_sol: float,
    vent: float,
    recommandation: str,
) -> str:
    """
    Construit un message vocal complet pour l'agriculteur.
    Adapté aux agriculteurs peu alphabétisés — message simple et direct.
    """
    message = (
        f"Bonjour {nom}. "
        f"Voici les conditions météo de votre station {station_nom}, en région {region}. "
        f"Température actuelle : {temp:.0f} degrés Celsius. "
        f"Humidité de l'air : {hum_air:.0f} pour cent. "
        f"Humidité du sol : {hum_sol:.0f} pour cent. "
        f"Vitesse du vent : {vent:.0f} kilomètres par heure. "
        f"Conseil de votre assistant agricole : {recommandation}. "
        f"Bonne journée et bonne récolte !"
    )
    return message
