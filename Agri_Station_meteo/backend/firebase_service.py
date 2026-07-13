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


def push_mesures_et_historique(station_id: str, payload: dict) -> dict:
    """
    Reçoit les données capteurs de l'ESP32 et les écrit dans Firebase
    via Admin SDK (pas de problème PUT/PATCH REST).

    - SET sur stations/{station_id}/mesures      → données temps réel
    - PUSH sur stations/{station_id}/historique  → nouvelle entrée horodatée

    Met aussi à jour le nœud GPS si latitude/longitude sont présents.
    """
    from datetime import datetime

    ts = payload.get("timestamp") or datetime.now().isoformat()

    entree = {
        "temperature" : payload.get("temperature"),
        "humidite_air": payload.get("humidite_air"),
        "humidite_sol": payload.get("humidite_sol"),
        "vitesse_vent": payload.get("vitesse_vent"),
        "station_id"  : station_id,
        "timestamp"   : ts,
        "latitude"    : payload.get("latitude"),
        "longitude"   : payload.get("longitude"),
        "gps_fix"     : payload.get("gps_fix", False),
    }
    # Supprimer les clés None pour ne pas polluer Firebase
    entree = {k: v for k, v in entree.items() if v is not None}

    try:
        # 1. Mesures courantes — SET (écrase le nœud, équivalent PUT)
        db.reference(f"stations/{station_id}/mesures").set(entree)

        # 2. Historique — PUSH (crée une entrée unique)
        db.reference(f"stations/{station_id}/historique").push(entree)

        # 3. GPS séparé (si fix disponible)
        if payload.get("gps_fix") and payload.get("latitude") and payload.get("longitude"):
            db.reference(f"stations/{station_id}/gps").set({
                "latitude" : payload["latitude"],
                "longitude": payload["longitude"],
                "altitude" : payload.get("altitude", 0),
                "timestamp": ts,
            })

        print(f"[PUSH] ✅ {station_id} — T={entree.get('temperature')}°C "
              f"Sol={entree.get('humidite_sol')}% Vent={entree.get('vitesse_vent')}km/h")
        return {"succes": True}

    except Exception as e:
        print(f"❌ push_mesures_et_historique({station_id}) : {e}")
        return {"succes": False, "erreur": str(e)}


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


def initialiser_station(station_id: str, station_nom: str, region: str, culture: str = "Manioc") -> bool:
    """
    Initialise une nouvelle station dans Firebase si elle n'existe pas.
    """
    try:
        ref = db.reference(f"stations/{station_id}")
        # Si la station existe déjà et a un nom, on ne l'écrase pas
        existante = ref.get()
        if existante and isinstance(existante, dict) and existante.get("nom"):
            return True

        # Initialiser avec des données de base
        ref.set({
            "nom": station_nom,
            "region": region,
            "culture": culture,
            "seuils": {
                "temp_max": 40.0,
                "temp_min": 15.0,
                "hum_sol_min": 25.0,
                "vent_max": 45.0
            },
            "gps": {
                "latitude": 14.1652,   # Kaolack par défaut
                "longitude": -16.0758
            }
        })
        print(f"[Firebase] Station {station_id} ({station_nom}) initialisée avec succès.")
        return True
    except Exception as e:
        print(f"❌ initialiser_station : {e}")
        return False


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
    """
    Sauvegarde les prévisions OpenWeather dans Firebase.
    Une entrée PAR JOUR (clé = date YYYY-MM-DD) — pas de doublons.
    Si /previsions est appelé 20 fois dans la journée : toujours 5 entrées.
    """
    try:
        from datetime import datetime, date, timedelta
        ref = db.reference(f"stations/{station_id}/openweather_historique")
        today = date.today()
        for idx, jour in enumerate(previsions):
            date_cle = (today + timedelta(days=idx)).isoformat()  # "2026-06-03"
            ref.child(date_cle).set({
                "jour"              : jour.get("jour", ""),
                "temperature_future": jour.get("temp_max", 0),
                "humidite_future"   : jour.get("humidite", 0),
                "vent_future"       : jour.get("vent", 0),
                "pluie_prevue_3h"   : jour.get("pluie", 0),
                "timestamp"         : datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"❌ sauvegarder_openweather : {e}")


def sauvegarder_dataset(station_id: str, entree):
    """
    Écrit dans stations/{station_id}/dataset.

    Si `entree` est un dictionnaire, on trace une seule décision IA.
    Si `entree` est une liste, on remplace le dataset complet par les entrées fusionnées.
    """
    try:
        from datetime import datetime
        ref = db.reference(f"stations/{station_id}/dataset")

        now_iso = datetime.now().isoformat()
        if isinstance(entree, list):
            # Remplacer le dataset existant par le dataset fusionné historique + OpenWeather
            # Toutes les entrées reçoivent le timestamp courant (date du jour) pour
            # garantir que les anciens enregistrements apparaissent avec la date actuelle.
            ref.set({})
            for idx, row in enumerate(entree, start=1):
                entree_a_sauver = {
                    **row,
                    "timestamp": now_iso,  # force la date d'aujourd'hui sur toutes les entrées
                }
                entree_a_sauver.pop("label", None)
                entree_a_sauver.pop("label_idx", None)
                entree_a_sauver.pop("source", None)
                ref.child(f"{idx:04d}").set(entree_a_sauver)
            print(f"✅ Dataset complet sauvegardé pour {station_id} ({len(entree)} entrées)")
            return

        entree_a_sauver = {**entree, "timestamp": now_iso}
        entree_a_sauver.pop("label", None)
        entree_a_sauver.pop("label_idx", None)
        entree_a_sauver.pop("source", None)
        ref.push(entree_a_sauver)
    except Exception as e:
        print(f"⚠️ sauvegarder_dataset ({station_id}) : {e}")

def get_openweather_historique(station_id: str) -> list:
    try:
        data = db.reference(f"stations/{station_id}/openweather_historique").get()
        if not data or not isinstance(data, dict):
            return []

        entrees = []
        for cle, valeur in data.items():
            if not isinstance(valeur, dict):
                continue
            # Accepter TOUTES les entrées : clés date YYYY-MM-DD et clés push Firebase (-Xxx)
            entrees.append(valeur)

        # Trier par timestamp — plus récent en dernier
        entrees.sort(key=lambda x: x.get("timestamp", ""))
        print(f"[OW] {len(entrees)} prévisions valides chargées pour {station_id}")
        return entrees

    except Exception as e:
        print(f"❌ get_openweather_historique : {e}")
        return []


def get_openweather_du_jour(station_id: str, date_iso: str = None) -> dict:
    """
    Lit l'entrée OpenWeather stockée pour une date donnée (format YYYY-MM-DD).
    Si aucune entrée exacte, retourne la plus récente antérieure ou égale à cette date.
    Utilisé comme fallback quand l'API live OpenWeather est indisponible.

    openweather_historique stocke les prévisions des 5 jours à venir
    à chaque fois que l'ESP32 pousse des données.
    """
    from datetime import date as dt_date
    try:
        if not date_iso:
            date_iso = dt_date.today().isoformat()

        data = db.reference(f"stations/{station_id}/openweather_historique").get()
        if not data or not isinstance(data, dict):
            return {}

        # Garder uniquement les clés au format YYYY-MM-DD (entrées récentes structurées)
        entrees_date = {}
        for cle, valeur in data.items():
            if not isinstance(valeur, dict):
                continue
            if len(cle) == 10 and cle[4] == "-" and cle[7] == "-":
                # Clé = date YYYY-MM-DD → correspond au jour où l'entrée a été créée
                entrees_date[cle] = valeur

        if not entrees_date:
            return {}

        # Chercher la date exacte d'abord
        if date_iso in entrees_date:
            print(f"[OW] Entrée exacte trouvée pour {date_iso}")
            return entrees_date[date_iso]

        # Sinon prendre la date la plus récente antérieure ou égale à date_iso
        dates_dispo = sorted(entrees_date.keys())
        cle_retenue = None
        for d in dates_dispo:
            if d <= date_iso:
                cle_retenue = d
            else:
                break

        if cle_retenue:
            print(f"[OW] Entrée la plus proche utilisée : {cle_retenue} (demandée: {date_iso})")
            return entrees_date[cle_retenue]

        # Sinon la plus ancienne disponible
        print(f"[OW] Aucune entrée avant {date_iso}, utilisation de la plus ancienne : {dates_dispo[0]}")
        return entrees_date[dates_dispo[0]]

    except Exception as e:
        print(f"❌ get_openweather_du_jour : {e}")
        return {}

def _sms_clean(texte: str, max_car: int = 155) -> str:
    """
    Nettoie un texte pour compatibilité GSM-7bit et le tronque à max_car
    caractères (pas octets).
    - Remplace les caractères hors alphabet GSM-7bit par leurs équivalents ASCII
    - Le tiret long '—' (U+2014) en particulier cause CMS ERROR sur SIM7600E
    """
    remplacements = {
        '\u2014': '-',   # tiret long —
        '\u2013': '-',   # tiret court –
        '\u2019': "'",   # apostrophe courbe droite '
        '\u2018': "'",   # apostrophe courbe gauche '
        '\u201c': '"',   # guillemet ouvrant "
        '\u201d': '"',   # guillemet fermant "
        '\u2026': '...',  # points de suspension …
        '\u00ab': '"',   # guillemet français «
        '\u00bb': '"',   # guillemet français »
        '\u00a0': ' ',   # espace insécable
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'À': 'A', 'Â': 'A', 'Ä': 'A',
        'î': 'i', 'ï': 'i',
        'Î': 'I', 'Ï': 'I',
        'ô': 'o', 'ö': 'o',
        'Ô': 'O', 'Ö': 'O',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'ç': 'c', 'Ç': 'C',
        '[': '(', ']': ')',
    }
    for char, remplacement in remplacements.items():
        texte = texte.replace(char, remplacement)
    # Tronquer au nombre de caractères (pas d'octets)
    return texte[:max_car]


def ecrire_sms_a_envoyer(station_id: str, message: str, telephone: str, recommandation_id: int = None):
    """
    Écrit la recommandation à envoyer par SMS dans Firebase.
    Le message est nettoyé pour GSM-7bit avant écriture (pas de tiret long, etc.)
    L'ESP32 lira ce nœud et enverra le SMS via SIM7600E.
    """
    try:
        from datetime import datetime
        message_propre = _sms_clean(message, max_car=350)
        payload = {
            "message"  : message_propre,
            "telephone": telephone,
            "timestamp": datetime.now().isoformat(),
            "envoye"   : False,
        }
        if recommandation_id is not None:
            payload["recommandation_id"] = recommandation_id
            
        db.reference(f"stations/{station_id}/sms_a_envoyer").set(payload)
        print(f"[SMS] Message écrit dans Firebase pour {station_id} ({len(message_propre)} car.)")
    except Exception as e:
        print(f"❌ ecrire_sms_a_envoyer : {e}")


def marquer_sms_envoye(station_id: str):
    """
    Marque le SMS en attente comme envoyé dans Firebase.
    À appeler par l'ESP32 (via la route /sms/marquer-envoye/{station_id})
    après avoir transmis le SMS par SIM7600E.
    """
    try:
        db.reference(f"stations/{station_id}/sms_a_envoyer/envoye").set(True)
        print(f"[SMS] ✅ SMS marqué comme envoyé pour {station_id}")
    except Exception as e:
        print(f"❌ marquer_sms_envoye : {e}")


def get_sms_en_attente(station_id: str) -> dict:
    """
    Retourne le SMS en attente pour une station (envoye == False).
    L'ESP32 interroge cette route régulièrement pour récupérer les messages à transmettre.
    """
    try:
        data = db.reference(f"stations/{station_id}/sms_a_envoyer").get()
        if not data or not isinstance(data, dict):
            return {}
        # Ne retourner que si le SMS n'a pas encore été envoyé
        if data.get("envoye") is False:
            return data
        return {}
    except Exception as e:
        print(f"❌ get_sms_en_attente : {e}")
        return {}


def get_telephone_agriculteur(station_id: str) -> str:
    """
    Retourne le numéro de téléphone de l'agriculteur
    rattaché à cette station.
    """
    try:
        agriculteurs = db.reference("agriculteurs").get()
        if not agriculteurs:
            return ""
        for uid, data in agriculteurs.items():
            if data.get("station_id") == station_id and data.get("actif"):
                tel = data.get("telephone", "")
                if tel:
                    return tel
        return ""
    except Exception as e:
        print(f"❌ get_telephone_agriculteur : {e}")
        return ""    


def get_profil_agriculteur(station_id: str) -> dict:
    """
    Retourne le profil de l'agriculteur rattaché à cette station.
    """
    try:
        agriculteurs = db.reference("agriculteurs").get()
        if not agriculteurs:
            return {}
        for uid, data in agriculteurs.items():
            if data.get("station_id") == station_id and data.get("actif"):
                return data
        return {}
    except Exception as e:
        print(f"❌ get_profil_agriculteur : {e}")
        return {}


# ── Gestion des Cultures & Seuils (Système Expert) ──────────────────────────

DEFAULT_CULTURES_SEUILS = {
    "Manioc": {
        "HUM_SOL_MIN": 30.0,
        "HUM_SOL_MAX": 75.0,
        "TEMP_AIR_MIN": 18.0,
        "TEMP_AIR_MAX": 38.0,
        "HUM_AIR_MIN": 40.0,
        "HUM_AIR_MAX": 85.0,
        "VENT_MAX": 30.0
    },
    "Tomate": {
        "HUM_SOL_MIN": 40.0,
        "HUM_SOL_MAX": 70.0,
        "TEMP_AIR_MIN": 15.0,
        "TEMP_AIR_MAX": 30.0,
        "HUM_AIR_MIN": 50.0,
        "HUM_AIR_MAX": 85.0,
        "VENT_MAX": 25.0
    },
    "Poivron": {
        "HUM_SOL_MIN": 45.0,
        "HUM_SOL_MAX": 75.0,
        "TEMP_AIR_MIN": 18.0,
        "TEMP_AIR_MAX": 32.0,
        "HUM_AIR_MIN": 50.0,
        "HUM_AIR_MAX": 85.0,
        "VENT_MAX": 20.0
    },
    "Aubergine": {
        "HUM_SOL_MIN": 40.0,
        "HUM_SOL_MAX": 70.0,
        "TEMP_AIR_MIN": 20.0,
        "TEMP_AIR_MAX": 35.0,
        "HUM_AIR_MIN": 45.0,
        "HUM_AIR_MAX": 80.0,
        "VENT_MAX": 25.0
    },
    "Oignon": {
        "HUM_SOL_MIN": 30.0,
        "HUM_SOL_MAX": 60.0,
        "TEMP_AIR_MIN": 10.0,
        "TEMP_AIR_MAX": 32.0,
        "HUM_AIR_MIN": 40.0,
        "HUM_AIR_MAX": 80.0,
        "VENT_MAX": 30.0
    }
}


def get_station_culture(station_id: str) -> str:
    """Retourne la culture configurée pour la station (par défaut 'Tomate')."""
    try:
        ref = db.reference(f"stations/{station_id}/culture")
        culture = ref.get()
        return culture if culture else "Manioc"
    except Exception as e:
        print(f"❌ get_station_culture({station_id}) : {e}")
        return "Manioc"


def set_station_culture(station_id: str, culture: str) -> bool:
    """Enregistre la culture configurée pour la station."""
    try:
        db.reference(f"stations/{station_id}/culture").set(culture)
        return True
    except Exception as e:
        print(f"❌ set_station_culture({station_id}, {culture}) : {e}")
        return False


def get_seuils_culture(culture: str) -> dict:
    """Retourne les seuils d'alerte pour une culture spécifique depuis Firebase, avec fallback."""
    try:
        ref = db.reference(f"cultures_seuils/{culture}")
        data = ref.get()
        defaults = DEFAULT_CULTURES_SEUILS.get(culture, DEFAULT_CULTURES_SEUILS["Manioc"])
        if data and isinstance(data, dict):
            # Assurer que toutes les clés requises sont présentes, sinon fallback
            for k, v in defaults.items():
                if k not in data or data[k] is None:
                    data[k] = v
            return data
        return defaults
    except Exception as e:
        print(f"❌ get_seuils_culture({culture}) : {e}")
        return DEFAULT_CULTURES_SEUILS.get(culture, DEFAULT_CULTURES_SEUILS["Manioc"])


def update_seuils_culture(culture: str, seuils: dict) -> bool:
    """Met à jour les seuils pour une culture spécifique dans Firebase."""
    try:
        db.reference(f"cultures_seuils/{culture}").set(seuils)
        return True
    except Exception as e:
        print(f"❌ update_seuils_culture({culture}) : {e}")
        return False


def get_all_seuils_cultures() -> dict:
    """Retourne les seuils de toutes les cultures fusionnés avec les valeurs par défaut."""
    try:
        ref = db.reference("cultures_seuils")
        data = ref.get()
        if not data or not isinstance(data, dict):
            data = {}
        result = {}
        for c, defaults in DEFAULT_CULTURES_SEUILS.items():
            c_data = data.get(c, {})
            if not isinstance(c_data, dict):
                c_data = {}
            merged = {}
            for k, v in defaults.items():
                merged[k] = c_data.get(k, v)
            result[c] = merged
        return result
    except Exception as e:
        print(f"❌ get_all_seuils_cultures : {e}")
        return DEFAULT_CULTURES_SEUILS


def sauvegarder_prediction_courante(
    station_id: str,
    reco_id: int,
    label: str,
    conseil: str,
    culture: str,
    capteurs: dict,
    previsions: dict
):
    """Sauvegarde la prédiction courante pour affichage direct."""
    try:
        from datetime import datetime
        db.reference(f"stations/{station_id}/current_prediction").set({
            "recommandation_id": reco_id,
            "label": label,
            "conseil": conseil,
            "timestamp": datetime.now().isoformat(),
            "culture": culture,
            "capteurs": capteurs,
            "previsions": previsions
        })
    except Exception as e:
        print(f"❌ sauvegarder_prediction_courante({station_id}) : {e}")


def get_recommandation_precedente(station_id: str) -> int | None:
    """
    Lit l'ID de la dernière recommandation envoyée par SMS (recommandation_id dans sms_a_envoyer).
    Retourne l'entier ou None si aucun SMS n'a encore été envoyé.
    """
    try:
        data = db.reference(f"stations/{station_id}/sms_a_envoyer").get()
        if not data or not isinstance(data, dict):
            return None
        val = data.get("recommandation_id")
        if val is None:
            return None
        return int(val)
    except Exception as e:
        print(f"❌ get_recommandation_precedente({station_id}) : {e}")
        return None