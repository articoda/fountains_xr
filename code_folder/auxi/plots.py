# Import numpy for array operations.
import numpy as np

# Import matplotlib for plotting.
import matplotlib.pyplot as plt

# Import LogNorm for logarithmic color scaling.
from matplotlib.colors import LogNorm

# Import plotting_extent to place raster data correctly on the map.
from rasterio.plot import plotting_extent


def plot_fountain_density_hexbin(
    fountains,
    boundary,
    output_file,
    gridsize=150,
    title="Public drinking-water fountains in Italy"
):
    """
    Create a national hexbin density plot of fountains.
    """

    # Extract the map extent from the boundary.
    xmin, ymin, xmax, ymax = boundary.total_bounds

    # Create the figure and axes.
    fig, ax = plt.subplots(figsize=(8, 10))

    # Create the hexagonal density map.
    hb = ax.hexbin(
        fountains.geometry.x,
        fountains.geometry.y,
        gridsize=gridsize,
        mincnt=1,
        cmap="magma",
        extent=(xmin, xmax, ymin, ymax),
        norm=LogNorm(),
        linewidths=0,
        alpha=0.9
    )

    # Plot the country boundary on top of the density map.
    boundary.boundary.plot(ax=ax, linewidth=0.7, color="black")

    # Add a colorbar explaining the hexbin colours.
    cbar = plt.colorbar(hb, ax=ax, shrink=0.75)

    # Add a label to the colorbar.
    cbar.set_label("Fountains per hexagon, log scale")

    # Set the horizontal map limits.
    ax.set_xlim(xmin, xmax)

    # Set the vertical map limits.
    ax.set_ylim(ymin, ymax)

    # Remove axes, ticks, and labels.
    ax.set_axis_off()

    # Add the map title.
    ax.set_title(title, fontsize=15)

    # Adjust spacing so everything fits well.
    plt.tight_layout()

    # Save the figure.
    plt.savefig(output_file, dpi=300)

    # Show the figure on screen.
    plt.show()

def plot_fountain_density_raster(
    fountain_raster,
    raster_transform,
    raster_crs,
    boundary,
    output_file,
    title="Rasterized public drinking-water fountains in Italy"
):
    """
    Plot rasterized fountain counts.

    Each raster cell contains the number of fountains inside that cell.
    This is mainly a test plot for the raster workflow.
    """

    # Replace zero-fountain cells with NaN so they are not plotted.
    fountain_plot = np.where(fountain_raster > 0, fountain_raster, np.nan)

    # Extract the positive fountain counts.
    positive_values = fountain_raster[fountain_raster > 0]

    # Stop if no fountains were rasterized.
    if len(positive_values) == 0:
        raise ValueError("No fountains found in the raster.")

    # Set the minimum color value.
    # Since these are counts, the smallest positive value is 1.
    vmin = 1

    # Use a percentile for vmax so extreme cells do not dominate the colors.
    vmax = np.nanpercentile(positive_values, 99.5)

    # Avoid LogNorm problems if all positive cells have the same value.
    if vmax <= vmin:
        vmax = vmin + 1

    # Compute the spatial extent of the raster.
    extent = plotting_extent(fountain_plot, raster_transform)

    # Reproject the boundary to the raster CRS.
    boundary_for_plot = boundary.to_crs(raster_crs)

    # Extract the boundary bounds.
    xmin, ymin, xmax, ymax = boundary_for_plot.total_bounds

    # Create figure and axes.
    fig, ax = plt.subplots(figsize=(8, 10))

    # Plot the rasterized fountain counts.
    img = ax.imshow(
        fountain_plot,
        extent=extent,
        origin="upper",
        cmap="magma",
        norm=LogNorm(vmin=vmin, vmax=vmax)
    )

    # Plot Italy's boundary on top.
    boundary_for_plot.boundary.plot(ax=ax, linewidth=0.7, color="black")

    # Add colorbar.
    cbar = plt.colorbar(img, ax=ax, shrink=0.75)

    # Label the colorbar.
    cbar.set_label("Fountains per raster cell, log scale")

    # Limit the plot to Italy's extent.
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    # Remove axes.
    ax.set_axis_off()

    # Add title.
    ax.set_title(title, fontsize=15)

    # Adjust layout.
    plt.tight_layout()

    # Save the figure.
    plt.savefig(output_file, dpi=300)

    # Show the figure.
    plt.show()

# Import numpy for array operations.
import numpy as np

# Import matplotlib for plotting.
import matplotlib.pyplot as plt

# Import LogNorm for logarithmic color scaling.
from matplotlib.colors import LogNorm

# Import Affine to update the raster transform after aggregation.
from affine import Affine

# Import plotting_extent to place raster data correctly on the map.
from rasterio.plot import plotting_extent


def aggregate_raster_sum(raster, transform, factor):
    """
    Aggregate a raster by summing blocks of size factor x factor.

    Example:
    If the input raster has 100 m pixels and factor=10,
    the output raster has 1 km pixels.
    """

    # Get raster dimensions.
    height, width = raster.shape

    # Crop the raster so its dimensions are divisible by factor.
    new_height = height // factor * factor
    new_width = width // factor * factor

    raster_cropped = raster[:new_height, :new_width]

    # Reshape into blocks and sum each block.
    raster_aggregated = raster_cropped.reshape(
        new_height // factor,
        factor,
        new_width // factor,
        factor
    ).sum(axis=(1, 3))

    # Update the transform so the new pixels have the correct larger size.
    new_transform = transform * Affine.scale(factor, factor)

    return raster_aggregated, new_transform


def plot_aggregated_fountain_raster(
    fountain_raster,
    raster_transform,
    raster_crs,
    boundary,
    output_file,
    aggregation_factor=10,
    title="Public drinking-water fountains in Italy"
):
    """
    Plot rasterized fountain counts after aggregating to larger cells.

    If the original raster has 100 m pixels:
    - aggregation_factor=10 gives 1 km cells;
    - aggregation_factor=25 gives 2.5 km cells;
    - aggregation_factor=50 gives 5 km cells.
    """

    # Aggregate fountain counts into larger raster cells.
    fountain_agg, agg_transform = aggregate_raster_sum(
        raster=fountain_raster,
        transform=raster_transform,
        factor=aggregation_factor
    )

    # Replace zero-count cells with NaN so they are transparent/not plotted.
    fountain_plot = np.where(fountain_agg > 0, fountain_agg, np.nan)

    # Extract positive values for color scaling.
    positive_values = fountain_agg[fountain_agg > 0]

    # Stop if no fountains are found.
    if len(positive_values) == 0:
        raise ValueError("No fountains found in the aggregated raster.")

    # Set color-scale limits.
    vmin = 1
    vmax = np.nanpercentile(positive_values, 99.5)

    # Avoid problems if all cells have the same value.
    if vmax <= vmin:
        vmax = vmin + 1

    # Compute map extent.
    extent = plotting_extent(fountain_plot, agg_transform)

    # Reproject boundary to raster CRS.
    boundary_for_plot = boundary.to_crs(raster_crs)

    # Get boundary limits.
    xmin, ymin, xmax, ymax = boundary_for_plot.total_bounds

    # Create figure.
    fig, ax = plt.subplots(figsize=(8, 10))

    # Plot aggregated fountain density.
    img = ax.imshow(
        fountain_plot,
        extent=extent,
        origin="upper",
        cmap="magma",
        norm=LogNorm(vmin=vmin, vmax=vmax),
        alpha=0.9
    )

    # Plot Italy boundary.
    boundary_for_plot.boundary.plot(ax=ax, linewidth=0.7, color="black")

    # Add colorbar.
    cbar = plt.colorbar(img, ax=ax, shrink=0.75)
    cbar.set_label("Fountains per aggregated raster cell, log scale")

    # Set map limits.
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    # Remove axes.
    ax.set_axis_off()

    # Add title.
    ax.set_title(title, fontsize=15)

    # Adjust layout.
    plt.tight_layout()

    # Save and show.
    plt.savefig(output_file, dpi=300)
    plt.show()
