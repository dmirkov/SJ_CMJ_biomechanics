#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UPOREDJIVANJE vTO IZMEĐU FORCE PLATE I QUALISYS
================================================
Izračunava korelacije između vTO (velocity at takeoff) iz FP i Qualisys podataka.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr, spearmanr
from datetime import datetime


def load_and_merge_data(excel_file: Path):
    """Učitaj i upari podatke iz FP i Qualisys sheetova."""
    
    # Učitaj Force Plate podatke
    sj_fp = pd.read_excel(excel_file, sheet_name='SJ_FP')
    cmj_fp = pd.read_excel(excel_file, sheet_name='CMJ_FP')
    
    # Učitaj Qualisys podatke
    sj_3d = pd.read_excel(excel_file, sheet_name='SJ3D')
    sj_2dl = pd.read_excel(excel_file, sheet_name='SJ2DL')
    sj_2dr = pd.read_excel(excel_file, sheet_name='SJ2DR')
    
    cmj_3d = pd.read_excel(excel_file, sheet_name='CMJ3D')
    cmj_2dl = pd.read_excel(excel_file, sheet_name='CMJ2DL')
    cmj_2dr = pd.read_excel(excel_file, sheet_name='CMJ2DR')
    
    # Kreiraj TrialID za uparivanje (SubjectID_TrialNo format)
    sj_fp['TrialID'] = sj_fp['SubjectID'].astype(str) + '_' + sj_fp['TrialNo'].astype(str)
    cmj_fp['TrialID'] = cmj_fp['SubjectID'].astype(str) + '_' + cmj_fp['TrialNo'].astype(str)
    
    sj_3d['TrialID'] = sj_3d['SubjectID'].astype(str) + '_' + sj_3d['TrialNo'].astype(str)
    sj_2dl['TrialID'] = sj_2dl['SubjectID'].astype(str) + '_' + sj_2dl['TrialNo'].astype(str)
    sj_2dr['TrialID'] = sj_2dr['SubjectID'].astype(str) + '_' + sj_2dr['TrialNo'].astype(str)
    
    cmj_3d['TrialID'] = cmj_3d['SubjectID'].astype(str) + '_' + cmj_3d['TrialNo'].astype(str)
    cmj_2dl['TrialID'] = cmj_2dl['SubjectID'].astype(str) + '_' + cmj_2dl['TrialNo'].astype(str)
    cmj_2dr['TrialID'] = cmj_2dr['SubjectID'].astype(str) + '_' + cmj_2dr['TrialNo'].astype(str)
    
    # Upari podatke
    merged_sj_3d = sj_fp.merge(sj_3d[['TrialID', 'vTO']], on='TrialID', how='inner', suffixes=('_FP', '_Q'))
    merged_sj_2dl = sj_fp.merge(sj_2dl[['TrialID', 'vTO']], on='TrialID', how='inner', suffixes=('_FP', '_Q'))
    merged_sj_2dr = sj_fp.merge(sj_2dr[['TrialID', 'vTO']], on='TrialID', how='inner', suffixes=('_FP', '_Q'))
    
    merged_cmj_3d = cmj_fp.merge(cmj_3d[['TrialID', 'vTO']], on='TrialID', how='inner', suffixes=('_FP', '_Q'))
    merged_cmj_2dl = cmj_fp.merge(cmj_2dl[['TrialID', 'vTO']], on='TrialID', how='inner', suffixes=('_FP', '_Q'))
    merged_cmj_2dr = cmj_fp.merge(cmj_2dr[['TrialID', 'vTO']], on='TrialID', how='inner', suffixes=('_FP', '_Q'))
    
    return {
        'SJ': {
            '3D': merged_sj_3d,
            '2DL': merged_sj_2dl,
            '2DR': merged_sj_2dr
        },
        'CMJ': {
            '3D': merged_cmj_3d,
            '2DL': merged_cmj_2dl,
            '2DR': merged_cmj_2dr
        }
    }


def calculate_correlations(merged_data: dict):
    """Izračunaj korelacije između vTO_FP i vTO_Q."""
    
    results = {}
    
    for jump_type in ['SJ', 'CMJ']:
        results[jump_type] = {}
        for model in ['3D', '2DL', '2DR']:
            df = merged_data[jump_type][model]
            
            # Filtriraj validne podatke
            valid_mask = (
                df['V_Takeoff_ms'].notna() & 
                df['vTO'].notna() &
                np.isfinite(df['V_Takeoff_ms']) &
                np.isfinite(df['vTO'])
            )
            
            valid_df = df[valid_mask]
            n_valid = len(valid_df)
            
            if n_valid < 3:
                results[jump_type][model] = {
                    'n': n_valid,
                    'error': 'Not enough valid data'
                }
                continue
            
            vto_fp = valid_df['V_Takeoff_ms'].values
            vto_q = valid_df['vTO'].values
            
            # Pearson korelacija
            r_pearson, p_pearson = pearsonr(vto_fp, vto_q)
            
            # Spearman korelacija
            r_spearman, p_spearman = spearmanr(vto_fp, vto_q)
            
            # Mean Absolute Error (MAE)
            mae = np.mean(np.abs(vto_fp - vto_q))
            
            # Mean Absolute Percentage Error (MAPE)
            mape = np.mean(np.abs((vto_fp - vto_q) / vto_q)) * 100
            
            # Bias (mean difference)
            bias = np.mean(vto_fp - vto_q)
            
            results[jump_type][model] = {
                'n': n_valid,
                'pearson_r': r_pearson,
                'pearson_p': p_pearson,
                'spearman_r': r_spearman,
                'spearman_p': p_spearman,
                'mae': mae,
                'mape': mape,
                'bias': bias,
                'vto_fp_mean': np.mean(vto_fp),
                'vto_q_mean': np.mean(vto_q),
                'vto_fp_std': np.std(vto_fp),
                'vto_q_std': np.std(vto_q)
            }
    
    return results


def main():
    base_path = Path(__file__).parent
    excel_file = base_path / "Output" / "Excel" / "MoCap_KPIs.xlsx"
    
    print("=" * 90)
    print("UPOREDJIVANJE vTO IZMEĐU FORCE PLATE I QUALISYS")
    print("=" * 90)
    print(f"Vreme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Excel fajl: {excel_file}")
    print("=" * 90)
    
    # Učitaj i upari podatke
    print("\nUčitavanje i uparivanje podataka...")
    merged_data = load_and_merge_data(excel_file)
    
    # Izračunaj korelacije
    print("\nIzračunavanje korelacija...")
    results = calculate_correlations(merged_data)
    
    # Prikaži rezultate
    print("\n" + "=" * 90)
    print("REZULTATI KORELACIJA")
    print("=" * 90)
    
    for jump_type in ['SJ', 'CMJ']:
        print(f"\n{jump_type}:")
        print("-" * 90)
        
        for model in ['3D', '2DL', '2DR']:
            r = results[jump_type][model]
            
            if 'error' in r:
                print(f"  {model}: {r['error']}")
                continue
            
            sig = "***" if r['pearson_p'] < 0.001 else "**" if r['pearson_p'] < 0.01 else "*" if r['pearson_p'] < 0.05 else ""
            
            print(f"\n  {model}:")
            print(f"    N validnih parova: {r['n']}")
            print(f"    Pearson r:  {r['pearson_r']:.4f}, p = {r['pearson_p']:.4f} {sig}")
            print(f"    Spearman r: {r['spearman_r']:.4f}, p = {r['spearman_p']:.4f} {sig}")
            print(f"    MAE:         {r['mae']:.4f} m/s")
            print(f"    MAPE:        {r['mape']:.2f}%")
            print(f"    Bias:        {r['bias']:.4f} m/s (FP - Q)")
            print(f"    vTO_FP:      {r['vto_fp_mean']:.4f} ± {r['vto_fp_std']:.4f} m/s")
            print(f"    vTO_Q:       {r['vto_q_mean']:.4f} ± {r['vto_q_std']:.4f} m/s")
    
    # Sažetak tabela
    print("\n" + "=" * 90)
    print("SAZETAK - PEARSON KORELACIJE")
    print("=" * 90)
    
    summary_data = []
    for jump_type in ['SJ', 'CMJ']:
        for model in ['3D', '2DL', '2DR']:
            r = results[jump_type][model]
            if 'error' not in r:
                summary_data.append({
                    'Tip': jump_type,
                    'Model': model,
                    'N': r['n'],
                    'r': f"{r['pearson_r']:.4f}",
                    'p': f"{r['pearson_p']:.4f}",
                    'MAE': f"{r['mae']:.4f}",
                    'Bias': f"{r['bias']:.4f}"
                })
    
    summary_df = pd.DataFrame(summary_data)
    print("\n" + summary_df.to_string(index=False))
    
    print("\n" + "=" * 90)
    print("ZAVRSENO")
    print("=" * 90)
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
