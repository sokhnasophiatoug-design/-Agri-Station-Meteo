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
    Utilise style.setProperty avec 'important' pour contourner les CSS !important.
    """
    st.markdown("""
    <!-- Overlay sombre (mobile) -->
    <div id="sidebar-overlay"></div>

    <!-- Bouton hamburger ☰ -->
    <div id="hamburger-btn" title="Menu">
        <span></span>
        <span></span>
        <span></span>
    </div>

    <script>
    (function() {
        var _open = false;

        function getSidebar() {
            try { return window.parent.document.querySelector('[data-testid="stSidebar"]'); }
            catch(e) { return null; }
        }

        function setTransform(sidebar, value) {
            /* style.setProperty avec 'important' passe au-dessus de tout CSS !important */
            sidebar.style.setProperty('transform',  value,          'important');
            sidebar.style.setProperty('transition', 'transform 0.32s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
            sidebar.style.setProperty('visibility', 'visible',      'important');
        }

        function animateBtn(open) {
            var btn   = document.getElementById('hamburger-btn');
            if (!btn) return;
            var spans = btn.querySelectorAll('span');
            if (spans.length < 3) return;
            if (open) {
                spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                spans[1].style.opacity   = '0';
                spans[1].style.transform = 'translateX(-12px)';
                spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
            } else {
                spans[0].style.transform = '';
                spans[1].style.opacity   = '1';
                spans[1].style.transform = '';
                spans[2].style.transform = '';
            }
        }

        function toggleSidebar() {
            var sidebar = getSidebar();
            if (!sidebar) return;
            var overlay = document.getElementById('sidebar-overlay');

            _open = !_open;

            if (_open) {
                setTransform(sidebar, 'translateX(0)');
                if (overlay) overlay.classList.add('active');
            } else {
                setTransform(sidebar, 'translateX(-100%)');
                if (overlay) overlay.classList.remove('active');
            }
            animateBtn(_open);
        }

        /* Initialiser : cacher la sidebar dès le chargement sur mobile */
        function initSidebar() {
            var sidebar = getSidebar();
            if (!sidebar) return;
            /* Masquer immédiatement sans animation */
            sidebar.style.setProperty('transform',  'translateX(-100%)', 'important');
            sidebar.style.setProperty('visibility', 'visible',           'important');
            sidebar.style.setProperty('transition', 'none',              'important');
            /* Remettre la transition après un tick */
            setTimeout(function() {
                if (sidebar) sidebar.style.setProperty('transition', 'transform 0.32s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
            }, 50);
        }

        /* Attacher le clic au bouton hamburger */
        document.addEventListener('DOMContentLoaded', function() {
            var btn = document.getElementById('hamburger-btn');
            if (btn) btn.addEventListener('click', toggleSidebar);

            var overlay = document.getElementById('sidebar-overlay');
            if (overlay) {
                overlay.addEventListener('click', function() {
                    if (_open) toggleSidebar();
                });
            }

            /* Init uniquement sur mobile */
            if (window.innerWidth <= 768) initSidebar();
        });

        /* Fallback si DOMContentLoaded déjà passé */
        if (document.readyState !== 'loading') {
            var btn = document.getElementById('hamburger-btn');
            if (btn && !btn._hasListener) {
                btn._hasListener = true;
                btn.addEventListener('click', toggleSidebar);
            }
            var overlay = document.getElementById('sidebar-overlay');
            if (overlay && !overlay._hasListener) {
                overlay._hasListener = true;
                overlay.addEventListener('click', function() {
                    if (_open) toggleSidebar();
                });
            }
            if (window.innerWidth <= 768) {
                setTimeout(initSidebar, 200);
            }
        }

        /* Exposer globalement si onclick HTML est utilisé */
        window.toggleSidebar = toggleSidebar;
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