# Import numpy for numerical operations.
import numpy as np

# Import geopandas for geographic vector data.
import geopandas as gpd

# Import rasterio for reading raster files such as WorldPop GeoTIFFs.
import rasterio

# Import mask to clip raster data to a polygon boundary.
from rasterio.mask import mask

# Import plotting_extent to get the spatial extent of a raster image.
from rasterio.plot import plotting_extent

# Import matplotlib for plotting.
import matplotlib.pyplot as plt

# Import LogNorm for logarithmic color scaling.
from matplotlib.colors import LogNorm


def load_worldpop_points(
    raster_path,
    boundary=None,
    output_crs="EPSG:3035",
    min_population=0
):
    """
    Load a WorldPop raster and convert populated raster cells to points.

    Each output point represents the centre of one raster cell.
    The column "population" contains the population value of that raster cell.
    """

    # Open the WorldPop raster file.
    with rasterio.open(raster_path) as src:

        # Check that the raster has a coordinate reference system.
        if src.crs is None:
            raise ValueError("The population raster has no CRS.")

        # If a boundary is provided, clip the raster to that boundary.
        if boundary is not None:

            # Reproject the boundary to the CRS of the raster.
            boundary_raster_crs = boundary.to_crs(src.crs)

            # Clip the raster to the boundary.
            pop_image, pop_transform = mask(
                src,
                list(boundary_raster_crs.geometry),
                crop=True,
                filled=True
            )

        # If no boundary is provided, read the full raster.
        else:

            # Read the full raster image.
            pop_image = src.read()

            # Store the original raster transform.
            pop_transform = src.transform

        # Extract the first band of the raster.
        pop = pop_image[0].astype(float)

        # Store the raster CRS.
        raster_crs = src.crs

        # Store the raster NoData value.
        nodata = src.nodata

    # Select finite values.
    valid = np.isfinite(pop)

    # Remove NoData values, if the raster defines one.
    if nodata is not None:
        valid = valid & (pop != nodata)

    # Keep only cells with population above the chosen threshold.
    valid = valid & (pop > min_population)

    # Get the row and column indices of valid population cells.
    rows, cols = np.where(valid)

    # Convert raster row/column indices to real-world coordinates.
    xs, ys = rasterio.transform.xy(
        pop_transform,
        rows,
        cols,
        offset="center"
    )

    # Extract the population values of the valid cells.
    pop_values = pop[rows, cols]

    # Create a GeoDataFrame where each populated raster cell is a point.
    pop_gdf = gpd.GeoDataFrame(
        {"population": pop_values},
        geometry=gpd.points_from_xy(xs, ys),
        crs=raster_crs
    )

    # Reproject the population points to the output CRS.
    pop_gdf = pop_gdf.to_crs(output_crs)

    # Return the population points.
    return pop_gdf


def plot_worldpop_density(
    raster_path,
    boundary,
    output_file,
    title="Population density in Italy"
):
    """
    Plot the WorldPop raster clipped to the given boundary.

    This is mainly a sanity-check plot to verify that the population raster
    was loaded and clipped correctly.
    """

    # Open the WorldPop raster file.
    with rasterio.open(raster_path) as src:

        # Check that the raster has a coordinate reference system.
        if src.crs is None:
            raise ValueError("The population raster has no CRS.")

        # Reproject the boundary to the CRS of the raster.
        boundary_raster_crs = boundary.to_crs(src.crs)

        # Clip the raster to the boundary.
        pop_image, pop_transform = mask(
            src,
            list(boundary_raster_crs.geometry),
            crop=True,
            filled=True
        )

        # Extract the first raster band.
        pop = pop_image[0].astype(float)

        # Store the raster NoData value.
        nodata = src.nodata

        # Store the raster CRS.
        raster_crs = src.crs

    # Select finite values.
    valid = np.isfinite(pop)

    # Remove NoData values, if present.
    if nodata is not None:
        valid = valid & (pop != nodata)

    # Keep only strictly positive population values.
    valid = valid & (pop > 0)

    # Replace invalid or zero values with NaN so they are not plotted.
    pop_plot = np.where(valid, pop, np.nan)

    # Extract positive population values for color-scale limits.
    positive_values = pop_plot[np.isfinite(pop_plot) & (pop_plot > 0)]

    # Stop with a clear error if no positive population values were found.
    if len(positive_values) == 0:
        raise ValueError("No positive population values found in the raster.")

    # Use percentiles to avoid one or two extreme cells dominating the colors.
    vmin = max(np.nanpercentile(positive_values, 1), 0.001)
    vmax = np.nanpercentile(positive_values, 99.5)

    # Compute the map extent of the clipped raster.
    extent = plotting_extent(pop_plot, pop_transform)

    # Reproject the boundary to the raster CRS for plotting.
    boundary_for_plot = boundary.to_crs(raster_crs)

    # Create figure and axes.
    fig, ax = plt.subplots(figsize=(8, 10))

    # Plot the population raster.
    img = ax.imshow(
        pop_plot,
        extent=extent,
        origin="upper",
        cmap="magma",
        norm=LogNorm(vmin=vmin, vmax=vmax)
    )

    # Plot the country boundary on top of the raster.
    boundary_for_plot.boundary.plot(ax=ax, linewidth=0.7, color="black")

    # Add a colorbar.
    cbar = plt.colorbar(img, ax=ax, shrink=0.75)

    # Add the colorbar label.
    cbar.set_label("Population per raster cell, log scale")

    # Remove map axes.
    ax.set_axis_off()

    # Add plot title.
    ax.set_title(title, fontsize=15)

    # Adjust layout.
    plt.tight_layout()

    # Save the figure.
    plt.savefig(output_file, dpi=300)

    # Show the figure.
    plt.show()
