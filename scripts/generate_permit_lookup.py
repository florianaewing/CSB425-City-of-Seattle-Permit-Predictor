"""
generate_permit_lookup.py
-------------------------
Builds permit_lookup.json from the full raw building_permits.csv file,
filtered to post-2000 permits with valid coordinates and recorded review times.

This produces broader address coverage than the modeling population alone,
giving the demo website more historical matches for the history card.

Input  : data/building_permits.csv
Output : permit_lookup.json (repository root, alongside index.html)

Run from the repository root:
    python scripts/generate_permit_lookup.py
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parent.parent
DATA_DIR    = REPO_ROOT / 'data'
OUTPUT_PATH = REPO_ROOT / 'permit_lookup.json'

INPUT_FILE  = DATA_DIR / 'building_permits.csv'

print(f'Loading: {INPUT_FILE}')
df = pd.read_csv(INPUT_FILE, low_memory=False)
print(f'Raw rows: {len(df):,}')

# ── Parse dates & filter to post-2000 ─────────────────────────────
df['applieddate'] = pd.to_datetime(df['applieddate'], errors='coerce')
df['app_year']    = df['applieddate'].dt.year

df = df[df['app_year'] >= 2000]
print(f'After post-2000 filter: {len(df):,}')

# ── Drop rows missing required fields ─────────────────────────────
df = df.dropna(subset=['latitude', 'longitude', 'totaldaysplanreview', 'originaladdress1'])
print(f'After dropping nulls: {len(df):,}')

# ── Drop impossible review times ──────────────────────────────────
df = df[df['totaldaysplanreview'] > 0]
print(f'After dropping zero/negative review times: {len(df):,}')

# ── Clean & round ──────────────────────────────────────────────────
df['latitude']            = df['latitude'].round(5)
df['longitude']           = df['longitude'].round(5)
df['totaldaysplanreview'] = df['totaldaysplanreview'].astype(int)
df['estprojectcost']      = df['estprojectcost'].fillna(0).astype(int)
df['permittypedesc']      = df['permittypedesc'].fillna('Unknown')
df['permitclass']         = df['permitclass'].fillna('Unknown')
df['zoning']              = df['zoning'].fillna('Unknown')
df['app_year']            = df['app_year'].astype(int)

# ── Build spatial grid index ───────────────────────────────────────
# Grid cells are ~110m squares (0.001 degree resolution)
# Each cell key maps to a list of permits in that area
df['grid_lat'] = df['latitude'].round(3)
df['grid_lon'] = df['longitude'].round(3)

index = {}
for _, row in df.iterrows():
    key = f"{row.grid_lat:.3f},{row.grid_lon:.3f}"
    rec = {
        'p':  row.permitnum,
        'a':  row.originaladdress1,
        'la': row.latitude,
        'lo': row.longitude,
        'd':  row.totaldaysplanreview,
        't':  row.permittypedesc,
        'c':  row.permitclass,
        'z':  row.zoning,
        'co': row.estprojectcost,
        'y':  row.app_year,
    }
    if key not in index:
        index[key] = []
    index[key].append(rec)

# ── Save ───────────────────────────────────────────────────────────
output_str = json.dumps(index, separators=(',', ':'))
size_kb    = len(output_str.encode('utf-8')) / 1024

with open(OUTPUT_PATH, 'w') as f:
    f.write(output_str)

print(f'\nDone.')
print(f'  Grid cells : {len(index):,}')
print(f'  Permits    : {len(df):,}')
print(f'  File size  : {size_kb:.0f} KB ({size_kb/1024:.2f} MB)')
print(f'  Saved to   : {OUTPUT_PATH}')