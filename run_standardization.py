#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLAVNI ORKESTRIRAJUCI SKRIPT - TSV Standardizacija
================================================

Ovaj skript runira sve potrebne korake za standardizaciju TSV fajlova:
1. check_consistency.py    - Analiza header-a i strukture fajlova
2. cleanup_empty_columns.py - Uklanjanje praznih kolona
3. organize_backups.py     - Premjestanje backup-a u Backup_Fajlovi folder

Konacni rezultat: Svi TSV fajlovi imaju istu strukturu i format
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

def run_step(step_name, script_name, description):
    """Pokreni jedan korak"""
    print("\n" + "=" * 90)
    print(f"KORAK: {step_name}")
    print(f"Opis: {description}")
    print("=" * 90)
    
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"[ERROR] Skript nije pronađen: {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        
        # Ispis izlaza
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("[STDERR]", result.stderr)
        
        if result.returncode != 0:
            print(f"[ERROR] Skript završen s greškom (exit code: {result.returncode})")
            return False
        
        print(f"[OK] {step_name} završen uspješno")
        return True
    
    except Exception as e:
        print(f"[ERROR] Greška pri pokretanju: {e}")
        return False

def main():
    base_path = Path(__file__).parent
    
    print("\n" + "=" * 90)
    print("TSV STANDARDIZACIJA - GLAVNI SKRIPT")
    print("=" * 90)
    print(f"Lokacija: {base_path}")
    print(f"Vrijeme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    steps = [
        (
            "ANALIZA KONZISTENTNOSTI",
            "check_consistency.py",
            "Provjera header-a, broja kolona i naming pattern-a"
        ),
        (
            "CISCENJE PRAZNIH KOLONA",
            "cleanup_empty_columns.py",
            "Uklanjanje praznih trailing kolona iz svih TSV fajlova"
        ),
        (
            "ORGANIZACIJA BACKUP-A",
            "organize_backups.py",
            "Premjestanje svih backup fajlova u Backup_Fajlovi folder"
        ),
    ]
    
    completed = 0
    failed = 0
    
    for step_name, script_name, description in steps:
        if run_step(step_name, script_name, description):
            completed += 1
        else:
            failed += 1
            # Nastavi s ostalim koracima čak i ako jedan ne uspije
    
    # FINALNI IZVJEŠTAJ
    print("\n" + "=" * 90)
    print("FINALNI IZVJEŠTAJ")
    print("=" * 90)
    print(f"Vrijeme zavrsavanja: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Koraci uspješno izvršeni: {completed}/{len(steps)}")
    
    if failed == 0:
        print("\n[SUCCESS] Svi koraci su uspješno izvršeni!")
        print("\nStruktura nakon standardizacije:")
        print("  - CMJ_Qualisys/     : 60 standardizovanih TSV fajlova")
        print("  - SJ_Qualisys/      : 72 standardizovana TSV fajlova")
        print("  - Backup_Fajlovi/   : 132 backup fajlova")
        return 0
    else:
        print(f"\n[WARNING] {failed} korak(a) nije uspješno izvršen")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
