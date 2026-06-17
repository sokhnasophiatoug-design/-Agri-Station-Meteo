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


# ── Événements de démarrage ──────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    print("[IA] Détection et entraînement automatique des modèles IA au démarrage...")
    try:
        stations = firebase_service.get_all_stations()
        if stations:
            for station_id in stations.keys():
                print(f"[IA] Essai de ré-entraînement pour la station : {station_id}")
                res = ia_service.reentainer_modele(station_id)
                if res.get("statut") == "firebase":
                    print(f"[IA] ✅ Station {station_id} entraînée avec succès !")
                else:
                    print(f"[IA] ℹ️ Station {station_id} conservée en mode Règles : {res.get('message')}")
        else:
            print("[IA] ⚠️ Aucune station détectée dans Firebase au démarrage.")
    except Exception as e:
        print(f"[IA] ❌ Erreur lors de l'entraînement au démarrage : {e}")


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


# ── Push ESP32 → Backend → Firebase (contourne les limites REST 4G) ──────────

class PushMesuresRequest(BaseModel):
    temperature:  float
    humidite_air: float
    humidite_sol: float
    vitesse_vent: float
    station_id:   Optional[str]   = None
    timestamp:    Optional[str]   = None
    latitude:     Optional[float] = None
    longitude:    Optional[float] = None
    altitude:     Optional[float] = None
    gps_fix:      Optional[bool]  = False

@app.post("/push/{station_id}", tags=["ESP32"])
def push_mesures(station_id: str, body: PushMesuresRequest):
    """
    L'ESP32 envoie ses capteurs ici (HTTP POST simple, pas de PUT/PATCH Firebase).
    Le backend effectue en séquence :
      1. SET stations/{station_id}/mesures      (données temps réel)
      2. PUSH stations/{station_id}/historique  (historique permanent)
      3. SET stations/{station_id}/gps          (si GPS fix disponible)
      4. Calcul recommandation IA + écriture SMS dans Firebase
         → l'ESP32 n'a plus besoin d'appeler /sms/recommandation séparément.
    """
    from datetime import datetime

    payload = body.dict()
    payload["station_id"] = station_id

    # ── 1-3. Écriture Firebase ───────────────────────────────────────────────
    result = firebase_service.push_mesures_et_historique(station_id, payload)
    if not result.get("succes"):
        raise HTTPException(status_code=500, detail=result.get("erreur", "Erreur Firebase"))

    # ── 4. Recommandation IA + SMS (non bloquant si erreur) ─────────────────
    sms_statut = "skipped"
    try:
        # Prévisions OpenWeather
        gps    = firebase_service.get_station_gps(station_id)
        prev   = weather_service.get_previsions_5j(
            region = "Kaolack",
            lat    = gps.get("latitude"),
            lon    = gps.get("longitude"),
        )
        if prev.get("ok") and prev.get("liste"):
            firebase_service.sauvegarder_openweather(station_id, prev["liste"])

        # Recommandation IA sur les capteurs reçus
        p  = float(prev.get("liste", [{}])[0].get("pluie",    0) if prev.get("ok") else 0)
        tf = float(prev.get("liste", [{}])[0].get("temp_max", body.temperature) if prev.get("ok") else body.temperature)
        hf = float(prev.get("liste", [{}])[0].get("humidite", body.humidite_air) if prev.get("ok") else body.humidite_air)
        vf = float(prev.get("liste", [{}])[0].get("vent",     0) if prev.get("ok") else 0)

        reco = ia_service.get_recommandation(
            temperature        = body.temperature,
            humidite_air       = body.humidite_air,
            humidite_sol       = body.humidite_sol,
            vitesse_vent       = body.vitesse_vent,
            pluie_prevue_3h    = p,
            temperature_future = tf,
            humidite_future    = hf,
            vent_future        = vf,
        )

        # Téléphone agriculteur
        telephone = firebase_service.get_telephone_agriculteur(station_id)
        if not telephone:
            sms_statut = "no_phone"
        else:
            if not telephone.startswith("+"):
                telephone = "+221" + telephone
            conseil = reco["conseil"][:80]
            message = (
                f"Agri Meteo {station_id} "
                f"[{reco['label'][:30]}]\n"
                f"{conseil}\n"
                f"Temp:{body.temperature:.0f}C Sol:{body.humidite_sol:.0f}% Vent:{body.vitesse_vent:.0f}km/h"
            )[:160]
            firebase_service.ecrire_sms_a_envoyer(station_id, message, telephone)
            sms_statut = "ok"
            print(f"[PUSH] 📱 SMS écrit pour {station_id} → {telephone}")

        # Traçabilité dataset
        firebase_service.sauvegarder_dataset(station_id, {
            "temperature"       : body.temperature,
            "humidite_air"      : body.humidite_air,
            "humidite_sol"      : body.humidite_sol,
            "vitesse_vent"      : body.vitesse_vent,
            "pluie_prevue_3h"   : p,
            "temperature_future": tf,
            "humidite_future"   : hf,
            "vent_future"       : vf,
            "label_idx"         : reco["label_idx"],
            "label"             : reco["label"],
            "source"            : reco["source"],
        })

    except Exception as e:
        print(f"[PUSH] ⚠️ Erreur pipeline SMS : {e}")
        sms_statut = f"error: {str(e)[:60]}"

    return {
        "statut"      : "ok",
        "station_id"  : station_id,
        "timestamp"   : payload.get("timestamp"),
        "temperature" : body.temperature,
        "humidite_sol": body.humidite_sol,
        "sms_statut"  : sms_statut,
    }


# ── Forcer la mise à jour de TOUTES les branches Firebase ────────────────────

@app.get("/forcer-maj/{station_id}", tags=["Administration"])
def forcer_mise_a_jour(station_id: str):
    """
    🔄 Déclenche manuellement la mise à jour de toutes les branches Firebase :
      - mesures      → dernier enregistrement de historique
      - gps          → coordonnées du dernier enregistrement
      - dataset      → nouvel échantillon ajouté (IA)
      - sms_a_envoyer→ nouveau message GSM-7bit calculé par l'IA

    Utile quand l'ESP32 n'est pas connecté ou quand le backend vient de démarrer.
    Appeler depuis le navigateur :
      https://agri-station-meteo.onrender.com/forcer-maj/ST002
    """
    from datetime import datetime
    rapport = {
        "station_id": station_id,
        "timestamp" : datetime.now().isoformat(),
        "mesures"   : "skipped",
        "gps"       : "skipped",
        "dataset"   : "skipped",
        "sms"       : "skipped",
    }

    # ── 1. Lire le dernier enregistrement de l'historique ────────────────────
    historique = firebase_service.get_historique(station_id, limit=1)
    if not historique:
        return {"erreur": "Aucun historique trouvé pour " + station_id, **rapport}

    dernier = historique[0]
    temperature  = float(dernier.get("temperature",  0))
    humidite_air = float(dernier.get("humidite_air", 0))
    humidite_sol = float(dernier.get("humidite_sol", 0))
    vitesse_vent = float(dernier.get("vitesse_vent", 0))
    ts           = dernier.get("timestamp", datetime.now().isoformat())

    print(f"[MAJ] Dernier historique : T={temperature} Sol={humidite_sol} @ {ts}")

    # ── 2. Mettre à jour mesures ─────────────────────────────────────────────
    try:
        db_ref = firebase_service.db
        db_ref.reference(f"stations/{station_id}/mesures").set({
            "temperature" : temperature,
            "humidite_air": humidite_air,
            "humidite_sol": humidite_sol,
            "vitesse_vent": vitesse_vent,
            "station_id"  : station_id,
            "timestamp"   : ts,
            "latitude"    : dernier.get("latitude"),
            "longitude"   : dernier.get("longitude"),
            "gps_fix"     : dernier.get("gps_fix", False),
        })
        rapport["mesures"] = f"ok - T={temperature}C Sol={humidite_sol}% @ {ts}"
        print(f"[MAJ] ✅ mesures mis a jour")
    except Exception as e:
        rapport["mesures"] = f"erreur: {str(e)[:60]}"

    # ── 3. Mettre à jour GPS ─────────────────────────────────────────────────
    try:
        lat = dernier.get("latitude")
        lon = dernier.get("longitude")
        if lat and lon:
            firebase_service.db.reference(f"stations/{station_id}/gps").set({
                "latitude" : lat,
                "longitude": lon,
                "altitude" : dernier.get("altitude", 0),
                "timestamp": ts,
            })
            rapport["gps"] = f"ok - {lat},{lon}"
            print(f"[MAJ] ✅ GPS mis a jour : {lat},{lon}")
        else:
            rapport["gps"] = "skipped - pas de coordonnees dans l'historique"
    except Exception as e:
        rapport["gps"] = f"erreur: {str(e)[:60]}"

    # ── 4. Prévisions météo + dataset ────────────────────────────────────────
    p = tf = hf = vf = 0.0
    try:
        gps  = firebase_service.get_station_gps(station_id)
        prev = weather_service.get_previsions_5j(
            region="Kaolack",
            lat=gps.get("latitude"),
            lon=gps.get("longitude"),
        )
        if prev.get("ok") and prev.get("liste"):
            firebase_service.sauvegarder_openweather(station_id, prev["liste"])
            p  = float(prev["liste"][0].get("pluie",    0))
            tf = float(prev["liste"][0].get("temp_max", temperature))
            hf = float(prev["liste"][0].get("humidite", humidite_air))
            vf = float(prev["liste"][0].get("vent",     0))

        reco = ia_service.get_recommandation(
            temperature=temperature, humidite_air=humidite_air,
            humidite_sol=humidite_sol, vitesse_vent=vitesse_vent,
            pluie_prevue_3h=p, temperature_future=tf,
            humidite_future=hf, vent_future=vf,
        )

        firebase_service.sauvegarder_dataset(station_id, {
            "temperature"       : temperature,
            "humidite_air"      : humidite_air,
            "humidite_sol"      : humidite_sol,
            "vitesse_vent"      : vitesse_vent,
            "pluie_prevue_3h"   : p,
            "temperature_future": tf,
            "humidite_future"   : hf,
            "vent_future"       : vf,
            "label_idx"         : reco["label_idx"],
            "label"             : reco["label"],
            "source"            : reco["source"],
        })
        rapport["dataset"] = f"ok - label={reco['label']} (conf={reco.get('confiance','?')})"
        print(f"[MAJ] ✅ dataset mis a jour : {reco['label']}")

        # ── 5. SMS ───────────────────────────────────────────────────────────
        telephone = firebase_service.get_telephone_agriculteur(station_id)
        if not telephone:
            rapport["sms"] = "skipped - pas de telephone agriculteur"
        else:
            if not telephone.startswith("+"):
                telephone = "+221" + telephone
            conseil = reco["conseil"][:80]
            message = (
                f"Agri Meteo {station_id} [{reco['label'][:30]}]\n"
                f"{conseil}\n"
                f"Temp:{temperature:.0f}C Sol:{humidite_sol:.0f}% Vent:{vitesse_vent:.0f}km/h"
            )
            message = firebase_service._sms_clean(message)
            firebase_service.ecrire_sms_a_envoyer(station_id, message, telephone)
            rapport["sms"] = f"ok - {len(message)} car. → {telephone}"
            print(f"[MAJ] ✅ SMS ecrit : {message[:60]}")

    except Exception as e:
        rapport["dataset"] = f"erreur: {str(e)[:80]}"
        rapport["sms"]     = "skipped (erreur dataset)"
        print(f"[MAJ] ❌ Erreur : {e}")

    print(f"[MAJ] Rapport final : {rapport}")
    return rapport


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


@app.get("/ia/status", tags=["IA"])
def get_ia_status():
    """
    Retourne la source actuelle du modèle IA ('Règles' ou 'Firebase').
    """
    return {
        "source": ia_service.get_source_modele(),
    }


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


@app.post("/ia/dataset/{station_id}", tags=["IA"])
@app.get("/ia/dataset/{station_id}", tags=["IA"])
def generer_dataset(station_id: str):
    """
    Génère le dataset fusionné historique + OpenWeather et l'écrit dans Firebase.
    Utile pour forcer la création de stations/{station_id}/dataset.
    """
    resultat = ia_service.generer_dataset_sur_firebase(station_id)
    if not resultat.get("succes"):
        raise HTTPException(status_code=404, detail=resultat.get("message", "Impossible de générer le dataset"))
    return resultat


@app.post("/sms/recommandation/{station_id}", tags=["SMS"])
@app.get("/sms/recommandation/{station_id}",  tags=["SMS"])
def envoyer_sms_recommandation(station_id: str, region: str = "Kaolack"):
    """
    Flux complet SMS — exécuté à chaque appel de l'ESP32 :
    0a. Rafraîchit les prévisions OpenWeather du jour dans Firebase
    0b. Reconstruit le dataset fusionné (capteurs + OpenWeather) dans Firebase
    1.  Lit la DERNIÈRE entrée du dataset Firebase
    2.  Calcule la recommandation IA sur cette entrée fraîche
    3.  Récupère le téléphone de l'agriculteur
    4.  Écrit le SMS dans Firebase → l'ESP32 l'envoie via SIM7600E
    """

    # ── 0a. Rafraîchir OpenWeather AVANT de lire le dataset ─────────────────
    try:
        gps = firebase_service.get_station_gps(station_id)
        lat_gps = gps.get("latitude")
        lon_gps = gps.get("longitude")
        previsions = weather_service.get_previsions_5j(
            region=region,
            lat=lat_gps,
            lon=lon_gps,
        )
        if previsions.get("ok") and previsions.get("liste"):
            firebase_service.sauvegarder_openweather(station_id, previsions["liste"])
            print(f"[SMS] ✅ OpenWeather rafraîchi pour {station_id} — "
                  f"{len(previsions['liste'])} jours")
        else:
            print(f"[SMS] ⚠️  OpenWeather non dispo : {previsions.get('erreur', '?')}")
    except Exception as e:
        # Ne jamais bloquer le flux si la météo est indisponible
        print(f"[SMS] ⚠️  Erreur rafraîchissement OpenWeather : {e}")

    # ── 0b. Reconstruire le dataset avec les données fraîches ───────────────
    try:
        resultat_ds = ia_service.reentainer_modele(station_id)
        print(f"[SMS] ✅ Dataset reconstruit — {resultat_ds.get('nb_entrees', 0)} entrées")
    except Exception as e:
        print(f"[SMS] ⚠️  Erreur reconstruction dataset : {e}")

    # ── 1. Lire la DERNIÈRE entrée du dataset fusionné ──────────────────────
    try:
        from firebase_admin import db
        dataset_raw = db.reference(f"stations/{station_id}/dataset").get()
        if not dataset_raw or not isinstance(dataset_raw, dict):
            raise HTTPException(
                status_code=404,
                detail="Dataset vide — attendez que l'ESP32 envoie des mesures",
            )

        # Conserver uniquement les entrées dictionnaires valides
        entrees_valides = [
            e for e in dataset_raw.values()
            if isinstance(e, dict) and e.get("temperature") is not None
        ]
        if not entrees_valides:
            raise HTTPException(status_code=404, detail="Dataset sans entrée valide")

        # Trier par timestamp ISO croissant → la plus récente est la dernière
        try:
            entrees_valides.sort(
                key=lambda x: x.get("timestamp", "0"),
                reverse=True,
            )
        except Exception:
            pass  # si le tri échoue, on prend la première (ordre Firebase)

        derniere = entrees_valides[0]
        print(
            f"[SMS] 📊 Dernière entrée dataset : "
            f"ts={derniere.get('timestamp')} "
            f"label={derniere.get('label')}"
        )

        temperature        = float(derniere.get("temperature",        0) or 0)
        humidite_air       = float(derniere.get("humidite_air",       0) or 0)
        humidite_sol       = float(derniere.get("humidite_sol",       0) or 0)
        vitesse_vent       = float(derniere.get("vitesse_vent",       0) or 0)
        pluie_prevue_3h    = float(derniere.get("pluie_prevue_3h",    0) or 0)
        temperature_future = float(derniere.get("temperature_future", 0) or 0)
        humidite_future    = float(derniere.get("humidite_future",    0) or 0)
        vent_future        = float(derniere.get("vent_future",        0) or 0)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    # ── 2. Recommandation IA ─────────────────────────────────────────────────
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
    print(f"[SMS] 🤖 Recommandation IA : label={reco['label_idx']} — {reco['label']}")

    # ── 3. Téléphone agriculteur ─────────────────────────────────────────────
    telephone = firebase_service.get_telephone_agriculteur(station_id)
    if not telephone:
        raise HTTPException(
            status_code=404,
            detail="Aucun agriculteur actif trouvé pour cette station",
        )

    # Format international Sénégal
    if not telephone.startswith("+"):
        telephone = "+221" + telephone

    # ── 4. Construire le message SMS (≤ 155 caractères, GSM-7bit pur) ──────────
    conseil = reco["conseil"][:80]
    message = (
        f"Agri Meteo {station_id} "
        f"[{reco['label'][:30]}]\n"
        f"{conseil}\n"
        f"Temp:{temperature:.0f}C Sol:{humidite_sol:.0f}% Vent:{vitesse_vent:.0f}km/h"
    )
    message = firebase_service._sms_clean(message)  # garantie GSM-7bit + 155 car.

    # ── 5. Écrire dans Firebase → ESP32 enverra le SMS ──────────────────────
    firebase_service.ecrire_sms_a_envoyer(station_id, message, telephone)
    print(f"[SMS] 📱 SMS écrit dans Firebase → {telephone}")

    return {
        "statut"         : "ok",
        "message"        : "SMS programmé dans Firebase",
        "telephone"      : telephone,
        "sms"            : message,
        "reco"           : reco,
        "donnees_source" : {
            "timestamp"        : derniere.get("timestamp"),
            "temperature"      : temperature,
            "humidite_sol"     : humidite_sol,
            "label"            : derniere.get("label"),
        },
    }


@app.get("/sms/en-attente/{station_id}", tags=["SMS"])
def sms_en_attente(station_id: str):
    """
    Retourne le SMS en attente pour l'ESP32 (envoye == False).
    L'ESP32 interroge cette route et envoie le message via SIM7600E.
    Si aucun SMS en attente : retourne un objet vide {}.
    """
    data = firebase_service.get_sms_en_attente(station_id)
    return data if data else {"statut": "aucun_sms_en_attente"}


@app.post("/sms/marquer-envoye/{station_id}", tags=["SMS"])
@app.get("/sms/marquer-envoye/{station_id}",  tags=["SMS"])
def marquer_sms_envoye(station_id: str):
    """
    Marque le SMS comme envoyé dans Firebase.
    L'ESP32 appelle cette route après avoir transmis le SMS par SIM7600E.
    Le champ `envoye` passe à True — évite les doubles envois.
    """
    firebase_service.marquer_sms_envoye(station_id)
    return {"statut": "ok", "message": f"SMS marqué comme envoyé pour {station_id}"}


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


@app.get("/stations/{station_id}/gps", tags=["Stations"])
def get_station_gps(station_id: str):
    """
    Retourne les coordonnées GPS de la station spécifiée.
    """
    gps = firebase_service.get_station_gps(station_id)
    return gps if gps else {"latitude": None, "longitude": None}


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