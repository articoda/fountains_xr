# Import Path to handle file paths cleanly.
from pathlib import Path

# Import the function that loads and prepares fountain data.
from auxi.fountains import load_fountains

# Import functions for loading Italy boundaries and clipping points to Italy.
from auxi.boundaries import load_country_boundary, clip_points_to_boundary

# Import the function that creates the density plot.
from auxi.plots import plot_fountain_density_hexbin


# Define the project folder.
# This means paths are relative to the folder containing this file.
PROJECT_DIR = Path(__file__).resolve().parent

# Define the path to the fountain CSV file.
FOUNTAIN_FILE = PROJECT_DIR / "italy_20260615.csv"

# Define the path to the Natural Earth country shapefile.
BOUNDARY_FILE = PROJECT_DIR / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.shp"

# Define the output figure path.
OUTPUT_FIGURE = PROJECT_DIR / "fountain_density_italy_pitch.png"


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

    # Create and save the fountain density plot.
    plot_fountain_density_hexbin(
        fountains=fountains,
        boundary=italy,
        output_file=OUTPUT_FIGURE,
        gridsize=150,
        title="Public drinking-water fountains in Italy"
    )


# Run main() only when this file is executed directly.
if __name__ == "__main__":
    main()
