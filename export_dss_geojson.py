import geopandas as gpd
import numpy as np

def minmax(series):
    mn = float(series.min())
    mx = float(series.max())
    if mx == mn:
        return np.zeros(len(series), dtype=float)
    return (series - mn) / (mx - mn)

# ====== INPUT FILES (pastikan sesuai lokasi Anda) ======
ZONES_PATH = "zones.geojson"
ACTIVITIES_PATH = "activities.geojson"

# ====== OUTPUT ======
OUT_GEOJSON = "leaflet/zones_with_dss.geojson"

# =========================
# 1) Load data
# =========================
zones = gpd.read_file(ZONES_PATH)
activities = gpd.read_file(ACTIVITIES_PATH)

if zones.crs is None:
    zones = zones.set_crs("EPSG:4326")
if activities.crs is None:
    activities = activities.set_crs(zones.crs)
activities = activities.to_crs(zones.crs)

# =========================
# 2) Part 2: Exposure
# =========================
joined = gpd.sjoin(activities, zones[["zone_id", "geometry"]], predicate="within", how="inner")
counts = joined.groupby("zone_id").size().reset_index(name="activity_count")

zones = zones.merge(counts, on="zone_id", how="left")
zones["activity_count"] = zones["activity_count"].fillna(0).astype(int)
zones["exposure_score"] = minmax(zones["activity_count"]).round(6)

# =========================
# 3) Part 3: Accessibility & Underserved
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
    return np.partition(d, k - 1)[:k]

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
# 4) Part 4: SSI
# =========================
zones["env_pressure"] = zones["exposure_score"]
zones["social_pressure"] = zones["underserved_score"]
zones["ops_pressure"] = zones["exposure_score"]  # proxy sederhana

w_env, w_soc, w_ops = 0.4, 0.4, 0.2
zones["ssi_score"] = (
    w_env * zones["env_pressure"] +
    w_soc * zones["social_pressure"] +
    w_ops * zones["ops_pressure"]
).round(6)

# =========================
# 5) Part 5: DSS Decision Layer
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

if len(candidates) < MAX_ZONES:
    candidates = zones[zones["ssi_score"] >= SSI_THRESHOLD].copy()
if len(candidates) < MAX_ZONES:
    candidates = zones.copy()

final = candidates.sort_values("ssi_score", ascending=False).head(MAX_ZONES).copy()

def dominant_pressure(row):
    pressures = {"ENV": row["env_pressure"], "SOCIAL": row["social_pressure"], "OPS": row["ops_pressure"]}
    return max(pressures, key=pressures.get)

zones["dominant_pressure"] = zones.apply(dominant_pressure, axis=1)

# Flag recommended zones (top-N decision output)
zones["is_recommended"] = zones["zone_id"].isin(final["zone_id"]).astype(int)

# Optional: rank (1..N) for recommended zones
rank_map = {zid: i+1 for i, zid in enumerate(final["zone_id"].tolist())}
zones["recommend_rank"] = zones["zone_id"].map(rank_map).fillna(0).astype(int)

# Keep properties clean for web map
keep_cols = [
    "zone_id",
    "activity_count",
    "access_score",
    "underserved_score",
    "env_pressure",
    "social_pressure",
    "ops_pressure",
    "ssi_score",
    "dominant_pressure",
    "is_recommended",
    "recommend_rank",
    "geometry"
]
zones_out = zones[keep_cols].copy()

# Ensure output is WGS84 for Leaflet
zones_out = zones_out.to_crs("EPSG:4326")
zones_out.to_file(OUT_GEOJSON, driver="GeoJSON")

print("Saved:", OUT_GEOJSON)
print("Recommended zones:", final["zone_id"].tolist())
