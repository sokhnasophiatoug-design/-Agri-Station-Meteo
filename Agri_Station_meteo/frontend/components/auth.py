"""
auth.py — Page de connexion + inscription (Streamlit)
Style : Verts très foncés (Station_meteo)
"""

import streamlit as st
import requests

FIREBASE_WEB_API_KEY = "AIzaSyBTgmYJn7WnhcXpKw0Yv8txfXTMKEYqmgo"
FIREBASE_SIGNIN_URL  = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    f"?key={FIREBASE_WEB_API_KEY}"
)
FIREBASE_SIGNUP_URL  = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
    f"?key={FIREBASE_WEB_API_KEY}"
)
BACKEND_URL = "http://localhost:8000"

REGIONS = [
    "Dakar", "Thiès", "Kaolack", "Saint-Louis", "Fatick",
    "Diourbel", "Ziguinchor", "Tambacounda", "Louga", "Matam",
    "Kaffrine", "Kédougou", "Kolda", "Sédhiou",
]

STATIONS_DISPO = {
    "ST001": "Station Thiès Nord",
    "ST002": "Station Kaolack Centre",
    "ST003": "Station Saint-Louis Sud",
    "ST004": "Station Fatick Est",
    "ST005": "Station Louga Ouest",
}


def _css_login():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Sora:wght@600;700;800&display=swap');

    html, body, [data-testid="stApp"] {
        background-image     : linear-gradient(rgba(10,46,12,0.68), rgba(10,46,12,0.68)),
                               url('https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1920&q=80') !important;
        background-size      : cover !important;
        background-position  : center !important;
        background-repeat    : no-repeat !important;
        background-attachment: fixed !important;
        font-family          : 'Nunito', sans-serif;
        min-height           : 100vh;
    }
    [data-testid="stMain"] { background: transparent; }

    /* ── Champs texte ── */
    .stTextInput > div > div > input {
        background    : rgba(255,255,255,0.95) !important;
        border        : 1px solid rgba(0,0,0,0.18) !important;
        border-radius : 10px !important;
        color         : #0D1F0E !important;
        font-family   : 'Nunito', sans-serif !important;
        font-weight   : 600 !important;
        padding       : 12px 14px !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: rgba(0,0,0,0.38) !important;
    }
    .stTextInput > div > div > input:focus {
        border-color : rgba(67,160,71,0.75) !important;
        box-shadow   : 0 0 0 3px rgba(67,160,71,0.18) !important;
    }

    /* ── Labels des champs ── */
    .stTextInput label,
    .stSelectbox label {
        color      : rgba(255,255,255,0.90) !important;
        font-size  : 0.82rem !important;
        font-weight: 700 !important;
    }

    /* ── Selectbox : conteneur affiché ── */
    .stSelectbox > div > div,
    .stSelectbox [data-baseweb="select"] > div,
    .stSelectbox [data-baseweb="select"] > div > div {
        background    : rgba(255,255,255,0.95) !important;
        border        : 1px solid rgba(0,0,0,0.18) !important;
        border-radius : 10px !important;
        color         : #0D1F0E !important;
    }

    /* ── Texte sélectionné visible dans la box ── */
    .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] div,
    .stSelectbox [data-baseweb="select"] input,
    .stSelectbox > div > div > div,
    .stSelectbox span {
        color: #0D1F0E !important;
    }

    /* ── Liste déroulante ouverte (popover / menu) ── */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="select-dropdown"] {
        background : #ffffff !important;
    }

    /* ── Options dans la liste ── */
    [role="option"],
    [role="listbox"] li,
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] [role="option"],
    ul[data-baseweb="menu"] > li {
        color      : #0D1F0E !important;
        background : #ffffff !important;
    }

    /* ── Option survolée / sélectionnée ── */
    [role="option"]:hover,
    [data-baseweb="menu"] [role="option"]:hover {
        background : #e8f5e9 !important;
        color      : #1B5E20 !important;
    }


    /* ── Boutons (tabs + submit) ── */
    .stButton > button,
    [data-testid="stFormSubmitButton"] > button {
        width         : 100%;
        background    : linear-gradient(135deg, #1B5E20, #43A047) !important;
        color         : white !important;
        border        : none !important;
        border-radius : 12px !important;
        padding       : 13px !important;
        font-family   : 'Sora', sans-serif !important;
        font-weight   : 700 !important;
        font-size     : 0.92rem !important;
        box-shadow    : 0 4px 15px rgba(67,160,71,0.32) !important;
        transition    : all 0.25s !important;
    }
    .stButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        transform  : translateY(-2px) !important;
        box-shadow : 0 6px 22px rgba(67,160,71,0.50) !important;
        color      : white !important;
    }

    /* ── Info-box ── */
    .info-box {
        background    : rgba(255,255,255,0.12);
        border        : 1px solid rgba(255,255,255,0.28);
        border-radius : 10px;
        padding       : 11px 14px;
        margin-bottom : 14px;
        color         : rgba(255,255,255,0.92);
        font-size     : 0.82rem;
        line-height   : 1.55;
        font-weight   : 600;
    }

    /* ── Titres h3 dans formulaire ── */
    .block-container h3 {
        color: white !important;
    }

    .stAlert { border-radius: 10px !important; font-family: 'Nunito', sans-serif !important; }
    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)


def _login_firebase(email, password):
    try:
        resp = requests.post(FIREBASE_SIGNIN_URL,
                             json={"email": email, "password": password, "returnSecureToken": True}, timeout=30)
        data = resp.json()
        if "idToken" in data:
            return {"ok": True, "idToken": data["idToken"]}
        return {"ok": False, "erreur": _trad(data.get("error", {}).get("message", "Erreur"))}
    except requests.Timeout:
        return {"ok": False, "erreur": "Délai dépassé — vérifiez votre connexion"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _signup_firebase(email, password):
    try:
        resp = requests.post(FIREBASE_SIGNUP_URL,
                             json={"email": email, "password": password, "returnSecureToken": True}, timeout=30)
        data = resp.json()
        if "idToken" in data:
            return {"ok": True, "idToken": data["idToken"], "uid": data["localId"]}
        return {"ok": False, "erreur": _trad_signup(data.get("error", {}).get("message", "Erreur"))}
    except requests.Timeout:
        return {"ok": False, "erreur": "Délai dépassé — vérifiez votre connexion"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _verify_role(id_token):
    try:
        resp = requests.post(f"{BACKEND_URL}/auth/verify", json={"id_token": id_token}, timeout=10)
        if resp.status_code == 200:
            return {"ok": True, **resp.json()}
        return {"ok": False, "erreur": resp.json().get("detail", "Accès refusé")}
    except requests.ConnectionError:
        return {"ok": False, "erreur": "Backend inaccessible (localhost:8000). Vérifiez qu'il est démarré."}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _inscrire_agriculteur(payload):
    try:
        resp = requests.post(f"{BACKEND_URL}/auth/register", json=payload, timeout=10)
        if resp.status_code == 200:
            return {"ok": True, **resp.json()}
        return {"ok": False, "erreur": resp.json().get("detail", "Erreur d'inscription")}
    except requests.ConnectionError:
        return {"ok": False, "erreur": "Backend inaccessible (localhost:8000)."}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _trad(msg):
    t = {"EMAIL_NOT_FOUND": "Email introuvable", "INVALID_PASSWORD": "Mot de passe incorrect",
         "USER_DISABLED": "Compte désactivé", "INVALID_EMAIL": "Email invalide",
         "TOO_MANY_ATTEMPTS_TRY_LATER": "Trop de tentatives", "INVALID_LOGIN_CREDENTIALS": "Email ou mot de passe incorrect"}
    for k, v in t.items():
        if k in msg: return v
    return msg


def _trad_signup(msg):
    t = {"EMAIL_EXISTS": "Email déjà utilisé", "INVALID_EMAIL": "Email invalide",
         "WEAK_PASSWORD": "Mot de passe trop faible (min. 6 caractères)",
         "TOO_MANY_ATTEMPTS_TRY_LATER": "Trop de tentatives"}
    for k, v in t.items():
        if k in msg: return v
    return msg


def _form_connexion():
    st.markdown('<div class="info-box">🌿 Connectez-vous pour accéder aux données météo de votre parcelle.</div>',
                unsafe_allow_html=True)
    with st.form("form_login", clear_on_submit=False):
        email    = st.text_input(" Adresse email",  placeholder="votre@email.com")
        password = st.text_input(" Mot de passe",   type="password", placeholder="••••••••")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button(" Connecter", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error(" Veuillez remplir tous les champs."); return
        with st.spinner("Connexion en cours..."):
            auth = _login_firebase(email, password)
            if not auth["ok"]: st.error(f" {auth['erreur']}"); return
            role = _verify_role(auth["idToken"])
            if not role["ok"]: st.error(f" {role['erreur']}"); return
        st.session_state.authenticated = True
        st.session_state.id_token      = auth["idToken"]
        st.session_state.role          = role.get("role")
        st.session_state.uid           = role.get("uid")
        st.session_state.nom           = role.get("nom", "Utilisateur")
        st.session_state.email         = role.get("email", email)
        st.session_state.station_id    = role.get("station_id", "")
        st.session_state.station_nom   = role.get("station_nom", "")
        st.session_state.region        = role.get("region", "")
        st.success(f"✅ Bienvenue, {st.session_state.nom} !")
        st.rerun()


def _form_inscription():
    st.markdown('<div class="info-box"> Créez votre compte. Un administrateur validera votre accès à la station.</div>',
                unsafe_allow_html=True)
    with st.form("form_inscription", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            prenom = st.text_input(" Prénom",      placeholder="Ex : Moussa")
            email  = st.text_input(" Email",        placeholder="email@exemple.com")
            region = st.selectbox(" Région",        REGIONS)
        with col2:
            nom  = st.text_input(" Nom",            placeholder="Ex : Diallo")
            mdp  = st.text_input("Mot de passe",   type="password", placeholder="Min. 6 caractères")
            tel  = st.text_input(" Téléphone",      placeholder="+221 77 XXX XX XX")

        station_id = st.selectbox(" Station",
            options=list(STATIONS_DISPO.keys()),
            format_func=lambda x: f" {STATIONS_DISPO[x]} ({x})")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button(" Créer mon compte", use_container_width=True)

    if submitted:
        if not all([prenom, nom, email, mdp]):
            st.error(" Veuillez remplir tous les champs obligatoires."); return
        if len(mdp) < 6:
            st.error(" Mot de passe trop court (min. 6 caractères)."); return
        if "@" not in email or "." not in email:
            st.error(" Email invalide."); return

        with st.spinner("Création du compte..."):
            signup = _signup_firebase(email, mdp)
            if not signup["ok"]: st.error(f" {signup['erreur']}"); return
            profil = _inscrire_agriculteur({
                "uid": signup["uid"], "id_token": signup["idToken"],
                "nom": f"{prenom} {nom}", "email": email, "telephone": tel,
                "region": region, "station_id": station_id,
                "station_nom": STATIONS_DISPO[station_id],
                "firebase_path": f"stations/{station_id}",
            })
            if not profil["ok"]: st.error(f"{profil['erreur']}"); return

        st.success("✅ Compte créé ! Vous pouvez maintenant vous connecter.")
        st.info("ℹ️ Un administrateur activera votre accès sous peu.")
        st.session_state["auth_tab"] = "connexion"
        st.rerun()


def page_login():
    _css_login()
    if "auth_tab" not in st.session_state:
        st.session_state["auth_tab"] = "connexion"

    _, col_c, _ = st.columns([1, 1.6, 1])
    with col_c:
        # Logo
        st.markdown("""
        <div style="text-align:center; padding:24px 0 16px;">
            <div style="font-size:3.8rem; filter:drop-shadow(0 0 18px rgba(67,160,71,0.6));">🌾</div>
            <div style="font-family:'Sora',sans-serif; font-size:1.65rem; font-weight:800;
                        color:#ffffff; letter-spacing:-0.5px; margin-top:6px;">
                Station Météo Agricole
            </div>
            <div style="color:rgba(255,255,255,0.50); font-size:0.83rem; margin-top:5px; font-weight:600;">
                Plateforme IoT — Surveillance climatique pour agriculteurs
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Switcher onglets
        tab_actuel = st.session_state["auth_tab"]
        col_conn, col_inscr = st.columns(2)
        with col_conn:
            if st.button("Se Connecter", key="btn_tab_conn", use_container_width=True):
                st.session_state["auth_tab"] = "connexion"; st.rerun()
        with col_inscr:
            if st.button("Créer un Compte", key="btn_tab_inscr", use_container_width=True):
                st.session_state["auth_tab"] = "inscription"; st.rerun()

       

        # Carte formulaire
        #st.markdown('<div class="login-card">', unsafe_allow_html=True)
        if tab_actuel == "connexion":
            st.markdown("### Connexion à votre espace")
            _form_connexion()
        else:
            st.markdown("### 🌱 Créer un compte agriculteur")
            _form_inscription()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align:center; color:rgba(255,255,255,0.28); font-size:0.72rem; margin-top:18px;">
            Projet IoT — Agriculture Intelligente au Sénégal<br>
            Université du Sine Saloum El Hâdj Ibrahima Niass (USSEIN)
        </div>
        """, unsafe_allow_html=True)


def deconnexion():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
