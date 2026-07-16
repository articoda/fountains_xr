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
