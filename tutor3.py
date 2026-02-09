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
services = gpd.read_file("activities.geojson")  # reinterpret as service points

# Ensure CRS exists
if zones.crs is None:
    zones = zones.set_crs("EPSG:4326")
if services.crs is None:
    services = services.set_crs(zones.crs)

# =========================
# 2) Project to metric CRS (meters)
# =========================
# EPSG:3857 is OK for a tutorial; for best accuracy in Indonesia you can later switch to UTM (e.g., EPSG:32748).
zones_m = zones.to_crs("EPSG:3857")
services_m = services.to_crs("EPSG:3857")

# =========================
# 3) Use zone centroids as representative points
# =========================
zone_pts = zones_m.copy()
zone_pts["geometry"] = zone_pts.geometry.centroid

# =========================
# 4) Compute nearest-K distances
# =========================
K = 5
alpha = 2000  # meters (distance decay scale)

# Convert service geometries to Nx2 coordinate array
svc_coords = np.array([(g.x, g.y) for g in services_m.geometry])

def nearest_k_distances(px, py, coords, k):
    dx = coords[:, 0] - px
    dy = coords[:, 1] - py
    d = np.sqrt(dx * dx + dy * dy)
    # take k smallest distances
    return np.partition(d, k-1)[:k]

nearest_dists = []
for g in zone_pts.geometry:
    d_k = nearest_k_distances(g.x, g.y, svc_coords, K)
    nearest_dists.append(np.sort(d_k))

nearest_dists = np.array(nearest_dists)  # shape: (n_zones, K)

# =========================
# 5) Distance-decay accessibility score
# access_raw = sum( 1 / (1 + d/alpha) ) over K nearest services
# =========================
access_raw = np.sum(1 / (1 + (nearest_dists / alpha)), axis=1)
zone_pts["access_raw"] = access_raw

# Normalize to 0..1
zone_pts["access_score"] = minmax(zone_pts["access_raw"]).round(6)

# Underserved = inverse accessibility
zone_pts["underserved_score"] = (1 - zone_pts["access_score"]).round(6)

# =========================
# 6) Output: Top underserved zones
# =========================
top10_underserved = zone_pts.sort_values(
    ["underserved_score", "access_raw"], ascending=False
).head(10)

print("\n=== TOP 10 UNDER-SERVED ZONES (lowest accessibility) ===")
print(top10_underserved[["zone_id", "access_raw", "access_score", "underserved_score"]].to_string(index=False))

# =========================
# 7) Optional: export results for mapping
# =========================
# Save as polygon zones with scores (merge back to original polygons)
zones_out = zones_m.merge(
    zone_pts[["zone_id", "access_raw", "access_score", "underserved_score"]],
    on="zone_id",
    how="left"
)

# zones_out.to_file("zones_with_accessibility.geojson", driver="GeoJSON")
# print("\nSaved: zones_with_accessibility.geojson")

# =========================
# 8) Sanity checks
# =========================
print("\n=== SANITY CHECKS ===")
print("Zones:", len(zone_pts))
print("Services:", len(services_m))
print("K used:", K)
print("alpha (m):", alpha)
print("access_raw range:", float(zone_pts['access_raw'].min()), "to", float(zone_pts['access_raw'].max()))
