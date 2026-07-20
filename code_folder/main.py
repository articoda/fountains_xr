# Import Path to handle file paths cleanly.
from pathlib import Path

# Import the function that loads and prepares fountain data.
from auxi.fountains import load_fountains

# Import functions for loading Italy boundaries and clipping points to Italy.
from auxi.boundaries import load_country_boundary, clip_points_to_boundary

# Import the function that creates the original hexbin density plot.
from auxi.plots import plot_fountain_density_hexbin

# Import the rasterized fountain plotting function.
from auxi.plots import plot_fountain_density_raster, plot_aggregated_fountain_raster

# Import the population-raster functions.
from auxi.population import (
    reproject_population_raster,
    rasterize_fountains_like_population
)


# Define the project folder.
# This means paths are relative to the folder containing this file.
PROJECT_DIR = Path(__file__).resolve().parent

# Define the path to the fountain CSV file.
FOUNTAIN_FILE = PROJECT_DIR / "italy_20260615.csv"

# Define the path to the Natural Earth country shapefile.
BOUNDARY_FILE = PROJECT_DIR / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.shp"

# Define the path to the original WorldPop raster.
WORLDPOP_FILE = PROJECT_DIR / "ita_ppp_2020_UNadj.tif"

# Define the path to the reprojected WorldPop raster.
# This raster is in EPSG:3035, so distances are in meters.
WORLDPOP_3035_FILE = PROJECT_DIR / "ita_ppp_2020_UNadj_EPSG3035_100m.tif"

# Define the output path for the original hexbin plot.
OUTPUT_HEXBIN_FIGURE = PROJECT_DIR / "fountain_density_italy_pitch.png"

# Define the output path for the rasterized fountain plot.
OUTPUT_RASTER_FIGURE = PROJECT_DIR / "fountain_density_italy_rasterized.png"


def main():
    # Load, clean, and project the fountain data.
    fountains = load_fountains(
        filename=FOUNTAIN_FILE,
        output_crs="EPSG:3035"
    )

    # Load Italy boundary and project it to the same CRS as the fountains.
    italy = load_country_boundary(
        shapefile=BOUNDARY_FILE,
        country_name="Italy",
        output_crs="EPSG:3035"
    )

    # Keep only fountain points that are actually inside the Italy polygon.
    fountains = clip_points_to_boundary(fountains, italy)

    # Print the number of fountains after all cleaning and clipping.
    print(f"Number of fountains inside Italy: {len(fountains):,}")

    # Reproject the WorldPop raster to EPSG:3035 if it does not already exist.
    # This gives us a raster grid in meters.
    if not WORLDPOP_3035_FILE.exists():
        print("Reprojecting WorldPop raster to EPSG:3035...")

        reproject_population_raster(
            input_raster=WORLDPOP_FILE,
            output_raster=WORLDPOP_3035_FILE,
            dst_crs="EPSG:3035",
            resolution=100
        )

        print(f"Saved reprojected raster to: {WORLDPOP_3035_FILE}")

    else:
        print(f"Reprojected WorldPop raster already exists: {WORLDPOP_3035_FILE}")

    # Rasterize the fountain points onto the same grid as the population raster.
    fountain_raster, raster_transform, raster_crs = rasterize_fountains_like_population(
        fountains=fountains,
        population_raster=WORLDPOP_3035_FILE
    )

    # Print how many fountains were burned into the raster.
    # This should be close to the number of fountain points.
    # If it is smaller, several fountains may be falling in the same raster cell.
    print(f"Total fountain count in raster: {int(fountain_raster.sum()):,}")

    # Create and save the original hexbin density plot.
    # This is still better for the national pitch figure.
    plot_fountain_density_hexbin(
        fountains=fountains,
        boundary=italy,
        output_file=OUTPUT_HEXBIN_FIGURE,
        gridsize=150,
        title="Public drinking-water fountains in Italy"
    )

    # Create and save the rasterized fountain plot.
    # This is mainly a test that fountains and population now live on the same grid.
    plot_aggregated_fountain_raster(
    fountain_raster=fountain_raster,
    raster_transform=raster_transform,
    raster_crs=raster_crs,
    boundary=italy,
    output_file=PROJECT_DIR / "fountain_density_italy_raster_1km.png",
    aggregation_factor=50,
    title="Public drinking-water fountains in Italy"
)


# Run main() only when this file is executed directly.
if __name__ == "__main__":
    main()
