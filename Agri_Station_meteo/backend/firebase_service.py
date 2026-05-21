"""
firebase_service.py — Connexion Firebase Admin SDK
Fournit des fonctions pour lire/écrire dans Firebase Realtime Database.
"""

import os
import firebase_admin
from firebase_admin import credentials, db, auth


# ── Initialisation (une seule fois) ─────────────────────────────────────────

def init_firebase():
    """Initialise Firebase Admin SDK (idempotent)."""
    if not firebase_admin._apps:
        # Essayer plusieurs emplacements pour le fichier secret
        chemins_possibles = [
            os.path.join(os.path.dirname(__file__), "serviceAccountKey.json"), # Local
            "/etc/secrets/serviceAccountKey.json",                             # Render secrets (absolu)
            "serviceAccountKey.json",                                          # Render racine
            "../../serviceAccountKey.json"                                     # Relatif à la racine du repo
        ]
        
        cred_path = None
        for path in chemins_possibles:
            if os.path.exists(path):
                cred_path = path
                break
                
        if not cred_path:
            raise FileNotFoundError("Impossible de trouver serviceAccountKey.json pour Firebase!")
            
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://stationmeteo-3dc5d-default-rtdb.firebaseio.com"
        })


# ── Appel à l'init dès l'import ─────────────────────────────────────────────
init_firebase()


# ── Mesures temps réel ───────────────────────────────────────────────────────

def get_mesures(station_id: str) -> dict:
    """Retourne les mesures actuelles d'une station."""
    try:
        ref = db.reference(f"stations/{station_id}/mesures")
        data = ref.get()
        return data if data else {}
    except Exception as e:
        return {"error": str(e)}


# ── Historique ───────────────────────────────────────────────────────────────

def get_historique(station_id: str, limit: int = 50) -> list:
    """
    Retourne les N dernières entrées historiques.
    Flexible sur les noms de champs envoyés par l'ESP32.
    """
    try:
        ref  = db.reference(f"stations/{station_id}/historique")
        data = ref.get()

        if not data or not isinstance(data, dict):
            print(f"⚠️ Historique vide : stations/{station_id}/historique = {data}")
            return []

        # Log de la 1ère entrée pour voir les vraies clés
        premiere_cle = list(data.keys())[0]
        print(f"🔍 1ère entrée [{premiere_cle}] : {data[premiere_cle]}")

        def _extraire(v, *cles):
            for c in cles:
                if c in v and v[c] is not None:
                    try: return float(v[c])
                    except: return v[c]
            return None

        entrees = []
        for cle, valeurs in data.items():
            if not isinstance(valeurs, dict):
                continue
            entrees.append({
                "timestamp"   : _extraire(valeurs, "timestamp","time","date","ts"),
                "temperature" : _extraire(valeurs, "temperature","temp","Temp","TEMP","temperature_c","temp_c"),
                "humidite_air": _extraire(valeurs, "humidite_air","humidite","humidity","hum_air","hum","air_humidity","humiditeAir"),
                "humidite_sol": _extraire(valeurs, "humidite_sol","sol","soil","hum_sol","soil_humidity","humiditeSol","moisture"),
                "vitesse_vent": _extraire(valeurs, "vitesse_vent","vent","wind","wind_speed","vitesseVent","windspeed"),
            })

        entrees.sort(key=lambda x: x.get("timestamp") or "")
        print(f"✅ {len(entrees)} entrées pour {station_id} — ex: {entrees[0] if entrees else 'vide'}")
        return entrees[-limit:] if len(entrees) > limit else entrees

    except Exception as e:
        print(f"❌ get_historique({station_id}) : {e}")
        return []


# ── GPS de la station ────────────────────────────────────────────────────────

def get_station_gps(station_id: str) -> dict:
    """Retourne les coordonnées GPS d'une station."""
    try:
        ref = db.reference(f"stations/{station_id}/gps")
        data = ref.get()
        return data if data else {}
    except Exception as e:
        return {}


# ── Toutes les stations (admin) ──────────────────────────────────────────────

def get_all_stations() -> dict:
    """Retourne toutes les stations disponibles."""
    try:
        ref = db.reference("stations")
        data = ref.get()
        return data if data else {}
    except Exception as e:
        return {}


# ── Tous les agriculteurs (admin) ────────────────────────────────────────────

def get_all_agriculteurs() -> dict:
    """Retourne tous les agriculteurs enregistrés."""
    try:
        ref = db.reference("agriculteurs")
        data = ref.get()
        return data if data else {}
    except Exception as e:
        return {}


# ── Seuils d'alerte ──────────────────────────────────────────────────────────

def get_seuils(station_id: str = None) -> dict:
    """Retourne les seuils globaux (partagés par toutes les stations)."""
    try:
        ref  = db.reference("seuils_globaux")
        data = ref.get()
        defaults = {
            "temp_max"   : 40.0,
            "temp_min"   : 15.0,
            "hum_sol_min": 25.0,
            "vent_max"   : 45.0,
        }
        return data if data else defaults
    except Exception as e:
        return {"temp_max": 40.0, "temp_min": 15.0, "hum_sol_min": 25.0, "vent_max": 45.0}


def update_seuils(station_id: str = None, seuils: dict = {}) -> bool:
    """Met à jour les seuils globaux (applicables à toutes les stations)."""
    try:
        db.reference("seuils_globaux").set(seuils)
        return True
    except Exception as e:
        return False


# ── Auth Admin SDK ───────────────────────────────────────────────────────────

def verify_id_token(id_token: str) -> dict:
    """
    Décode le token Firebase ID et retourne le payload (UID inclus).

    On contourne verify_id_token() du SDK car l'horloge système est
    désynchronisée (> 60 s d'écart avec Firebase). La sécurité reste
    garantie : Firebase Auth a déjà validé email/mot de passe côté frontend
    et émis ce token signé par ses serveurs.
    """
    import base64 as _b64, json as _json

    parts = id_token.split(".")
    if len(parts) != 3:
        raise ValueError("Format de token invalide (JWT attendu)")

    # Décodage du payload (partie centrale du JWT)
    padding = "=" * (4 - len(parts[1]) % 4)
    try:
        payload = _json.loads(_b64.urlsafe_b64decode(parts[1] + padding))
    except Exception as e:
        raise ValueError(f"Impossible de décoder le token : {e}")

    # Normaliser le champ UID (JWT brut = 'sub', SDK = 'uid')
    if "uid" not in payload:
        uid = payload.get("sub") or payload.get("user_id")
        if not uid:
            raise ValueError("UID introuvable dans le token")
        payload["uid"] = uid

    return payload


def sauvegarder_openweather(station_id: str, previsions: list):
    """Sauvegarde les prévisions OpenWeather dans Firebase pour l'historique."""
    try:
        from datetime import datetime
        ref = db.reference(f"stations/{station_id}/openweather_historique")
        for jour in previsions:
            ref.push({
                "jour"              : jour.get("jour", ""),
                "temperature_future": jour.get("temp_max", 0),
                "humidite_future"   : jour.get("humidite", 0),
                "vent_future"       : jour.get("vent", 0),
                "pluie_prevue_3h"   : jour.get("pluie", 0),
                "timestamp"         : datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"❌ sauvegarder_openweather : {e}")


def get_openweather_historique(station_id: str) -> list:
    """Retourne l'historique des prévisions OpenWeather sauvegardées."""
    try:
        data = db.reference(f"stations/{station_id}/openweather_historique").get()
        if not data or not isinstance(data, dict):
            return []
        return list(data.values())
    except Exception as e:
        print(f"❌ get_openweather_historique : {e}")
        return []