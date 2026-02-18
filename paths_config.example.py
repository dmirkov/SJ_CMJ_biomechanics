#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KONFIGURACIJA PUTANJA
=====================
1. Kopiraj ovaj fajl kao paths_config.py
2. Postavi DATA_ROOT na cloud lokaciju gde su podaci (TSV, FP, processed_data)
3. PROJECT_ROOT se automatski detektuje - ne menjaj ako nije potrebno
"""
from pathlib import Path

# Koren projekta (gde je repo) - automatski
PROJECT_ROOT = Path(__file__).parent

# Koren podataka - OBAVEZNO postavi na cloud lokaciju
# Primer: OneDrive, Google Drive, Dropbox, ili lokalni disk ako nije cloud
DATA_ROOT = Path(r"X:\SJ_CMJ_Data")  # <-- PROMENI na svoju putanju

# Izvedene putanje (podaci na cloud-u)
PROCESSED_DATA_DIR = DATA_ROOT / "processed_data"
SJ_FORCE_PLATES = DATA_ROOT / "SJ_ForcePlates"
CMJ_FORCE_PLATES = DATA_ROOT / "CMJ_ForcePlates"
SJ_QUALISYS = DATA_ROOT / "SJ_Qualisys"
CMJ_QUALISYS = DATA_ROOT / "CMJ_Qualisys"
SJ_QUALISYS_COM = DATA_ROOT / "SJ_Qualisys_CoM"
CMJ_QUALISYS_COM = DATA_ROOT / "CMJ_Qualisys_CoM"

# Output ostaje u projektu (ne opterecuje cloud)
OUTPUT_DIR = PROJECT_ROOT / "Output"
EXCEL_DIR = OUTPUT_DIR / "Excel"
