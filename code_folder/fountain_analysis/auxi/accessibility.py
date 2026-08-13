# Import numpy for raster array operations.
import numpy as np

# Import rasterio for reading raster metadata and data.
import rasterio

# Import geometry_mask to select only cells inside Italy.
from rasterio.features import geometry_mask

# Import distance_transform_edt to compute distance to the nearest fountain cell.
from scipy.ndimage import distance_transform_edt

# Import Affine to update the raster transform after aggregation.
from affine import Affine


def compute_population_accessibility(
    population_raster,
    fountain_raster,
    boundary=None,
    thresholds=(250, 500),
    map_threshold=250
):
    """
    Compute population accessibility to fountains.

    Parameters
    ----------
    population_raster:
        Path to the reprojected WorldPop raster in EPSG:3035.

    fountain_raster:
        Rasterized fountain counts on the same grid as the population raster.

    boundary:
        Optional GeoDataFrame boundary, for example Italy.
        If provided, only population cells inside the boundary are counted.

    thresholds:
        Distances, in meters, for which accessibility statistics are computed.

    map_threshold:
        Distance threshold, in meters, used to produce the output map.

    Returns
    -------
    results:
        Dictionary with total population and shares within each threshold.

    accessible_population_map:
        Raster array containing population values only where people are within
        `map_threshold` meters of a fountain. Other cells are NaN.

    raster_transform:
        Transform of the population raster.

    raster_crs:
        CRS of the population raster.
    """

    # Open the population raster.
    with rasterio.open(population_raster) as src:

        # Check that the raster is in a projected CRS.
        # Distances like 250 m only make sense in a CRS measured in meters.
        if not src.crs.is_projected:
            raise ValueError(
                "The population raster is not projected. "
                "Use the EPSG:3035 raster before computing distances."
            )

        # Read the population raster as float32 to save memory.
        population = src.read(1).astype("float32")

        # Store raster metadata.
        nodata = src.nodata
        raster_transform = src.transform
        raster_crs = src.crs

        # Store pixel size in meters.
        pixel_width = abs(src.transform.a)
        pixel_height = abs(src.transform.e)

    # Check that the fountain raster has the same shape as the population raster.
    if fountain_raster.shape != population.shape:
        raise ValueError(
            "Population raster and fountain raster have different shapes. "
            f"Population shape: {population.shape}, "
            f"fountain shape: {fountain_raster.shape}"
        )

    # Select finite population cells.
    valid_population = np.isfinite(population)

    # Remove NoData cells, if a NoData value is defined.
    if nodata is not None:
        valid_population = valid_population & (population != nodata)

    # Keep only cells with positive population.
    valid_population = valid_population & (population > 0)

    # If a boundary is provided, keep only cells inside it.
    if boundary is not None:

        # Reproject the boundary to the raster CRS.
        boundary_raster_crs = boundary.to_crs(raster_crs)

        # Create a mask that is True inside the boundary.
        inside_boundary = geometry_mask(
            geometries=list(boundary_raster_crs.geometry),
            out_shape=population.shape,
            transform=raster_transform,
            invert=True
        )

        # Keep only valid population cells inside the boundary.
        valid_population = valid_population & inside_boundary

    # Replace invalid population cells with zero.
    population_clean = np.where(valid_population, population, 0.0).astype("float32")

    # Convert the fountain raster into a boolean raster.
    # True means at least one fountain is present in that cell.
    fountain_cells = fountain_raster > 0

    # Stop if there are no fountains in the raster.
    if not np.any(fountain_cells):
        raise ValueError("No fountain cells found in the raster.")

    # distance_transform_edt computes distance to the nearest zero/False cell.
    # Therefore we pass the opposite of fountain_cells:
    # - fountain cells are False;
    # - non-fountain cells are True.
    non_fountain_cells = ~fountain_cells

    # Compute Euclidean distance to the nearest fountain cell.
    # sampling converts pixel distances into meters.
    distance_to_fountain = distance_transform_edt(
        non_fountain_cells,
        sampling=(pixel_height, pixel_width)
    ).astype("float32")

    # Compute total population inside the analysis area.
    total_population = float(population_clean.sum())

    # Prepare the results dictionary.
    results = {
        "total_population": total_population,
        "pixel_width_m": pixel_width,
        "pixel_height_m": pixel_height,
        "number_of_fountain_cells": int(fountain_cells.sum()),
        "total_fountains_in_raster": int(fountain_raster.sum())
    }

    # Compute accessibility statistics for each threshold.
    for threshold in thresholds:

        # Select cells within this distance from a fountain.
        within_threshold = (distance_to_fountain <= threshold) & valid_population

        # Sum population within this distance.
        population_within = float(population_clean[within_threshold].sum())

        # Compute population share.
        share_within = population_within / total_population

        # Store results.
        results[f"population_within_{threshold}m"] = population_within
        results[f"share_within_{threshold}m"] = share_within

    # Create the map for the chosen threshold.
    accessible_mask = (distance_to_fountain <= map_threshold) & valid_population

    # Keep population values only where the cell is accessible.
    # Everywhere else becomes NaN and will not be plotted.
    accessible_population_map = np.where(
        accessible_mask,
        population_clean,
        np.nan
    ).astype("float32")

    # Return results and the map-ready raster.
    return results, accessible_population_map, raster_transform, raster_crs

def aggregate_raster_sum(raster, transform, factor):
    """
    Aggregate a raster by summing blocks of size factor x factor.

    Example:
    If the input raster has 100 m pixels and factor=25,
    the output raster has 2.5 km pixels.
    """

    # Get raster dimensions.
    height, width = raster.shape

    # Crop the raster so dimensions are divisible by factor.
    new_height = height // factor * factor
    new_width = width // factor * factor

    # Keep only the cropped part.
    raster_cropped = raster[:new_height, :new_width]

    # Reshape the raster into blocks and sum over each block.
    raster_aggregated = raster_cropped.reshape(
        new_height // factor,
        factor,
        new_width // factor,
        factor
    ).sum(axis=(1, 3))

    # Update the transform so the new pixels have the correct size.
    new_transform = transform * Affine.scale(factor, factor)

    # Return aggregated raster and updated transform.
    return raster_aggregated, new_transform


def compute_accessibility_share_grid(
    population_raster,
    fountain_raster,
    boundary=None,
    threshold=250,
    aggregation_factor=25,
    min_total_population=10
):
    """
    Compute, for each aggregated raster cell, the percentage of population
    living within `threshold` meters of a fountain.

    Example:
    If the population raster has 100 m cells and aggregation_factor=25,
    the output map has 2.5 km cells.

    The output value is:

        accessible population in coarse cell / total population in coarse cell * 100
    """

    # Open the population raster.
    with rasterio.open(population_raster) as src:

        # Check that the raster is projected.
        if not src.crs.is_projected:
            raise ValueError(
                "The population raster is not projected. "
                "Use the EPSG:3035 raster before computing distances."
            )

        # Read population as float32 to save memory.
        population = src.read(1).astype("float32")

        # Store raster metadata.
        nodata = src.nodata
        raster_transform = src.transform
        raster_crs = src.crs

        # Store pixel size in meters.
        pixel_width = abs(src.transform.a)
        pixel_height = abs(src.transform.e)

    # Check that the population and fountain rasters have the same shape.
    if fountain_raster.shape != population.shape:
        raise ValueError(
            "Population raster and fountain raster have different shapes. "
            f"Population shape: {population.shape}, "
            f"fountain shape: {fountain_raster.shape}"
        )

    # Select finite population cells.
    valid_population = np.isfinite(population)

    # Remove NoData cells.
    if nodata is not None:
        valid_population = valid_population & (population != nodata)

    # Keep only positive-population cells.
    valid_population = valid_population & (population > 0)

    # If a boundary is provided, keep only cells inside it.
    if boundary is not None:

        # Reproject boundary to the raster CRS.
        boundary_raster_crs = boundary.to_crs(raster_crs)

        # Create a mask that is True inside the boundary.
        inside_boundary = geometry_mask(
            geometries=list(boundary_raster_crs.geometry),
            out_shape=population.shape,
            transform=raster_transform,
            invert=True
        )

        # Keep only population cells inside the boundary.
        valid_population = valid_population & inside_boundary

    # Set invalid population cells to zero.
    total_population_raster = np.where(
        valid_population,
        population,
        0.0
    ).astype("float32")

    # Convert fountain raster to boolean.
    fountain_cells = fountain_raster > 0

    # Stop if no fountains exist in the raster.
    if not np.any(fountain_cells):
        raise ValueError("No fountain cells found in the raster.")

    # Compute Euclidean distance to nearest fountain cell.
    distance_to_fountain = distance_transform_edt(
        ~fountain_cells,
        sampling=(pixel_height, pixel_width)
    ).astype("float32")

    # Create mask of population cells within threshold distance.
    accessible_mask = (distance_to_fountain <= threshold) & valid_population

    # Keep population only where it is accessible.
    accessible_population_raster = np.where(
        accessible_mask,
        total_population_raster,
        0.0
    ).astype("float32")

    # Aggregate total population to larger cells.
    total_population_agg, agg_transform = aggregate_raster_sum(
        total_population_raster,
        raster_transform,
        aggregation_factor
    )

    # Aggregate accessible population to the same larger cells.
    accessible_population_agg, _ = aggregate_raster_sum(
        accessible_population_raster,
        raster_transform,
        aggregation_factor
    )

    # Create empty percentage map.
    accessibility_share = np.full(
        total_population_agg.shape,
        np.nan,
        dtype="float32"
    )

    # Only compute shares where the aggregated cell has enough population.
    valid_agg = total_population_agg >= min_total_population

    # Compute percentage of population with access.
    accessibility_share[valid_agg] = (
        accessible_population_agg[valid_agg]
        / total_population_agg[valid_agg]
        * 100
    )

    # Prepare summary results.
    results = {
        "threshold_m": threshold,
        "aggregation_factor": aggregation_factor,
        "aggregated_cell_size_x_m": pixel_width * aggregation_factor,
        "aggregated_cell_size_y_m": pixel_height * aggregation_factor,
        "total_population": float(total_population_raster.sum()),
        "accessible_population": float(accessible_population_raster.sum()),
        "share_accessible": float(accessible_population_raster.sum() / total_population_raster.sum()),
    }

    # Return results and map layers.
    return (
        results,
        accessibility_share,
        accessible_population_agg,
        total_population_agg,
        agg_transform,
        raster_crs
    )
