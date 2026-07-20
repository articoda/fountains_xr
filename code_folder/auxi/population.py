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

# Import raster reprojection tools.
from rasterio.warp import calculate_default_transform, reproject, Resampling

# Import matplotlib for plotting.
import matplotlib.pyplot as plt

# Import LogNorm for logarithmic color scaling.
from matplotlib.colors import LogNorm

# Import rasterize to convert vector points into a raster grid.
from rasterio.features import rasterize

# Import MergeAlg so multiple fountains in the same raster cell are counted, not overwritten.
from rasterio.enums import MergeAlg


def reproject_population_raster(
    input_raster,
    output_raster,
    dst_crs="EPSG:3035",
    resolution=100
):
    """
    Reproject a WorldPop population raster to a metric CRS.

    The output raster has pixels of size `resolution` meters.
    For example, resolution=100 gives 100 m x 100 m cells.

    This is useful because distances such as 250 m and 500 m should be
    computed in a projected CRS measured in meters, not in longitude/latitude.
    """

    # Open the original WorldPop raster.
    with rasterio.open(input_raster) as src:

        # Check that the input raster has a CRS.
        if src.crs is None:
            raise ValueError("The input population raster has no CRS.")

        # Compute the transform, width, and height of the reprojected raster.
        transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs,
            src.width,
            src.height,
            *src.bounds,
            resolution=resolution
        )

        # Copy the metadata from the original raster.
        kwargs = src.meta.copy()

        # Update the metadata for the output raster.
        # Compression keeps the new GeoTIFF smaller on disk.
        kwargs.update({
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height,
            "nodata": src.nodata,
            "compress": "lzw",
            "tiled": True,
            "bigtiff": "if_safer"
        })

        # Create the reprojected output raster.
        with rasterio.open(output_raster, "w", **kwargs) as dst:

            # Reproject the first raster band.
            # WorldPop values are population counts per cell,
            # so Resampling.sum is the safest option when changing grid.
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.sum
            )


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

    Warning: this can create millions of points and use a lot of memory.
    For the main accessibility analysis, the raster-based strategy is better.
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

def rasterize_fountains_like_population(
    fountains,
    population_raster
):
    """
    Rasterize fountain points onto the same grid as the population raster.

    Output:
    - fountain_raster: array where each cell contains the number of fountains in that cell.
    - raster_transform: spatial transform of the raster.
    - raster_crs: CRS of the raster.

    This is useful because later we can compare fountain locations and population
    using raster operations on the same grid.
    """

    # Open the population raster.
    # We use it as a template for shape, transform, and CRS.
    with rasterio.open(population_raster) as src:

        # Reproject the fountain points to the CRS of the population raster.
        fountains_same_crs = fountains.to_crs(src.crs)

        # Build a list of geometries to burn into the raster.
        # Each fountain receives value 1.
        shapes = [
            (geom, 1)
            for geom in fountains_same_crs.geometry
            if geom is not None and not geom.is_empty
        ]

        # Rasterize the fountain points.
        # `merge_alg=MergeAlg.add` means that if multiple fountains fall in the same
        # raster cell, they are added together instead of overwriting each other.
        fountain_raster = rasterize(
            shapes=shapes,
            out_shape=(src.height, src.width),
            transform=src.transform,
            fill=0,
            dtype="uint32",
            merge_alg=MergeAlg.add
        )

        # Store the raster transform.
        raster_transform = src.transform

        # Store the raster CRS.
        raster_crs = src.crs

    # Return the rasterized fountains and raster metadata.
    return fountain_raster, raster_transform, raster_crs
