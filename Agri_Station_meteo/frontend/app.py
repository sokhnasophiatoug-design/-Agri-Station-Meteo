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
    """Injecte le bouton hamburger + CSS responsive mobile dans le document
    parent via st.components.v1.html() — seule méthode fiable sur Streamlit Cloud.
    """
    import streamlit.components.v1 as components

    components.html("""
    <script>
    (function() {
        var parentDoc = window.parent.document;
        if (parentDoc.getElementById('custom-hamburger-btn')) return;

        var isMobile = window.parent.innerWidth <= 768;

        /* ══════════ CSS RESPONSIVE — injecté dans <head> ══════════
           On injecte le CSS ici pour qu'il ait la priorité maximale
           et soit appliqué APRES les styles inline de Streamlit.
        ══════════════════════════════════════════════════════════ */
        if (!parentDoc.getElementById('custom-mobile-css')) {
            var mobileStyle = parentDoc.createElement('style');
            mobileStyle.id  = 'custom-mobile-css';
            mobileStyle.textContent =
                '@media(max-width:768px){' +
                '  .block-container{padding:0.4rem 0.4rem 1rem !important;padding-top:3.8rem !important;max-width:100vw !important;overflow-x:hidden !important;}' +
                /* Seuls les blocs de 4 colonnes (métriques) sont forcés en 2x2 */
                '  [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;gap:5px !important;}' +
                '  [data-testid="stMetric"]{min-height:55px !important;padding:6px 4px !important;}' +
                '  [data-testid="stMetricValue"]{font-size:0.82rem !important;line-height:1.1 !important;}' +
                '  [data-testid="stMetricLabel"]{font-size:0.44rem !important;letter-spacing:0 !important;}' +
                '  .previsions-grid{grid-template-columns:repeat(2,1fr) !important;gap:6px !important;}' +
                '  .meteo-card{min-height:unset !important;padding:8px 5px !important;}' +
                '  .meteo-card .temp{font-size:0.85rem !important;}' +
                '  .meteo-card .jour{font-size:0.56rem !important;}' +
                '  .meteo-card .desc{font-size:0.58rem !important;}' +
                '  h1{font-size:1.05rem !important;}' +
                '  .entete h1,.entete-admin h1{font-size:1.05rem !important;}' +
                '  .entete,.entete-admin,.page-header{padding:10px 12px !important;border-radius:14px !important;margin-bottom:10px !important;}' +
                '  .sous-titre{font-size:0.64rem !important;}' +
                '  .stTabs [data-baseweb="tab"]{font-size:0.62rem !important;padding:4px 5px !important;}' +
                '  .stButton>button{font-size:0.76rem !important;padding:8px !important;}' +
                '  .reco-card{padding:12px 14px !important;}' +
                '  .reco-titre{font-size:0.85rem !important;}' +
                '  .reco-desc{font-size:0.74rem !important;}' +
                '  .meteo-now-card{max-width:100% !important;padding:10px !important;}' +
                '  .meteo-now-temp{font-size:1.2rem !important;}' +
                '}';
            parentDoc.head.appendChild(mobileStyle);
        }

        /* ── fixColumns : détecte les blocs métriques par leur CONTENU (stMetric).
           - Blocs avec stMetric  → 48% chacun (2×2 grid sur mobile)
           - Tous les autres      → 100% chacun (empilés : section IA, jauges, etc.)
           Le JS est nécessaire car Streamlit injecte inline style="flex:3" etc.
           que même CSS !important ne neutralise pas toujours. ── */
        function fixColumns() {
            if (window.parent.innerWidth > 768) return;
            parentDoc.querySelectorAll('[data-testid="stHorizontalBlock"]').forEach(function(block) {
                block.style.setProperty('flex-wrap', 'wrap', 'important');
                block.style.setProperty('gap',       '5px',  'important');

                var isMetricBlock = !!block.querySelector('[data-testid="stMetric"]');
                var size = isMetricBlock ? 'calc(48% - 3px)' : '100%';

                block.querySelectorAll('[data-testid="stColumn"]').forEach(function(col) {
                    col.style.setProperty('flex',      '0 0 ' + size, 'important');
                    col.style.setProperty('max-width', size,           'important');
                    col.style.setProperty('min-width', '0',            'important');
                    col.style.setProperty('width',     size,           'important');
                    col.style.setProperty('box-sizing','border-box',   'important');
                });
            });
        }

        /* Appliquer au chargement et après chaque re-render Streamlit */
        fixColumns();
        setTimeout(fixColumns, 500);
        setTimeout(fixColumns, 1500);
        setTimeout(fixColumns, 3000);

        /* MutationObserver : se déclenche à chaque update du DOM Streamlit */
        new MutationObserver(function() { fixColumns(); })
            .observe(parentDoc.body, { childList: true, subtree: true });

        /* ══════════ BOUTON HAMBURGER ══════════ */
        var btn = parentDoc.createElement('div');
        btn.id = 'custom-hamburger-btn';
        btn.title = 'Menu';
        btn.innerHTML = '<span></span><span></span><span></span>';
        btn.style.cssText = [
            'position:fixed', 'top:12px', 'left:12px', 'z-index:99999',
            'width:46px', 'height:46px', 'background:#0A2E0C',
            'border:1px solid rgba(255,255,255,0.25)', 'border-radius:12px',
            'cursor:pointer', 'display:' + (isMobile ? 'flex' : 'none'),
            'flex-direction:column', 'align-items:center', 'justify-content:center',
            'gap:5px', 'box-shadow:0 4px 18px rgba(0,0,0,0.55)',
            'transition:background 0.25s ease'
        ].join(';');
        btn.querySelectorAll('span').forEach(function(s) {
            s.style.cssText = 'display:block;width:20px;height:2.5px;background:white;border-radius:2px;transition:all 0.3s ease;';
        });
        parentDoc.body.appendChild(btn);

        /* ══════════ OVERLAY ══════════ */
        var overlay = parentDoc.createElement('div');
        overlay.id = 'custom-sidebar-overlay';
        overlay.style.cssText = 'display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.5);z-index:9990;opacity:0;transition:opacity 0.3s ease;';
        parentDoc.body.appendChild(overlay);

        /* ══════════ SIDEBAR TOGGLE ══════════ */
        var _open = false;
        function getSidebar() { return parentDoc.querySelector('[data-testid="stSidebar"]'); }

        function setSidebar(open) {
            var sb = getSidebar();
            if (!sb) return;
            _open = open;
            if (open) {
                sb.style.setProperty('transform',  'translateX(0)',    'important');
                sb.style.setProperty('visibility', 'visible',          'important');
                sb.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                overlay.style.display = 'block';
                setTimeout(function(){ overlay.style.opacity = '1'; }, 20);
            } else {
                sb.style.setProperty('transform',  'translateX(-100%)', 'important');
                sb.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important');
                overlay.style.opacity = '0';
                setTimeout(function(){ overlay.style.display = 'none'; }, 300);
            }
            var s = btn.querySelectorAll('span');
            if (open) {
                s[0].style.transform = 'rotate(45deg) translate(5px,6px)';
                s[1].style.opacity   = '0';
                s[2].style.transform = 'rotate(-45deg) translate(5px,-6px)';
            } else {
                s[0].style.transform = s[2].style.transform = '';
                s[1].style.opacity   = '1';
            }
        }

        btn.addEventListener('click', function(e) { e.stopPropagation(); setSidebar(!_open); });
        overlay.addEventListener('click', function() { setSidebar(false); });

        if (isMobile) {
            var sb = getSidebar();
            if (sb) {
                sb.style.setProperty('transform',  'translateX(-100%)', 'important');
                sb.style.setProperty('visibility', 'visible',           'important');
                sb.style.setProperty('transition', 'none',              'important');
                setTimeout(function(){ sb.style.setProperty('transition', 'transform 0.3s cubic-bezier(0.25,0.46,0.45,0.94)', 'important'); }, 100);
            }
        }

        var nativeBtn = parentDoc.querySelector('[data-testid="collapsedControl"]');
        if (nativeBtn) nativeBtn.style.setProperty('display', 'none', 'important');

        window.parent.addEventListener('resize', function() {
            var mobile = window.parent.innerWidth <= 768;
            btn.style.display = mobile ? 'flex' : 'none';
            if (!mobile) {
                var sb = getSidebar();
                if (sb) { sb.style.removeProperty('transform'); sb.style.removeProperty('transition'); }
                overlay.style.display = 'none';
                _open = false;
                var s = btn.querySelectorAll('span');
                s[0].style.transform = s[2].style.transform = '';
                s[1].style.opacity = '1';
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

    # ── Routing par rôle ──────────────────────────────────────────────────────
    if not st.session_state.get("authenticated", False):
        # Page login : PAS de hamburger ni de CSS responsive dashboard
        page_login()

    elif st.session_state.get("role") == "admin":
        _inject_hamburger()
        page_admin()

    elif st.session_state.get("role") == "agriculteur":
        _inject_hamburger()
        page_agriculteur()

    else:
        st.error("❌ Rôle non reconnu. Veuillez vous reconnecter.")
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


if __name__ == "__main__":
    main()