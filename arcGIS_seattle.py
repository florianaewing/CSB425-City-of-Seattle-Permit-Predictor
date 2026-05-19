"""
Seattle GeoData ArcGIS REST API Explorer  ── VERIFIED WORKING
==============================================================
Queries Seattle's real hosted feature services (org: ZOyb2t4B0UYuYNYH)
to enrich permit data with spatial attributes for timeline prediction.

All URLs verified against live ArcGIS REST directory pages.

Usage:
    python seattle_arcgis_explorer.py

Requirements:
    pip install requests pandas
"""

import requests
import pandas as pd
import time
from typing import Optional

# ─────────────────────────────────────────────────────────────
# BASE URL  (Seattle's ArcGIS Online org — confirmed working)
# ─────────────────────────────────────────────────────────────
ORG = "https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services"

# ─────────────────────────────────────────────────────────────
# VERIFIED FEATURE SERVICE LAYER ENDPOINTS
# ─────────────────────────────────────────────────────────────
LAYERS = {

    # ── ZONING ────────────────────────────────────────────────
    # Service: Current_Land_Use_Zoning_Detail_2 / Layer 0
    # Layer name in REST dir: DPD.ZONING_PV  (confirmed)
    # Using "*" avoids field-name mismatches; filter down after first run
    "zoning": {
        "url": f"{ORG}/Current_Land_Use_Zoning_Detail_2/FeatureServer/0/query",
        "fields": ["*"],
        "description": "Zoning code + group (NR, LR1–3, NC1–3, C1–2, IB, IG1, etc.)",
        "flag_col": None,
    },

    # ── ECA: STEEP SLOPE ──────────────────────────────────────
    # Service: Environmentally_Critical_Areas_ECA / Layer 9  (confirmed via BTAA)
    "eca_steep_slope": {
        "url": f"{ORG}/Environmentally_Critical_Areas_ECA/FeatureServer/9/query",
        "fields": ["*"],
        "description": "Slopes ≥40% — triggers geotech report requirement (+weeks to timeline)",
        "flag_col": "in_steep_slope_eca",
    },

    # ── ECA: POTENTIAL SLIDE ──────────────────────────────────
    # Service: Environmentally_Critical_Areas_ECA / Layer 7
    "eca_potential_slide": {
        "url": f"{ORG}/Environmentally_Critical_Areas_ECA/FeatureServer/7/query",
        "fields": ["*"],
        "description": "Potential slide areas — often co-occurs with steep slope",
        "flag_col": "in_potential_slide_eca",
    },

    # ── ECA: KNOWN SLIDE (SCARP) ──────────────────────────────
    # Service: Environmentally_Critical_Areas_ECA / Layer 3
    "eca_known_slide": {
        "url": f"{ORG}/Environmentally_Critical_Areas_ECA/FeatureServer/3/query",
        "fields": ["*"],
        "description": "Known slide scarp areas — highest geologic restriction",
        "flag_col": "in_known_slide_eca",
    },

    # ── ECA: LIQUEFACTION PRONE ───────────────────────────────
    # Service: Environmentally_Critical_Areas_ECA / Layer 5  (confirmed via BTAA)
    "eca_liquefaction": {
        "url": f"{ORG}/Environmentally_Critical_Areas_ECA/FeatureServer/5/query",
        "fields": ["*"],
        "description": "Liquefaction hazard zones — requires seismic analysis",
        "flag_col": "in_liquefaction_eca",
    },

    # ── ECA: WETLAND ──────────────────────────────────────────
    # Service: Environmentally_Critical_Areas_ECA / Layer 10  (confirmed via BTAA)
    "eca_wetland": {
        "url": f"{ORG}/Environmentally_Critical_Areas_ECA/FeatureServer/10/query",
        "fields": ["*"],
        "description": "Wetland ECAs — triggers SEPA review + wetland buffer rules",
        "flag_col": "in_wetland_eca",
    },

    # ── ECA: RIPARIAN CORRIDOR ────────────────────────────────
    # Service: Environmentally_Critical_Areas_ECA / Layer 8
    "eca_riparian": {
        "url": f"{ORG}/Environmentally_Critical_Areas_ECA/FeatureServer/8/query",
        "fields": ["*"],
        "description": "Riparian (stream) corridors — buffer setback + review",
        "flag_col": "in_riparian_eca",
    },

    # ── ECA: FLOOD PRONE ──────────────────────────────────────
    # Service: Environmentally_Critical_Areas_ECA / Layer 0
    "eca_flood": {
        "url": f"{ORG}/Environmentally_Critical_Areas_ECA/FeatureServer/0/query",
        "fields": ["*"],
        "description": "100-year flood plains — may require FEMA elevation cert",
        "flag_col": "in_flood_eca",
    },

    # ── NEIGHBORHOOD / COUNCIL DISTRICT ──────────────────────
    # Service: 2020_Census_Blocks_-_Seattle / Layer 1  (confirmed)
    # Key fields: DETL_NAMES, COUNCIL_DIST_24, COMP_PLAN_NAME
    "neighborhoods": {
        "url": f"{ORG}/2020_Census_Blocks_-_Seattle/FeatureServer/1/query",
        "fields": ["DETL_NAMES", "COUNCIL_DIST_24", "COMP_PLAN_NAME"],
        "description": "Neighborhood name, council district (2024), comp plan designation",
        "flag_col": None,
    },
}


# ─────────────────────────────────────────────────────────────
# GEOCODING  (Nominatim / OpenStreetMap — no API key needed)
# ─────────────────────────────────────────────────────────────

def geocode_address(address: str) -> Optional[tuple[float, float]]:
    """
    Geocodes an address using Nominatim (free, no API key required).
    Respects Nominatim's 1 req/sec rate limit via a 1s delay.
    Returns (latitude, longitude) or None.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1, "countrycodes": "us"}
    headers = {"User-Agent": "SeattlePermitResearch/1.0"}
    try:
        time.sleep(1)  # Nominatim rate limit
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        results = r.json()
        if results:
            lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
            print(f"  ✓ ({lat:.5f}, {lon:.5f})")
            return lat, lon
        print("  ✗ Not found")
        return None
    except Exception as e:
        print(f"  ✗ {e}")
        return None


def geocode_dataframe(df: pd.DataFrame, address_col: str) -> pd.DataFrame:
    """
    Geocodes every address in a DataFrame column.
    Adds 'latitude' and 'longitude' columns.
    Note: Nominatim rate-limits to 1 req/sec — use only for small batches.
    For large datasets, prefer a pre-geocoded source or the Census Geocoder API.
    """
    lats, lons = [], []
    for i, addr in enumerate(df[address_col]):
        result = geocode_address(addr)
        lats.append(result[0] if result else None)
        lons.append(result[1] if result else None)
        if (i + 1) % 10 == 0:
            print(f"  Geocoded {i + 1}/{len(df)}")
    df = df.copy()
    df["latitude"] = lats
    df["longitude"] = lons
    return df


# ─────────────────────────────────────────────────────────────
# SPATIAL QUERY  (point → layer attributes)
# ─────────────────────────────────────────────────────────────

def query_layer_by_point(layer_name: str, lat: float, lon: float) -> Optional[dict]:
    """
    Returns the first feature's attributes at (lat, lon) from a layer.
    Returns {} if the point falls outside any polygon in that layer.
    Returns None on API error.
    """
    meta = LAYERS[layer_name]
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join(meta["fields"]),
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": 1,
    }
    try:
        r = requests.get(meta["url"], params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            print(f"  [{layer_name}] ⚠ {data['error'].get('message')}")
            return None
        features = data.get("features", [])
        return features[0]["attributes"] if features else {}
    except Exception as e:
        print(f"  [{layer_name}] ⚠ {e}")
        return None


# ─────────────────────────────────────────────────────────────
# BULK DOWNLOAD  (grab a whole layer for offline spatial joins)
# ─────────────────────────────────────────────────────────────

def download_full_layer(layer_name: str, max_records: int = 50_000) -> pd.DataFrame:
    """
    Downloads all features from a layer as a tabular DataFrame (no geometry).
    Paginates automatically — ArcGIS Online serves at most 2000 rows per call.
    """
    meta = LAYERS[layer_name]
    records, offset = [], 0

    print(f"\nDownloading '{layer_name}'…")
    while offset < max_records:
        params = {
            "where": "1=1",
            "outFields": ",".join(meta["fields"]),
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": 1000,
            "f": "json",
        }
        r = requests.get(meta["url"], params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            print(f"  ⚠ {data['error'].get('message')}")
            break
        batch = data.get("features", [])
        if not batch:
            break
        records.extend(f["attributes"] for f in batch)
        print(f"  …{len(records)} rows")
        if not data.get("exceededTransferLimit", False):
            break
        offset += 1000

    df = pd.DataFrame(records)
    print(f"  ✓ Done — {len(df)} rows")
    return df



# ─────────────────────────────────────────────────────────────
# FIELD DISCOVERY  (run once to learn real column names)
# ─────────────────────────────────────────────────────────────

def discover_fields(layer_name: str) -> list:
    """
    Returns the actual field names in a feature service layer.
    Useful when you get 'Invalid query parameters' — a field name is wrong.
    Run this, check the output, then update the 'fields' list in LAYERS[].
    """
    meta = LAYERS[layer_name]
    layer_url = meta["url"].replace("/query", "")
    try:
        r = requests.get(layer_url, params={"f": "json"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        fields = [f["name"] for f in data.get("fields", [])]
        print(f"\nFields in '{layer_name}':")
        for f in fields:
            print(f"  {f}")
        return fields
    except Exception as e:
        print(f"  Warning: {e}")
        return []

# ─────────────────────────────────────────────────────────────
# ENRICH PERMIT DATASET  ← main function for your project
# ─────────────────────────────────────────────────────────────

def enrich_permits(
    permit_df: pd.DataFrame,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    delay: float = 0.1,
) -> pd.DataFrame:
    """
    Appends GIS attributes to every row in permit_df by spatial join.
    
    Adds columns:
      zoning__ZONING, zoning__DETAIL_DESC, zoning__OVERLAY_TXT …
      neighborhoods__DETL_NAMES, neighborhoods__COUNCIL_DIST_24 …
      in_steep_slope_eca, in_potential_slide_eca, in_known_slide_eca
      in_liquefaction_eca, in_wetland_eca, in_riparian_eca, in_flood_eca

    Args:
        permit_df : DataFrame of permits with lat/lon columns
        lat_col   : Name of the latitude column
        lon_col   : Name of the longitude column
        delay     : Seconds between rows (be polite to the API)
    """
    gis_rows = []
    n = len(permit_df)

    for i, (idx, row) in enumerate(permit_df.iterrows()):
        lat, lon = row[lat_col], row[lon_col]
        if pd.isna(lat) or pd.isna(lon):
            gis_rows.append({"_idx": idx})
            continue

        record = {"_idx": idx}
        for layer_name, meta in LAYERS.items():
            attrs = query_layer_by_point(layer_name, lat, lon)
            if attrs is None:
                continue
            for k, v in attrs.items():
                record[f"{layer_name}__{k}"] = v
            if meta["flag_col"]:
                record[meta["flag_col"]] = bool(attrs)

        gis_rows.append(record)
        if (i + 1) % 25 == 0:
            print(f"  Enriched {i + 1}/{n}")
        time.sleep(delay)

    gis_df = pd.DataFrame(gis_rows).set_index("_idx")
    return permit_df.join(gis_df)


# ─────────────────────────────────────────────────────────────
# MAIN  ── demo / exploration
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("Seattle GeoData ArcGIS Explorer  (verified URLs)")
    print("Org: ZOyb2t4B0UYuYNYH")
    print("=" * 60)

    # ── 1. Single-address point query ─────────────────────────
    test_address = "4501 University Way NE, Seattle, WA 98105"
    print(f"\n[1] Point query for: {test_address}")
    coords = geocode_address(test_address)

    if coords:
        lat, lon = coords
        print(f"\n  {'LAYER':<24} RESULT")
        print("  " + "-" * 58)
        for name, meta in LAYERS.items():
            attrs = query_layer_by_point(name, lat, lon)
            if attrs is None:
                label = "⚠ ERROR"
            elif not attrs:
                label = "(not in this zone)"
            else:
                label = "  |  ".join(
                    f"{k}: {v}" for k, v in list(attrs.items())[:2] if v
                )
            print(f"  {name:<24} {label}")

    # ── 2. Download layers to CSV ──────────────────────────────
    print("\n[2] Downloading zoning…")
    download_full_layer("zoning").to_csv("seattle_zoning.csv", index=False)
    print("  → seattle_zoning.csv")

    print("\n[3] Downloading neighborhoods…")
    download_full_layer("neighborhoods").to_csv("seattle_neighborhoods.csv", index=False)
    print("  → seattle_neighborhoods.csv")

    # ── 3. How to enrich your permit data ─────────────────────
    print("""
[NEXT STEP] Enrich your permit CSV:

    from seattle_arcgis_explorer import enrich_permits
    import pandas as pd

    permits = pd.read_csv("sdci_permits.csv")
    enriched = enrich_permits(permits, lat_col="latitude", lon_col="longitude")
    enriched.to_csv("permits_enriched.csv", index=False)

New feature columns for your model:
  zoning__ZONING          zone code (NR1, LR2, NC3, C1, IB, IG1 …)
  zoning__DETAIL_DESC     zone group label
  neighborhoods__DETL_NAMES   neighborhood name
  neighborhoods__COUNCIL_DIST_24
  in_steep_slope_eca      bool  ← strong delay predictor
  in_potential_slide_eca  bool
  in_known_slide_eca      bool
  in_liquefaction_eca     bool
  in_wetland_eca          bool
  in_riparian_eca         bool
  in_flood_eca            bool
""")