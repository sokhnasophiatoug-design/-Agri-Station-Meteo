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
    """Injecte le bouton hamburger dans le document parent via
    st.components.v1.html() — la seule méthode qui exécute réellement le JS
    dans Streamlit Cloud.
    """
    import streamlit.components.v1 as components

    components.html("""
    <script>
    (function() {
        /* ── Éviter les doublons si Streamlit re-render ── */
        var parentDoc = window.parent.document;
        if (parentDoc.getElementById('custom-hamburger-btn')) return;

        var isMobile = window.parent.innerWidth <= 768;

        /* ══════════ CRÉER LE BOUTON HAMBURGER ══════════ */
        var btn = parentDoc.createElement('div');
        btn.id = 'custom-hamburger-btn';
        btn.title = 'Menu';
        btn.innerHTML = '<span></span><span></span><span></span>';
        btn.style.cssText = [
            'position:fixed',
            'top:12px', 'left:12px',
            'z-index:99999',
            'width:46px', 'height:46px',
            'background:#0A2E0C',
            'border:1px solid rgba(255,255,255,0.25)',
            'border-radius:12px',
            'cursor:pointer',
            'display:' + (isMobile ? 'flex' : 'none'),
            'flex-direction:column',
            'align-items:center',
            'justify-content:center',
            'gap:5px',
            'box-shadow:0 4px 18px rgba(0,0,0,0.55)',
            'transition:background 0.25s ease'
        ].join(';');

        var spans = btn.querySelectorAll('span');
        for (var i = 0; i < spans.length; i++) {
            spans[i].style.cssText = 'display:block;width:20px;height:2.5px;background:white;border-radius:2px;transition:all 0.3s ease;';
        }

        parentDoc.body.appendChild(btn);

        /* ══════════ CRÉER L'OVERLAY SOMBRE ══════════ */
        var overlay = parentDoc.createElement('div');
        overlay.id = 'custom-sidebar-overlay';
        overlay.style.cssText = [
            'display:none',
            'position:fixed', 'top:0', 'left:0',
            'width:100vw', 'height:100vh',
            'background:rgba(0,0,0,0.5)',
            'z-index:9990',
            'opacity:0',
            'transition:opacity 0.3s ease'
        ].join(';');
        parentDoc.body.appendChild(overlay);

        /* ══════════ LOGIQUE TOGGLE ══════════ */
        var _open = false;

        function getSidebar() {
            return parentDoc.querySelector('[data-testid="stSidebar"]');
        }

        function setSidebar(open) {
            var sidebar = getSidebar();
            if (!sidebar) return;
            _open = open;

            if (open) {
                sidebar.style.setProperty('transform',  'translateX(0)',    'important');
                sidebar.style.setProperty('visibility', 'visible',          'important');
                sidebar.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                overlay.style.display = 'block';
                setTimeout(function(){ overlay.style.opacity = '1'; }, 20);
            } else {
                sidebar.style.setProperty('transform',  'translateX(-100%)', 'important');
                sidebar.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                overlay.style.opacity = '0';
                setTimeout(function(){ overlay.style.display = 'none'; }, 300);
            }

            /* Animation ☰ → ✕ */
            var s = btn.querySelectorAll('span');
            if (open) {
                s[0].style.transform = 'rotate(45deg) translate(5px,6px)';
                s[1].style.opacity   = '0';
                s[2].style.transform = 'rotate(-45deg) translate(5px,-6px)';
            } else {
                s[0].style.transform = '';
                s[1].style.opacity   = '1';
                s[2].style.transform = '';
            }
        }

        /* Clic sur le bouton */
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            setSidebar(!_open);
        });

        /* Clic sur l'overlay → fermer */
        overlay.addEventListener('click', function() {
            setSidebar(false);
        });

        /* ══════════ INIT MOBILE ══════════ */
        if (isMobile) {
            var sidebar = getSidebar();
            if (sidebar) {
                sidebar.style.setProperty('transform',  'translateX(-100%)', 'important');
                sidebar.style.setProperty('visibility', 'visible',           'important');
                sidebar.style.setProperty('transition', 'none',              'important');
                setTimeout(function(){
                    sidebar.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                }, 100);
            }
        }

        /* Cacher le bouton natif Streamlit */
        var nativeBtn = parentDoc.querySelector('[data-testid="collapsedControl"]');
        if (nativeBtn) nativeBtn.style.setProperty('display', 'none', 'important');

        /* ══════════ RESIZE ══════════ */
        window.parent.addEventListener('resize', function() {
            var mobile = window.parent.innerWidth <= 768;
            btn.style.display = mobile ? 'flex' : 'none';
            if (!mobile) {
                var sidebar = getSidebar();
                if (sidebar) {
                    sidebar.style.removeProperty('transform');
                    sidebar.style.removeProperty('transition');
                }
                overlay.style.display = 'none';
                _open = false;
                var s = btn.querySelectorAll('span');
                s[0].style.transform = '';
                s[1].style.opacity   = '1';
                s[2].style.transform = '';
            }
        });
    })();
    </script>
    """, height=0)


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