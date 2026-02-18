#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLAVNA SKRIPTA ZA IZRACUNAVANJE KPIs
====================================
1. Priprema podatke (dodaje velocity kolone)
2. Izračunava KPIs za sve modele (3D, 2DL, 2DR)
3. Eksportuje u Excel sa listovima: SJ3D, SJ2DL, SJ2DR, CMJ3D, CMJ2DL, CMJ2DR
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "lib"))
import config


def run_prepare_data():
    """Pokreni pripremu podataka"""
    print("\n" + "=" * 90)
    print("KORAK 1: PRIprema PODATAKA")
    print("=" * 90)
    
    from paths_config import PROCESSED_DATA_DIR
    processed_data_dir = PROCESSED_DATA_DIR
    
    if processed_data_dir.exists():
        processed_files = list(processed_data_dir.glob("*_processed.tsv"))
        if len(processed_files) > 0:
            print(f"[INFO] Processed fajlovi već postoje ({len(processed_files)} fajlova)")
            print("[SKIP] Preskačem pripremu podataka")
            return True
    
    # Ako ne postoje, pokreni pripremu
    script_path = Path(__file__).parent / "prepare_kpi_data.py"
    
    if not script_path.exists():
        print(f"[ERROR] Skript nije pronađen: {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("[STDERR]", result.stderr)
        
        if result.returncode != 0:
            print(f"[ERROR] Skript završen s greškom (exit code: {result.returncode})")
            return False
        
        print("[OK] Priprema podataka završena uspešno")
        return True
    
    except Exception as e:
        print(f"[ERROR] Greška pri pokretanju: {e}")
        return False


def run_kpi_calculation():
    """Pokreni KPI izračunavanje"""
    print("\n" + "=" * 90)
    print("KORAK 2: IZRACUNAVANJE KPIs")
    print("=" * 90)
    
    from paths_config import PROCESSED_DATA_DIR, EXCEL_DIR
    config.PROCESSED_DATA_DIR = PROCESSED_DATA_DIR
    output_excel = EXCEL_DIR / "MoCap_KPIs.xlsx"
    output_excel.parent.mkdir(parents=True, exist_ok=True)
    config.EXCEL_OUTPUT_FILE = output_excel
    
    # Import i pokreni main_kpi
    from main_kpi import process_files
    
    try:
        process_files(mode='all', limit=None, step=None, model=None, verbose=False)
        print("[OK] KPI izračunavanje završeno uspešno")
        return True
    except Exception as e:
        print(f"[ERROR] Greška pri izračunavanju KPIs: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    base_path = Path(__file__).parent
    
    print("=" * 90)
    print("IZRACUNAVANJE KPIs ZA SJ I CMJ SKOKOVE")
    print("=" * 90)
    print(f"Vreme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Lokacija: {base_path}")
    print("=" * 90)
    
    # Korak 1: Priprema podataka
    if not run_prepare_data():
        print("\n[ERROR] Priprema podataka nije uspela. Prekidam.")
        return 1
    
    # Korak 2: KPI izračunavanje
    if not run_kpi_calculation():
        print("\n[ERROR] KPI izračunavanje nije uspelo. Prekidam.")
        return 1
    
    # Finalni izveštaj
    print("\n" + "=" * 90)
    print("FINALNI IZVESTAJ")
    print("=" * 90)
    print(f"Vreme završetka: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    from paths_config import EXCEL_DIR
    output_excel = EXCEL_DIR / "MoCap_KPIs.xlsx"
    if output_excel.exists():
        print(f"\n[SUCCESS] Excel fajl sa KPIs je kreiran!")
        print(f"Lokacija: {output_excel}")
        print(f"\nSheetovi:")
        print("  - SJ3D (SJ 3D model)")
        print("  - SJ2DL (SJ 2D leva strana)")
        print("  - SJ2DR (SJ 2D desna strana)")
        print("  - CMJ3D (CMJ 3D model)")
        print("  - CMJ2DL (CMJ 2D leva strana)")
        print("  - CMJ2DR (CMJ 2D desna strana)")
        return 0
    else:
        print(f"\n[WARNING] Excel fajl nije kreiran: {output_excel}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
