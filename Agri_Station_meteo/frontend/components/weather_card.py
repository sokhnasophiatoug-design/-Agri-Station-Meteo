"""
weather_card.py — Composant prévisions météo 5 jours pour Streamlit
Affiche des cartes visuelles par jour avec icônes et températures.
"""

import streamlit as st

# Mapping emoji OpenWeather (inline — pas d'import du backend)
_EMOJI_METEO = {
    "01": "☀️", "02": "⛅", "03": "☁️", "04": "☁️",
    "09": "🌧️", "10": "🌦️", "11": "⛈️", "13": "❄️", "50": "🌫️",
}

def icone_emoji(code: str) -> str:
    return _EMOJI_METEO.get(code[:2], "🌡️")


def afficher_meteo_actuelle(meteo: dict):
    if not meteo.get("ok"):
        st.warning("⚠️ Météo indisponible")
        return

    emoji = icone_emoji(meteo.get("icone", "01d"))

    html = (
        '<div style="background:linear-gradient(135deg,#16351c,#1f4d2c);'
        'border-radius:18px;padding:20px 22px;color:white;'
        'box-shadow:0 6px 22px rgba(0,0,0,0.28);'
        'border:1px solid rgba(255,255,255,0.08);margin-bottom:8px;">'

        '<div style="display:flex;align-items:center;gap:16px;">'
        f'<div style="font-size:3rem;line-height:1;">{emoji}</div>'
        '<div>'
        f'<div style="font-size:2rem;font-weight:800;line-height:1.1;">{meteo.get("temp","--")}°C</div>'
        f'<div style="font-size:0.9rem;opacity:0.85;margin-top:3px;">{meteo.get("description","")}</div>'
        '</div>'
        '</div>'

        f'<div style="margin-top:14px;font-size:0.88rem;opacity:0.9;">📍 {meteo.get("ville","")}</div>'

        '<div style="margin-top:10px;padding-top:10px;'
        'border-top:1px solid rgba(255,255,255,0.12);'
        'font-size:0.85rem;opacity:0.92;display:flex;gap:18px;">'
        f'<span>💧 {meteo.get("humidite","--")}%</span>'
        f'<span>💨 {meteo.get("vent","--")} km/h</span>'
        f'<span>🌡️ Ressenti {meteo.get("ressenti","--")}°C</span>'
        '</div>'

        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def afficher_previsions(previsions_data: dict):
    if not previsions_data.get("ok"):
        st.warning(f"⚠️ Prévisions indisponibles : {previsions_data.get('erreur', 'Erreur inconnue')}")
        return

    liste = previsions_data.get("liste", [])
    ville = previsions_data.get("ville", "")

    if ville:
        st.markdown(f"<small style='color:#94a3b8'>📍 Données météo pour : <b>{ville}</b></small>",
                    unsafe_allow_html=True)

    if not liste:
        st.info("Aucune prévision disponible.")
        return

    # ── Rendu HTML 2 colonnes — fonctionne sur mobile ET desktop ──
    cartes = []
    for jour in liste:
        emoji     = icone_emoji(jour.get("icone", "01d"))
        label     = jour.get("jour") or jour.get("date", "")
        temp_max  = jour.get("temp_max", "--")
        temp_min  = jour.get("temp_min", "--")
        temp_str  = f"{temp_min}° ── {temp_max}°" if temp_max != "--" else f"{jour.get('temp', '--')}°C"
        pluie     = jour.get("pluie", 0) or 0
        risque    = jour.get("risque_pluie", 0)
        pluie_str = f"🌧 {pluie:.1f} mm" if pluie > 0 else f"☀️ {risque}% pluie" if risque > 10 else "☀️ Sec"
        hum       = jour.get("humidite", "--")
        vent      = jour.get("vent", "--")
        desc      = jour.get("description", "")

        cartes.append(f"""
        <div style="background:rgba(255,255,255,0.97);border-radius:18px;padding:14px 12px;
                    border-top:4px solid #1B7F2A;
                    box-shadow:0 6px 18px rgba(0,0,0,0.14);text-align:center;">
            <div style="color:#1B5E20;font-size:0.7rem;font-weight:900;text-transform:uppercase;
                        letter-spacing:0.8px;margin-bottom:6px;">{label}</div>
            <div style="font-size:1.6rem;margin-bottom:6px;">{emoji}</div>
            <div style="color:#062B0D;font-size:1.2rem;font-weight:900;
                        font-family:'Roboto Mono',monospace;margin-bottom:6px;">{temp_str}</div>
            <div style="color:#4A5568;font-size:0.75rem;font-weight:700;margin-bottom:4px;">{desc}</div>
            <div style="color:#374151;font-size:0.72rem;font-weight:600;">
                💧 {hum}% &nbsp;|&nbsp; 💨 {vent} km/h
            </div>
            <div style="color:#374151;font-size:0.72rem;font-weight:600;margin-top:3px;">{pluie_str}</div>
        </div>
        """)

    # Grid 2 colonnes — adapté mobile ET desktop
    html = '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;">'
    html += "".join(cartes)
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

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
   