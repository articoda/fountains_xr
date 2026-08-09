# Import argparse to read command-line options.
import argparse

# Import Path to handle file paths cleanly.
from pathlib import Path

# Import numpy for quick raster diagnostics.
import numpy as np

# Import the function that loads and prepares fountain data.
from auxi.fountains import load_fountains

# Import functions for loading Italy boundaries and clipping points to Italy.
from auxi.boundaries import (
    load_country_boundary,
    load_boundary_layer,
    select_boundary,
    clip_points_to_boundary,
    print_boundary_columns
)

# Import plotting functions.
from auxi.plots import (
    plot_fountain_density_hexbin,
    plot_aggregated_fountain_raster,
    plot_accessible_population_raster,
    plot_accessibility_share_raster,
    choose_plot_settings
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

# Column containing region names in the ISTAT regions shapefile.
# If this does not work, print the columns and adjust it.
REGION_NAME_COLUMN = "DEN_REG"

# Define the path to the fountain CSV file.
FOUNTAIN_FILE = PROJECT_DIR / "italy_20260615.csv"

# Define the path to the Natural Earth country shapefile.
BOUNDARY_FILE = PROJECT_DIR / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.shp"

# Define the path to the ISTAT regions shapefile.
# Change this path to the actual file name after unzipping the ISTAT data.
ISTAT_REGIONS_FILE = (
    PROJECT_DIR
    / "limiti_istat"
    / "Reg01012026"
    / "Reg01012026_WGS84.shp"
)

# Define the path to the ISTAT municipalities shapefile.
# Change this to the actual file name after unzipping the ISTAT data.
ISTAT_TOWNS_FILE = (
    PROJECT_DIR
    / "limiti_istat"
    / "Com01012026"
    / "Com01012026_WGS84.shp"
)

# Column containing town/municipality names in the ISTAT municipalities shapefile.
TOWN_NAME_COLUMN = "COMUNE"

# Define the path to the original WorldPop raster.
WORLDPOP_FILE = PROJECT_DIR / "ita_ppp_2020_UNadj.tif"

# Define the path to the reprojected WorldPop raster.
# This raster is in EPSG:3035, so distances are in meters.
WORLDPOP_3035_FILE = PROJECT_DIR / "ita_ppp_2020_UNadj_EPSG3035_100m.tif"

# Parse command-line arguments.
# Examples:
# python main.py -l italy
# python main.py -l region -r Piemonte
# python main.py -l region -r "Emilia-Romagna"

def parse_arguments():
    """
    Parse command-line arguments.

    Examples:
        python main.py -l italy
        python main.py -l region -r Piemonte
        python main.py -l town -t Parma
        python main.py -l town -t "Reggio nell'Emilia"
    """

    parser = argparse.ArgumentParser(
        description="Analyse public drinking-water fountain accessibility."
    )

    parser.add_argument(
        "-l",
        "--level",
        choices=["italy", "region", "town"],
        default="italy",
        help="Analysis level: 'italy', 'region', or 'town'. Default: italy."
    )

    parser.add_argument(
        "-r",
        "--region",
        default=None,
        help="Region name, used only when --level region. Example: Piemonte."
    )

    parser.add_argument(
        "-t",
        "--town",
        default=None,
        help="Town/municipality name, used only when --level town. Example: Parma."
    )

    args = parser.parse_args()

    if args.level == "region" and args.region is None:
        parser.error("When using -l region, you must also specify -r REGION_NAME.")

    if args.level == "town" and args.town is None:
        parser.error("When using -l town, you must also specify -t TOWN_NAME.")

    return args

# Define output paths.
def safe_name(name):
    """
    Make a safe folder/file name from an area name.
    """

    return (
        name.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("'", "")
    )


def main(analysis_level, region_name=None, town_name=None):

    # Decide the area label used for folders and titles.
    if analysis_level == "italy":
        area_label = "Italy"

    elif analysis_level == "region":
        area_label = region_name

    elif analysis_level == "town":
        area_label = town_name

    else:
        raise ValueError(f"Unknown analysis level: {analysis_level}")
    # Create a safe folder name.
    area_folder_name = safe_name(area_label)

    # Create an output folder specific to the selected area.
    output_dir = PROJECT_DIR / "plots" / area_folder_name

    # Create the folder if it does not exist.
    output_dir.mkdir(parents=True, exist_ok=True)

    # Choose plot settings automatically from the analysis scale.
    plot_settings = choose_plot_settings(analysis_level)

    aggregation_factor = plot_settings["aggregation_factor"]
    min_total_population = plot_settings["min_total_population"]
    hexbin_gridsize = plot_settings["hexbin_gridsize"]
    cell_label = plot_settings["cell_label"]

    # Define output paths.
    output_hexbin_figure = output_dir / "fountain_density_pitch.png"

    output_accessible_population_250m = (
        output_dir / "population_within_250m_of_fountain.png"
    )

    output_accessibility_share_250m = (
        output_dir / f"share_population_within_250m_of_fountain_{cell_label}.png"
    )

    output_aggregated_raster_figure = (
        output_dir / f"fountain_density_raster_{cell_label}.png"
    )

    # Load, clean, and project the fountain data.
    fountains = load_fountains(
        filename=FOUNTAIN_FILE,
        output_crs="EPSG:3035"
    )

        # Load the analysis boundary.
    if analysis_level == "italy":

        # Load Italy boundary from Natural Earth.
        area = load_country_boundary(
            shapefile=BOUNDARY_FILE,
            country_name="Italy",
            output_crs="EPSG:3035"
        )

    elif analysis_level == "region":

        # Load all ISTAT regions.
        regions = load_boundary_layer(
            shapefile=ISTAT_REGIONS_FILE,
            output_crs="EPSG:3035"
        )

        # Select the chosen region.
        area = select_boundary(
            boundaries=regions,
            column=REGION_NAME_COLUMN,
            value=region_name
        )

    elif analysis_level == "town":

        # Load all ISTAT towns/municipalities.
        towns = load_boundary_layer(
            shapefile=ISTAT_TOWNS_FILE,
            output_crs="EPSG:3035"
        )

        # Optional debugging line if TOWN_NAME_COLUMN does not work.
        # print_boundary_columns(towns)

        # Select the chosen town.
        area = select_boundary(
            boundaries=towns,
            column=TOWN_NAME_COLUMN,
            value=town_name
        )

    else:
        raise ValueError(f"Unknown analysis level: {analysis_level}")

    # Keep only fountain points that are inside the selected area.
    fountains = clip_points_to_boundary(fountains, area)

    # Print the number of fountains after all cleaning and clipping.
    print(f"Analysis area: {area_label}")
    print(f"Number of fountains inside area: {len(fountains):,}")

    # Choose plot settings automatically from the analysis scale.
    plot_settings = choose_plot_settings(analysis_level)

    aggregation_factor = plot_settings["aggregation_factor"]
    min_total_population = plot_settings["min_total_population"]
    hexbin_gridsize = plot_settings["hexbin_gridsize"]
    cell_label = plot_settings["cell_label"]

    output_aggregated_raster_figure = (
        output_dir / f"fountain_density_raster_{cell_label}.png"
    )

    output_accessibility_share_250m = (
        output_dir / f"share_population_within_250m_of_fountain_{cell_label}.png"
    )

    print(f"Aggregation factor: {aggregation_factor}")
    print(f"Aggregated cell size: {cell_label}")

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
        boundary=area,
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
        boundary=area,
        output_file=output_accessible_population_250m,
        threshold=250,
        title=f"Population within 250 m\nof a drinking-water fountain in {area_label}"
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
        boundary=area,
        threshold=250,
        aggregation_factor=aggregation_factor,
        min_total_population=min_total_population
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
        boundary=area,
        output_file=output_accessibility_share_250m,
        threshold=250,
        title=f"Share of population\nwithin 250 m of a drinking-water fountain in {area_label}"
    )

    # Create and save the original hexbin density plot.
    # This is still better for the national pitch figure.
    plot_fountain_density_hexbin(
        fountains=fountains,
        boundary=area,
        output_file=output_hexbin_figure,
        gridsize=hexbin_gridsize,
        title=f"Public drinking-water fountains in {area_label}"
    )

    # Create and save the aggregated rasterized fountain plot.
    # Since the population raster is 100 m, aggregation_factor=25 gives 2.5 km cells.
    plot_aggregated_fountain_raster(
        fountain_raster=fountain_raster,
        raster_transform=raster_transform,
        raster_crs=raster_crs,
        boundary=area,
        output_file=output_aggregated_raster_figure,
        aggregation_factor=aggregation_factor,
        title=f"Public drinking-water fountains in {area_label}"
    )


# Run main() only when this file is executed directly.
if __name__ == "__main__":
    args = parse_arguments()

    main(
        analysis_level=args.level,
        region_name=args.region,
        town_name=args.town
    )
