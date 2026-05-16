# Station Météo Agricole — Plan d'Implémentation Complet

> **Architecture validée** : `Frontend (Streamlit + CSS) ←→ Backend (Python FastAPI) ←→ Firebase + OpenWeather`

## Contexte du Projet

Plateforme IoT complète de surveillance météorologique pour agriculteurs sénégalais.  
Des ESP32 physiques collectent les données (température, humidité air/sol, vitesse du vent) et les envoient vers Firebase Realtime Database. Une application web (Frontend + Backend séparés) offre deux interfaces : une pour les agriculteurs, une pour l'administrateur.

---

## Architecture Retenue

```
Agri_Station_meteo/
│
├── backend/                    # Serveur Python (FastAPI)
│   ├── main.py                 # Point d'entrée — routes API REST
│   ├── firebase_service.py     # Connexion Firebase Admin SDK
│   ├── auth_service.py         # Vérification rôle (admin/agriculteur)
│   ├── weather_service.py      # API OpenWeather (prévisions 5j)
│   ├── ia_service.py           # Arbre de décision scikit-learn
│   ├── tts_service.py          # Lecture vocale gTTS → MP3
│   ├── requirements.txt
│   └── serviceAccountKey.json  # (vous l'avez déjà)
│
├── frontend/                   # Application Streamlit
│   ├── app.py                  # Point d'entrée — router login/rôle
│   ├── pages/
│   │   ├── agriculteur.py      # Dashboard agriculteur
│   │   └── admin.py            # Dashboard administrateur
│   ├── css/
│   │   └── styles.css          # CSS custom injecté dans Streamlit
│   ├── components/
│   │   ├── auth.py             # Login/logout Firebase Auth REST
│   │   ├── charts.py           # Graphiques Plotly/Altair
│   │   ├── weather_card.py     # Carte prévisions météo
│   │   └── map_component.py    # Carte Leaflet (admin)
│   └── requirements.txt
│
└── contexte.txt                # (déjà présent)
```

---

## Stack Technique

| Composant | Technologie | Raison |
|---|---|---|
| **Backend** | Python + FastAPI | Léger, rapide, parfait pour APIs REST |
| **Firebase** | Admin SDK Python | Accès sécurisé sans exposer les clés |
| **Frontend** | Streamlit + CSS custom | Pur Python, rapide à développer, personnalisable |
| **Auth** | Firebase Auth REST | Login email/mdp, redirection par rôle |
| **Graphiques** | Plotly (via st.plotly_chart) | Interactifs, modernes |
| **Météo** | OpenWeather API | Prévisions 5 jours |
| **IA** | scikit-learn DecisionTree | Recommandations arroser/attendre/pulvériser |
| **Voix** | gTTS → MP3 → st.audio | Lecture vocale en français dans le navigateur |
| **Carte** | Folium (via streamlit-folium) | Carte interactive OpenStreetMap gratuite |

---

## Clés & Identifiants (depuis contexte.txt)

| Clé | Valeur |
|---|---|
| `OPENWEATHER_API_KEY` | `652d3abf887689071d07dcec5e333309` |
| `FIREBASE_WEB_API_KEY` | `AIzaSyBTgmYJn7WnhcXpKw0Yv8txfXTMKEYqmgo` |
| `FIREBASE_DB_URL` | `https://stationmeteo-3dc5d-default-rtdb.firebaseio.com` |
| Admin UID | `vr17AOR9v8hd83oNSEfWFUXMssH2` |
| Agriculteur UID | `AayXUAnqVjctobKJjmTnE2gOTNw2` |
| Station | `ST002` — "Station Kaolack Centre" |

---

## Fonctionnalités par Interface

### 🌾 Interface Agriculteur (après connexion)
- [ ] Mesures temps réel (4 capteurs) depuis Firebase
- [ ] Graphiques d'évolution historique (Chart.js)
- [ ] Prévisions météo 5 jours (OpenWeather)
- [ ] Recommandations IA automatiques (arbre de décision) : arroser / attendre / pulvériser
- [ ] Alertes importantes (seuils dépassés)
- [ ] Bouton lecture vocale (gTTS) — pour agriculteurs peu alphabétisés

### 🛠️ Interface Administrateur (après connexion)
- [ ] Carte Leaflet de toutes les stations (latitude/longitude depuis Firebase)
- [ ] Tableau de bord global (toutes les stations)
- [ ] Configuration des seuils d'alerte
- [ ] Gestion des contacts agriculteurs

### 🔐 Authentification (commune)
- [ ] Login par email/mot de passe (Firebase Auth REST)
- [ ] Redirection automatique : admin → admin.html, agriculteur → agriculteur.html
- [ ] Déconnexion sécurisée

---

## Plan d'Exécution (Étapes)

### Étape 1 — Structure & Backend (FastAPI)
1. Créer l'arborescence des dossiers
2. `backend/requirements.txt` + installation des dépendances
3. `firebase_service.py` — connexion Firebase Admin SDK
4. `auth_service.py` — vérification token Firebase + rôle
5. `weather_service.py` — appel OpenWeather (prévisions 5j)
6. `ia_service.py` — arbre de décision scikit-learn (règles agro sénégalaises)
7. `tts_service.py` — génération MP3 gTTS en français
8. `main.py` — routes FastAPI : `/mesures`, `/historique`, `/previsions`, `/recommandation`, `/tts`, `/stations`, `/agriculteurs`

### Étape 2 — Frontend Streamlit : Auth + Design
1. `frontend/requirements.txt` — streamlit, requests, streamlit-folium, plotly...
2. `css/styles.css` — design system (dark mode, vert agricole, typographie moderne)
3. `components/auth.py` — login Firebase REST, gestion session `st.session_state`
4. `app.py` — point d'entrée : page de login → redirection par rôle

### Étape 3 — Interface Agriculteur (Streamlit)
1. `pages/agriculteur.py` — dashboard complet
   - Mesures temps réel (4 capteurs, cartes métriques)
   - Graphiques Plotly historique
   - Prévisions météo 5 jours
   - Recommandation IA (arbre de décision)
   - Alertes
   - Bouton lecture vocale (`st.audio`)

### Étape 4 — Interface Administrateur (Streamlit)
1. `pages/admin.py` — tableau de bord admin
   - Carte Folium toutes stations
   - Vue globale toutes stations
   - Gestion agriculteurs
   - Configuration seuils d'alerte

### Étape 5 — Tests & Validation
1. Démarrer le backend : `uvicorn main:app --reload`
2. Démarrer le frontend : `streamlit run app.py`
3. Tester login agriculteur et admin
4. Vérifier données Firebase ST002 en temps réel

---

## Questions Ouvertes

> [!IMPORTANT]
> **serviceAccountKey.json** : Vous mentionnez l'avoir. Pourrez-vous le placer dans `backend/` au moment voulu ? Il est nécessaire pour que le backend Python accède à Firebase de façon sécurisée.

> [!NOTE]
> **Lecture vocale** : gTTS génère un MP3 côté backend → envoyé au frontend Streamlit → joué via `st.audio()`. Appui sur un bouton → lecture instantanée dans le navigateur.

> [!NOTE]
> **Modèle IA** : L'arbre de décision sera entraîné sur des règles agro-climatiques pour le Sénégal (température > 35°C = stress hydrique, humidité sol < 30% = arroser, etc.).

> [!NOTE]
> **Session Streamlit** : L'authentification utilise `st.session_state` pour stocker le token Firebase, le rôle et l'UID entre les pages.

---

## Vérification Finale
- Backend FastAPI accessible sur `http://localhost:8000` (Swagger UI : `/docs`)
- Frontend Streamlit accessible sur `http://localhost:8501`
- Login agriculteur (`ssophiatou.gueye@etu.ussein.edu.sn`) → dashboard ST002 en temps réel
- Login admin (`sokhnasophiatoug@gmail.com`) → carte toutes les stations
- Recommandation IA visible + lecture vocale fonctionnelle
