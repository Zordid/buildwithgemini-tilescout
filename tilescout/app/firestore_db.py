"""Firestore database client and repository for TileScout.

Stores tile exploration missions, target borders, status (planned/completed),
disciplines, parking coordinates, and distance stats.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from google.cloud import firestore

# Hardcoded project ID as string to prevent project number resolution issues on Agent Platform
GCP_PROJECT_ID: str = "qwiklabs-gcp-04-d76281bee5fc"
COLLECTION_NAME: str = "tile_missions"


def get_firestore_client() -> firestore.Client:
    """Returns a Firestore client bound to the explicit project ID string."""
    return firestore.Client(project=GCP_PROJECT_ID)


def save_mission(
    title: str,
    target_border: str,
    target_size: str,
    missing_tiles_count: int,
    missing_tiles: List[str],
    discipline: str,
    estimated_km: float,
    parking_lat: float,
    parking_lon: float,
    brouter_url: str = "",
    status: str = "planned",
    notes: str = "",
    mission_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Saves or updates a tile mission in Firestore.
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(mission_id) if mission_id else db.collection(COLLECTION_NAME).document()

    data = {
        "title": title,
        "target_border": target_border,
        "target_size": target_size,
        "missing_tiles_count": missing_tiles_count,
        "missing_tiles": missing_tiles,
        "discipline": discipline,
        "estimated_km": estimated_km,
        "parking": {
            "lat": parking_lat,
            "lon": parking_lon,
        },
        "brouter_url": brouter_url,
        "status": status,
        "notes": notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    doc = doc_ref.get()
    if not doc.exists:
        data["created_at"] = datetime.now(timezone.utc).isoformat()

    doc_ref.set(data, merge=True)
    data["id"] = doc_ref.id
    return data


def list_missions(
    status: Optional[str] = None,
    discipline: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Lists tile missions from Firestore, optionally filtered by status or discipline.
    """
    db = get_firestore_client()
    query = db.collection(COLLECTION_NAME)

    if status:
        query = query.where("status", "==", status)
    if discipline:
        query = query.where("discipline", "==", discipline)

    docs = query.limit(limit).stream()
    missions = []
    for d in docs:
        item = d.to_dict()
        item["id"] = d.id
        missions.append(item)
    return missions


def update_mission_status(mission_id: str, status: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Updates the status (e.g. 'planned', 'completed', 'skipped') and optional notes of a mission.
    """
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(mission_id)
    doc = doc_ref.get()
    if not doc.exists:
        return None

    update_data: Dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if notes is not None:
        update_data["notes"] = notes

    doc_ref.update(update_data)
    refreshed = doc_ref.get().to_dict()
    if refreshed:
        refreshed["id"] = doc_ref.id
    return refreshed
