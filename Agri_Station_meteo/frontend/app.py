"""
app.py — Point d'entrée principal de l'application Streamlit
Route vers le bon dashboard selon le rôle de l'utilisateur connecté.
"""

import streamlit as st
import os, sys

# Ajouter le dossier frontend au path Python
sys.path.insert(0, os.path.dirname(__file__))

from components.auth   import page_login
from pages.agriculteur import page_agriculteur
from pages.admin       import page_admin


# ── CSS global ───────────────────────────────────────────────────────────────

def _load_css():
    css_path = os.path.join(os.path.dirname(__file__), "css", "styles.css")
    if os.path.exists(css_path):
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _inject_hamburger():
    """Injecte le bouton hamburger custom (3 traits) pour mobile.
    Toggle la sidebar via JavaScript en ajoutant/retirant la classe CSS.
    """
    st.markdown("""
    <!-- Overlay sombre derrière la sidebar (mobile) -->
    <div id="sidebar-overlay"></div>

    <!-- Bouton hamburger custom ☰ -->
    <div id="hamburger-btn" title="Ouvrir le menu" onclick="toggleSidebar()">
        <span></span>
        <span></span>
        <span></span>
    </div>

    <script>
    function toggleSidebar() {
        const sidebar  = window.parent.document.querySelector('[data-testid="stSidebar"]');
        const overlay  = document.getElementById('sidebar-overlay');
        const btn      = document.getElementById('hamburger-btn');

        if (!sidebar) return;

        const isOpen = sidebar.classList.contains('sidebar-open');

        if (isOpen) {
            sidebar.classList.remove('sidebar-open');
            if (overlay)  overlay.classList.remove('active');
            if (btn) btn.setAttribute('aria-expanded', 'false');
            // Animer les 3 traits → hamburger
            animateHamburger(btn, false);
        } else {
            sidebar.classList.add('sidebar-open');
            if (overlay)  overlay.classList.add('active');
            if (btn) btn.setAttribute('aria-expanded', 'true');
            // Animer les 3 traits → X
            animateHamburger(btn, true);
        }
    }

    function animateHamburger(btn, open) {
        if (!btn) return;
        const spans = btn.querySelectorAll('span');
        if (spans.length < 3) return;
        if (open) {
            spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
            spans[1].style.opacity   = '0';
            spans[1].style.transform = 'translateX(-10px)';
            spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
        } else {
            spans[0].style.transform = '';
            spans[1].style.opacity   = '1';
            spans[1].style.transform = '';
            spans[2].style.transform = '';
        }
    }

    // Fermer sidebar en cliquant sur l'overlay
    (function() {
        const overlay = document.getElementById('sidebar-overlay');
        if (overlay) {
            overlay.addEventListener('click', function() {
                const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
                const btn     = document.getElementById('hamburger-btn');
                if (sidebar) sidebar.classList.remove('sidebar-open');
                overlay.classList.remove('active');
                animateHamburger(btn, false);
            });
        }
    })();
    </script>
    """, unsafe_allow_html=True)


# ── Application principale ───────────────────────────────────────────────────

def main():
    # Sidebar state dynamique
    sidebar_state = "expanded"
    
    st.set_page_config(
        page_title="Station Météo Agricole",
        page_icon="🌾",
        layout="wide",
        initial_sidebar_state=sidebar_state,
        menu_items={
            "Get Help":     None,
            "Report a bug": None,
            "About":        "Station Météo Agricole — Projet IoT USSEIN Sénégal",
        },
    )

    _load_css()
    _inject_hamburger()

    # ── Routing par rôle ──────────────────────────────────────────────────────
    if not st.session_state.get("authenticated", False):
        page_login()

    elif st.session_state.get("role") == "admin":
        page_admin()

    elif st.session_state.get("role") == "agriculteur":
        page_agriculteur()

    else:
        st.error("❌ Rôle non reconnu. Veuillez vous reconnecter.")
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


if __name__ == "__main__":
    main()