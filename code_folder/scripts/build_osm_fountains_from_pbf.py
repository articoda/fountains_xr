# Build OSM fountain CSVs from the local Geofabrik Italy PBF.

from pathlib import Path
from datetime import datetime, timezone
import json
import time

import osmium
import pandas as pd


# Repository/code folder is the parent of the script/ folder.
CODE_DIR = Path(__file__).resolve().parents[1]

# Analysis folder.
PROJECT_DIR = CODE_DIR / "fountain_analysis"

# Input PBF downloaded by prepare_data.py.
OSM_PBF_FILE = PROJECT_DIR / "data" / "osm" / "italy-latest.osm.pbf"

# Output folders.
FOUNTAIN_DIR = PROJECT_DIR / "data" / "fountains"
OSM_CHECK_DIR = PROJECT_DIR / "data" / "osm_checks"

# Output files.
FOUNTAIN_RAW_FILE = FOUNTAIN_DIR / "fountains_osm_raw.csv"
FOUNTAIN_CLEAN_FILE = FOUNTAIN_DIR / "fountains_osm_clean.csv"
OSM_CHECK_SUMMARY_FILE = OSM_CHECK_DIR / "fountains_osm_check_summary.csv"


def matching_rules(tags):
    """
    Identify which OSM tagging rule matched this object.
    """

    rules = []

    if tags.get("amenity") == "drinking_water":
        rules.append("amenity=drinking_water")

    if tags.get("amenity") == "fountain" and tags.get("drinking_water") == "yes":
        rules.append("amenity=fountain + drinking_water=yes")

    if tags.get("man_made") == "water_tap" and tags.get("drinking_water") == "yes":
        rules.append("man_made=water_tap + drinking_water=yes")

    if tags.get("fountain") == "drinking":
        rules.append("fountain=drinking")

    return rules


def exclusion_reason(tags):
    """
    Decide whether to exclude a candidate from the clean dataset.
    """

    if tags.get("drinking_water") == "no":
        return "drinking_water=no"

    if tags.get("access") in {"private", "no", "customers"}:
        return f"access={tags.get('access')}"

    if tags.get("fee") == "yes":
        return "fee=yes"

    if tags.get("indoor") == "yes":
        return "indoor=yes"

    if tags.get("disused") == "yes":
        return "disused=yes"

    if tags.get("abandoned") == "yes":
        return "abandoned=yes"

    for key in tags:
        if key.startswith("disused:"):
            return "disused"

        if key.startswith("abandoned:"):
            return "abandoned"

        if key.startswith("was:"):
            return "was"

    return ""


class FountainNodeHandler(osmium.SimpleHandler):
    """
    Extract drinking-water fountain candidates from OSM nodes.

    First version: node-only.
    Most fountains and water taps are mapped as nodes.

    The progress indicator prints how many nodes have been scanned,
    how many candidates have been found, and how long the scan has taken.
    """

    def __init__(self, report_every=1_000_000):
        super().__init__()

        self.rows = []
        self.extracted_at = datetime.now(timezone.utc).isoformat()

        self.nodes_seen = 0
        self.candidates_found = 0
        self.clean_found = 0
        self.report_every = report_every
        self.start_time = time.time()

    def print_progress(self):
        """
        Print progress information.
        """

        elapsed = time.time() - self.start_time

        print(
            f"Scanned {self.nodes_seen:,} nodes | "
            f"candidates: {self.candidates_found:,} | "
            f"clean: {self.clean_found:,} | "
            f"elapsed: {elapsed / 60:.1f} min",
            flush=True,
        )

    def node(self, node):
        """
        Process one OSM node.
        """

        self.nodes_seen += 1

        if self.nodes_seen % self.report_every == 0:
            self.print_progress()

        tags = {tag.k: tag.v for tag in node.tags}

        rules = matching_rules(tags)

        if not rules:
            return

        if not node.location.valid():
            return

        reason = exclusion_reason(tags)

        self.candidates_found += 1

        if reason == "":
            self.clean_found += 1

        osm_type = "node"
        osm_id = node.id

        self.rows.append(
            {
                "id": f"{osm_type}/{osm_id}",
                "osm_type": osm_type,
                "osm_id": osm_id,
                "osm_version": node.version,
                "osm_timestamp": str(node.timestamp),
                "osm_user": node.user,
                "osm_uid": node.uid,
                "lat": node.location.lat,
                "lon": node.location.lon,
                "matched_rules": "; ".join(rules),
                "amenity": tags.get("amenity", ""),
                "man_made": tags.get("man_made", ""),
                "fountain": tags.get("fountain", ""),
                "drinking_water": tags.get("drinking_water", ""),
                "access": tags.get("access", ""),
                "fee": tags.get("fee", ""),
                "indoor": tags.get("indoor", ""),
                "name": tags.get("name", ""),
                "operator": tags.get("operator", ""),
                "include_clean": reason == "",
                "exclusion_reason": reason,
                "source_file": OSM_PBF_FILE.name,
                "source_extracted_at": self.extracted_at,
                "tags_json": json.dumps(tags, ensure_ascii=False, sort_keys=True),
            }
        )


def build_summary(df):
    """
    Build a compact summary CSV to check what we extracted.
    """

    rows = []

    rows.append(
        {
            "check": "raw_candidates",
            "category": "all",
            "count": len(df),
        }
    )

    rows.append(
        {
            "check": "clean_fountains",
            "category": "all",
            "count": int(df["include_clean"].sum()),
        }
    )

    for reason, count in df["exclusion_reason"].replace("", "included").value_counts().items():
        rows.append(
            {
                "check": "exclusion_reason",
                "category": reason,
                "count": int(count),
            }
        )

    exploded = (
        df.assign(matched_rule=df["matched_rules"].str.split("; "))
        .explode("matched_rule")
    )

    for rule, count in exploded["matched_rule"].value_counts().items():
        rows.append(
            {
                "check": "matched_rule",
                "category": rule,
                "count": int(count),
            }
        )

    for column in [
        "amenity",
        "man_made",
        "fountain",
        "drinking_water",
        "access",
        "fee",
        "indoor",
    ]:
        for value, count in df[column].replace("", "missing").value_counts().items():
            rows.append(
                {
                    "check": column,
                    "category": value,
                    "count": int(count),
                }
            )

    return pd.DataFrame(rows)


def main():
    """
    Extract fountains from the local Italy PBF and save CSVs.
    """

    if not OSM_PBF_FILE.exists():
        raise FileNotFoundError(
            f"OSM PBF not found:\n  {OSM_PBF_FILE}\n\n"
            "Run prepare_data.py first, or place italy-latest.osm.pbf there manually."
        )

    FOUNTAIN_DIR.mkdir(parents=True, exist_ok=True)
    OSM_CHECK_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading local OSM file:")
    print(f"  {OSM_PBF_FILE}")
    print()
    print("This may take a few minutes...")
    print()

    handler = FountainNodeHandler(report_every=1_000_000)

    handler.apply_file(
        str(OSM_PBF_FILE),
        locations=True,
    )

    handler.print_progress()

    df = pd.DataFrame(handler.rows)

    if df.empty:
        raise RuntimeError("No fountain candidates found.")

    df = df.drop_duplicates(subset=["osm_type", "osm_id"])
    df = df.sort_values(["osm_type", "osm_id"]).reset_index(drop=True)

    clean = df[df["include_clean"]].copy()

    df.to_csv(
        FOUNTAIN_RAW_FILE,
        sep="|",
        index=False,
    )

    clean.to_csv(
        FOUNTAIN_CLEAN_FILE,
        sep="|",
        index=False,
    )

    summary = build_summary(df)

    summary.to_csv(
        OSM_CHECK_SUMMARY_FILE,
        index=False,
    )

    print()
    print("Saved raw fountain candidates:")
    print(f"  {FOUNTAIN_RAW_FILE}")

    print("Saved clean fountain file:")
    print(f"  {FOUNTAIN_CLEAN_FILE}")

    print("Saved OSM check summary:")
    print(f"  {OSM_CHECK_SUMMARY_FILE}")

    print()
    print(f"Raw candidates: {len(df):,}")
    print(f"Clean fountains: {len(clean):,}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
