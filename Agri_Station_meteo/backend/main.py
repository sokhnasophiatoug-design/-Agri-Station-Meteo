"""
main.py — API FastAPI pour la Station Météo Agricole
Routes : /auth, /mesures, /historique, /previsions, /recommandation, /tts, /stations, /agriculteurs
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

import auth_service
import firebase_service
import weather_service
import ia_service
import tts_service


# ── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Station Météo Agricole API",
    description="API backend pour la plateforme IoT agricole sénégalaise",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Streamlit tourne en local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schémas de données ───────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    id_token: str

class RecommandationRequest(BaseModel):
    # ── Capteurs ESP32 (temps réel) ──
    temperature:  float
    humidite_air: float
    humidite_sol: float
    vitesse_vent: float
    # ── Prévisions OpenWeather ────────
    pluie_prevue_3h:    Optional[float] = 0.0
    temperature_future: Optional[float] = 0.0
    humidite_future:    Optional[float] = 0.0
    vent_future:        Optional[float] = 0.0
    # ── Métadonnées vocales ───────────
    station_id:   Optional[str]   = "ST002"  
    nom:    Optional[str] = "Agriculteur"
    region: Optional[str] = ""

class TTSRequest(BaseModel):
    texte: str
    lent:  Optional[bool] = False

class SeuilsRequest(BaseModel):
    station_id: str
    temp_max:   float
    temp_min:   float
    hum_sol_min: float
    vent_max:   float


# ── Santé ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    uid:           str
    id_token:      str
    nom:           str
    email:         str
    telephone:     Optional[str] = ""
    region:        Optional[str] = ""
    station_id:    Optional[str] = ""
    station_nom:   Optional[str] = ""
    firebase_path: Optional[str] = ""


@app.get("/", tags=["Santé"])
def health():
    return {"statut": "ok", "service": "Station Météo Agricole API v1.0"}


# ── Authentification ─────────────────────────────────────────────────────────

@app.post("/auth/verify", tags=["Auth"])
def verify_token(body: TokenRequest):
    """Vérifie le token Firebase et retourne le rôle + profil."""
    result = auth_service.verify_token_and_get_role(body.id_token)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.post("/auth/register", tags=["Auth"])
def register_agriculteur(body: RegisterRequest):
    """Inscrit un nouvel agriculteur dans Firebase DB."""
    result = auth_service.register_agriculteur(body.uid, body.dict())
    if not result.get("succes"):
        raise HTTPException(status_code=500, detail=result.get("erreur", "Erreur d'inscription"))
    return {"statut": "ok", "message": "Compte agriculteur créé avec succès"}



# ── Mesures temps réel ───────────────────────────────────────────────────────

@app.get("/mesures/{station_id}")
def get_mesures(station_id: str):
    try:
        data = firebase_service.get_mesures(station_id)

        # 🔥 sécurité anti None
        if not data or not isinstance(data, dict):
            return {}

        if "error" in data:
            return {"error": data["error"]}

        return data

    except Exception as e:
        import traceback
        print("🔥 FULL ERROR:")
        traceback.print_exc()

        return {"error": str(e)}

# ── Historique ───────────────────────────────────────────────────────────────

@app.get("/historique/{station_id}", tags=["Données"])
def get_historique(station_id: str, limit: int = 50):
    """Historique des mesures (triées par timestamp, les N dernières)."""
    data = firebase_service.get_historique(station_id, limit=limit)
    return {"station_id": station_id, "count": len(data), "historique": data}



# ── Debug Firebase ────────────────────────────────────────────────────────────

@app.get("/debug/{station_id}", tags=["Debug"])
def debug_firebase(station_id: str):
    """Inspecte la structure Firebase réelle pour diagnostiquer l'historique."""
    from firebase_admin import db
    resultat = {}

    for chemin in [
        f"stations/{station_id}",
        f"stations/{station_id}/historique",
        f"stations/{station_id}/mesures",
        "station/historique",
        "station/mesures",
        station_id,
        f"{station_id}/historique",
    ]:
        try:
            val = db.reference(chemin).get()
            if val is not None:
                if isinstance(val, dict):
                    cles = list(val.keys())
                    resultat[chemin] = {
                        "type": "dict",
                        "nb_cles": len(cles),
                        "exemple_cles": cles[:5],
                        "exemple_valeur": dict(list(val.items())[:1])
                    }
                else:
                    resultat[chemin] = {"type": type(val).__name__, "valeur": str(val)[:200]}
            else:
                resultat[chemin] = "VIDE"
        except Exception as e:
            resultat[chemin] = {"erreur": str(e)}

    try:
        racine = db.reference("/").get()
        resultat["_racine_cles"] = list(racine.keys()) if isinstance(racine, dict) else []
    except Exception as e:
        resultat["_racine_cles"] = {"erreur": str(e)}

    return resultat


# ── Prévisions météo ─────────────────────────────────────────────────────────
@app.get("/previsions/{station_id}", tags=["Météo"])
def get_previsions(station_id: str, region: str = "Kaolack", lat: float = None, lon: float = None):
    """Prévisions météo 5 jours + sauvegarde dans Firebase.

    Comportement :
    - si `lat` et `lon` fournis en query params, utilisation directe.
    - sinon, tentative de lecture GPS depuis Firebase pour la station.
    - sinon, fallback sur `region`.
    """
    # Priorité : params explicites > GPS station > region
    if lat is None or lon is None:
        gps = firebase_service.get_station_gps(station_id)
        lat = lat or gps.get("latitude")
        lon = lon or gps.get("longitude")

    result = weather_service.get_previsions_5j(region=region, lat=lat, lon=lon)
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("erreur", "Erreur météo"))

    # Sauvegarder dans Firebase pour l'historique IA (si on a une liste)
    if isinstance(result.get("liste"), list) and result.get("liste"):
        try:
            firebase_service.sauvegarder_openweather(station_id, result["liste"])
        except Exception:
            # Ne pas interrompre le flux principal si sauvegarde échoue
            print(f"⚠️ Impossible de sauvegarder les prévisions pour {station_id}")

    return result

# ── Météo actuelle ───────────────────────────────────────
@app.get("/meteo-actuelle", tags=["Météo"])
def meteo_actuelle(region: str = "Kaolack"):
    """
    Retourne la météo actuelle d'une région.
    """
    result = weather_service.get_meteo_actuelle_simple(region)

    if not result.get("ok"):
        raise HTTPException(
            status_code=503,
            detail=result.get("erreur", "Erreur météo")
        )

    return result

# ── Recommandation IA ────────────────────────────────────────────────────────
@app.post("/recommandation", tags=["IA"])
def get_recommandation(body: RecommandationRequest):
    """
    Retourne la recommandation IA basée sur 8 features :
      - 4 capteurs ESP32 temps réel (temperature, humidite_air, humidite_sol, vitesse_vent)
      - 4 prévisions OpenWeather    (pluie_prevue_3h, temperature_future, humidite_future, vent_future)
    Trace chaque décision dans stations/{station_id}/dataset/ (traçabilité).
    """
    p  = body.pluie_prevue_3h    or 0.0
    tf = body.temperature_future or 0.0
    hf = body.humidite_future    or 0.0
    vf = body.vent_future        or 0.0

    result = ia_service.get_recommandation(
        temperature        = body.temperature,
        humidite_air       = body.humidite_air,
        humidite_sol       = body.humidite_sol,
        vitesse_vent       = body.vitesse_vent,
        pluie_prevue_3h    = p,
        temperature_future = tf,
        humidite_future    = hf,
        vent_future        = vf,
    )

    result["message_vocal"] = ia_service.get_message_vocal(
        nom                = body.nom,
        region             = body.region,
        temperature        = body.temperature,
        humidite_air       = body.humidite_air,
        humidite_sol       = body.humidite_sol,
        vitesse_vent       = body.vitesse_vent,
        pluie_prevue_3h    = p,
        temperature_future = tf,
        humidite_future    = hf,
        vent_future        = vf,
    )

    # Traçabilité dataset — non bloquant
    firebase_service.sauvegarder_dataset(body.station_id or "ST002", {
        "temperature"       : body.temperature,
        "humidite_air"      : body.humidite_air,
        "humidite_sol"      : body.humidite_sol,
        "vitesse_vent"      : body.vitesse_vent,
        "pluie_prevue_3h"   : p,
        "temperature_future": tf,
        "humidite_future"   : hf,
        "vent_future"       : vf,
        "label_idx"         : result["label_idx"],
        "label"             : result["label"],
        "source"            : result["source"],
    })

    return result


@app.get("/ia/predire/{station_id}", tags=["IA"])
def predire_auto(station_id: str, region: str = "Kaolack"):
    """
    Recommandation automatique pour demain — aucun paramètre à passer.

    Le backend va chercher lui-même :
      1. La DERNIÈRE mesure réelle ESP32 depuis Firebase (temperature, humidite_air, humidite_sol, vitesse_vent)
      2. Les prévisions OpenWeather actuelles (pluie_prevue_3h, temperature_future, humidite_future, vent_future)

    Puis applique l'arbre de décision et retourne la recommandation.
    Fonctionne dès la première mesure reçue — aucune attente.
    """
    result = ia_service.predire_depuis_firebase(station_id, region=region)
    if not result.get("succes"):
        raise HTTPException(status_code=404, detail=result.get("erreur", "Aucune donnée"))
    return result

@app.post("/sms/recommandation/{station_id}", tags=["SMS"])
@app.get("/sms/recommandation/{station_id}",  tags=["SMS"])
def envoyer_sms_recommandation(station_id: str, region: str = "Kaolack"):
    """
    1. Lit le dataset Firebase (mesures + prévisions fusionnées)
    2. Calcule la recommandation IA
    3. Récupère le téléphone de l'agriculteur
    4. Écrit le SMS dans Firebase → l'ESP32 l'envoie via SIM7600E
    """
    # 1. Lire le dataset fusionné depuis Firebase
    try:
        from firebase_admin import db
        dataset_raw = db.reference(f"stations/{station_id}/dataset").get()
        if not dataset_raw or not isinstance(dataset_raw, dict):
            raise HTTPException(status_code=404,
                detail="Dataset vide — attendez que l'ESP32 envoie des mesures")

        # Prendre la dernière entrée triée par timestamp
        entrees = list(dataset_raw.values())
        entrees_valides = [e for e in entrees if isinstance(e, dict)]
        if not entrees_valides:
            raise HTTPException(status_code=404, detail="Dataset vide")
        
        # Trier par timestamp pour prendre la plus récente
        try:
            entrees_valides.sort(
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )
        except Exception:
            pass
        
        derniere = entrees_valides[0]

        temperature        = float(derniere.get("temperature",        0) or 0)
        humidite_air       = float(derniere.get("humidite_air",       0) or 0)
        humidite_sol       = float(derniere.get("humidite_sol",       0) or 0)
        vitesse_vent       = float(derniere.get("vitesse_vent",       0) or 0)
        pluie_prevue_3h    = float(derniere.get("pluie_prevue_3h",    0) or 0)
        temperature_future = float(derniere.get("temperature_future",  0) or 0)
        humidite_future    = float(derniere.get("humidite_future",     0) or 0)
        vent_future        = float(derniere.get("vent_future",         0) or 0)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 2. Recommandation IA
    reco = ia_service.get_recommandation(
        temperature        = temperature,
        humidite_air       = humidite_air,
        humidite_sol       = humidite_sol,
        vitesse_vent       = vitesse_vent,
        pluie_prevue_3h    = pluie_prevue_3h,
        temperature_future = temperature_future,
        humidite_future    = humidite_future,
        vent_future        = vent_future,
    )

    # 3. Téléphone agriculteur
    telephone = firebase_service.get_telephone_agriculteur(station_id)
    if not telephone:
        raise HTTPException(status_code=404,
            detail="Aucun agriculteur actif trouvé pour cette station")

    # Format international Sénégal
    if not telephone.startswith("+"):
        telephone = "+221" + telephone

    # 4. Construire le message SMS (court — max 160 caractères)
    emoji   = reco["emoji"]
    conseil = reco["conseil"][:100]   # tronquer si trop long
    
    # SMS sans emojis — compatibilité maximale GSM
    message = (
        f"Agri Meteo {station_id}\n"
        f"{reco['label']}\n"
        f"{conseil[:80]}\n"
        f"Temp:{temperature:.0f}C Sol:{humidite_sol:.0f}% Vent:{vitesse_vent:.0f}km/h"
    )
    # Limiter à 160 caractères (1 SMS)
    message = message[:160]

    # 5. Écrire dans Firebase → ESP32 enverra le SMS
    firebase_service.ecrire_sms_a_envoyer(station_id, message, telephone)

    return {
        "statut"    : "ok",
        "message"   : "SMS programmé dans Firebase",
        "telephone" : telephone,
        "sms"       : message,
        "reco"      : reco,
    }


@app.get("/ia/reentainer/{station_id}", tags=["IA"])  # GET pour déclencher depuis le navigateur
@app.post("/ia/reentainer/{station_id}", tags=["IA"])
def reentainer_ia(station_id: str):
    """
    Re-entraîne le modèle IA avec les données réelles de Firebase.
    Fusionne historique capteurs + OpenWeather, génère les labels via les règles,
    puis remplace le modèle CSV par le modèle Firebase.
    Le badge passe de 'CSV' à 'Firebase' dans l'interface.
    """
    resultat = ia_service.reentainer_modele(station_id)
    return {
    "statut"    : "ok" if resultat.get("statut") == "firebase" else "insuffisant",
    "message"   : resultat.get("message", ""),
    "nb_entrees": resultat.get("nb_entrees", 0),
    "score"     : resultat.get("score"),
    "source"    : ia_service.get_source_modele(),
}

# ── Synthèse vocale ──────────────────────────────────────────────────────────

@app.post("/tts", tags=["Voix"])
def text_to_speech(body: TTSRequest):
    """Génère un fichier MP3 à partir d'un texte en français."""
    try:
        audio_bytes = tts_service.generer_audio(body.texte, lent=body.lent)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur TTS : {str(e)}")


# ── Stations (admin) ─────────────────────────────────────────────────────────

@app.get("/stations", tags=["Admin"])
def get_all_stations():
    """Retourne toutes les stations avec leurs mesures actuelles."""
    stations = firebase_service.get_all_stations()
    if not stations:
        return {"stations": {}}
    # Enrichir avec les GPS
    result = {}
    for st_id, st_data in stations.items():
        result[st_id] = {
            "mesures":   st_data.get("mesures", {}),
            "gps":       st_data.get("gps", {}),
            "seuils":    st_data.get("seuils", {}),
        }
    return {"stations": result}


# ── Agriculteurs (admin) ─────────────────────────────────────────────────────

@app.get("/agriculteurs", tags=["Admin"])
def get_all_agriculteurs():
    """Retourne la liste de tous les agriculteurs enregistrés."""
    data = firebase_service.get_all_agriculteurs()
    return {"agriculteurs": data}


# ── Seuils d'alerte ──────────────────────────────────────────────────────────

@app.get("/seuils", tags=["Admin"])
def get_seuils():
    """Retourne les seuils globaux (partagés par toutes les stations)."""
    return firebase_service.get_seuils()


@app.post("/seuils", tags=["Admin"])
def update_seuils(body: SeuilsRequest):
    """Met à jour les seuils globaux (applicables à toutes les stations)."""
    ok = firebase_service.update_seuils(seuils={
        "temp_max":    body.temp_max,
        "temp_min":    body.temp_min,
        "hum_sol_min": body.hum_sol_min,
        "vent_max":    body.vent_max,
    })
    if not ok:
        raise HTTPException(status_code=500, detail="Erreur de mise à jour des seuils")
    return {"statut": "ok", "message": "Seuils globaux mis à jour"}