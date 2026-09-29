"""Seed script for Firestore tile_missions collection.

Hardcodes GCP Project ID as string per instructions.
"""

from app.firestore_db import save_mission, list_missions, GCP_PROJECT_ID

print(f"Seeding Firestore in project: {GCP_PROJECT_ID}...")

# Seed 3 high-priority tile missions
m1 = save_mission(
    title="SE Border Expansion Mission (Dorfen - Haag)",
    target_border="South-East",
    target_size="66x66",
    missing_tiles_count=6,
    missing_tiles=["(8746, 5657)", "(8746, 5658)", "(8746, 5680)", "(8746, 5682)", "(8746, 5683)", "(8746, 5698)"],
    discipline="gravel",
    estimated_km=62.5,
    parking_lat=48.5530,
    parking_lon=12.1838,
    brouter_url="https://brouter.de/brouter-web/#map=11/48.5530/12.1838/standard&lonlats=12.18380,48.55300|12.18380,48.53840|12.18380,48.21740|12.18380,48.55300&profile=gravel",
    status="planned",
    notes="The highest leverage mission to unlock 66x66 Max Square with only 6 missing tiles."
)

m2 = save_mission(
    title="Chiemgau Foothills Gravel Tour",
    target_border="South",
    target_size="66x66",
    missing_tiles_count=12,
    missing_tiles=["(8720, 5708)", "(8721, 5708)", "(8722, 5708)"],
    discipline="gravel",
    estimated_km=74.0,
    parking_lat=47.8500,
    parking_lon=12.2000,
    brouter_url="https://brouter.de/brouter-web/#map=11/47.8500/12.2000/standard&lonlats=12.2000,47.8500|12.2200,47.8600&profile=gravel",
    status="planned",
    notes="Scenic gravel loop with moderate rolling hills."
)

m3 = save_mission(
    title="Altmühltal Donauwörth Trail Run / Hike",
    target_border="North-West",
    target_size="66x66",
    missing_tiles_count=19,
    missing_tiles=["(8680, 5643)", "(8680, 5644)"],
    discipline="hike",
    estimated_km=21.0,
    parking_lat=48.7200,
    parking_lon=10.7800,
    brouter_url="https://brouter.de/brouter-web/#map=12/48.7200/10.7800/standard&lonlats=10.7800,48.7200|10.8000,48.7400&profile=hiking-mountain",
    status="completed",
    notes="Completed steep ridge section on foot to bag inaccessible forest tiles."
)

print(f"Successfully seeded missions:")
for m in list_missions():
    print(f" - [{m['status'].upper()}] {m['title']} ({m['discipline']}, ~{m['estimated_km']} km) - ID: {m['id']}")
