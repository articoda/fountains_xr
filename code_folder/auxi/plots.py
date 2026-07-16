# Import matplotlib for plotting.
import matplotlib.pyplot as plt

# Import LogNorm for logarithmic colour scaling.
from matplotlib.colors import LogNorm


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
