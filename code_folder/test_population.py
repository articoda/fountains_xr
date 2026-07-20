# Import Path to handle file paths cleanly.
from pathlib import Path

# Import numpy for numerical operations.
import numpy as np

# Import rasterio to read the WorldPop raster.
import rasterio

# Import mask to clip the raster to Italy.
from rasterio.mask import mask

# Import the boundary-loading function.
from auxi.boundaries import load_country_boundary

# Import population functions.
from auxi.population import (
    reproject_population_raster,
    plot_worldpop_density
)


# Define the project folder.
PROJECT_DIR = Path(__file__).resolve().parent

# Define the path to the Natural Earth country shapefile.
BOUNDARY_FILE = PROJECT_DIR / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.shp"

# Define the path to the original WorldPop raster.
WORLDPOP_FILE = PROJECT_DIR / "ita_ppp_2020_UNadj.tif"

# Define the path to the reprojected WorldPop raster.
WORLDPOP_3035_FILE = PROJECT_DIR / "ita_ppp_2020_UNadj_EPSG3035_100m.tif"

# Define the output file for the test population plot.
OUTPUT_POPULATION_PLOT = PROJECT_DIR / "population_density_italy_test.png"


def inspect_reprojected_population_raster(raster_path, boundary, min_population=0):
    """
    Inspect the reprojected population raster clipped to Italy.

    This does not convert cells to GeoDataFrame points.
    It only reads the raster as an array and prints basic diagnostics.
    """

    # Open the reprojected raster.
    with rasterio.open(raster_path) as src:

        # Print basic raster metadata.
        print("Raster CRS:", src.crs)
        print("Raster width:", src.width)
        print("Raster height:", src.height)
        print("Total raster pixels:", f"{src.width * src.height:,}")
        print("Raster data type:", src.dtypes[0])
        print("Raster NoData value:", src.nodata)
        print("Raster bounds:", src.bounds)
        print("Pixel width, m:", abs(src.transform.a))
        print("Pixel height, m:", abs(src.transform.e))

        # Reproject the Italy boundary to the raster CRS.
        boundary_raster_crs = boundary.to_crs(src.crs)

        # Clip the raster to Italy.
        pop_image, pop_transform = mask(
            src,
            list(boundary_raster_crs.geometry),
            crop=True,
            filled=True
        )

        # Extract the first raster band as float.
        pop = pop_image[0].astype(float)

        # Store NoData value.
        nodata = src.nodata

    # Select finite raster cells.
    valid = np.isfinite(pop)

    # Remove NoData cells, if NoData is defined.
    if nodata is not None:
        valid = valid & (pop != nodata)

    # Keep only cells above the minimum population threshold.
    valid = valid & (pop > min_population)

    # Count valid populated cells.
    number_of_populated_cells = int(valid.sum())

    # Sum population over valid cells.
    total_population = float(pop[valid].sum())

    # Estimate memory needed for simple raster arrays.
    # One float64 array has 8 bytes per cell.
    one_array_memory_gb = pop.size * 8 / 1e9

    # Estimate memory required if converted to GeoDataFrame points.
    estimated_gdf_memory_gb = number_of_populated_cells * 400 / 1e9

    # Print clipped raster information.
    print()
    print("After clipping to Italy:")
    print("Clipped raster shape:", pop.shape)
    print("Clipped raster pixels:", f"{pop.size:,}")
    print(f"Cells with population > {min_population}: {number_of_populated_cells:,}")
    print(f"Total estimated population: {total_population:,.0f}")
    print(f"Approx. memory for one raster array: {one_array_memory_gb:.2f} GB")
    print(f"Rough GeoDataFrame memory estimate: {estimated_gdf_memory_gb:.2f} GB")


def main():
    # Load Italy boundary and project it to EPSG:3035.
    italy = load_country_boundary(
        shapefile=BOUNDARY_FILE,
        country_name="Italy",
        output_crs="EPSG:3035"
    )

    # Reproject the original WorldPop raster to EPSG:3035.
    # This creates a new raster with coordinates in meters.
    # You only need to run this once; later you can comment this block out.
    reproject_population_raster(
        input_raster=WORLDPOP_FILE,
        output_raster=WORLDPOP_3035_FILE,
        dst_crs="EPSG:3035",
        resolution=100
    )

    # Plot the reprojected WorldPop population raster as a sanity check.
    plot_worldpop_density(
        raster_path=WORLDPOP_3035_FILE,
        boundary=italy,
        output_file=OUTPUT_POPULATION_PLOT,
        title="WorldPop population distribution in Italy"
    )

    # Inspect the reprojected raster.
    inspect_reprojected_population_raster(
        raster_path=WORLDPOP_3035_FILE,
        boundary=italy,
        min_population=0
    )


# Run main() only when this file is executed directly.
if __name__ == "__main__":
    main()
