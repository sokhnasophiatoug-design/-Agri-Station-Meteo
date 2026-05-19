"""
html_render.py — Affichage HTML fiable sur Streamlit Cloud.

st.markdown(..., unsafe_allow_html=True) peut afficher le HTML en texte brut
(parseur Markdown). st.html() injecte le HTML directement (Streamlit ≥ 1.33).
"""

from __future__ import annotations

import html as html_module

import streamlit as st


def esc(value) -> str:
    """Échappe le texte avant injection dans du HTML."""
    return html_module.escape(str(value), quote=True)


def render_html(fragment: str) -> None:
    """Affiche un fragment HTML sans l'échapper."""
    if hasattr(st, "html"):
        st.html(fragment)
    else:
        st.markdown(fragment, unsafe_allow_html=True)
