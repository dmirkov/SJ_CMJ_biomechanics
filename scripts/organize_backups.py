#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KORAK 3: ORGANIZACIJA BACKUP-A
==============================
Premješa sve backup fajlove iz CMJ_Qualisys i SJ_Qualisys 
u centralizovani Backup_Fajlovi folder.
"""

import shutil
from pathlib import Path

def organize_backups():
    """Premjesti sve backup fajlove"""
    
    base_path = Path(__file__).parent.parent
    backup_folder = base_path / "Backup_Fajlovi"
    
    # Kreiraj Backup_Fajlovi folder ako ne postoji
    backup_folder.mkdir(exist_ok=True)
    
    cmj_folder = base_path / "CMJ_Qualisys"
    sj_folder = base_path / "SJ_Qualisys"
    
    total_moved = 0
    
    # Premjesti iz CMJ_Qualisys
    if cmj_folder.exists():
        cmj_backups = sorted(cmj_folder.glob("*_backup_*.tsv"))
        for backup_file in cmj_backups:
            destination = backup_folder / backup_file.name
            shutil.move(str(backup_file), str(destination))
            total_moved += 1
    
    # Premjesti iz SJ_Qualisys
    if sj_folder.exists():
        sj_backups = sorted(sj_folder.glob("*_backup_*.tsv"))
        for backup_file in sj_backups:
            destination = backup_folder / backup_file.name
            shutil.move(str(backup_file), str(destination))
            total_moved += 1
    
    return total_moved

def verify_organization():
    """Verificira da su backup-i pravilno organizovani"""
    
    base_path = Path(__file__).parent.parent
    
    cmj_folder = base_path / "CMJ_Qualisys"
    sj_folder = base_path / "SJ_Qualisys"
    backup_folder = base_path / "Backup_Fajlovi"
    
    cmj_backups = list(cmj_folder.glob("*_backup_*.tsv"))
    sj_backups = list(sj_folder.glob("*_backup_*.tsv"))
    backup_files = list(backup_folder.glob("*.tsv"))
    
    return {
        'cmj_backups_left': len(cmj_backups),
        'sj_backups_left': len(sj_backups),
        'backup_folder_count': len(backup_files),
        'clean': len(cmj_backups) == 0 and len(sj_backups) == 0
    }

def main():
    print("=" * 80)
    print("KORAK 3: ORGANIZACIJA BACKUP-A")
    print("=" * 80)
    
    print("\nPremjestanje backup fajlova...")
    total_moved = organize_backups()
    print(f"Premješteno: {total_moved} fajlova")
    
    print("\nVerifikacija organizacije...")
    verification = verify_organization()
    
    print(f"\nRezultati:")
    print(f"  Backup fajlova u CMJ_Qualisys: {verification['cmj_backups_left']} (trebalo 0)")
    print(f"  Backup fajlova u SJ_Qualisys: {verification['sj_backups_left']} (trebalo 0)")
    print(f"  Backup fajlova u Backup_Fajlovi: {verification['backup_folder_count']}")
    
    print("\n" + "=" * 80)
    if verification['clean']:
        print("Rezultat: SUCCESS - Sve backup fajlove su pravilno organizovane!")
    else:
        print("Rezultat: PROBLEM - Neke backup fajlove nisu pravilno premještene")
    print("=" * 80)

if __name__ == "__main__":
    main()
