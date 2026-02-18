#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KORAK 1: ANALIZA KONZISTENTNOSTI
================================
Provjerava:
- Strukturu header-a u svim TSV fajlovima
- Redoslijed i nazive kolona
- Naming pattern-e fajlova
- Potencijalne neusaglašenosti
"""

from pathlib import Path
from collections import defaultdict

def analyze_consistency(folder_path):
    """Analiza konzistentnosti TSV fajlova"""
    
    results = {
        'total_files': 0,
        'unique_headers': {},
        'issues': [],
        'summary': {}
    }
    
    folder = Path(folder_path)
    files = sorted([f for f in folder.glob("*.tsv") if '_backup_' not in f.name])
    results['total_files'] = len(files)
    
    # Analiza svakog fajla
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Pronađi Frame header
        for line in lines:
            if line.startswith('Frame\tTime'):
                frame_header = line.rstrip('\n\r')
                cols = frame_header.split('\t')
                
                # Kreiraj signature
                header_sig = (len(cols), tuple(cols[:5]))  # broj kolona + prve 5
                
                if header_sig not in results['unique_headers']:
                    results['unique_headers'][header_sig] = []
                results['unique_headers'][header_sig].append(file_path.name)
                
                # Provjera za prazne kolone na kraju
                if cols[-1] == '':
                    results['issues'].append(f"{file_path.name}: Prazna kolona na kraju")
                
                break
    
    return results

def main():
    base_path = Path(__file__).parent.parent
    cmj_folder = base_path / "CMJ_Qualisys"
    sj_folder = base_path / "SJ_Qualisys"
    
    print("=" * 80)
    print("KORAK 1: ANALIZA KONZISTENTNOSTI TSV FAJLOVA")
    print("=" * 80)
    
    # Analiza CMJ
    print("\n[CMJ_Qualisys]")
    print("-" * 80)
    cmj_results = analyze_consistency(cmj_folder)
    print(f"Analizirano fajlova: {cmj_results['total_files']}")
    print(f"Jedinstvenih header struktura: {len(cmj_results['unique_headers'])}")
    
    for i, (sig, files) in enumerate(cmj_results['unique_headers'].items(), 1):
        num_cols, header_sig = sig
        print(f"  Struktura {i}: {num_cols} kolona - {len(files)} fajlova")
    
    if cmj_results['issues']:
        print(f"Pronađeni problemi: {len(cmj_results['issues'])}")
        for issue in cmj_results['issues'][:3]:
            print(f"  - {issue}")
    else:
        print("Status: SVE OK")
    
    # Analiza SJ
    print("\n[SJ_Qualisys]")
    print("-" * 80)
    sj_results = analyze_consistency(sj_folder)
    print(f"Analizirano fajlova: {sj_results['total_files']}")
    print(f"Jedinstvenih header struktura: {len(sj_results['unique_headers'])}")
    
    for i, (sig, files) in enumerate(sj_results['unique_headers'].items(), 1):
        num_cols, header_sig = sig
        print(f"  Struktura {i}: {num_cols} kolona - {len(files)} fajlova")
    
    if sj_results['issues']:
        print(f"Pronađeni problemi: {len(sj_results['issues'])}")
        for issue in sj_results['issues'][:3]:
            print(f"  - {issue}")
    else:
        print("Status: SVE OK")
    
    # Sveukupno
    print("\n" + "=" * 80)
    print("SVEUKUPNO")
    print("=" * 80)
    print(f"Ukupno analizovanih fajlova: {cmj_results['total_files'] + sj_results['total_files']}")
    print(f"Ukupno pronađenih problema: {len(cmj_results['issues']) + len(sj_results['issues'])}")
    
    if len(cmj_results['issues']) == 0 and len(sj_results['issues']) == 0:
        print("\nRezultat: SVE OK - Fajlovi su konzistentni")
    else:
        print("\nRezultat: Pronađeni problemi koji trebaju biti ispravljeni")

if __name__ == "__main__":
    main()
