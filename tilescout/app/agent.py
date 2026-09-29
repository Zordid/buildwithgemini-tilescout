"""
TileScout - ADK Agent for Statshunters Tile & Max Square Exploration.
Helps athletes decide where to ride (Road, Gravel, MTB) or hike next to efficiently expand their square,
finding optimal driving-accessible start points and minimizing Stich out-and-backs.
"""

import os
from typing import Dict, Any, List, Optional
from google.adk.agents import Agent
from google.genai import types

from app.tile_math import (
    latlon_to_tile,
    tile_to_latlon_center,
    haversine_km,
    compute_max_square,
    evaluate_square_expansions,
    plan_loop_waypoints,
    generate_brouter_link,
    group_missing_tiles_into_subclusters,
    plan_cluster_expansion_options,
)
from app.statshunters import StatsHuntersClient

MODEL = "gemini-2.5-flash"
DEFAULT_SHARE_CODE = os.getenv("STATSHUNTERS_SHARE_CODE", "cbcc3a92f286")

# In-memory cache for tile data
_TILE_CACHE: Dict[str, Any] = {}

def get_my_tile_profile(share_code: str = "") -> str:
    """
    Connects to StatsHunters to fetch your current visited tiles, compute your Max Square,
    and summarize your current exploration state.

    Args:
        share_code: Optional StatsHunters share code or link. If omitted, uses configured default.

    Returns:
        A formatted summary of visited tiles count, current max square (size and center location).
    """
    code = share_code.strip() if share_code.strip() else DEFAULT_SHARE_CODE
    try:
        client = StatsHuntersClient(code)
        data = client.fetch_tiles_and_activities()
        tiles = data["tiles"]
        sq = compute_max_square(tiles)
        _TILE_CACHE[code] = {"tiles": tiles, "square": sq}

        center = sq.get("center") or {"lat": 0.0, "lon": 0.0}
        return (
            f"StatsHunters Profile for code '{code}':\n"
            f"- Total Explored Tiles: {data['visited_tiles_count']}\n"
            f"- Total Logged Activities: {data['total_activities']}\n"
            f"- Current Max Square: {sq['size']}x{sq['size']}\n"
            f"- Square Geographic Center: lat={center['lat']:.4f}, lon={center['lon']:.4f}\n"
            f"- Square Tile Bounds: {sq['bounds']}\n"
        )
    except Exception as e:
        return f"Error retrieving StatsHunters data: {str(e)}"

def plan_square_expansion_mission(
    discipline: str = "cycling",
    max_driving_km: float = 40.0,
    max_activity_km: float = 65.0,
    avoid_stiche: bool = True,
    share_code: str = ""
) -> str:
    """
    Finds the highest-leverage mission to expand your Max Square to (N+1)x(N+1).
    Evaluates missing tiles on each border, checks driving distance from home,
    plans a circular loop piercing the missing tiles, and minimizes dead-end spurs ('Stiche').

    Args:
        discipline: Sport discipline ('cycling', 'road_bike', 'gravel', 'mtb', 'hike').
        max_driving_km: Maximum acceptable one-way driving distance to the start point (km).
        max_activity_km: Maximum activity distance budget (km).
        avoid_stiche: If true, strongly penalize dead-end spurs ('Stiche') and prioritize continuous loops.
        share_code: Optional StatsHunters share code.

    Returns:
        Ranked expansion missions with target border, missing tile coordinates, suggested parking, and BRouter routing link.
    """
    code = share_code.strip() if share_code.strip() else DEFAULT_SHARE_CODE
    if code not in _TILE_CACHE:
        get_my_tile_profile(code)

    cached = _TILE_CACHE.get(code)
    if not cached:
        return "No tile data available. Please check your share code."

    tiles = cached["tiles"]
    current_sq = cached["square"]
    if current_sq["size"] == 0:
        return "Could not compute max square from tiles."

    options = plan_cluster_expansion_options(
        tiles=tiles,
        current_square=current_sq,
        max_activity_km=max_activity_km,
        discipline=discipline,
        avoid_stiche=avoid_stiche,
    )
    if not options:
        return "No expansion options found."

    # First, look for missions that fit the user's distance budget
    budget_friendly = [o for o in options if o["fits_budget"]]

    if budget_friendly:
        # Prefer immediate max square if one fits budget, otherwise best stepping stone / cluster builder
        best = next((o for o in budget_friendly if o["type"] == "immediate_max_square"), budget_friendly[0])
    else:
        # If none fit the budget, pick the shortest stepping stone or closest mission
        options_sorted_by_km = sorted(options, key=lambda o: o["estimated_km"])
        best = options_sorted_by_km[0]

    target_tiles = best["missing_tiles"]
    route = best["route"]
    start_lat = target_tiles[0]["lat"]
    start_lon = target_tiles[0]["lon"]

    # Discipline notes
    disc_lower = discipline.lower()
    if "road" in disc_lower:
        disc_recommendation = "Road Bike: Paved roads and cycleways recommended."
    elif "gravel" in disc_lower:
        disc_recommendation = "Gravel Bike: Ideal for mixed tarmac, canal towpaths, and hard-packed gravel."
    elif "mtb" in disc_lower:
        disc_recommendation = "MTB: Ideal for rough singletrack, forest paths, or rugged terrain."
    elif "hike" in disc_lower:
        disc_recommendation = "Hiking / Trail Run: Best for footpaths, nature reserves, or steep climbs."
    else:
        disc_recommendation = "Cycling (General): Mixed paved and gravel cycle routes."

    tile_strings = [f"({t['x']}, {t['y']})" for t in target_tiles]
    budget_status = f"~{route['estimated_km']} km (Fits within your {max_activity_km} km budget! ✅)" if route['estimated_km'] <= max_activity_km else f"~{route['estimated_km']} km (Budget: {max_activity_km} km)"

    summary = [
        f"🎯 **Recommended Tile Mission: {best['name']}**",
        f"- Mission Type: {'Immediate Max Square Unlock' if best['type'] == 'immediate_max_square' else 'Cluster Expansion & Max Square Stepping-Stone'}",
        f"- Strategy: {best['description']}",
        f"- Target Square Goal: **{best['target_size']}** (current: {current_sq['size']}x{current_sq['size']})",
        f"- Target Tiles to Capture: **{best['missing_tiles_count']} tiles**",
        f"- Target Tile List: {', '.join(tile_strings)}",
        f"- Discipline: {disc_recommendation}",
        f"- Recommended Start / Parking: lat={start_lat:.4f}, lon={start_lon:.4f}",
        f"- Estimated Activity Loop Distance: {budget_status}",
        f"- Stich Detour Policy: {'Minimizing dead-end spurs (Stiche)' if avoid_stiche else 'Direct out-and-backs permitted'}",
        f"- BRouter Route: [Open Interactive Route in BRouter]({route['brouter_url']})",
        "",
        "**Alternative Mission Options:**"
    ]

    for alt in options:
        if alt["name"] == best["name"]:
            continue
        km_tag = f"~{alt['estimated_km']} km"
        fit_tag = "✅ in budget" if alt["fits_budget"] else "⚠️ exceeds budget"
        summary.append(
            f"- **{alt['name']}**: {alt['missing_tiles_count']} tiles, {km_tag} ({fit_tag}) — {alt['description']}"
        )

    return "\n".join(summary)


from .firestore_db import save_mission as db_save_mission, list_missions as db_list_missions, update_mission_status as db_update_mission_status


def save_tile_mission(
    title: str,
    target_border: str,
    target_size: str,
    missing_tiles: List[str],
    discipline: str = "gravel",
    estimated_km: float = 50.0,
    parking_lat: float = 48.5,
    parking_lon: float = 12.0,
    brouter_url: str = "",
    notes: str = "",
) -> str:
    """
    Saves a newly planned tile mission to the user's Firestore missions database.

    Args:
        title: Title of the mission (e.g. 'SE Border Mission 66x66').
        target_border: Target border ('South-East', 'South-West', 'North-East', 'North-West').
        target_size: Target square size reached upon completion (e.g. '66x66').
        missing_tiles: List of missing tile coordinate strings like ['(8746, 5657)', '(8746, 5658)'].
        discipline: Sport discipline ('gravel', 'road_bike', 'mtb', 'hike').
        estimated_km: Estimated activity distance in km.
        parking_lat: Starting/parking latitude.
        parking_lon: Starting/parking longitude.
        brouter_url: BRouter routing link.
        notes: Optional mission strategy notes.

    Returns:
        Confirmation message with the Firestore mission ID.
    """
    res = db_save_mission(
        title=title,
        target_border=target_border,
        target_size=target_size,
        missing_tiles_count=len(missing_tiles),
        missing_tiles=missing_tiles,
        discipline=discipline,
        estimated_km=estimated_km,
        parking_lat=parking_lat,
        parking_lon=parking_lon,
        brouter_url=brouter_url,
        status="planned",
        notes=notes,
    )
    return f"✅ Saved mission '{title}' to Firestore with ID: {res['id']} (Status: planned)."


def list_saved_missions(
    status: str = "",
    discipline: str = "",
    limit: int = 10,
) -> str:
    """
    Retrieves saved tile missions from Firestore database.

    Args:
        status: Optional filter by status ('planned', 'completed', 'skipped').
        discipline: Optional filter by discipline ('gravel', 'road_bike', 'mtb', 'hike').
        limit: Max number of missions to retrieve (default 10).

    Returns:
        Formatted summary of saved missions.
    """
    missions = db_list_missions(
        status=status.strip() if status.strip() else None,
        discipline=discipline.strip() if discipline.strip() else None,
        limit=limit,
    )
    if not missions:
        return "No tile missions found in Firestore matching the criteria."

    lines = [f"📋 **Found {len(missions)} saved missions in Firestore:**"]
    for m in missions:
        route_str = f"  Route: [Open Route in BRouter]({m['brouter_url']})\n" if m.get("brouter_url") else ""
        lines.append(
            f"- [{m.get('status', 'planned').upper()}] **{m.get('title')}** (ID: `{m.get('id')}`)\n"
            f"  Border: {m.get('target_border')}, Target: {m.get('target_size')}, Discipline: {m.get('discipline')}, ~{m.get('estimated_km')} km\n"
            f"  Missing tiles: {', '.join(m.get('missing_tiles', []))}\n"
            f"{route_str}"
            f"  Notes: {m.get('notes', '')}"
        )
    return "\n\n".join(lines)


def update_mission_progress(
    mission_id: str,
    status: str,
    notes: str = "",
) -> str:
    """
    Updates a mission's status (e.g. mark 'completed', 'planned', or 'skipped') in Firestore.

    Args:
        mission_id: The Firestore document ID of the mission.
        status: New status ('completed', 'planned', 'skipped').
        notes: Optional extra notes or ride impressions.

    Returns:
        Confirmation of update.
    """
    res = db_update_mission_status(mission_id=mission_id, status=status, notes=notes if notes else None)
    if not res:
        return f"Mission with ID `{mission_id}` not found in Firestore."
    return f"Updated mission `{mission_id}` ('{res.get('title')}') status to **{status}**."


from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

# WRITE: after each turn, send the session to Memory Bank for extraction if configured.
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except (ValueError, RuntimeError):
        # Gracefully pass if running in an environment without a memory service
        pass
    return None


system_instruction = (
    "You are TileScout, an enthusiastic and tactical exploration coach for cyclists, runners, and hikers "
    "who use StatsHunters to explore geographic tiles and grow their Max Square.\n\n"
    "Your strengths:\n"
    "1. You remember the user's home location / address, preferred sports types (road bike, gravel, MTB, hike), "
    "and typical activity & driving distance budgets across sessions, personalizing all route recommendations.\n"
    "2. You understand Slippy Map Zoom 14 (z14) tile math, Max Square, and Tile Clusters.\n"
    "3. When suggesting where to go, you first look for opportunities to unlock the next (N+1)x(N+1) Max Square.\n"
    "4. Crucially: If a full border expansion is too long for the user's budget, NEVER refuse or say no route exists! Instead, you proactively offer 'stepping-stone' rides or cluster expansion pockets (shorter loops capturing a subset of missing tiles or pushing out the cluster perimeter within their distance budget).\n"
    "5. You respect the user's travel parameters: maximum driving distance to the start point, maximum activity distance/elevation, and sport discipline.\n"
    "6. You specifically know and respect German cycling/hiking culture regarding 'Stiche' (out-and-back dead-end spurs): you actively prioritize flowing circular loops and minimize dead-end 'Stiche'.\n"
    "7. You support multimodal activities: Road Bike, Gravel, MTB, and Hiking for tiles inaccessible by bike.\n"
    "8. Provide helpful links to BRouter web for route visualization when relevant.\n"
    "9. You have a Firestore database backend to save planned missions, list existing saved missions, and mark missions completed.\n\n"
    "Respond in clean, well-formatted markdown. Summarize tile profiles, mission plans, stats, and database updates clearly."
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    description="An intelligent exploration coach for StatsHunters and VeloViewer tile hunters.",
    instruction=system_instruction,
    tools=[
        PreloadMemoryTool(),
        get_my_tile_profile,
        plan_square_expansion_mission,
        save_tile_mission,
        list_saved_missions,
        update_mission_progress,
    ],
    after_agent_callback=generate_memories_callback,
)

from google.adk.memory import VertexAiMemoryBankService

def memory_bank_service_builder():
    memory_bank_id = os.environ.get("MEMORY_BANK_ID", "2523642518780772352")
    return VertexAiMemoryBankService(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-d76281bee5fc"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        agent_engine_id=memory_bank_id,
    )

app = App(
    root_agent=root_agent,
    name="app",
)
agent = root_agent







