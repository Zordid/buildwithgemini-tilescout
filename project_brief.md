# My agent: TileScout (Statshunters Explorer Coach)
One-liner: A conversational exploration coach that integrates with the StatsHunters API to help athletes decide where to ride (Road, Gravel, MTB) or hike next to efficiently expand their max square and tile cluster, finding optimal driving-accessible start points for targeted tile missions.

Key Principles & Constraints:
- Data Source: Live or configured StatsHunters API / Share Code to pull explored z14 tile indices, cluster bounds, and max square coordinates.
- Start point & trailhead flexibility: The user can choose a starting point or drive/park near unvisited tiles to begin their loop/out-and-back.
- Multimodal discipline support: Default is cycling, but supports specific bike disciplines (Road Bike, Gravel, MTB) as well as Hiking/Trail Running for rugged or bike-inaccessible tiles (e.g., steep peaks, nature reserves, or rough terrain).
- Efficiency metric: Prioritize routes that unlock the highest number of critical square-expansion tiles with the least redundant distance.

Tool coverage:
- Memory: Remembers your StatsHunters API/share code, home/starting location, vehicle/drive willingness (e.g., max driving radius), discipline preference (Road, Gravel, MTB, Hike), typical physical range (distance/elevation budget), current max square coordinates/size (e.g., 14x14), and target expansion borders.
- Tools:
  - `fetch_statshunters_tiles`: Queries StatsHunters API to retrieve current visited tiles, cluster, and max square boundaries.
  - `find_square_expansion_targets`: Analyzes the grid around the max square to identify which border/edge unvisited tiles unlock the next (N+1)x(N+1) size.
  - `find_parking_and_trailheads`: Identifies driving-accessible starting locations/parking spots near high-leverage tile targets.
  - `filter_missions_by_discipline`: Recommends Road vs. Gravel vs. MTB vs. Hike routes depending on elevation and terrain profile.
- Catalog/UI: Catalog of "Tile Missions" displayed as rich A2UI cards (recommended start/parking location, required discipline, target tiles unlocked, elevation gain, efficiency score) and comparison tables.
- Image gen: Generates custom milestone achievement badges and expedition summary postcards when a square level (e.g., 15x15) is achieved.
- Sandbox: Calculates square expansion geometry (identifying the fewest unvisited tiles needed to unlock the next N+1 square), computes route efficiency scores (new tiles per km traveled), and calculates driving vs. riding logistics.

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): code sandbox for square geometry & tile efficiency calculations, StatsHunters API integration, trailhead/parking lookup, Cloud Trace.
