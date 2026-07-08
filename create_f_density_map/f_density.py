import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

filename = "italy_20260615.csv"

# Load the file
# The file uses | as separator
df = pd.read_csv(filename, sep="|", dtype=str)

df.columns = df.columns.str.strip()

# Test lines to print the columns
# print("Columns read by pandas:")
# print(df.columns)
# print(df.head())

# Rename the columns
df = df.rename(columns={
    "@id": "id",
    "@lat": "lat",
    "@lon": "lon"
})

# Reformat data
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

# This removes all rows where either lat or lon is missing
df = df.dropna(subset=["lat", "lon"])

# This keeps only rows where the column amenity is exactly equal to drinking_water
df = df[df["amenity"] == "drinking_water"]

# Remove missing and wrong data
df = df[
    df["lon"].between(6, 19) &
    df["lat"].between(35, 48)
]

print(f"Number of fountains: {len(df)}")

# Create geopandas database
gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["lon"], df["lat"]),
    crs="EPSG:4326"   # WGS84 lon/lat
)

# Project to meters
gdf = gdf.to_crs("EPSG:3035")

# Load Italy boundaries
italy = gpd.read_file("ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp")
italy = italy[italy["ADMIN"] == "Italy"]
italy = italy.to_crs("EPSG:3035")

# Clip data points to Italy
italy_geom = italy.geometry.union_all()
gdf = gdf[gdf.geometry.within(italy_geom)]

# Create figure
xmin, ymin, xmax, ymax = italy.total_bounds
fig, ax = plt.subplots(figsize=(8, 10))

# Settings for hexagon bin
hb = ax.hexbin(
    gdf.geometry.x,
    gdf.geometry.y,
    gridsize=150, # controls resolution
    mincnt=1,
    cmap="magma",
    extent=(xmin, xmax, ymin, ymax),
    norm=LogNorm(), # log scale on
    linewidths=0,
    alpha=0.9
)

# Plot the boundary of Italy
italy.boundary.plot(ax=ax, linewidth=0.7, color="black")

# Add a colorbar high 75% of image
# The colorbar explains how colors correspond to fountain counts
cbar = plt.colorbar(hb, ax=ax, shrink=0.75)
# Title of color bar
cbar.set_label("Fountains per hexagon, log scale")

ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)

ax.set_axis_off()
ax.set_title("Public drinking-water fountains in Italy", fontsize=15)

# Automatically adjust spacing so the title, map, and colorbar fit nicely
plt.tight_layout()

# Save the figure as a PNG file.
# `dpi=300` gives print-quality resolution.
plt.savefig("fountain_density_italy_pitch.png", dpi=300)
plt.show()
