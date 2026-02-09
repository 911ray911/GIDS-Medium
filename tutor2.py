import geopandas as gpd
import numpy as np

def minmax(series):
    mn = float(series.min())
    mx = float(series.max())
    if mx == mn:
        return np.zeros(len(series), dtype=float)
    return (series - mn) / (mx - mn)

# 1) Load data
zones = gpd.read_file("zones.geojson")
activities = gpd.read_file("activities.geojson")

# 2) Ensure CRS is consistent
if zones.crs is None:
    zones = zones.set_crs("EPSG:4326")
if activities.crs is None:
    activities = activities.set_crs(zones.crs)

activities = activities.to_crs(zones.crs)

# 3) Spatial join: activities within zones (exposure)
joined = gpd.sjoin(activities, zones[["zone_id", "geometry"]], predicate="within", how="inner")
not_joined = activities[~activities.index.isin(joined.index)]
print("Activities not assigned to any zone:", len(not_joined))
# 4) Count exposure per zone
exposure = joined.groupby("zone_id").size().reset_index(name="exposure_count")

zones = zones.merge(exposure, on="zone_id", how="left")
zones["exposure_count"] = zones["exposure_count"].fillna(0).astype(int)

# 5) Normalize exposure -> exposure_score (0..1)
zones["exposure_score"] = minmax(zones["exposure_count"]).round(6)

# 6) Interpret exposure as vulnerability (exposure-driven vulnerability)
zones["vulnerability_score"] = zones["exposure_score"]

# 7) Output: top priority zones
top10 = zones.sort_values(["vulnerability_score", "exposure_count"], ascending=False).head(10)
print("\n=== TOP 10 Zones by Vulnerability (Exposure-driven) ===")
print(top10[["zone_id", "exposure_count", "exposure_score", "vulnerability_score"]].to_string(index=False))

# 8) Sanity checks
print("\n=== SANITY CHECKS ===")
print("Total zones:", len(zones))
print("Total activities:", len(activities))
print("Total counted via join (sum exposure_count):", int(zones["exposure_count"].sum()))

# 9) Optional: export zones with scores for mapping
# zones.to_file("zones_with_vulnerability.geojson", driver="GeoJSON")
# print("\nSaved: zones_with_vulnerability.geojson")
