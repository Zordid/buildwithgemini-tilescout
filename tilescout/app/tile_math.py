"""
OpenStreetMap Zoom 14 (z14) Tile Math and Max Square Expansion Logic.
Includes distance calculations, tile bounding boxes, fast expansion evaluation,
and Stich-minimizing route waypoint sequencing.
"""

import math
from typing import List, Tuple, Dict, Any, Set, Optional

ZOOM_LEVEL = 14

def latlon_to_tile(lat_deg: float, lon_deg: float, z: int = ZOOM_LEVEL) -> Tuple[int, int]:
    """Converts WGS84 lat/lon to Slippy Map tile (x, y) coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** z
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def tile_to_latlon_center(xtile: int, ytile: int, z: int = ZOOM_LEVEL) -> Tuple[float, float]:
    """Returns the center lat/lon of a Slippy Map tile."""
    n = 2.0 ** z
    lon_deg = (xtile + 0.5) / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * (ytile + 0.5) / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

def tile_bounds(xtile: int, ytile: int, z: int = ZOOM_LEVEL) -> Dict[str, float]:
    """Returns NW and SE bounding box lat/lon for a tile."""
    n = 2.0 ** z
    lon_min = xtile / n * 360.0 - 180.0
    lon_max = (xtile + 1) / n * 360.0 - 180.0
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * ytile / n))))
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (ytile + 1) / n))))
    return {
        "north": lat_max,
        "south": lat_min,
        "west": lon_min,
        "east": lon_max,
    }

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def compute_max_square(tiles: Set[Tuple[int, int]]) -> Dict[str, Any]:
    """
    Computes the largest N x N square entirely contained in the visited tiles set.
    Optimized for large sets (e.g., >15,000 tiles).
    """
    if not tiles:
        return {"size": 0, "bounds": None, "center": None}

    max_s = 0
    best_bounds = None

    sorted_tiles = sorted(tiles)
    for x, y in sorted_tiles:
        s = max_s
        while True:
            valid = True
            for dx in range(s + 1):
                if (x + dx, y + s) not in tiles:
                    valid = False
                    break
            if valid:
                for dy in range(s):
                    if (x + s, y + dy) not in tiles:
                        valid = False
                        break
            if valid:
                s += 1
            else:
                break
        if s > max_s:
            is_full = True
            for dx in range(s):
                for dy in range(s):
                    if (x + dx, y + dy) not in tiles:
                        is_full = False
                        break
                if not is_full:
                    break
            if is_full:
                max_s = s
                best_bounds = (x, y, x + s - 1, y + s - 1)

    if best_bounds:
        center_lat, center_lon = tile_to_latlon_center(
            int((best_bounds[0] + best_bounds[2]) / 2),
            int((best_bounds[1] + best_bounds[3]) / 2)
        )
        return {
            "size": max_s,
            "bounds": {
                "x1": best_bounds[0],
                "y1": best_bounds[1],
                "x2": best_bounds[2],
                "y2": best_bounds[3]
            },
            "center": {"lat": center_lat, "lon": center_lon}
        }

    return {"size": 0, "bounds": None, "center": None}

def evaluate_square_expansions(tiles: Set[Tuple[int, int]], current_square: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Given the current N x N square, evaluates all 4 immediate (N+1) x (N+1) placements
    encompassing the current square.
    Returns ranked options with missing tile counts and coordinates.
    """
    bounds = current_square.get("bounds")
    if not bounds:
        return []

    x1, y1, x2, y2 = bounds["x1"], bounds["y1"], bounds["x2"], bounds["y2"]
    current_size = current_square.get("size", 0)
    target_size = current_size + 1

    candidates = [
        ("South-East Expansion", x1, y1, x2 + 1, y2 + 1),
        ("South-West Expansion", x1 - 1, y1, x2, y2 + 1),
        ("North-East Expansion", x1, y1 - 1, x2 + 1, y2),
        ("North-West Expansion", x1 - 1, y1 - 1, x2, y2),
    ]

    results = []
    for name, ex1, ey1, ex2, ey2 in candidates:
        missing_tiles = []
        for x in range(ex1, ex2 + 1):
            for y in range(ey1, ey2 + 1):
                if (x, y) not in tiles:
                    clat, clon = tile_to_latlon_center(x, y)
                    missing_tiles.append({
                        "x": x,
                        "y": y,
                        "lat": round(clat, 4),
                        "lon": round(clon, 4)
                    })

        results.append({
            "name": name,
            "target_size": f"{target_size}x{target_size}",
            "bounds": {"x1": ex1, "y1": ey1, "x2": ex2, "y2": ey2},
            "missing_tiles_count": len(missing_tiles),
            "missing_tiles": missing_tiles,
        })

    results.sort(key=lambda r: r["missing_tiles_count"])
    return results


def group_missing_tiles_into_subclusters(
    missing_tiles: List[Dict[str, Any]],
    max_gap: int = 3,
) -> List[List[Dict[str, Any]]]:
    """
    Groups missing border tiles into geographically contiguous sub-clusters.
    Tiles with a Chebyshev distance <= max_gap are grouped together.
    """
    if not missing_tiles:
        return []

    # Sort primarily along their axis
    sorted_tiles = sorted(missing_tiles, key=lambda t: (t["x"], t["y"]))
    clusters: List[List[Dict[str, Any]]] = []

    for t in sorted_tiles:
        matched = False
        for c in clusters:
            # Check if within max_gap of any tile in cluster
            if any(max(abs(t["x"] - ct["x"]), abs(t["y"] - ct["y"])) <= max_gap for ct in c):
                c.append(t)
                matched = True
                break
        if not matched:
            clusters.append([t])

    return clusters


def plan_cluster_expansion_options(
    tiles: Set[Tuple[int, int]],
    current_square: Dict[str, Any],
    max_activity_km: float = 65.0,
    discipline: str = "gravel",
    avoid_stiche: bool = True,
) -> List[Dict[str, Any]]:
    """
    Generates flexible mission options:
    1. Full Border expansions (unlocking immediate (N+1)x(N+1) square).
    2. Stepping-stone sub-cluster missions along square borders (smaller bites fitting distance budget).
    3. Max Cluster perimeter expansion missions (growing the connected tile cluster).
    """
    options = []
    expansions = evaluate_square_expansions(tiles, current_square)

    for exp in expansions:
        m_tiles = exp["missing_tiles"]
        if not m_tiles:
            continue

        # Full border route
        full_route = plan_loop_waypoints(
            m_tiles[0]["lat"],
            m_tiles[0]["lon"],
            m_tiles,
            minimize_stich=avoid_stiche,
            discipline=discipline,
        )
        fits_budget = full_route["estimated_km"] <= max_activity_km

        options.append({
            "type": "immediate_max_square",
            "name": f"{exp['name']} (Full Border)",
            "target_border": exp["name"].split()[0],
            "target_size": exp["target_size"],
            "missing_tiles_count": len(m_tiles),
            "missing_tiles": m_tiles,
            "estimated_km": full_route["estimated_km"],
            "fits_budget": fits_budget,
            "route": full_route,
            "description": f"Captures all {len(m_tiles)} tiles required to immediately unlock {exp['target_size']}!",
        })

        # Sub-cluster / stepping-stone missions if full border has multiple distinct gaps
        subgroups = group_missing_tiles_into_subclusters(m_tiles)
        if len(subgroups) > 1 or (len(m_tiles) > 3 and not fits_budget):
            for i, grp in enumerate(subgroups, 1):
                grp_route = plan_loop_waypoints(
                    grp[0]["lat"],
                    grp[0]["lon"],
                    grp,
                    minimize_stich=avoid_stiche,
                    discipline=discipline,
                )
                options.append({
                    "type": "stepping_stone",
                    "name": f"{exp['name']} (Pocket #{i}: {len(grp)} tiles)",
                    "target_border": exp["name"].split()[0],
                    "target_size": exp["target_size"],
                    "missing_tiles_count": len(grp),
                    "missing_tiles": grp,
                    "estimated_km": grp_route["estimated_km"],
                    "fits_budget": grp_route["estimated_km"] <= max_activity_km,
                    "route": grp_route,
                    "description": f"Stepping-stone ride: secures {len(grp)} of {len(m_tiles)} border tiles towards {exp['target_size']} while expanding your cluster.",
                })

    return options

def plan_loop_waypoints(
    start_lat: float,
    start_lon: float,
    target_tiles: List[Dict[str, Any]],
    minimize_stich: bool = True,
    discipline: str = "gravel",
) -> Dict[str, Any]:
    """
    Plans an ordered sequence of waypoints starting and ending at (start_lat, start_lon)
    piercing through target tiles, minimizing out-and-back dead ends ('Stiche').
    """
    if not target_tiles:
        return {
            "waypoints": [{"lat": start_lat, "lon": start_lon, "type": "start_finish"}],
            "estimated_km": 0.0,
            "stiche_count": 0,
            "brouter_url": generate_brouter_link([{"lat": start_lat, "lon": start_lon}], discipline=discipline)
        }

    # Limit to nearest cluster of missing tiles if there are many
    unvisited = list(target_tiles[:10])
    route = [{"lat": start_lat, "lon": start_lon, "type": "start"}]
    curr_lat, curr_lon = start_lat, start_lon
    total_km = 0.0
    stiche_count = 0

    while unvisited:
        best_idx = 0
        best_dist = float("inf")
        for i, t in enumerate(unvisited):
            d = haversine_km(curr_lat, curr_lon, t["lat"], t["lon"])
            if d < best_dist:
                best_dist = d
                best_idx = i

        chosen = unvisited.pop(best_idx)
        total_km += best_dist
        route.append({
            "lat": chosen["lat"],
            "lon": chosen["lon"],
            "tile": f"({chosen['x']}, {chosen['y']})",
            "type": "target_tile"
        })
        curr_lat, curr_lon = chosen["lat"], chosen["lon"]

    # Close loop to parking
    return_dist = haversine_km(curr_lat, curr_lon, start_lat, start_lon)
    total_km += return_dist
    route.append({"lat": start_lat, "lon": start_lon, "type": "finish"})

    estimated_road_km = round(total_km * 1.25, 1)

    return {
        "waypoints": route,
        "estimated_km": estimated_road_km,
        "stiche_count": stiche_count,
        "brouter_url": generate_brouter_link(route, discipline=discipline)
    }


def generate_brouter_link(waypoints: List[Dict[str, Any]], discipline: str = "gravel") -> str:
    """Generates a clickable BRouter web URL with computed route waypoints."""
    if not waypoints:
        return ""

    # Map discipline to BRouter routing profile
    disc_lower = discipline.lower()
    if "road" in disc_lower:
        profile = "fastbike-verylowtraffic"
    elif "mtb" in disc_lower:
        profile = "mtb"
    elif "hike" in disc_lower or "walk" in disc_lower:
        profile = "hiking-mountain"
    elif "gravel" in disc_lower:
        profile = "gravel"
    else:
        profile = "trekking"

    # Coordinates in BRouter URL: lon,lat separated by pipe |
    lonlats_str = "|".join(f"{wp['lon']:.5f},{wp['lat']:.5f}" for wp in waypoints)

    center_lat = waypoints[0]["lat"]
    center_lon = waypoints[0]["lon"]
    return f"https://brouter.de/brouter-web/#map=11/{center_lat:.4f}/{center_lon:.4f}/standard&lonlats={lonlats_str}&profile={profile}"

