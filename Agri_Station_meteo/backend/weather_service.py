"""
weather_service.py — Prévisions météo via OpenWeather API
Même logique que Station_meteo : recherche par nom de ville,
temp_max/min calculés sur toutes les entrées du jour.
"""


import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # Charge les variables depuis le fichier .env
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
BASE_URL            = "https://api.openweathermap.org/data/2.5"

DEFAULT_LAT = 14.1520
DEFAULT_LON = -16.0726

# Correspondance région Sénégal → nom ville OpenWeather
REGION_VILLE = {
    "Dakar"       : "Dakar",
    "Thiès"       : "Thiès",
    "Kaolack"     : "Kaolack",
    "Saint-Louis" : "Saint-Louis",
    "Fatick"      : "Fatick",
    "Diourbel"    : "Diourbel",
    "Ziguinchor"  : "Ziguinchor",
    "Tambacounda" : "Tambacounda",
    "Louga"       : "Louga",
    "Matam"       : "Matam",
    "Kaffrine"    : "Kaffrine",
    "Kédougou"    : "Kédougou",
    "Kolda"       : "Kolda",
    "Sédhiou"     : "Sédhiou",
}

EMOJI_METEO = {
    "01": "☀️", "02": "⛅", "03": "☁️", "04": "☁️",
    "09": "🌧️", "10": "🌦️", "11": "⛈️", "13": "❄️", "50": "🌫️",
}


def icone_emoji(code: str) -> str:
    return EMOJI_METEO.get(code[:2], "🌡️")


def icone_url(code: str) -> str:
    return f"https://openweathermap.org/img/wn/{code}@2x.png"



JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
MOIS_FR  = ["jan", "fév", "mar", "avr", "mai", "jun",
             "jul", "aoû", "sep", "oct", "nov", "déc"]

def _jour_fr(dt) -> str:
    return f"{JOURS_FR[dt.weekday()]} {dt.day:02d}/{dt.month:02d}"

def get_previsions_5j(region: str = "Kaolack", lat: float = None, lon: float = None) -> dict:
    """
    Prévisions 5 jours — même logique que Station_meteo :
    - Recherche par nom de ville (q=Kaolack,SN)
    - temp_max/min calculés sur TOUTES les entrées de chaque jour
    - risque_pluie = probabilité de précipitation (pop)
    """
    try:
        ville = REGION_VILLE.get(region, region)

        params = {
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang" : "fr",
            "cnt"  : 40,
        }

        # Priorité : nom de ville (comme Station_meteo), sinon coordonnées GPS
        if ville:
            params["q"] = f"{ville},SN"
        elif lat and lon:
            params["lat"] = lat
            params["lon"] = lon
        else:
            params["lat"] = DEFAULT_LAT
            params["lon"] = DEFAULT_LON

        resp = requests.get(f"{BASE_URL}/forecast", params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        # Regrouper par jour et calculer max/min sur toute la journée
        # (exactement comme Station_meteo)
        jours = {}
        for item in raw.get("list", []):
            jour = item["dt_txt"][:10]
            if jour not in jours:
                jours[jour] = {
                    "jour"        : _jour_fr(datetime.strptime(jour, "%Y-%m-%d")),
                    "temp_max"    : item["main"]["temp_max"],
                    "temp_min"    : item["main"]["temp_min"],
                    "temp"        : item["main"]["temp"],
                    "humidite"    : item["main"]["humidity"],
                    "vent"        : round(item["wind"]["speed"] * 3.6, 1),
                    "risque_pluie": int(item.get("pop", 0) * 100),
                    "description" : item["weather"][0]["description"].capitalize(),
                    "icone"       : item["weather"][0]["icon"],
                    "pluie"       : item.get("rain", {}).get("3h", 0),
                }
            else:
                # Mettre à jour max/min sur toute la journée
                jours[jour]["temp_max"]     = max(jours[jour]["temp_max"], item["main"]["temp_max"])
                jours[jour]["temp_min"]     = min(jours[jour]["temp_min"], item["main"]["temp_min"])
                jours[jour]["risque_pluie"] = max(jours[jour]["risque_pluie"], int(item.get("pop", 0) * 100))
                # Garder la description de midi (12h) si disponible
                if "12:00:00" in item["dt_txt"]:
                    jours[jour]["description"] = item["weather"][0]["description"].capitalize()
                    jours[jour]["icone"]       = item["weather"][0]["icon"]
                    jours[jour]["humidite"]    = item["main"]["humidity"]
                    jours[jour]["vent"]        = round(item["wind"]["speed"] * 3.6, 1)

        previsions = list(jours.values())[:5]

        return {
            "ok"    : True,
            "ville" : raw.get("city", {}).get("name", ville),
            "liste" : previsions,
        }

    except requests.Timeout:
        return {"ok": False, "erreur": "Délai dépassé — vérifier la connexion internet"}
    except requests.HTTPError as e:
        return {"ok": False, "erreur": f"OpenWeather HTTP {e.response.status_code} : {e.response.text[:200]}"}
    except Exception as e:
        import traceback
        return {"ok": False, "erreur": f"{type(e).__name__}: {str(e)}", "trace": traceback.format_exc()[-300:]}


def get_meteo_actuelle_simple(region: str = "Kaolack", lat: float = None, lon: float = None) -> dict:
    """Météo actuelle par nom de ville (comme Station_meteo)."""
    try:
        ville  = REGION_VILLE.get(region, region)
        params = {"appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "fr"}

        if ville:
            params["q"] = f"{ville},SN"
        elif lat and lon:
            params["lat"] = lat
            params["lon"] = lon
        else:
            params["lat"] = DEFAULT_LAT
            params["lon"] = DEFAULT_LON

        resp = requests.get(f"{BASE_URL}/weather", params=params, timeout=10)
        resp.raise_for_status()
        raw  = resp.json()
        return {
            "ok"         : True,
            "ville"      : raw.get("name", ""),
            "temp"       : round(raw["main"]["temp"], 1),
            "ressenti"   : round(raw["main"]["feels_like"], 1),
            "humidite"   : raw["main"]["humidity"],
            "description": raw["weather"][0]["description"].capitalize(),
            "icone"      : raw["weather"][0]["icon"],
            "vent"       : round(raw["wind"]["speed"] * 3.6, 1),
            "pression"   : raw["main"]["pressure"],
        }
    except Exception as e:
        return {"ok": False, "erreur": str(e)}
    
def snapshot_openweather_ia(region: str = "Kaolack", lat: float = None, lon: float = None) -> dict:
    raw = requests.get(
        f"{BASE_URL}/forecast",
        params={
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "fr",
            "q": f"{REGION_VILLE.get(region, region)},SN"
        },
        timeout=10
    ).json()

    items = raw.get("list", [])
    if len(items) < 2:
        return {}

    item = items[1]

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "forecast_for": item.get("dt_txt"),

        "temperature_future": round(item["main"]["temp"], 1),
        "humidite_future": item["main"]["humidity"],
        "vent_future": round(item["wind"]["speed"] * 3.6, 1),
        "pluie_future": round(float(item.get("pop", 0)) * 100, 1),

        "source": "openweather"
    }

def save_openweather_to_firebase(db, station_id: str, snapshot: dict):
    if not snapshot:
        return

    ref = db.reference(f"stations/{station_id}/openweather_historique")
    ref.push(snapshot)