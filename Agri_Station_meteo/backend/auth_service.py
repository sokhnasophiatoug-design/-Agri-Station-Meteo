"""
auth_service.py — Authentification Firebase
Vérifie le token Firebase ID et retourne le rôle de l'utilisateur.
"""

from firebase_service import verify_id_token, get_all_agriculteurs
from firebase_admin import db


def verify_token_and_get_role(id_token: str) -> dict:
    """
    Vérifie un token Firebase ID et détermine le rôle de l'utilisateur.

    Returns:
        dict avec clés : role, uid, nom, (et données spécifiques au rôle)
        ou dict avec clé 'error' en cas d'échec.
    """
    try:
        decoded = verify_id_token(id_token)
        uid = decoded["uid"]

        # ── Vérifier si administrateur ───────────────────────────────────────
        print("=== AVANT ADMIN GET ===")
        admin_ref = db.reference(f"admins/{uid}")
        admin_data = admin_ref.get()
        print("=== APRES ADMIN GET ===")
        if admin_data:
            return {
                "role":  "admin",
                "uid":   uid,
                "nom":   "Administrateur",
                "email": decoded.get("email", ""),
            }

        # ── Vérifier si agriculteur ──────────────────────────────────────────
        print("=== AVANT AGRI GET ===")
        agri_ref = db.reference(f"agriculteurs/{uid}")
        agri_data = agri_ref.get()
        print("=== APRES AGRI GET ===")
        if agri_data:
            return {
                "role":         "agriculteur",
                "uid":          uid,
                "nom":          agri_data.get("nom", "Agriculteur"),
                "email":        agri_data.get("email", ""),
                "station_id":   agri_data.get("station_id", ""),
                "station_nom":  agri_data.get("station_nom", ""),
                "region":       agri_data.get("region", ""),
                "firebase_path":agri_data.get("firebase_path", ""),
                "telephone":    agri_data.get("telephone", ""),
                "actif":        agri_data.get("actif", True),
            }

        # ── Utilisateur non reconnu ──────────────────────────────────────────
        return {"error": "Utilisateur non reconnu. Contactez l'administrateur."}

    except ValueError as e:
        return {"error": f"Token invalide : {str(e)}"}
    except Exception as e:
        return {"error": f"Erreur d'authentification : {str(e)}"}


def register_agriculteur(uid: str, profil: dict) -> dict:
    """Enregistre le profil d'un nouvel agriculteur dans Firebase Realtime DB."""
    try:
        from firebase_admin import db
        from datetime import datetime
        db.reference(f"agriculteurs/{uid}").set({
            "nom":           profil.get("nom", ""),
            "email":         profil.get("email", ""),
            "telephone":     profil.get("telephone", ""),
            "region":        profil.get("region", ""),
            "station_id":    profil.get("station_id", ""),
            "station_nom":   profil.get("station_nom", ""),
            "firebase_path": profil.get("firebase_path", ""),
            "actif":         True,
            "date_creation": datetime.now().isoformat(),
            "role":          "agriculteur",
        })
        return {"succes": True}
    except Exception as e:
        return {"succes": False, "erreur": str(e)}
