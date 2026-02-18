#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADD CoM COLUMNS TO TSV FILES
============================
Dodaje Center of Mass (CoM) kolone u TSV fajlove koristeći mocap_com_v2_sexmap.py

Kreira nove fajlove sa CoM kolonama u:
- CMJ_Qualisys_CoM/
- SJ_Qualisys_CoM/

Originalni fajlovi ostaju netaknuti.
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional

# Import mocap_com_v2_sexmap module
# Prvo pokušaj da importuje iz relativnog puta, pa iz apsolutnog
try:
    # Pokušaj da importuje iz trenutnog foldera (ako je kopiran)
    from mocap_com_v2_sexmap import (
        read_qualisys_tsv,
        add_com_columns,
        parse_subject_id_from_filename,
    )
except ImportError:
    # Ako ne postoji lokalno, importuj iz drugog projekta
    sys.path.insert(0, str(Path(__file__).parent / "lib"))
    from mocap_com_v2_sexmap import (
        read_qualisys_tsv,
        add_com_columns,
        parse_subject_id_from_filename,
    )

import pandas as pd
import numpy as np


def read_tsv_with_header(file_path: Path) -> Tuple[list, pd.DataFrame, int]:
    """
    Čita TSV fajl sa header-om i vraća header linije, DataFrame i indeks gde počinju podaci.
    
    Returns:
        (header_lines, df, data_start_line)
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


def write_tsv_with_header(
    file_path: Path,
    header_lines: list,
    df: pd.DataFrame,
    data_start_idx: int,
) -> None:
    """
    Piše TSV fajl sa header-om i DataFrame podacima.
    
    Args:
        file_path: Putanja gde da se sačuva fajl
        header_lines: Lista header linija (bez novog reda)
        df: DataFrame sa podacima (uključujući CoM kolone)
        data_start_idx: Indeks gde počinju podaci (Frame\tTime linija)
    """
    # Kreiraj kopiju header_lines za modifikaciju
    updated_header = header_lines.copy()
    
    # Pronađi i ažuriraj NO_OF_DATA_TYPES
    no_data_types_idx = None
    for i, line in enumerate(updated_header):
        if line.startswith("NO_OF_DATA_TYPES"):
            no_data_types_idx = i
            break
    
    if no_data_types_idx is not None:
        # Stari broj + 7 novih CoM kolona
        old_count = int(updated_header[no_data_types_idx].split("\t")[1])
        new_count = old_count + 7
        updated_header[no_data_types_idx] = f"NO_OF_DATA_TYPES\t{new_count}"
    
    # Pronađi i ažuriraj DATA_TYPES liniju
    data_types_idx = None
    for i, line in enumerate(updated_header):
        if line.startswith("DATA_TYPES"):
            data_types_idx = i
            break
    
    if data_types_idx is not None:
        # Ekstraktuj postojeće DATA_TYPES kolone
        existing_types = updated_header[data_types_idx].split("\t")[1:]  # Preskoči "DATA_TYPES"
        
        # Dodaj nove CoM kolone
        com_types = [
            "CoM3D_X", "CoM3D_Y", "CoM3D_Z",
            "CoM2DL_X", "CoM2DL_Z",
            "CoM2DR_X", "CoM2DR_Z"
        ]
        
        # Ažuriraj DATA_TYPES liniju
        all_types = existing_types + com_types
        updated_header[data_types_idx] = "DATA_TYPES\t" + "\t".join(all_types)
    
    # Napiši ažurirani header (sve linije do data_start_idx)
    with file_path.open("w", encoding="utf-8", errors="replace") as f:
        # Napiši sve header linije do data_start_idx (uključujući ažurirane)
        # data_start_idx je indeks Frame\tTime linije, tako da pišemo sve do nje
        # Ali preskačemo prazne linije koje su već uključene u header_lines
        for i in range(data_start_idx):
            f.write(updated_header[i] + "\n")
        
        # Napiši Frame\tTime header sa svim kolonama (zamenjuje originalni Frame\tTime header)
        column_names = list(df.columns)  # df već ima Frame, Time i sve ostale kolone
        f.write("\t".join(column_names) + "\n")
        
        # Napiši podatke
        df.to_csv(f, sep="\t", index=False, header=False, lineterminator="\n")


def process_tsv_file(input_file: Path, output_file: Path) -> Tuple[bool, str]:
    """
    Procesira jedan TSV fajl: dodaje CoM kolone i čuva u output fajl.
    
    Returns:
        (success, message)
    """
    try:
        # Pročitaj TSV sa header-om
        header_lines, df, data_start_idx = read_tsv_with_header(input_file)
        
        # Ekstraktuj SubjectID iz imena fajla
        subject_id = parse_subject_id_from_filename(input_file.name)
        
        # Dodaj CoM kolone
        df_with_com, qc = add_com_columns(
            df_raw=df,
            subject_id=subject_id,
            default_sex_if_unknown="male",
            auto_units=True,
        )
        
        # Proveri da li postoje CoM kolone
        com_cols = ["CoM3D_X", "CoM3D_Y", "CoM3D_Z", "CoM2DL_X", "CoM2DL_Z", "CoM2DR_X", "CoM2DR_Z"]
        missing_com = [col for col in com_cols if col not in df_with_com.columns]
        
        if missing_com:
            return False, f"CoM kolone nisu dodate: {missing_com}. QC: {qc}"
        
        # Sačuvaj novi fajl sa header-om
        output_file.parent.mkdir(parents=True, exist_ok=True)
        write_tsv_with_header(output_file, header_lines, df_with_com, data_start_idx)
        
        # QC informacije
        qc_info = f"sex={qc.get('sex_used', 'unknown')}, units_converted={qc.get('units_mm_to_m', '0')}"
        
        return True, f"OK - {qc_info}"
    
    except Exception as e:
        return False, f"ERROR: {str(e)}"


def main():
    from paths_config import CMJ_QUALISYS, SJ_QUALISYS, CMJ_QUALISYS_COM, SJ_QUALISYS_COM
    cmj_input = CMJ_QUALISYS
    sj_input = SJ_QUALISYS
    cmj_output = CMJ_QUALISYS_COM
    sj_output = SJ_QUALISYS_COM
    
    print("=" * 90)
    print("DODAVANJE CoM KOLONA U TSV FAJLOVE")
    print("=" * 90)
    print(f"Vreme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nInput folderi:")
    print(f"  - {cmj_input}")
    print(f"  - {sj_input}")
    print(f"\nOutput folderi:")
    print(f"  - {cmj_output}")
    print(f"  - {sj_output}")
    print("=" * 90)
    
    total_processed = 0
    total_success = 0
    total_failed = 0
    
    # Procesiraj CMJ folder
    if cmj_input.exists():
        cmj_files = sorted(cmj_input.glob("*.tsv"))
        print(f"\n[CMJ_Qualisys] Obrada {len(cmj_files)} fajlova...")
        
        for input_file in cmj_files:
            output_file = cmj_output / input_file.name
            success, message = process_tsv_file(input_file, output_file)
            
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
        print(f"\n[SJ_Qualisys] Obrada {len(sj_files)} fajlova...")
        
        for input_file in sj_files:
            output_file = sj_output / input_file.name
            success, message = process_tsv_file(input_file, output_file)
            
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
    print(f"Vreme završetka: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ukupno obrađeno: {total_processed}")
    print(f"Uspešno: {total_success}")
    print(f"Neuspešno: {total_failed}")
    
    if total_failed == 0:
        print("\n[SUCCESS] Svi fajlovi su uspešno obrađeni!")
        print(f"\nNovi fajlovi sa CoM kolonama su sačuvani u:")
        print(f"  - {cmj_output}")
        print(f"  - {sj_output}")
        return 0
    else:
        print(f"\n[WARNING] {total_failed} fajlova nije uspešno obrađeno")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
