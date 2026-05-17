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
    """Injecte un bouton hamburger custom visible sur mobile uniquement,
    avec overlay sombre et toggle JS fiable pour la sidebar Streamlit.
    """
    st.markdown("""
    <!-- ═══ Overlay sombre mobile ═══ -->
    <div id="sidebar-overlay" style="
        display:none;
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background:rgba(0,0,0,0.55);
        z-index:9990;
        transition:opacity 0.3s ease;
    "></div>

    <!-- ═══ Bouton Hamburger ☰ (mobile only) ═══ -->
    <div id="hamburger-btn" style="
        display:none;
        position:fixed;
        top:12px; left:12px;
        z-index:99999;
        width:44px; height:44px;
        background:#0A2E0C;
        border:1px solid rgba(255,255,255,0.25);
        border-radius:10px;
        cursor:pointer;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        gap:5px;
        box-shadow:0 4px 16px rgba(0,0,0,0.55);
        transition:background 0.25s ease;
    ">
        <span style="display:block;width:20px;height:2.5px;background:white;border-radius:2px;transition:all 0.3s ease;"></span>
        <span style="display:block;width:20px;height:2.5px;background:white;border-radius:2px;transition:all 0.3s ease;"></span>
        <span style="display:block;width:20px;height:2.5px;background:white;border-radius:2px;transition:all 0.3s ease;"></span>
    </div>

    <script>
    (function() {
        var _sidebarOpen = false;

        function isMobile() { return window.innerWidth <= 768; }

        function getSidebar() {
            try { return window.parent.document.querySelector('[data-testid="stSidebar"]'); }
            catch(e) { return null; }
        }

        function showHamburger() {
            var btn = document.getElementById('hamburger-btn');
            if (btn) btn.style.display = isMobile() ? 'flex' : 'none';
        }

        function setSidebar(open) {
            var sidebar = getSidebar();
            if (!sidebar) return;
            var overlay = document.getElementById('sidebar-overlay');
            var btn     = document.getElementById('hamburger-btn');
            _sidebarOpen = open;

            if (open) {
                sidebar.style.setProperty('transform',  'translateX(0)',    'important');
                sidebar.style.setProperty('visibility', 'visible',          'important');
                sidebar.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                if (overlay) { overlay.style.display = 'block'; setTimeout(function(){ overlay.style.opacity = '1'; }, 10); }
            } else {
                sidebar.style.setProperty('transform',  'translateX(-100%)', 'important');
                sidebar.style.setProperty('visibility', 'visible',           'important');
                sidebar.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                if (overlay) { overlay.style.opacity = '0'; setTimeout(function(){ overlay.style.display = 'none'; }, 300); }
            }

            /* Animer les 3 barres du hamburger en ✕ */
            if (btn) {
                var spans = btn.querySelectorAll('span');
                if (spans.length >= 3) {
                    if (open) {
                        spans[0].style.transform = 'rotate(45deg) translate(5px,5px)';
                        spans[1].style.opacity   = '0';
                        spans[2].style.transform = 'rotate(-45deg) translate(5px,-5px)';
                    } else {
                        spans[0].style.transform = '';
                        spans[1].style.opacity   = '1';
                        spans[2].style.transform = '';
                    }
                }
            }
        }

        function toggleSidebar() { setSidebar(!_sidebarOpen); }

        /* ── Initialisation ── */
        function init() {
            showHamburger();

            var btn = document.getElementById('hamburger-btn');
            if (btn && !btn._bound) {
                btn._bound = true;
                btn.addEventListener('click', toggleSidebar);
            }

            var overlay = document.getElementById('sidebar-overlay');
            if (overlay && !overlay._bound) {
                overlay._bound = true;
                overlay.addEventListener('click', function() { if (_sidebarOpen) setSidebar(false); });
            }

            /* Cacher la sidebar sur mobile au chargement */
            if (isMobile()) {
                var sidebar = getSidebar();
                if (sidebar) {
                    sidebar.style.setProperty('transform',  'translateX(-100%)', 'important');
                    sidebar.style.setProperty('visibility', 'visible',           'important');
                    sidebar.style.setProperty('transition', 'none',              'important');
                    setTimeout(function(){
                        sidebar.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                    }, 50);
                }
                _sidebarOpen = false;
            }

            /* Cacher le bouton natif collapsedControl — on utilise le nôtre */
            try {
                var native = window.parent.document.querySelector('[data-testid="collapsedControl"]');
                if (native) native.style.setProperty('display', 'none', 'important');
            } catch(e){}
        }

        /* Lancer init */
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function(){ setTimeout(init, 300); });
        } else {
            setTimeout(init, 300);
        }

        /* Ré-appliquer après les reruns Streamlit */
        try {
            var observer = new MutationObserver(function(){ setTimeout(function(){ showHamburger(); }, 200); });
            observer.observe(window.parent.document.body, { childList:true, subtree:true });
        } catch(e){}

        /* Adaptation au resize */
        window.addEventListener('resize', function() {
            showHamburger();
            if (!isMobile()) {
                var sidebar = getSidebar();
                if (sidebar) {
                    sidebar.style.removeProperty('transform');
                    sidebar.style.removeProperty('transition');
                    sidebar.style.removeProperty('visibility');
                }
                var overlay = document.getElementById('sidebar-overlay');
                if (overlay) overlay.style.display = 'none';
                _sidebarOpen = false;
            }
        });

        window.toggleSidebar = toggleSidebar;
    })();
    </script>
    """, unsafe_allow_html=True)


# ── Application principale ───────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Station Météo Agricole",
        page_icon="🌾",
        layout="wide",
        initial_sidebar_state="collapsed",
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