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
activities = gpd.read_file("activities.geojson")

# Ensure CRS exists
if zones.crs is None:
    zones = zones.set_crs("EPSG:4326")
if activities.crs is None:
    activities = activities.set_crs(zones.crs)

activities = activities.to_crs(zones.crs)

# =========================
# 2) Part 2: Exposure (activity concentration)
# =========================
joined = gpd.sjoin(activities, zones[["zone_id", "geometry"]], predicate="within", how="inner")
counts = joined.groupby("zone_id").size().reset_index(name="activity_count")

zones = zones.merge(counts, on="zone_id", how="left")
zones["activity_count"] = zones["activity_count"].fillna(0).astype(int)

zones["exposure_score"] = minmax(zones["activity_count"]).round(6)

# =========================
# 3) Part 3: Accessibility & Underserved (distance-decay to K nearest points)
# =========================
zones_m = zones.to_crs("EPSG:3857")
acts_m = activities.to_crs("EPSG:3857")

zone_pts = zones_m.copy()
zone_pts["geometry"] = zone_pts.geometry.centroid

K = 5
alpha = 2000  # meters

svc_coords = np.array([(g.x, g.y) for g in acts_m.geometry])

def nearest_k_distances(px, py, coords, k):
    dx = coords[:, 0] - px
    dy = coords[:, 1] - py
    d = np.sqrt(dx * dx + dy * dy)
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

zones = zones.merge(
    zone_pts[["zone_id", "access_raw", "access_score", "underserved_score"]],
    on="zone_id",
    how="left"
)

# =========================
# 4) Part 4: SSI (Spatial Sustainability Index)
# =========================
# Pressures: higher => higher priority
zones["env_pressure"] = zones["exposure_score"]
zones["social_pressure"] = zones["underserved_score"]

# Simple ops proxy (keep distinct if you have another indicator later)
zones["ops_pressure"] = zones["exposure_score"]

w_env, w_soc, w_ops = 0.4, 0.4, 0.2
zones["ssi_score"] = (
    w_env * zones["env_pressure"] +
    w_soc * zones["social_pressure"] +
    w_ops * zones["ops_pressure"]
).round(6)

# =========================
# 5) Part 5: Decision Layer (rules + constraints)
# =========================
SSI_THRESHOLD = 0.60
CRITICAL_PRESSURE = 0.70
MAX_ZONES = 5

candidates = zones[
    (zones["ssi_score"] >= SSI_THRESHOLD) &
    (
        (zones["env_pressure"] >= CRITICAL_PRESSURE) |
        (zones["social_pressure"] >= CRITICAL_PRESSURE)
    )
].copy()

# If strict rules produce too few candidates, relax gracefully (still deterministic)
if len(candidates) < MAX_ZONES:
    # Relax: keep SSI threshold only
    candidates = zones[zones["ssi_score"] >= SSI_THRESHOLD].copy()

if len(candidates) < MAX_ZONES:
    # Relax further: take top SSI overall
    candidates = zones.copy()

final = candidates.sort_values("ssi_score", ascending=False).head(MAX_ZONES).copy()

# =========================
# 6) Explainability: dominant pressure label
# =========================
def dominant_pressure(row):
    pressures = {
        "ENV": row["env_pressure"],
        "SOCIAL": row["social_pressure"],
        "OPS": row["ops_pressure"]
    }
    dom = max(pressures, key=pressures.get)
    return dom

final["dominant_pressure"] = final.apply(dominant_pressure, axis=1)

# =========================
# 7) Output
# =========================
print("\n=== FINAL DSS RECOMMENDATION (Top Zones to Act On) ===")
print(final[[
    "zone_id",
    "ssi_score",
    "env_pressure",
    "social_pressure",
    "ops_pressure",
    "dominant_pressure",
    "activity_count"
]].to_string(index=False))

print("\n=== RULES USED ===")
print("SSI_THRESHOLD:", SSI_THRESHOLD)
print("CRITICAL_PRESSURE:", CRITICAL_PRESSURE)
print("MAX_ZONES:", MAX_ZONES)
print("Weights (env, social, ops):", (w_env, w_soc, w_ops), "sum =", w_env + w_soc + w_ops)

print("\n=== SANITY CHECKS ===")
print("Total zones:", len(zones))
print("Total activities:", len(activities))
print("Total counted (sum activity_count):", int(zones["activity_count"].sum()))
print("Candidates count:", len(candidates))

# =========================
# 8) Optional: export GeoJSON with DSS outputs
# =========================
# zones.to_file("zones_with_dss.geojson", driver="GeoJSON")
# final.to_file("final_recommendation_zones.geojson", driver="GeoJSON")
# print("\nSaved: zones_with_dss.geojson & final_recommendation_zones.geojson")
