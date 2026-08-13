# Import pandas for tabular data handling.
import pandas as pd

# Import geopandas for geographic data handling.
import geopandas as gpd


def load_fountains(filename, output_crs="EPSG:3035"):
    """
    Load the OSM fountain CSV, clean it, convert it to a GeoDataFrame,
    and project it to a metric CRS.
    """

    # Read the CSV file.
    # Your file uses | as the separator.
    df = pd.read_csv(filename, sep="|", dtype=str)

    # Remove accidental spaces around column names.
    df.columns = df.columns.str.strip()

    # Rename OSM-style columns to simpler names.
    df = df.rename(columns={
        "@id": "id",
        "@lat": "lat",
        "@lon": "lon"
    })

    # Convert latitude values from text to numbers.
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")

    # Convert longitude values from text to numbers.
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    # Remove rows where latitude or longitude is missing.
    df = df.dropna(subset=["lat", "lon"])

    # Keep only rows tagged as drinking water.
    df = df[df["amenity"] == "drinking_water"]

    # Remove obviously wrong coordinates using a rough Italy bounding box.
    df = df[
        df["lon"].between(6, 19) &
        df["lat"].between(35, 48)
    ]

    # Convert the dataframe to a GeoDataFrame with point geometries.
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326"
    )

    # Project the points to a metric CRS.
    # EPSG:3035 is useful for Europe-wide area/distance calculations.
    gdf = gdf.to_crs(output_crs)

    # Return the cleaned and projected fountain GeoDataFrame.
    return gdf
