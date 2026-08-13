# Download and prepare external data needed by the project.

from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile


# Repository/code folder is the parent of the scripts/ folder.
CODE_DIR = Path(__file__).resolve().parents[1]

# Analysis folder containing main.py, auxi/, and the data files.
PROJECT_DIR = CODE_DIR / "fountain_analysis"

if not PROJECT_DIR.exists():
    raise FileNotFoundError(
        f"Analysis folder not found: {PROJECT_DIR}"
    )

# Temperature-analysis folder.
# This assumes temperature_analysis/ is a sibling of fountain_analysis/.
TEMPERATURE_ANALYSIS_DIR = CODE_DIR / "temperature_analysis"

# Expected large temperature data bundle.
TEMPERATURE_DATA_ZIP = TEMPERATURE_ANALYSIS_DIR / "data.zip"

# Manual download link for the temperature data bundle.
TEMPERATURE_DATA_URL = (
    "https://drive.proton.me/urls/Y4T203YJD0#zXrhkVjLqHBk"
)

# Make fountain_analysis/ importable when running this script from scripts/.
sys.path.insert(0, str(PROJECT_DIR))

from auxi.population import reproject_population_raster


# WorldPop 2020 Italy population raster.
# This is the unconstrained UN-adjusted file used by the project.
WORLDPOP_URL = (
    "https://worldpop-public-data.soton.ac.uk/"
    "GIS/Population/Global_2000_2020/2020/ITA/"
    "ita_ppp_2020_UNadj.tif"
)

# ISTAT 2026 non-generalized administrative boundaries.
# This contains municipality and region shapefiles.
ISTAT_LIMITS_URL = (
    "https://www.istat.it/storage/cartografia/"
    "confini_amministrativi/non_generalizzati/2026/"
    "Limiti01012026.zip"
)


# Local output paths.
RASTER_DIR = PROJECT_DIR / "data" / "rasters"

WORLDPOP_FILE = RASTER_DIR / "ita_ppp_2020_UNadj.tif"
WORLDPOP_3035_FILE = RASTER_DIR / "ita_ppp_2020_UNadj_EPSG3035_100m.tif"

DATA_RAW_DIR = PROJECT_DIR / "data" / "raw"
ISTAT_ZIP_FILE = DATA_RAW_DIR / "Limiti01012026.zip"
ISTAT_OUTPUT_DIR = PROJECT_DIR / "limiti_istat"

# Folder containing fountain CSV data.
FOUNTAIN_DIR = PROJECT_DIR / "data" / "fountains"

# Local fountain CSV path.
FOUNTAIN_FILE = FOUNTAIN_DIR / "italy_20260615.csv"

def check_temperature_data_zip():
    """
    Check whether the temperature-analysis data bundle exists.

    The Proton Drive link is intended as a manual download link, not as a
    direct script-download URL.
    """

    print()
    print("Temperature-analysis data")
    print("-------------------------")

    if TEMPERATURE_DATA_ZIP.exists():
        print(f"Found: {TEMPERATURE_DATA_ZIP}")
        return

    print("Temperature data bundle not found.")
    print()
    print("Expected file:")
    print(f"  {TEMPERATURE_DATA_ZIP}")
    print()
    print("Please download data.zip manually from:")
    print(f"  {TEMPERATURE_DATA_URL}")
    print()
    print("Then place it here:")
    print(f"  {TEMPERATURE_ANALYSIS_DIR}")

def download_file(url, output_file):
    """
    Download a file if it does not already exist.
    """

    output_file.parent.mkdir(parents=True, exist_ok=True)

    if output_file.exists():
        print(f"Already exists: {output_file}")
        return

    print(f"Downloading:")
    print(f"  {url}")
    print(f"to:")
    print(f"  {output_file}")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request) as response:
        with open(output_file, "wb") as file:
            shutil.copyfileobj(response, file)

    print(f"Saved: {output_file}")


def extract_zip(zip_file, output_dir):
    """
    Extract a zip file if the expected ISTAT folders are not already present.
    """

    expected_region_folder = output_dir / "Reg01012026"
    expected_town_folder = output_dir / "Com01012026"

    if expected_region_folder.exists() and expected_town_folder.exists():
        print(f"ISTAT folders already exist in: {output_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting {zip_file} to {output_dir}")

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(output_dir)

    normalize_istat_folders(output_dir)


def normalize_istat_folders(output_dir):
    """
    Make sure the folders have the structure expected by main.py:

        limiti_istat/
        ├── Com01012026/
        └── Reg01012026/

    Depending on the ISTAT zip, these folders may be nested one level deeper.
    """

    for folder_name in ["Com01012026", "Reg01012026"]:

        wanted_folder = output_dir / folder_name

        if wanted_folder.exists():
            continue

        candidates = [
            path for path in output_dir.rglob(folder_name)
            if path.is_dir()
        ]

        if not candidates:
            print(f"WARNING: could not find folder {folder_name}")
            continue

        source_folder = candidates[0]

        print(f"Moving {source_folder} to {wanted_folder}")
        shutil.move(str(source_folder), str(wanted_folder))


def check_istat_outputs():
    """
    Print the shapefiles found after extraction.
    """

    for folder_name in ["Reg01012026", "Com01012026"]:
        folder = ISTAT_OUTPUT_DIR / folder_name
        shapefiles = sorted(folder.glob("*.shp"))

        print()
        print(f"{folder_name}:")
        if not shapefiles:
            print("  WARNING: no .shp file found")
        else:
            for shp in shapefiles:
                print(f"  {shp}")


def main():
    """
    Download and prepare all external data.
    """
    # Create raster-data folder if needed.
    RASTER_DIR.mkdir(parents=True, exist_ok=True)

    # Create fountain-data folder if needed.
    FOUNTAIN_DIR.mkdir(parents=True, exist_ok=True)

    # Download the original WorldPop raster.
    download_file(
        url=WORLDPOP_URL,
        output_file=WORLDPOP_FILE
    )

    # Generate the EPSG:3035 version used for distance calculations.
    if WORLDPOP_3035_FILE.exists():
        print(f"Already exists: {WORLDPOP_3035_FILE}")
    else:
        print("Reprojecting WorldPop raster to EPSG:3035...")

        reproject_population_raster(
            input_raster=WORLDPOP_FILE,
            output_raster=WORLDPOP_3035_FILE,
            dst_crs="EPSG:3035",
            resolution=100
        )

        print(f"Saved: {WORLDPOP_3035_FILE}")

    # Download ISTAT administrative boundaries.
    download_file(
        url=ISTAT_LIMITS_URL,
        output_file=ISTAT_ZIP_FILE
    )

    # Extract ISTAT boundaries.
    extract_zip(
        zip_file=ISTAT_ZIP_FILE,
        output_dir=ISTAT_OUTPUT_DIR
    )

    # Check if fountain csv exists
    if not FOUNTAIN_FILE.exists():
        print()
        print("WARNING: fountain CSV not found.")
        print(f"Expected file: {FOUNTAIN_FILE}")
        print("For now, place italy_20260615.csv manually in data/fountains/.")
    else: print(f'Fountain file exists: {FOUNTAIN_FILE}')

    # Check resulting folders.
    check_istat_outputs()

    # Check whether the temperature-analysis data bundle is available.
    check_temperature_data_zip()

    print()
    print("Done. Data are ready.")


if __name__ == "__main__":
    main()
