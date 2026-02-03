#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IZRACUNAVANJE KORELACIJA IZMEDJU hCoM, hv, hFT
===============================================
Izračunava Pearson korelacije između hCoM, hv i hFT za svaki sheet u Excel fajlu.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr
from scipy.stats import spearmanr


def calculate_correlations(df: pd.DataFrame, sheet_name: str) -> dict:
    """
    Izračunava korelacije između hCoM, hv i hFT.
    
    Returns:
        Dictionary sa korelacijama i brojem validnih podataka
    """
    results = {
        'sheet': sheet_name,
        'n_valid': 0,
        'correlations': {}
    }
    
    # Proveri da li postoje kolone
    required_cols = ['hCoM', 'hv', 'hFT']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        results['error'] = f"Missing columns: {missing_cols}"
        return results
    
    # Filtriraj validne podatke (sve tri kolone moraju biti validne)
    valid_mask = (
        df['hCoM'].notna() & 
        df['hv'].notna() & 
        df['hFT'].notna() &
        np.isfinite(df['hCoM']) &
        np.isfinite(df['hv']) &
        np.isfinite(df['hFT'])
    )
    
    valid_data = df[valid_mask]
    n_valid = len(valid_data)
    results['n_valid'] = n_valid
    
    if n_valid < 3:
        results['error'] = f"Not enough valid data points (n={n_valid}, need at least 3)"
        return results
    
    # Izračunaj Pearson korelacije
    hcom = valid_data['hCoM'].values
    hv_vals = valid_data['hv'].values
    hft = valid_data['hFT'].values
    
    # hCoM vs hv
    r_pearson_hcom_hv, p_pearson_hcom_hv = pearsonr(hcom, hv_vals)
    r_spearman_hcom_hv, p_spearman_hcom_hv = spearmanr(hcom, hv_vals)
    
    # hCoM vs hFT
    r_pearson_hcom_hft, p_pearson_hcom_hft = pearsonr(hcom, hft)
    r_spearman_hcom_hft, p_spearman_hcom_hft = spearmanr(hcom, hft)
    
    # hv vs hFT
    r_pearson_hv_hft, p_pearson_hv_hft = pearsonr(hv_vals, hft)
    r_spearman_hv_hft, p_spearman_hv_hft = spearmanr(hv_vals, hft)
    
    results['correlations'] = {
        'hCoM_vs_hv': {
            'pearson_r': r_pearson_hcom_hv,
            'pearson_p': p_pearson_hcom_hv,
            'spearman_r': r_spearman_hcom_hv,
            'spearman_p': p_spearman_hcom_hv
        },
        'hCoM_vs_hFT': {
            'pearson_r': r_pearson_hcom_hft,
            'pearson_p': p_pearson_hcom_hft,
            'spearman_r': r_spearman_hcom_hft,
            'spearman_p': p_spearman_hcom_hft
        },
        'hv_vs_hFT': {
            'pearson_r': r_pearson_hv_hft,
            'pearson_p': p_pearson_hv_hft,
            'spearman_r': r_spearman_hv_hft,
            'spearman_p': p_spearman_hv_hft
        }
    }
    
    # Dodatne statistike
    results['statistics'] = {
        'hCoM': {
            'mean': np.mean(hcom),
            'std': np.std(hcom),
            'min': np.min(hcom),
            'max': np.max(hcom)
        },
        'hv': {
            'mean': np.mean(hv_vals),
            'std': np.std(hv_vals),
            'min': np.min(hv_vals),
            'max': np.max(hv_vals)
        },
        'hFT': {
            'mean': np.mean(hft),
            'std': np.std(hft),
            'min': np.min(hft),
            'max': np.max(hft)
        }
    }
    
    return results


def format_correlation(corr_dict: dict, var1: str, var2: str) -> str:
    """Formatira korelaciju za prikaz"""
    r_p = corr_dict['pearson_r']
    p_p = corr_dict['pearson_p']
    r_s = corr_dict['spearman_r']
    p_s = corr_dict['spearman_p']
    
    # Značajnost
    sig_p = "***" if p_p < 0.001 else "**" if p_p < 0.01 else "*" if p_p < 0.05 else ""
    sig_s = "***" if p_s < 0.001 else "**" if p_s < 0.01 else "*" if p_s < 0.05 else ""
    
    return f"{var1} vs {var2}:\n" \
           f"  Pearson:  r = {r_p:.4f}, p = {p_p:.4f} {sig_p}\n" \
           f"  Spearman: r = {r_s:.4f}, p = {p_s:.4f} {sig_s}"


def main():
    base_path = Path(__file__).parent
    excel_file = base_path / "Output" / "Excel" / "MoCap_KPIs.xlsx"
    
    if not excel_file.exists():
        print(f"[ERROR] Excel fajl ne postoji: {excel_file}")
        return 1
    
    print("=" * 90)
    print("IZRACUNAVANJE KORELACIJA IZMEDJU hCoM, hv, hFT")
    print("=" * 90)
    print(f"Excel fajl: {excel_file}")
    print("=" * 90)
    
    # Učitaj Excel fajl
    sheet_names = ['SJ3D', 'SJ2DL', 'SJ2DR', 'CMJ3D', 'CMJ2DL', 'CMJ2DR']
    
    all_results = {}
    
    for sheet_name in sheet_names:
        print(f"\n{'='*90}")
        print(f"SHEET: {sheet_name}")
        print('='*90)
        
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            results = calculate_correlations(df, sheet_name)
            all_results[sheet_name] = results
            
            if 'error' in results:
                print(f"[ERROR] {results['error']}")
                continue
            
            print(f"\nBroj validnih podataka: {results['n_valid']}")
            
            # Statistike
            print("\n--- DESKRIPTIVNE STATISTIKE ---")
            for var in ['hCoM', 'hv', 'hFT']:
                stats = results['statistics'][var]
                print(f"{var}:")
                print(f"  Mean: {stats['mean']:.4f} m")
                print(f"  Std:  {stats['std']:.4f} m")
                print(f"  Min:  {stats['min']:.4f} m")
                print(f"  Max:  {stats['max']:.4f} m")
            
            # Korelacije
            print("\n--- KORELACIJE ---")
            corr = results['correlations']
            
            print(format_correlation(corr['hCoM_vs_hv'], 'hCoM', 'hv'))
            print()
            print(format_correlation(corr['hCoM_vs_hFT'], 'hCoM', 'hFT'))
            print()
            print(format_correlation(corr['hv_vs_hFT'], 'hv', 'hFT'))
            
        except Exception as e:
            print(f"[ERROR] Greška pri obradi {sheet_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Sažetak
    print("\n" + "=" * 90)
    print("SAZETAK KORELACIJA")
    print("=" * 90)
    
    summary_data = []
    for sheet_name in sheet_names:
        if sheet_name in all_results and 'error' not in all_results[sheet_name]:
            r = all_results[sheet_name]
            corr = r['correlations']
            summary_data.append({
                'Sheet': sheet_name,
                'N': r['n_valid'],
                'hCoM-hv (r)': f"{corr['hCoM_vs_hv']['pearson_r']:.4f}",
                'hCoM-hv (p)': f"{corr['hCoM_vs_hv']['pearson_p']:.4f}",
                'hCoM-hFT (r)': f"{corr['hCoM_vs_hFT']['pearson_r']:.4f}",
                'hCoM-hFT (p)': f"{corr['hCoM_vs_hFT']['pearson_p']:.4f}",
                'hv-hFT (r)': f"{corr['hv_vs_hFT']['pearson_r']:.4f}",
                'hv-hFT (p)': f"{corr['hv_vs_hFT']['pearson_p']:.4f}",
            })
    
    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        print("\nPearson korelacije (r) i p-vrednosti:")
        print(summary_df.to_string(index=False))
    
    print("\n" + "=" * 90)
    print("ZAVRSENO")
    print("=" * 90)
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
