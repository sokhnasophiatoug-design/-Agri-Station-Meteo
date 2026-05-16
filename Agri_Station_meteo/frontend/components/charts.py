"""
charts.py — Composants graphiques Plotly pour Streamlit
Graphiques d'historique, jauges et prévisions météo.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import List

# Palette de couleurs du design system
COULEURS = {
    "primary":  "#00d97e",
    "info":     "#38bdf8",
    "warning":  "#fbbf24",
    "danger":   "#f87171",
    "muted":    "#94a3b8",
    "bg":       "rgba(0,0,0,0)",
    "grid":     "rgba(255,255,255,0.06)",
    "text":     "#e2e8f0",
}

CAPTEUR_CONFIG = {
    "temperature":  {"label": "Température (°C)",    "couleur": COULEURS["danger"],   "unite": "°C",  "min": 10,  "max": 50},
    "humidite_air": {"label": "Humidité air (%)",     "couleur": COULEURS["info"],     "unite": "%",   "min": 0,   "max": 100},
    "humidite_sol": {"label": "Humidité sol (%)",     "couleur": COULEURS["primary"],  "unite": "%",   "min": 0,   "max": 100},
    "vitesse_vent": {"label": "Vitesse vent (km/h)",  "couleur": COULEURS["warning"],  "unite": "km/h","min": 0,   "max": 60},
}


def _hex_to_rgba(hex_color: str, alpha: float = 0.10) -> str:
    """Convertit un hex (#rrggbb) en rgba() valide pour Plotly."""
    hex_color = hex_color.strip("#")
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    # Si déjà rgba/rgb, on le retourne tel quel
    return hex_color

LAYOUT_BASE = dict(
    paper_bgcolor=COULEURS["bg"],
    plot_bgcolor=COULEURS["bg"],
    font=dict(color=COULEURS["text"], family="Inter, sans-serif"),
    margin=dict(l=10, r=10, t=40, b=10),
    xaxis=dict(gridcolor=COULEURS["grid"], showgrid=True),
    yaxis=dict(gridcolor=COULEURS["grid"], showgrid=True),
)


def graphique_historique(historique: List[dict], capteur: str) -> go.Figure:
    """
    Graphique linéaire de l'évolution d'un capteur dans le temps.
    historique : liste de dicts avec 'timestamp' et les valeurs capteurs.
    """
    if not historique:
        fig = go.Figure()
        fig.add_annotation(text="Aucune donnée disponible", showarrow=False,
                           font=dict(color=COULEURS["muted"]))
        fig.update_layout(**LAYOUT_BASE, title="Historique")
        return fig

    cfg = CAPTEUR_CONFIG.get(capteur, {"label": capteur, "couleur": COULEURS["primary"], "unite": ""})
    df  = pd.DataFrame(historique)
    df  = df.dropna(subset=[capteur])

    # Parser timestamps flexibles : format FR "25/12/2024 à 14:30" ou ISO
    import datetime as dt
    def _parse_ts(ts):
        if not ts:
            return None
        ts = str(ts).replace(" à ", " ")
        for fmt in ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d %H:%M:%S"]:
            try: return dt.datetime.strptime(ts, fmt)
            except: continue
        try: return pd.to_datetime(ts)
        except: return None

    df["timestamp"] = df["timestamp"].apply(_parse_ts)
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df[capteur],
        mode="lines+markers",
        name=cfg["label"],
        line=dict(color=cfg["couleur"], width=2.5),
        marker=dict(size=5, color=cfg["couleur"]),
        fill="tozeroy",
        fillcolor=_hex_to_rgba(cfg["couleur"], 0.10),
        hovertemplate=f"<b>%{{x|%d/%m %H:%M}}</b><br>{cfg['label']}: %{{y:.1f}} {cfg['unite']}<extra></extra>",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text=f"📈 Évolution — {cfg['label']}", font=dict(size=14)),
        xaxis_title="",
        yaxis_title=cfg["unite"],
        showlegend=False,
        height=280,
    )
    return fig


def graphique_jauge(valeur: float, capteur: str, seuil_min: float = None, seuil_max: float = None) -> go.Figure:
    """Jauge circulaire pour la valeur actuelle d'un capteur."""
    cfg = CAPTEUR_CONFIG.get(capteur, {"label": capteur, "couleur": COULEURS["primary"], "unite": "", "min": 0, "max": 100})

    # Couleur selon les seuils
    couleur = cfg["couleur"]
    if seuil_max and valeur > seuil_max:
        couleur = COULEURS["danger"]
    elif seuil_min and valeur < seuil_min:
        couleur = COULEURS["warning"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=valeur,
        number=dict(suffix=cfg["unite"], font=dict(size=22, color=couleur)),
        gauge=dict(
            axis=dict(range=[cfg["min"], cfg["max"]], tickfont=dict(color=COULEURS["muted"], size=10)),
            bar=dict(color=couleur, thickness=0.25),
            bgcolor=COULEURS["grid"],
            borderwidth=0,
            steps=[dict(range=[cfg["min"], cfg["max"]], color="rgba(255,255,255,0.03)")],
            threshold=dict(
                line=dict(color=COULEURS["danger"], width=3),
                thickness=0.8,
                value=seuil_max or cfg["max"] * 0.85,
            ) if seuil_max else dict(),
        ),
        title=dict(text=cfg["label"], font=dict(color=COULEURS["muted"], size=12)),
    ))
    fig.update_layout(
        paper_bgcolor=COULEURS["bg"],
        font=dict(family="Inter, sans-serif"),
        margin=dict(l=15, r=15, t=50, b=15),
        height=200,
    )
    return fig


def graphique_tous_capteurs(historique: List[dict]) -> go.Figure:
    """Graphique multi-lignes de tous les capteurs (normalisé 0-100%)."""
    if not historique:
        return go.Figure()

    df = pd.DataFrame(historique)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    fig = go.Figure()
    for capteur, cfg in CAPTEUR_CONFIG.items():
        if capteur not in df.columns:
            continue
        col = df[capteur].dropna()
        norm = (col - cfg["min"]) / (cfg["max"] - cfg["min"]) * 100
        fig.add_trace(go.Scatter(
            x=df.loc[col.index, "timestamp"],
            y=norm,
            name=cfg["label"],
            line=dict(color=cfg["couleur"], width=2),
            mode="lines",
            hovertemplate=f"{cfg['label']}: %{{customdata:.1f}} {cfg['unite']}<extra></extra>",
            customdata=col,
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text="📊 Vue globale (normalisée 0–100%)", font=dict(size=14)),
        xaxis_title="",
        yaxis_title="Valeur normalisée (%)",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
            font=dict(size=11),
        ),
        height=320,
    )
    return fig
