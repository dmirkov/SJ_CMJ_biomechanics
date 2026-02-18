#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREPARE DATA FOR KPI CALCULATION
=================================
Učitava TSV fajlove sa CoM kolonama, dodaje velocity kolone i priprema za KPI izračunavanje.
"""

import sys
import re
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent / "lib"))
import config


def read_tsv_with_header(file_path: Path) -> Tuple[list, pd.DataFrame, int]:
    """
    Čita TSV fajl sa header-om i vraća header linije, DataFrame i indeks gde počinju podaci.
    """
    header_lines = []
    data_start_idx = None
    
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            stripped = line.rstrip("\n\r")
            header_lines.append(stripped)
            if line.startswith("Frame\tTime\t"):
                data_start_idx = i
                break
    
    if data_start_idx is None:
        raise ValueError(f"Cannot find 'Frame\\tTime\\t' header in {file_path.name}")
    
    # Pročitaj DataFrame počevši od data_start_idx
    df = pd.read_csv(file_path, sep="\t", skiprows=data_start_idx, header=0)
    
    return header_lines, df, data_start_idx


def calculate_velocity(position: np.ndarray, time: np.ndarray, fs: float = None) -> np.ndarray:
    """
    Izračunava brzinu iz pozicije koristeći numeričku diferencijaciju.
    
    Args:
        position: Niz pozicija (m)
        time: Niz vremena (s)
        fs: Sampling rate (Hz), ako nije dat, izračunava se iz time
        
    Returns:
        Niz brzina (m/s)
    """
    if fs is None:
        if len(time) > 1:
            dt = np.mean(np.diff(time))
            if dt > 0:
                fs = 1.0 / dt
            else:
                fs = config.FS_DEFAULT
        else:
            fs = config.FS_DEFAULT
    
    dt = 1.0 / fs
    
    # Koristi numpy gradient za numeričku diferencijaciju
    # gradient koristi centralne razlike gde je moguće
    velocity = np.gradient(position, dt)
    
    return velocity


def parse_filename(filename: str) -> Optional[dict]:
    """
    Parsira ime fajla u formatu: "##_#_#.tsv"
    """
    basename = filename.replace('.tsv', '')
    pattern = r'^(\d+)_(\d+)_(\d+)$'
    match = re.match(pattern, basename)
    
    if not match:
        return None
    
    subject_id = match.group(1)
    jump_type_code = int(match.group(2))
    trial_no = int(match.group(3))
    
    # Mapiranje JumpTypeCode na JumpType
    if jump_type_code == 3:
        jump_type = 'SJ'
    elif jump_type_code == 4:
        jump_type = 'CMJ'
    else:
        return None
    
    return {
        'SubjectID': subject_id,
        'JumpTypeCode': jump_type_code,
        'TrialNo': trial_no,
        'JumpType': jump_type,
        'basename': basename,
        'filename': filename
    }


def process_file(input_file: Path, output_dir: Path) -> Tuple[bool, str]:
    """
    Procesira jedan TSV fajl: dodaje velocity kolone i čuva kao processed fajl.
    
    Returns:
        (success, message)
    """
    try:
        # Parsiraj ime fajla
        file_info = parse_filename(input_file.name)
        if file_info is None:
            return False, f"Cannot parse filename: {input_file.name}"
        
        # Pročitaj TSV sa header-om
        header_lines, df, data_start_idx = read_tsv_with_header(input_file)
        
        # Proveri da li postoje CoM kolone
        com_cols = {
            '3D': 'CoM3D_Z',
            '2DL': 'CoM2DL_Z',
            '2DR': 'CoM2DR_Z'
        }
        
        missing_com = []
        for model, col in com_cols.items():
            if col not in df.columns:
                missing_com.append(col)
        
        if missing_com:
            return False, f"Missing CoM columns: {missing_com}"
        
        # Proveri Time kolonu
        if 'Time' not in df.columns:
            return False, "Missing Time column"
        
        # Izračunaj sampling rate
        time = df['Time'].values
        if len(time) > 1:
            valid_time = time[~pd.isna(time)]
            if len(valid_time) > 1:
                dt = np.mean(np.diff(valid_time))
                if dt > 0:
                    fs = 1.0 / dt
                else:
                    fs = config.FS_DEFAULT
            else:
                fs = config.FS_DEFAULT
        else:
            fs = config.FS_DEFAULT
        
        # Izračunaj velocity kolone za svaki model
        velocity_cols = {
            '3D': 'V_z_3D',
            '2DL': 'V_z_2DL',
            '2DR': 'V_z_2DR'
        }
        
        for model, com_col in com_cols.items():
            vz_col = velocity_cols[model]
            
            # Izračunaj brzinu
            com_z = df[com_col].values
            
            # Popuni NaN vrednosti
            com_z = pd.Series(com_z).ffill().bfill().values
            
            # Izračunaj velocity
            vz = calculate_velocity(com_z, time, fs)
            
            # Dodaj u DataFrame
            df[vz_col] = vz
        
        # Kreiraj output ime fajla: ##_#_#_processed.tsv
        output_filename = f"{file_info['basename']}_processed.tsv"
        output_file = output_dir / output_filename
        
        # Sačuvaj kao TSV (bez header-a, samo podaci)
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, sep="\t", index=False)
        
        return True, f"OK - fs={fs:.1f}Hz"
    
    except Exception as e:
        return False, f"ERROR: {str(e)}"


def main():
    from paths_config import CMJ_QUALISYS_COM, SJ_QUALISYS_COM, PROCESSED_DATA_DIR
    cmj_input = CMJ_QUALISYS_COM
    sj_input = SJ_QUALISYS_COM
    output_dir = PROCESSED_DATA_DIR
    
    print("=" * 90)
    print("PREPARACIJA PODATAKA ZA KPI IZRACUNAVANJE")
    print("=" * 90)
    print(f"\nInput folderi:")
    print(f"  - {cmj_input}")
    print(f"  - {sj_input}")
    print(f"\nOutput folder:")
    print(f"  - {output_dir}")
    print("=" * 90)
    
    total_processed = 0
    total_success = 0
    total_failed = 0
    
    # Procesiraj CMJ folder
    if cmj_input.exists():
        cmj_files = sorted(cmj_input.glob("*.tsv"))
        print(f"\n[CMJ_Qualisys_CoM] Obrada {len(cmj_files)} fajlova...")
        
        for input_file in cmj_files:
            success, message = process_file(input_file, output_dir)
            
            total_processed += 1
            if success:
                total_success += 1
                print(f"  [OK] {input_file.name}: {message}")
            else:
                total_failed += 1
                print(f"  [ERROR] {input_file.name}: {message}")
    else:
        print(f"\n[WARNING] Folder ne postoji: {cmj_input}")
    
    # Procesiraj SJ folder
    if sj_input.exists():
        sj_files = sorted(sj_input.glob("*.tsv"))
        print(f"\n[SJ_Qualisys_CoM] Obrada {len(sj_files)} fajlova...")
        
        for input_file in sj_files:
            success, message = process_file(input_file, output_dir)
            
            total_processed += 1
            if success:
                total_success += 1
                print(f"  [OK] {input_file.name}: {message}")
            else:
                total_failed += 1
                print(f"  [ERROR] {input_file.name}: {message}")
    else:
        print(f"\n[WARNING] Folder ne postoji: {sj_input}")
    
    # Finalni izveštaj
    print("\n" + "=" * 90)
    print("FINALNI IZVESTAJ")
    print("=" * 90)
    print(f"Ukupno obrađeno: {total_processed}")
    print(f"Uspešno: {total_success}")
    print(f"Neuspešno: {total_failed}")
    
    if total_failed == 0:
        print("\n[SUCCESS] Svi fajlovi su uspešno pripremljeni!")
        print(f"\nProcessed fajlovi su sačuvani u: {output_dir}")
        print("\nSledeći korak: Pokrenite KPI izračunavanje")
        return 0
    else:
        print(f"\n[WARNING] {total_failed} fajlova nije uspešno obrađeno")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
