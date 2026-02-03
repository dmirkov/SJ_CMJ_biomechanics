#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Provera konzistentnosti TSV fajlova:
1. Isti header struktura
2. Isti nazivi kolona
3. Postoje li podaci u svim kolonama
"""

import os
from pathlib import Path
from collections import defaultdict

def read_tsv_header(filepath):
    """Pročita header i prve nekoliko redova podataka"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    header_lines = []
    data_start_idx = None
    
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n\r')
        header_lines.append(stripped)
        
        if stripped.startswith('Frame\tTime'):
            data_start_idx = i + 1
            break
    
    # Ako nema Frame/Time header, traži prvi red sa podacima
    if data_start_idx is None:
        for i, line in enumerate(lines):
            stripped = line.rstrip('\n\r')
            if stripped and not stripped.startswith('NO_OF_') and not stripped.startswith('DATA_') and not stripped.startswith('FREQUENCY') and not stripped.startswith('TIME_STAMP'):
                if '\t' in stripped and len(stripped.split('\t')) > 2:
                    data_start_idx = i
                    break
    
    return header_lines, data_start_idx, lines[data_start_idx:min(data_start_idx+5, len(lines))] if data_start_idx else []

def extract_metadata(header_lines):
    """Ekstraktuje metadata iz header-a"""
    metadata = {}
    data_types_line = None
    frame_header_line = None
    
    for line in header_lines:
        if line.startswith('NO_OF_FRAMES'):
            metadata['NO_OF_FRAMES'] = line.split('\t', 1)[1]
        elif line.startswith('NO_OF_DATA_TYPES'):
            metadata['NO_OF_DATA_TYPES'] = line.split('\t', 1)[1]
        elif line.startswith('FREQUENCY'):
            metadata['FREQUENCY'] = line.split('\t', 1)[1]
        elif line.startswith('TIME_STAMP'):
            metadata['TIME_STAMP'] = line.split('\t', 1)[1]
        elif line.startswith('DATA_INCLUDED'):
            metadata['DATA_INCLUDED'] = line.split('\t', 1)[1]
        elif line.startswith('DATA_TYPES'):
            data_types_line = line
        elif line.startswith('Frame\tTime'):
            frame_header_line = line
    
    return metadata, data_types_line, frame_header_line

def check_data_completeness(filepath, data_types_line, frame_header_line):
    """Proverava da li sve kolone imaju podatke"""
    if not data_types_line or not frame_header_line:
        return None, "Nedostaje DATA_TYPES ili Frame/Time header"
    
    # Ekstraktuj kolone
    data_types_cols = data_types_line.split('\t')[1:]
    frame_cols = frame_header_line.split('\t')[2:]
    
    if len(data_types_cols) != len(frame_cols):
        return None, f"Broj kolona se ne poklapa: DATA_TYPES={len(data_types_cols)}, Frame={len(frame_cols)}"
    
    # Pročitaj podatke
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Pronađi početak podataka
    data_start = None
    for i, line in enumerate(lines):
        if line.startswith('Frame\tTime'):
            data_start = i + 1
            break
    
    if data_start is None:
        return None, "Nije pronađen početak podataka"
    
    # Proveri prvih 10 redova podataka
    empty_columns = set()
    total_rows = 0
    
    for i in range(data_start, min(data_start + 10, len(lines))):
        row = lines[i].rstrip('\n\r')
        if not row.strip():
            continue
        
        parts = row.split('\t')
        if len(parts) < 2:
            continue
        
        # Preskoči Frame i Time kolone
        data_parts = parts[2:]
        total_rows += 1
        
        for col_idx, value in enumerate(data_parts):
            if col_idx < len(frame_cols):
                if not value.strip() or value.strip() == '':
                    empty_columns.add(col_idx)
    
    return {
        'total_columns': len(frame_cols),
        'empty_columns': len(empty_columns),
        'empty_column_indices': sorted(empty_columns),
        'rows_checked': total_rows
    }, None

def analyze_folder(folder_path):
    """Analizira sve TSV fajlove u folderu"""
    folder = Path(folder_path)
    tsv_files = sorted(folder.glob('*.tsv'))
    
    print(f"\n{'='*80}")
    print(f"Analiza foldera: {folder.name}")
    print(f"Ukupno fajlova: {len(tsv_files)}")
    print(f"{'='*80}\n")
    
    # Grupiši po header strukturi
    header_patterns = defaultdict(list)
    column_patterns = defaultdict(list)
    issues = []
    
    for tsv_file in tsv_files:
        try:
            header_lines, data_start, sample_data = read_tsv_header(tsv_file)
            metadata, data_types_line, frame_header_line = extract_metadata(header_lines)
            
            # Kreiraj ključ za header pattern
            header_key = '\n'.join(header_lines[:6])  # Prvih 6 linija
            header_patterns[header_key].append(tsv_file.name)
            
            # Kreiraj ključ za kolone
            if data_types_line:
                cols_key = data_types_line
                column_patterns[cols_key].append(tsv_file.name)
            
            # Proveri podatke
            if data_types_line and frame_header_line:
                completeness, error = check_data_completeness(tsv_file, data_types_line, frame_header_line)
                if error:
                    issues.append(f"{tsv_file.name}: {error}")
                elif completeness and completeness['empty_columns'] > 0:
                    issues.append(f"{tsv_file.name}: {completeness['empty_columns']} praznih kolona u prvih {completeness['rows_checked']} redova")
            
        except Exception as e:
            issues.append(f"{tsv_file.name}: GREŠKA - {str(e)}")
    
    # Izveštaj
    print(f"Različiti header patterni: {len(header_patterns)}")
    if len(header_patterns) > 1:
        print("⚠️  NEDOSLEDNOSTI U HEADER STRUKTURI:")
        for i, (pattern, files) in enumerate(header_patterns.items(), 1):
            print(f"\n  Pattern {i} ({len(files)} fajlova):")
            print(f"    Primer fajlova: {', '.join(files[:5])}")
            if len(files) > 5:
                print(f"    ... i još {len(files)-5} fajlova")
    
    print(f"\nRazličiti column patterni: {len(column_patterns)}")
    if len(column_patterns) > 1:
        print("⚠️  NEDOSLEDNOSTI U NAZIVIMA KOLONA:")
        for i, (pattern, files) in enumerate(column_patterns.items(), 1):
            print(f"\n  Pattern {i} ({len(files)} fajlova):")
            cols = pattern.split('\t')[1:6]  # Prvih 5 kolona
            print(f"    Prvih 5 kolona: {', '.join(cols)}")
            print(f"    Primer fajlova: {', '.join(files[:5])}")
            if len(files) > 5:
                print(f"    ... i još {len(files)-5} fajlova")
    
    if issues:
        print(f"\n⚠️  PROBLEMI ({len(issues)}):")
        for issue in issues[:20]:  # Prvih 20 problema
            print(f"  - {issue}")
        if len(issues) > 20:
            print(f"  ... i još {len(issues)-20} problema")
    else:
        print("\n✅ Nema problema!")
    
    return {
        'total_files': len(tsv_files),
        'header_patterns': len(header_patterns),
        'column_patterns': len(column_patterns),
        'issues': len(issues)
    }

if __name__ == '__main__':
    base_path = Path(__file__).parent
    
    print("="*80)
    print("PROVERA KONZISTENTNOSTI TSV FAJLOVA")
    print("="*80)
    
    cmj_results = analyze_folder(base_path / 'CMJ_Qualisys')
    sj_results = analyze_folder(base_path / 'SJ_Qualisys')
    
    print(f"\n{'='*80}")
    print("REZIME")
    print(f"{'='*80}")
    print(f"\nCMJ_Qualisys:")
    print(f"  Ukupno fajlova: {cmj_results['total_files']}")
    print(f"  Header patterni: {cmj_results['header_patterns']}")
    print(f"  Column patterni: {cmj_results['column_patterns']}")
    print(f"  Problemi: {cmj_results['issues']}")
    
    print(f"\nSJ_Qualisys:")
    print(f"  Ukupno fajlova: {sj_results['total_files']}")
    print(f"  Header patterni: {sj_results['header_patterns']}")
    print(f"  Column patterni: {sj_results['column_patterns']}")
    print(f"  Problemi: {sj_results['issues']}")
    
    total_issues = cmj_results['issues'] + sj_results['issues']
    if total_issues == 0:
        print(f"\n✅ SVI FAJLOVI SU KONZISTENTNI!")
    else:
        print(f"\n⚠️  Ukupno problema: {total_issues}")
