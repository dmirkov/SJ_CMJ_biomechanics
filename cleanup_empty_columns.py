#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to remove empty trailing columns from TSV files.
Ensures consistent format: removes trailing empty tab-delimited columns.
"""

from pathlib import Path
import shutil
from datetime import datetime

def cleanup_tsv_file(filepath, backup=True):
    """Remove empty trailing columns from TSV file"""
    
    # Create backup
    if backup:
        backup_path = filepath.parent / f"{filepath.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{filepath.suffix}"
        shutil.copy2(filepath, backup_path)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    header_line_idx = None
    frame_header_idx = None
    
    for i, line in enumerate(lines):
        line_stripped = line.rstrip('\n\r')
        
        # Find Frame header line
        if line_stripped.startswith('Frame\tTime'):
            frame_header_idx = i
            # Remove trailing empty tab columns from Frame header
            parts = line_stripped.split('\t')
            # Remove trailing empty strings (from trailing tabs)
            while parts and parts[-1] == '':
                parts.pop()
            new_line = '\t'.join(parts)
            new_lines.append(new_line + '\n')
        else:
            # For data rows (after Frame header), remove trailing empty columns too
            if frame_header_idx is not None and i > frame_header_idx:
                parts = line_stripped.split('\t')
                # Remove trailing empty strings
                while parts and parts[-1] == '':
                    parts.pop()
                new_line = '\t'.join(parts)
                new_lines.append(new_line + '\n')
            else:
                # For header lines before Frame, keep as is
                new_lines.append(line.rstrip('\n\r') + '\n')
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    return backup_path if backup else None

def main():
    base_path = Path(__file__).parent
    
    cmj_folder = base_path / "CMJ_Qualisys"
    sj_folder = base_path / "SJ_Qualisys"
    
    print("=" * 80)
    print("CISCENJE PRAZNIH KOLONA")
    print("=" * 80)
    
    total_processed = 0
    total_backup = 0
    
    # Process CMJ folder
    if cmj_folder.exists():
        cmj_files = sorted(cmj_folder.glob("*.tsv"))
        print(f"\n[CMJ_Qualisys] Obrada {len(cmj_files)} fajlova...")
        for file in cmj_files:
            try:
                backup_path = cleanup_tsv_file(file, backup=True)
                total_processed += 1
                if backup_path:
                    total_backup += 1
                print(f"  OK: {file.name}")
            except Exception as e:
                print(f"  ERROR: {file.name}: {e}")
    
    # Process SJ folder
    if sj_folder.exists():
        sj_files = sorted(sj_folder.glob("*.tsv"))
        print(f"\n[SJ_Qualisys] Obrada {len(sj_files)} fajlova...")
        for file in sj_files:
            try:
                backup_path = cleanup_tsv_file(file, backup=True)
                total_processed += 1
                if backup_path:
                    total_backup += 1
                print(f"  OK: {file.name}")
            except Exception as e:
                print(f"  ERROR: {file.name}: {e}")
    
    print("\n" + "=" * 80)
    print(f"ZAVRSENO: {total_processed} fajlova obrađeno, {total_backup} backup-a kreirano")
    print("=" * 80)

if __name__ == "__main__":
    main()
