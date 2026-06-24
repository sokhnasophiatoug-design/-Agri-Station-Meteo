"""
map_component.py — Carte interactive des stations (admin)
Utilise Folium + streamlit-folium pour afficher toutes les stations sur une carte.
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
from folium import MacroElement
from jinja2 import Template

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
        tiles=None,
        prefer_canvas=True,
        max_zoom=22,
    )

    # Couche 1 : Carte sombre (CartoDB Dark Matter) - par défaut
    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="Carte Sombre",
        attr="CartoDB",
        max_zoom=22,
        max_native_zoom=20,
    ).add_to(m)

    # Couche 2 : Carte standard (OpenStreetMap)
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Carte Standard",
        max_zoom=22,
        max_native_zoom=19,
    ).add_to(m)

    # Couche 3 : Vue Satellite Google
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Maps",
        name="Vue Satellite (Google - Recommandé)",
        max_zoom=22,
        max_native_zoom=20,
    ).add_to(m)

    # Couche 4 : Vue Satellite Esri
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Vue Satellite (Esri)",
        max_zoom=22,
        max_native_zoom=17,
    ).add_to(m)

    # Ajouter le sélecteur de couche dans le coin supérieur droit
    folium.LayerControl(position="topright").add_to(m)

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

    st_folium(m, height=480, use_container_width=True, returned_objects=[])


def afficher_carte_parcelle(lat: float, lon: float, station_id: str, mesures: dict):
    """
    Affiche une carte Folium zoomée sur la parcelle d'une station spécifique.
    - Vue satellite Google définie par défaut (première couche ajoutée).
    - Cercle vert dynamique : opacité diminue quand le zoom augmente (zone visible
      surtout aux zooms éloignés, quasi-invisible en vue très rapprochée).
    """
    if not lat or not lon:
        st.warning("Coordonnées GPS de la parcelle indisponibles.")
        return

    m = folium.Map(
        location=[lat, lon],
        zoom_start=18,
        tiles=None,
        prefer_canvas=True,
        max_zoom=22,
    )

    # ── Couche 1 (défaut) : Vue Satellite Google ──────────────────────────────
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Maps",
        name="🛰️ Vue Satellite (Google - Recommandé)",
        max_zoom=22,
        max_native_zoom=20,
    ).add_to(m)

    # ── Couche 2 : Vue Satellite Esri ─────────────────────────────────────────
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="🛰️ Vue Satellite (Esri)",
        max_zoom=22,
        max_native_zoom=17,
    ).add_to(m)

    # ── Couche 3 : Carte standard OpenStreetMap ───────────────────────────────
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="🗺️ Carte Standard",
        max_zoom=22,
        max_native_zoom=19,
    ).add_to(m)

    # ── Sélecteur de couche ───────────────────────────────────────────────────
    folium.LayerControl(position="topright").add_to(m)

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
        <h4 style="margin:0 0 8px; color:#1b5e20;">🌾 Parcelle {station_id}</h4>
        <table style="width:100%; font-size:13px;">
            <tr><td>🌡️ Température</td><td><b>{temp}°C</b></td></tr>
            <tr><td>🌱 Humidité sol</td><td><b>{hum_sol}%</b></td></tr>
            <tr><td>💨 Vent</td><td><b>{vent} km/h</b></td></tr>
            <tr><td>🕐 Relevé</td><td><b>{ts}</b></td></tr>
        </table>
    </div>
    """

    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"🌾 Votre Parcelle ({station_id})",
        icon=folium.Icon(color=couleur, icon="home", prefix="fa"),
    ).add_to(m)

    # ── Cercle dynamique : opacité inversement proportionnelle au zoom ────────
    # À zoom 10 → opacité ~0.55 / À zoom 14 → ~0.25 / À zoom 18+ → ~0.05
    circle = folium.Circle(
        location=[lat, lon],
        radius=100,
        color="#2E7D32",
        weight=2,
        fill=True,
        fill_color="#A5D6A7",
        fill_opacity=0.2,
    )
    circle.add_to(m)

    # Récupérer l'identifiant Leaflet du cercle pour le cibler en JS
    circle_var = circle.get_name()

    # Script JS injecté : écoute l'événement 'zoomend' et recalcule l'opacité
    zoom_script = MacroElement()
    zoom_script._template = Template("""
        {% macro script(this, kwargs) %}
        (function() {
            var circle = {{ circle_var }};

            function updateOpacity() {
                var zoom = {{ this._parent.get_name() }}.getZoom();
                // Opacité : diminue avec le zoom (0.55 à z=10, 0.05 à z=20)
                var fillOpacity = Math.max(0.02, 0.6 - (zoom - 10) * 0.055);
                var strokeOpacity = Math.max(0.1, 0.9 - (zoom - 10) * 0.08);
                circle.setStyle({
                    fillOpacity: fillOpacity,
                    opacity: strokeOpacity
                });
            }

            // Appliquer au chargement initial
            {{ this._parent.get_name() }}.on('zoomend', updateOpacity);
            updateOpacity();
        })();
        {% endmacro %}
    """.replace("{{ circle_var }}", circle_var))
    m.get_root().script.add_child(zoom_script)

    st_folium(m, height=350, use_container_width=True, returned_objects=[])
