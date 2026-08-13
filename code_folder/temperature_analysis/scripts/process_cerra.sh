#!/bin/bash

# ============================================================
# Process CERRA 2 m temperature data over Italy
#
# Folder structure:
#
# parent_folder/
# ├── script/
# │   └── process_cerra.sh
# └── data/
#     ├── input_file.grib
#     └── mask/
#         └── italy_mask_bbox.nc
#
# Usage:
#   ./process_cerra.sh input_file.grib
#
# Outputs are written to the data folder:
#   cerra_2mt_2025_italy.nc
#   cerra_2mt_2025_italy_dm.nc
#
# Processing:
#   1. Sort timesteps chronologically
#   2. Extract Italy bounding box
#   3. Apply Italy mask
#   4. Calculate daily means
# ============================================================


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

# Folder containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parent project folder
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Data and mask folders
DATA_DIR="$BASE_DIR/data"
MASK="$DATA_DIR/mask/italy_mask_bbox.nc"


# ------------------------------------------------------------
# Input
# ------------------------------------------------------------

if [ -z "$1" ]; then
    echo "Usage: $0 <input_file>"
    exit 1
fi

INPUT="$DATA_DIR/$1"

# Italy bounding box on CERRA grid
BBOX="516,699,249,477"


# ------------------------------------------------------------
# Output filenames
# ------------------------------------------------------------

# Remove extension from input filename
NAME="$(basename "$1")"
BASE="${NAME%.*}"

ITALY="$DATA_DIR/${BASE}_italy.nc"
DMEAN="$DATA_DIR/${BASE}_italy_dm.nc"


# ------------------------------------------------------------
# 1. Sort, crop and mask CERRA data
# ------------------------------------------------------------

echo "Processing Italy data..."

cdo -O ifthen "$MASK" \
    -selindexbox,$BBOX \
    -sorttimestamp "$INPUT" \
    "$ITALY"


# ------------------------------------------------------------
# 2. Calculate daily means
# ------------------------------------------------------------

echo "Calculating daily means..."

cdo -O daymean \
    "$ITALY" \
    "$DMEAN"


# ------------------------------------------------------------
# Done
# ------------------------------------------------------------

echo "Done."
echo "Italy file:      $ITALY"
echo "Daily mean file: $DMEAN"