#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROVERA ROBUSTNOSTI FORCE PLATE KPI IZRACUNAVANJA
=================================================
Proverava QC flagove i analizira neispravne skokove.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def analyze_qc_flags(excel_file: Path):
    """Analizira QC flagove u FP sheetovima."""
    
    sj_fp = pd.read_excel(excel_file, sheet_name='SJ_FP')
    cmj_fp = pd.read_excel(excel_file, sheet_name='CMJ_FP')
    
    print("=" * 90)
    print("ANALIZA QC FLAGOVA - FORCE PLATE KPIs")
    print("=" * 90)
    
    # SJ analiza
    print("\n[SJ_FP] Analiza:")
    print("-" * 90)
    print(f"Ukupno skokova: {len(sj_fp)}")
    print(f"Countermovement detektovan: {sj_fp['has_countermovement'].sum()}")
    print(f"Negativan vTO: {sj_fp['negative_vto'].sum()}")
    print(f"Invalid jump (ukupno): {sj_fp['invalid_jump'].sum()}")
    
    invalid_sj = sj_fp[sj_fp['invalid_jump'] == True]
    if len(invalid_sj) > 0:
        print(f"\nNeispravni SJ skokovi ({len(invalid_sj)}):")
        print(invalid_sj[['FileName', 'SubjectID', 'TrialNo', 'has_countermovement', 
                          'negative_vto', 'V_Takeoff_ms', 'qc_notes']].to_string(index=False))
    
    # CMJ analiza
    print("\n[CMJ_FP] Analiza:")
    print("-" * 90)
    print(f"Ukupno skokova: {len(cmj_fp)}")
    print(f"Negativan vTO: {cmj_fp['negative_vto'].sum()}")
    print(f"Invalid jump: {cmj_fp['invalid_jump'].sum()}")
    
    invalid_cmj = cmj_fp[cmj_fp['invalid_jump'] == True]
    if len(invalid_cmj) > 0:
        print(f"\nNeispravni CMJ skokovi ({len(invalid_cmj)}):")
        print(invalid_cmj[['FileName', 'SubjectID', 'TrialNo', 'negative_vto', 
                           'V_Takeoff_ms', 'qc_notes']].to_string(index=False))
    
    # Statistike za validne skokove
    print("\n" + "=" * 90)
    print("STATISTIKE ZA VALIDNE SKOKOVE")
    print("=" * 90)
    
    valid_sj = sj_fp[sj_fp['invalid_jump'] == False]
    valid_cmj = cmj_fp[cmj_fp['invalid_jump'] == False]
    
    print(f"\n[SJ] Validni skokovi: {len(valid_sj)}/{len(sj_fp)} ({100*len(valid_sj)/len(sj_fp):.1f}%)")
    if len(valid_sj) > 0:
        print(f"  V_Takeoff_ms: {valid_sj['V_Takeoff_ms'].mean():.4f} ± {valid_sj['V_Takeoff_ms'].std():.4f} m/s")
        print(f"  Height_V_m:   {valid_sj['Height_V_m'].mean():.4f} ± {valid_sj['Height_V_m'].std():.4f} m")
        print(f"  Height_T_m:   {valid_sj['Height_T_m'].mean():.4f} ± {valid_sj['Height_T_m'].std():.4f} m")
    
    print(f"\n[CMJ] Validni skokovi: {len(valid_cmj)}/{len(cmj_fp)} ({100*len(valid_cmj)/len(cmj_fp):.1f}%)")
    if len(valid_cmj) > 0:
        print(f"  V_Takeoff_ms: {valid_cmj['V_Takeoff_ms'].mean():.4f} ± {valid_cmj['V_Takeoff_ms'].std():.4f} m/s")
        print(f"  Height_V_m:   {valid_cmj['Height_V_m'].mean():.4f} ± {valid_cmj['Height_V_m'].std():.4f} m")
        print(f"  Height_T_m:   {valid_cmj['Height_T_m'].mean():.4f} ± {valid_cmj['Height_T_m'].std():.4f} m")
    
    # Preporuke za robustnost
    print("\n" + "=" * 90)
    print("PREPORUKE ZA ROBUSTNOST")
    print("=" * 90)
    
    sj_cm_rate = sj_fp['has_countermovement'].sum() / len(sj_fp) * 100
    sj_neg_vto_rate = sj_fp['negative_vto'].sum() / len(sj_fp) * 100
    
    print(f"\n[SJ] Countermovement rate: {sj_cm_rate:.1f}%")
    print(f"[SJ] Negativan vTO rate: {sj_neg_vto_rate:.1f}%")
    
    if sj_cm_rate > 10:
        print("\n[WARNING] VISOK PROCENAT COUNTERMOVEMENT U SJ SKOKOVIMA!")
        print("   Preporuka: Proverite protokol merenja ili poostrite kriterijume za detekciju.")
    
    if sj_neg_vto_rate > 5:
        print("\n[WARNING] VISOK PROCENAT NEGATIVNIH vTO!")
        print("   Preporuka: Proverite drift correction i event detection logiku.")
    
    # Proveri konzistentnost između Height_V i Height_T
    print("\n" + "=" * 90)
    print("KONZISTENTNOST VISINA")
    print("=" * 90)
    
    if len(valid_sj) > 0:
        sj_height_diff = np.abs(valid_sj['Height_V_m'] - valid_sj['Height_T_m'])
        print(f"\n[SJ] Mean |Height_V - Height_T|: {sj_height_diff.mean():.4f} m")
        print(f"[SJ] Max |Height_V - Height_T|:  {sj_height_diff.max():.4f} m")
        print(f"[SJ] Skokovi sa razlikom > 0.05m: {(sj_height_diff > 0.05).sum()}")
    
    if len(valid_cmj) > 0:
        cmj_height_diff = np.abs(valid_cmj['Height_V_m'] - valid_cmj['Height_T_m'])
        print(f"\n[CMJ] Mean |Height_V - Height_T|: {cmj_height_diff.mean():.4f} m")
        print(f"[CMJ] Max |Height_V - Height_T|:  {cmj_height_diff.max():.4f} m")
        print(f"[CMJ] Skokovi sa razlikom > 0.05m: {(cmj_height_diff > 0.05).sum()}")
    
    print("\n" + "=" * 90)
    print("ZAVRSENO")
    print("=" * 90)
    
    return {
        'sj_total': len(sj_fp),
        'sj_invalid': sj_fp['invalid_jump'].sum(),
        'sj_cm': sj_fp['has_countermovement'].sum(),
        'sj_neg_vto': sj_fp['negative_vto'].sum(),
        'cmj_total': len(cmj_fp),
        'cmj_invalid': cmj_fp['invalid_jump'].sum(),
        'cmj_neg_vto': cmj_fp['negative_vto'].sum(),
    }


def main():
    base_path = Path(__file__).parent
    excel_file = base_path / "Output" / "Excel" / "MoCap_KPIs.xlsx"
    
    if not excel_file.exists():
        print(f"[ERROR] Excel fajl ne postoji: {excel_file}")
        return 1
    
    results = analyze_qc_flags(excel_file)
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
