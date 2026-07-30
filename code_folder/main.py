# Import Path to handle file paths cleanly.
from pathlib import Path

# Import numpy for quick raster diagnostics.
import numpy as np

# Import the function that loads and prepares fountain data.
from auxi.fountains import load_fountains

# Import functions for loading Italy boundaries and clipping points to Italy.
from auxi.boundaries import load_country_boundary, clip_points_to_boundary

# Import plotting functions.
from auxi.plots import (
    plot_fountain_density_hexbin,
    plot_aggregated_fountain_raster,
    plot_accessible_population_raster,
    plot_accessibility_share_raster
)

# Import the population-raster functions.
from auxi.population import (
    reproject_population_raster,
    rasterize_fountains_like_population
)

# Import the accessibility computation.

from auxi.accessibility import (
    compute_population_accessibility,
    compute_accessibility_share_grid
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

# Define output paths.
OUTPUT_HEXBIN_FIGURE = PROJECT_DIR / "fountain_density_italy_pitch.png"
OUTPUT_AGGREGATED_RASTER_FIGURE = PROJECT_DIR / "fountain_density_italy_raster_25km.png"
OUTPUT_ACCESSIBLE_POPULATION_250M = PROJECT_DIR / "population_within_250m_of_fountain.png"
OUTPUT_ACCESSIBILITY_SHARE_250M = PROJECT_DIR / "share_population_within_250m_of_fountain.png"


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
    print(f"Original fountain points: {len(fountains):,}")
    print(f"Total fountain count in raster: {int(fountain_raster.sum()):,}")
    print(f"Raster cells with at least one fountain: {np.count_nonzero(fountain_raster):,}")
    print(f"Maximum fountains in one raster cell: {int(fountain_raster.max())}")

    # Compute population accessibility to fountains.
    accessibility_results, accessible_population_250m, pop_transform, pop_crs = compute_population_accessibility(
        population_raster=WORLDPOP_3035_FILE,
        fountain_raster=fountain_raster,
        boundary=italy,
        thresholds=(250, 500),
        map_threshold=250
    )

    # Print accessibility summary.
    print()
    print("Population accessibility to drinking-water fountains")
    print("---------------------------------------------------")
    print(f"Total population: {accessibility_results['total_population']:,.0f}")
    print(f"Population within 250 m: {accessibility_results['population_within_250m']:,.0f}")
    print(f"Share within 250 m: {accessibility_results['share_within_250m']:.2%}")
    print(f"Population within 500 m: {accessibility_results['population_within_500m']:,.0f}")
    print(f"Share within 500 m: {accessibility_results['share_within_500m']:.2%}")

    # Plot population living within 250 m of a fountain.
    plot_accessible_population_raster(
        accessible_population_map=accessible_population_250m,
        raster_transform=pop_transform,
        raster_crs=pop_crs,
        boundary=italy,
        output_file=OUTPUT_ACCESSIBLE_POPULATION_250M,
        threshold=250,
        title="Population within 250 m of a drinking-water fountain"
    )

    # Compute an aggregated map where each large cell contains the percentage
    # of population living within 250 m of a fountain.
    (
        share_grid_results,
        accessibility_share_250m,
        accessible_population_agg,
        total_population_agg,
        share_grid_transform,
        share_grid_crs
    ) = compute_accessibility_share_grid(
        population_raster=WORLDPOP_3035_FILE,
        fountain_raster=fountain_raster,
        boundary=italy,
        threshold=250,
        aggregation_factor=25,
        min_total_population=10
    )

    # Print summary of the aggregated accessibility map.
    print()
    print("Aggregated accessibility map")
    print("----------------------------")
    print(f"Threshold: {share_grid_results['threshold_m']} m")
    print(
        "Aggregated cell size: "
        f"{share_grid_results['aggregated_cell_size_x_m']:.0f} m × "
        f"{share_grid_results['aggregated_cell_size_y_m']:.0f} m"
    )
    print(f"Overall share accessible: {share_grid_results['share_accessible']:.2%}")

    # Plot the percentage accessibility map.
    plot_accessibility_share_raster(
        accessibility_share=accessibility_share_250m,
        raster_transform=share_grid_transform,
        raster_crs=share_grid_crs,
        boundary=italy,
        output_file=OUTPUT_ACCESSIBILITY_SHARE_250M,
        threshold=250,
        title="Share of population within 250 m of a drinking-water fountain"
    )

    # Create and save the original hexbin density plot.
    # This is still better for the national pitch figure.
    plot_fountain_density_hexbin(
        fountains=fountains,
        boundary=italy,
        output_file=OUTPUT_HEXBIN_FIGURE,
        gridsize=150,
        title="Public drinking-water fountains in Italy"
    )

    # Create and save the aggregated rasterized fountain plot.
    # Since the population raster is 100 m, aggregation_factor=25 gives 2.5 km cells.
    plot_aggregated_fountain_raster(
        fountain_raster=fountain_raster,
        raster_transform=raster_transform,
        raster_crs=raster_crs,
        boundary=italy,
        output_file=OUTPUT_AGGREGATED_RASTER_FIGURE,
        aggregation_factor=25,
        title="Public drinking-water fountains in Italy"
    )


# Run main() only when this file is executed directly.
if __name__ == "__main__":
    main()
