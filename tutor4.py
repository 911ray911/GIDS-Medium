import geopandas as gpd
import numpy as np

def minmax(series):
    mn = float(series.min())
    mx = float(series.max())
    if mx == mn:
        return np.zeros(len(series), dtype=float)
    return (series - mn) / (mx - mn)

# =========================
# 1) Load data
# =========================
zones = gpd.read_file("zones.geojson")
activities = gpd.read_file("activities.geojson")  # used as activity/service points

# Ensure CRS exists
if zones.crs is None:
    zones = zones.set_crs("EPSG:4326")
if activities.crs is None:
    activities = activities.set_crs(zones.crs)

activities = activities.to_crs(zones.crs)

# =========================
# 2) Part 2: Exposure (activity concentration per zone)
# =========================
joined = gpd.sjoin(activities, zones[["zone_id", "geometry"]], predicate="within", how="inner")
counts = joined.groupby("zone_id").size().reset_index(name="activity_count")

zones = zones.merge(counts, on="zone_id", how="left")
zones["activity_count"] = zones["activity_count"].fillna(0).astype(int)

zones["exposure_score"] = minmax(zones["activity_count"]).round(6)  # 0..1

# =========================
# 3) Part 3: Accessibility & Underserved
#    (distance-decay to K nearest activity/service points)
# =========================
# Project to meters for distance
zones_m = zones.to_crs("EPSG:3857")
acts_m = activities.to_crs("EPSG:3857")

# Represent each zone by centroid point
zone_pts = zones_m.copy()
zone_pts["geometry"] = zone_pts.geometry.centroid

K = 5
alpha = 2000  # meters

svc_coords = np.array([(g.x, g.y) for g in acts_m.geometry])

def nearest_k_distances(px, py, coords, k):
    dx = coords[:, 0] - px
    dy = coords[:, 1] - py
    d = np.sqrt(dx * dx + dy * dy)
    # k smallest without full sort
    return np.partition(d, k-1)[:k]

nearest_dists = []
for g in zone_pts.geometry:
    d_k = nearest_k_distances(g.x, g.y, svc_coords, K)
    nearest_dists.append(np.sort(d_k))

nearest_dists = np.array(nearest_dists)

access_raw = np.sum(1 / (1 + (nearest_dists / alpha)), axis=1)
zone_pts["access_raw"] = access_raw
zone_pts["access_score"] = minmax(zone_pts["access_raw"]).round(6)
zone_pts["underserved_score"] = (1 - zone_pts["access_score"]).round(6)

# Merge accessibility metrics back into zones (by zone_id)
zones = zones.merge(
    zone_pts[["zone_id", "access_raw", "access_score", "underserved_score"]],
    on="zone_id",
    how="left"
)

# =========================
# 4) Part 4: Build Spatial Sustainability Index (SSI)
# =========================
# Define pressures (direction aligned: higher = worse / more priority)
zones["env_pressure"] = zones["exposure_score"]          # environmental/pressure proxy
zones["social_pressure"] = zones["underserved_score"]    # equity proxy
zones["ops_pressure"] = zones["exposure_score"]          # simple proxy; can be replaced later

# Weights (must sum to 1.0)
w_env = 0.4
w_soc = 0.4
w_ops = 0.2

zones["ssi_score"] = (
    w_env * zones["env_pressure"] +
    w_soc * zones["social_pressure"] +
    w_ops * zones["ops_pressure"]
).round(6)

# =========================
# 5) Output: Top 10 priority zones
# =========================
top10 = zones.sort_values(["ssi_score", "env_pressure"], ascending=False).head(10)

print("\n=== TOP 10 PRIORITY ZONES by Spatial Sustainability Index (SSI) ===")
print(top10[[
    "zone_id",
    "activity_count",
    "env_pressure",
    "social_pressure",
    "ops_pressure",
    "ssi_score"
]].to_string(index=False))

# =========================
# 6) Sanity checks
# =========================
print("\n=== SANITY CHECKS ===")
print("Zones:", len(zones))
print("Activities:", len(activities))
print("Total counted (sum activity_count):", int(zones["activity_count"].sum()))
print("SSI range:", float(zones["ssi_score"].min()), "to", float(zones["ssi_score"].max()))
print("Weights:", w_env, w_soc, w_ops, "sum =", w_env + w_soc + w_ops)

# =========================
# 7) Optional: export GeoJSON for mapping
# =========================
# zones.to_file("zones_with_ssi.geojson", driver="GeoJSON")
# print("\nSaved: zones_with_ssi.geojson")
