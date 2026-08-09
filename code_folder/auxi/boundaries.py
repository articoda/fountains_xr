# Import geopandas for reading and processing shapefiles.
import geopandas as gpd


def load_country_boundary(shapefile, country_name="Italy", output_crs="EPSG:3035"):
    """
    Load a Natural Earth country shapefile and select one country.
    """

    # Read the Natural Earth country shapefile.
    countries = gpd.read_file(shapefile)

    # Select the requested country.
    # Natural Earth usually stores country names in the ADMIN column.
    country = countries[countries["ADMIN"] == country_name]

    # Check that the country was actually found.
    if country.empty:
        raise ValueError(f"Country not found in shapefile: {country_name}")

    # Project the country boundary to the requested CRS.
    country = country.to_crs(output_crs)

    # Return the projected country boundary.
    return country


def clip_points_to_boundary(points, boundary):
    """
    Keep only points that fall within the given boundary polygon.
    """

    # Combine all boundary geometries into one geometry.
    boundary_geometry = boundary.geometry.union_all()

    # Keep only points inside the boundary geometry.
    clipped_points = points[points.geometry.within(boundary_geometry)].copy()

    # Return the clipped point dataset.
    return clipped_points

def load_boundary_layer(shapefile, output_crs="EPSG:3035"):
    """
    Load a generic boundary shapefile and project it.

    This can be used for ISTAT regions, provinces, municipalities, etc.
    """

    # Read the shapefile.
    boundaries = gpd.read_file(shapefile)

    # Project to the requested CRS.
    boundaries = boundaries.to_crs(output_crs)

    # Return the full boundary layer.
    return boundaries


def print_boundary_columns(boundaries):
    """
    Print boundary columns and first rows.

    Useful because ISTAT column names can vary depending on the file.
    """

    print("Boundary columns:")
    print(boundaries.columns)

    print()
    print("First rows:")
    print(boundaries.head())


def select_boundary(boundaries, column, value):
    """
    Select one boundary polygon from a boundary layer.

    Example:
        select_boundary(regions, column="DEN_REG", value="Lazio")
    """

    # Select rows matching the requested value.
    selected = boundaries[boundaries[column] == value].copy()

    # Stop if nothing was found.
    if selected.empty:
        raise ValueError(f"No boundary found with {column} = {value}")

    # Return the selected boundary.
    return selected
