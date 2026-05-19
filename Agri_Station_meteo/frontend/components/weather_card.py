"""
weather_card.py — Composant prévisions météo 5 jours pour Streamlit
Affiche des cartes visuelles par jour avec icônes et températures.
"""

import streamlit as st

from components.html_render import esc, render_html

# Mapping emoji OpenWeather (inline — pas d'import du backend)
_EMOJI_METEO = {
    "01": "☀️", "02": "⛅", "03": "☁️", "04": "☁️",
    "09": "🌧️", "10": "🌦️", "11": "⛈️", "13": "❄️", "50": "🌫️",
}

def icone_emoji(code: str) -> str:
    return _EMOJI_METEO.get(code[:2], "🌡️")


def html_meteo_entete(meteo: dict) -> str:
    """Bandeau météo compact pour l'entête (mobile + desktop)."""
    if not meteo.get("ok"):
        return ""
    emoji_m = icone_emoji(meteo.get("icone", "01d"))
    temp_m  = esc(meteo.get("temp", "--"))
    desc_m  = esc(meteo.get("description", ""))
    hum_m   = esc(meteo.get("humidite", "--"))
    vent_m  = esc(meteo.get("vent", "--"))
    return (
        "<div class='meteo-entete'>"
        + emoji_m
        + " <strong>" + temp_m + "°C</strong>"
        + "<span class='meteo-entete-sep'>·</span> "
        + desc_m
        + "<span class='meteo-entete-sep'>·</span> "
        + "💧" + hum_m + "%"
        + "<span class='meteo-entete-sep'>·</span> "
        + "💨" + vent_m + " km/h"
        + "</div>"
    )


def html_meteo_carte_ia(meteo: dict) -> str:
    """Carte météo complète (colonne IA, masquée sur mobile via CSS)."""
    if not meteo.get("ok"):
        return ""
    emoji_m    = icone_emoji(meteo.get("icone", "01d"))
    temp_m     = esc(meteo.get("temp", "--"))
    desc_m     = esc(meteo.get("description", ""))
    ville_m    = esc(meteo.get("ville", ""))
    hum_m      = esc(meteo.get("humidite", "--"))
    vent_m     = esc(meteo.get("vent", "--"))
    ressenti_m = esc(meteo.get("ressenti", "--"))
    return (
        "<div class='ia-meteo-desktop'>"
        "<div style='background:linear-gradient(135deg,#16351c,#1f4d2c);border-radius:14px;"
        "padding:14px;color:white;'>"
        "<div style='font-size:0.75rem;font-weight:800;opacity:0.7;margin-bottom:8px;'>"
        "🌤️ Météo actuelle</div>"
        "<div style='display:flex;align-items:center;gap:12px;'>"
        "<span style='font-size:2rem;'>" + emoji_m + "</span>"
        "<div>"
        "<div style='font-size:1.5rem;font-weight:900;'>" + temp_m + "°C</div>"
        "<div style='font-size:0.78rem;opacity:0.85;'>" + desc_m + "</div>"
        "</div></div>"
        "<div style='margin-top:8px;font-size:0.78rem;opacity:0.9;'>"
        "📍 " + ville_m + "</div>"
        "<div style='margin-top:6px;font-size:0.78rem;opacity:0.88;"
        "display:flex;gap:12px;flex-wrap:wrap;'>"
        "<span>💧 " + hum_m + "%</span>"
        "<span>💨 " + vent_m + " km/h</span>"
        "<span>🌡️ " + ressenti_m + "°C</span>"
        "</div></div></div>"
    )


def afficher_meteo_actuelle(meteo: dict):
    if not meteo.get("ok"):
        st.warning("⚠️ Météo indisponible")
        return
    html = html_meteo_carte_ia(meteo)
    if html:
        render_html(html.replace("ia-meteo-desktop", "meteo-now-card", 1))


def afficher_previsions(previsions_data: dict):
    if not previsions_data.get("ok"):
        st.warning(f"⚠️ Prévisions indisponibles : {previsions_data.get('erreur', 'Erreur inconnue')}")
        return

    liste = previsions_data.get("liste", [])
    ville = previsions_data.get("ville", "")

    if ville:
        render_html(
            "<small style='color:#94a3b8'>📍 Données météo pour : <b>"
            + esc(ville) + "</b></small>"
        )

    cards_html = "<div class='previsions-grid'>"
    for jour in liste:
        emoji     = icone_emoji(jour.get("icone", "01d"))
        label     = esc(jour.get("jour") or jour.get("date", ""))
        temp_max  = jour.get("temp_max", "--")
        temp_min  = jour.get("temp_min", "--")
        temp_str  = esc(f"{temp_min}° ── {temp_max}°" if temp_max != "--" else f"{jour.get('temp', '--')}°C")
        pluie     = jour.get("pluie", 0) or 0
        risque    = jour.get("risque_pluie", 0)
        pluie_str = esc(
            f"🌧 {pluie:.1f} mm" if pluie > 0
            else f"☀️ {risque}% pluie" if risque > 10
            else "☀️ Sec"
        )
        cards_html += (
            "<div class='meteo-card'>"
            "<div class='jour'>" + label + "</div>"
            "<div class='icon'>" + emoji + "</div>"
            "<div class='temp'>" + temp_str + "</div>"
            "<div class='desc'>" + esc(jour.get("description", "")) + "</div>"
            "<div class='desc' style='margin-top:6px'>"
            "💧 " + esc(jour.get("humidite", "--")) + "% &nbsp;|&nbsp; "
            "💨 " + esc(jour.get("vent", "--")) + " km/h"
            "</div>"
            "<div class='desc'>" + pluie_str + "</div>"
            "</div>"
        )

    cards_html += "</div>"
    render_html(cards_html)


def afficher_alerte_meteo(previsions_data: dict) -> list:
    alertes = []
    if not previsions_data.get("ok"):
        return alertes

    for jour in previsions_data.get("liste", []):
        label    = jour.get("jour") or jour.get("date", "")
        temp_max = jour.get("temp_max") or jour.get("temp") or 0
        vent     = jour.get("vent", 0) or 0
        pluie    = jour.get("pluie", 0) or 0

        if temp_max > 40:
            alertes.append(f"🌡️ Chaleur extrême prévue le {label} ({temp_max}°C) — risque de stress thermique")
        if vent > 45:
            alertes.append(f"💨 Vent fort prévu le {label} ({vent} km/h) — protéger les cultures")
        if pluie > 20:
            alertes.append(f"🌧️ Fortes pluies prévues le {label} ({pluie:.0f} mm) — surveiller le drainage")

    return alertes
