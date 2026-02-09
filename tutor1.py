import geopandas as gpd

zones = gpd.read_file("zones.geojson")
points = gpd.read_file("activities.geojson")

# pastikan CRS sama
points = points.to_crs(zones.crs)

# spatial join
joined = gpd.sjoin(points, zones, predicate="within")

# hitung jumlah aktivitas per zona
zone_counts = joined.groupby("zone_id").size().reset_index(name="activity_count")
zones = zones.merge(zone_counts, on="zone_id", how="left").fillna(0)

# normalisasi (0..1)
zones["activity_score"] = (
    zones["activity_count"] - zones["activity_count"].min()
) / (
    zones["activity_count"].max() - zones["activity_count"].min()
)

print(zones.sort_values("activity_score", ascending=False).head(10)[
    ["zone_id", "activity_count", "activity_score"]
])
