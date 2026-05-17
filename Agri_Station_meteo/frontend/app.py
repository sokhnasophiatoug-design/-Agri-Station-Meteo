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
    """Injecte un script léger qui garantit que le bouton natif Streamlit
    (collapsedControl) est visible et cliquable sur mobile, sans interférer
    avec le mécanisme natif d'ouverture/fermeture de la sidebar.
    """
    st.markdown("""
    <script>
    (function() {
        /* Sur mobile, on s'assure que le bouton natif Streamlit est visible
           et que la sidebar n'est pas bloquée par des styles inline résiduels. */
        function fixMobileSidebar() {
            if (window.innerWidth > 768) return; /* Desktop : rien à faire */

            try {
                var doc = window.parent.document;

                /* 1. Forcer le bouton natif collapsedControl à être visible */
                var nativeBtn = doc.querySelector('[data-testid="collapsedControl"]');
                if (nativeBtn) {
                    nativeBtn.style.setProperty('display',    'flex',    'important');
                    nativeBtn.style.setProperty('visibility', 'visible', 'important');
                    nativeBtn.style.setProperty('opacity',    '1',       'important');
                    nativeBtn.style.setProperty('z-index',    '99999',   'important');
                }

                /* 2. Retirer tout style inline résiduel sur la sidebar
                      qui empêcherait Streamlit de gérer l'ouverture/fermeture */
                var sidebar = doc.querySelector('[data-testid="stSidebar"]');
                if (sidebar) {
                    sidebar.style.removeProperty('transform');
                    sidebar.style.removeProperty('transition');
                }
            } catch(e) { /* cross-origin : on ignore silencieusement */ }
        }

        /* Exécuter au chargement et après chaque rerun Streamlit */
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(fixMobileSidebar, 300);
            });
        } else {
            setTimeout(fixMobileSidebar, 300);
        }

        /* Observer les mutations pour ré-appliquer après les reruns */
        try {
            var observer = new MutationObserver(function() {
                setTimeout(fixMobileSidebar, 200);
            });
            observer.observe(window.parent.document.body, {
                childList: true, subtree: true
            });
        } catch(e) {}
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