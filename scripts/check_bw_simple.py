#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROSTA PROVERA BW VREDNOSTI
============================
Proverava BW vrednosti iz Excel fajla.
"""

import sys
import pandas as pd
from pathlib import Path


def main():
    base_path = Path(__file__).parent.parent
    excel_file = base_path / "Output" / "Excel" / "MoCap_KPIs.xlsx"
    
    print("=" * 90)
    print("PROVERA BW VREDNOSTI")
    print("=" * 90)
    
    sj_fp = pd.read_excel(excel_file, sheet_name='SJ_FP')
    cmj_fp = pd.read_excel(excel_file, sheet_name='CMJ_FP')
    
    print("\n[SJ_FP] BW statistike:")
    print(f"  Ukupno: {len(sj_fp)}")
    print(f"  Mean: {sj_fp['BW_N'].mean():.1f} N")
    print(f"  Std:  {sj_fp['BW_N'].std():.1f} N")
    print(f"  Min:  {sj_fp['BW_N'].min():.1f} N")
    print(f"  Max:  {sj_fp['BW_N'].max():.1f} N")
    print(f"  Razumnih (200-2000N): {((sj_fp['BW_N'] >= 200) & (sj_fp['BW_N'] <= 2000)).sum()}")
    print(f"  Nerealnih: {((sj_fp['BW_N'] < 200) | (sj_fp['BW_N'] > 2000)).sum()}")
    
    print("\n[CMJ_FP] BW statistike:")
    print(f"  Ukupno: {len(cmj_fp)}")
    print(f"  Mean: {cmj_fp['BW_N'].mean():.1f} N")
    print(f"  Std:  {cmj_fp['BW_N'].std():.1f} N")
    print(f"  Min:  {cmj_fp['BW_N'].min():.1f} N")
    print(f"  Max:  {cmj_fp['BW_N'].max():.1f} N")
    print(f"  Razumnih (200-2000N): {((cmj_fp['BW_N'] >= 200) & (cmj_fp['BW_N'] <= 2000)).sum()}")
    print(f"  Nerealnih: {((cmj_fp['BW_N'] < 200) | (cmj_fp['BW_N'] > 2000)).sum()}")
    
    # Primeri nerealnih
    sj_unreasonable = sj_fp[(sj_fp['BW_N'] < 200) | (sj_fp['BW_N'] > 2000)]
    if len(sj_unreasonable) > 0:
        print(f"\n[SJ] Primeri nerealnih BW ({len(sj_unreasonable)}):")
        print(sj_unreasonable[['FileName', 'SubjectID', 'TrialNo', 'BW_N']].head(10).to_string(index=False))
    
    cmj_unreasonable = cmj_fp[(cmj_fp['BW_N'] < 200) | (cmj_fp['BW_N'] > 2000)]
    if len(cmj_unreasonable) > 0:
        print(f"\n[CMJ] Primeri nerealnih BW ({len(cmj_unreasonable)}):")
        print(cmj_unreasonable[['FileName', 'SubjectID', 'TrialNo', 'BW_N']].head(10).to_string(index=False))
    
    print("\n" + "=" * 90)
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
