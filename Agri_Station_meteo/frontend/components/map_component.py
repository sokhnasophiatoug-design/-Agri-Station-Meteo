"""
map_component.py — Carte interactive des stations (admin)
Utilise Folium + streamlit-folium pour afficher toutes les stations sur une carte.
"""

import streamlit as st
import folium
from streamlit_folium import st_folium

# Centre par défaut : Sénégal
SENEGAL_CENTER = [14.4974, -14.4524]
SENEGAL_ZOOM   = 7


def afficher_carte_stations(stations: dict):
    """
    Affiche une carte Folium avec un marqueur pour chaque station.
    stations : dict { station_id: { mesures: {...}, gps: {...} } }
    """
    m = folium.Map(
        location=SENEGAL_CENTER,
        zoom_start=SENEGAL_ZOOM,
        tiles="CartoDB dark_matter",
        prefer_canvas=True,
    )

    has_marker = False

    for station_id, data in stations.items():
        gps     = data.get("gps", {})
        mesures = data.get("mesures", {})
        lat = gps.get("latitude")
        lon = gps.get("longitude")

        # Si pas de GPS, on utilise des coordonnées estimées par région
        if not lat or not lon:
            coords_defaut = {
                "ST001": [14.6928, -17.4467],   # Dakar
                "ST002": [14.1520, -16.0726],   # Kaolack
                "ST003": [15.9000, -16.5167],   # Saint-Louis
                "ST004": [14.8333, -16.5667],   # Thiès
                "ST005": [14.3386, -16.7246],   # Fatick
            }
            default = coords_defaut.get(station_id, [14.4974, -14.4524])
            lat, lon = default

        temp    = mesures.get("temperature", "N/A")
        hum_sol = mesures.get("humidite_sol", "N/A")
        vent    = mesures.get("vitesse_vent", "N/A")
        ts      = mesures.get("timestamp", "N/A")

        # Couleur du marqueur selon la température
        if isinstance(temp, (int, float)):
            couleur = "red" if temp > 38 else ("orange" if temp > 32 else "green")
        else:
            couleur = "gray"

        popup_html = f"""
        <div style="font-family:sans-serif; min-width:200px; color:#1e293b;">
            <h4 style="margin:0 0 8px; color:#00a86b;">📡 {station_id}</h4>
            <table style="width:100%; font-size:13px;">
                <tr><td>🌡️ Température</td><td><b>{temp}°C</b></td></tr>
                <tr><td>🌱 Humidité sol</td><td><b>{hum_sol}%</b></td></tr>
                <tr><td>💨 Vent</td><td><b>{vent} km/h</b></td></tr>
                <tr><td>🕐 Mise à jour</td><td><b>{ts}</b></td></tr>
            </table>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"📡 {station_id} — {temp}°C",
            icon=folium.Icon(color=couleur, icon="leaf", prefix="fa"),
        ).add_to(m)

        # Cercle de couverture
        folium.Circle(
            location=[lat, lon],
            radius=5000,
            color="#00d97e",
            weight=1,
            fill=True,
            fill_color="#00d97e",
            fill_opacity=0.07,
        ).add_to(m)

        has_marker = True

    if not has_marker:
        st.info("ℹ️ Aucune station avec données GPS disponible pour le moment.")

    st_folium(m, width=None, height=480, returned_objects=[])
