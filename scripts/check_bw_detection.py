#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROVERA BW I SD_BW DETEKCIJE
=============================
Korak po korak provera da li se BW i SD_BW ispravno računaju.
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import butter, filtfilt


CONFIG = {
    'FILTER_FREQ': 50.0,
    'FILTER_ORDER': 2,
    'GRAVITY': 9.81,
}


def butter_lowpass_filter(data, cutoff, fs, order=2):
    """Butterworth lowpass filter."""
    if len(data) <= 3 * order:
        return data
    if cutoff >= fs / 2:
        cutoff = fs / 2.1
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    if normal_cutoff >= 1.0:
        normal_cutoff = 0.99
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)


def calculate_body_weight_robust(force, fs, min_idx):
    """Robustniji algoritam za izračunavanje body weight-a."""
    n_samples = len(force)
    
    if n_samples < 100 or min_idx < 0 or min_idx >= n_samples:
        quiet_period = int(0.5 * fs)
        bw = np.mean(force[:quiet_period])
        bw_sd = np.std(force[:quiet_period], ddof=1)
        return bw, bw_sd, 'fallback_quiet_period', None, None
    
    # Pronađi period 0.5s pre minimuma
    period_before_min = int(0.5 * fs)
    start_idx = max(0, min_idx - period_before_min)
    end_idx = min_idx
    
    if end_idx <= start_idx or end_idx - start_idx < 50:
        quiet_period = int(0.5 * fs)
        bw = np.mean(force[:quiet_period])
        bw_sd = np.std(force[:quiet_period], ddof=1)
        return bw, bw_sd, 'fallback_insufficient_segment', None, None
    
    # Segment pre minimuma
    segment = force[start_idx:end_idx]
    
    if len(segment) < 50:
        quiet_period = int(0.5 * fs)
        bw = np.mean(force[:quiet_period])
        bw_sd = np.std(force[:quiet_period], ddof=1)
        return bw, bw_sd, 'fallback_short_segment', None, None
    
    try:
        # Prvo aproksimacija
        bw_est = np.median(segment)
        bw_std_est = np.std(segment, ddof=1)
        
        if np.isnan(bw_est) or np.isnan(bw_std_est) or bw_std_est == 0:
            quiet_period = int(0.5 * fs)
            bw = np.mean(force[:quiet_period])
            bw_sd = np.std(force[:quiet_period], ddof=1)
            return bw, bw_sd, 'fallback_nan', None, None
        
        # Filtriranje: tačke unutar 2*SD
        mask = (segment > bw_est - 2 * bw_std_est) & (segment < bw_est + 2 * bw_std_est)
        clean_indices = np.where(mask)[0]
        
        if len(clean_indices) > 50:
            final_bw = np.mean(segment[clean_indices])
            final_sd = np.std(segment[clean_indices], ddof=1)
            method = 'robust_filtered'
            clean_segment = segment[clean_indices]
        else:
            final_bw = np.mean(segment)
            final_sd = np.std(segment, ddof=1)
            method = 'robust_full_segment'
            clean_segment = segment
        
        if np.isnan(final_bw) or np.isnan(final_sd) or final_sd == 0:
            quiet_period = int(0.5 * fs)
            bw = np.mean(force[:quiet_period])
            bw_sd = np.std(force[:quiet_period], ddof=1)
            return bw, bw_sd, 'fallback_nan_final', None, None
        
        return final_bw, final_sd, method, (start_idx, end_idx), clean_segment
    except Exception as e:
        quiet_period = int(0.5 * fs)
        bw = np.mean(force[:quiet_period])
        bw_sd = np.std(force[:quiet_period], ddof=1)
        return bw, bw_sd, f'fallback_exception_{str(e)[:20]}', None, None


def read_force_file(filepath: Path):
    """Učitaj Force Plate fajl."""
    try:
        fs = 1000.0
        
        try:
            df = pd.read_csv(filepath, skiprows=1, header=None, sep=None, engine='python', decimal=',')
        except:
            df = pd.read_csv(filepath, skiprows=1, header=None, sep=',', decimal=',')
        
        if df.shape[1] >= 9:
            col_L, col_R = 2, 8
        else:
            col_L, col_R = 0, 1
        
        raw_L = pd.to_numeric(df.iloc[:, col_L], errors='coerce').values
        raw_R = pd.to_numeric(df.iloc[:, col_R], errors='coerce').values
        
        valid = ~np.isnan(raw_L) & ~np.isnan(raw_R)
        force_L = raw_L[valid]
        force_R = raw_R[valid]
        force = force_L + force_R
        
        return force, force_L, force_R, fs
    except Exception as e:
        print(f"[ERROR] Greška pri čitanju {filepath}: {e}")
        return None, None, None, None


def analyze_bw_detection(filepath: Path, jump_type: int, output_dir: Path):
    """Analiziraj BW detekciju za jedan fajl i kreiraj plot."""
    
    force, force_L, force_R, fs = read_force_file(filepath)
    if force is None:
        return None
    
    # Filtriranje
    force = butter_lowpass_filter(force, CONFIG['FILTER_FREQ'], fs, CONFIG['FILTER_ORDER'])
    
    # Nađi apsolutni minimum
    idx_abs_min = np.argmin(force)
    
    # Izračunaj BW
    bw, bw_sd, method, segment_indices, clean_segment = calculate_body_weight_robust(force, fs, idx_abs_min)
    
    # Kreiraj plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))
    
    t = np.arange(len(force)) / fs
    
    # Plot 1: Ceo signal sa označenim tačkama
    ax1.plot(t, force, 'b-', linewidth=1, alpha=0.7, label='Force')
    ax1.axhline(y=bw, color='green', linestyle='--', linewidth=2, label=f'BW = {bw:.1f} N')
    ax1.axhline(y=bw + bw_sd, color='orange', linestyle=':', linewidth=1, label=f'BW + SD = {bw + bw_sd:.1f} N')
    ax1.axhline(y=bw - bw_sd, color='orange', linestyle=':', linewidth=1, label=f'BW - SD = {bw - bw_sd:.1f} N')
    ax1.axhline(y=bw + 5*bw_sd, color='red', linestyle=':', linewidth=1, label=f'BW + 5*SD = {bw + 5*bw_sd:.1f} N (SJ threshold)')
    ax1.axhline(y=bw - 5*bw_sd, color='red', linestyle=':', linewidth=1, label=f'BW - 5*SD = {bw - 5*bw_sd:.1f} N (CMJ threshold)')
    
    # Obeleži minimum
    ax1.plot(t[idx_abs_min], force[idx_abs_min], 'ro', markersize=12, label=f'Min @ {t[idx_abs_min]:.3f}s')
    
    # Obeleži segment za BW ako postoji
    if segment_indices is not None:
        start_idx, end_idx = segment_indices
        ax1.axvspan(t[start_idx], t[end_idx], alpha=0.2, color='green', label='BW segment')
        ax1.plot(t[start_idx:end_idx], force[start_idx:end_idx], 'g-', linewidth=2, alpha=0.8)
    
    ax1.set_xlabel('Vreme (s)', fontsize=12)
    ax1.set_ylabel('Sila (N)', fontsize=12)
    ax1.set_title(f'{filepath.stem} - BW Detekcija\nMethod: {method}, BW = {bw:.2f} N, SD = {bw_sd:.2f} N', fontsize=11, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Zoom na quiet standing segment
    if segment_indices is not None:
        start_idx, end_idx = segment_indices
        zoom_start = max(0, start_idx - int(0.1 * fs))
        zoom_end = min(len(force), end_idx + int(0.1 * fs))
        
        ax2.plot(t[zoom_start:zoom_end], force[zoom_start:zoom_end], 'b-', linewidth=1.5, alpha=0.7, label='Force')
        ax2.axhline(y=bw, color='green', linestyle='--', linewidth=2, label=f'BW = {bw:.1f} N')
        ax2.axhline(y=bw + 2*bw_sd, color='orange', linestyle=':', linewidth=1, label=f'BW ± 2*SD')
        ax2.axhline(y=bw - 2*bw_sd, color='orange', linestyle=':', linewidth=1)
        
        # Obeleži segment
        ax2.axvspan(t[start_idx], t[end_idx], alpha=0.2, color='green', label='BW segment')
        ax2.plot(t[start_idx:end_idx], force[start_idx:end_idx], 'g-', linewidth=2, alpha=0.8)
        
        # Obeleži clean segment ako postoji
        if clean_segment is not None and len(clean_segment) > 0 and segment_indices is not None:
            segment_len = end_idx - start_idx
            clean_start = start_idx + (segment_len - len(clean_segment))
            if clean_start < len(force) and clean_start >= 0:
                clean_end = min(clean_start + len(clean_segment), len(force))
                ax2.plot(t[clean_start:clean_end], clean_segment[:clean_end-clean_start], 'r-', linewidth=2, alpha=0.8, label='Clean segment (used for BW)')
        
        ax2.plot(t[idx_abs_min], force[idx_abs_min], 'ro', markersize=12, label=f'Min @ {t[idx_abs_min]:.3f}s')
        
        ax2.set_xlabel('Vreme (s)', fontsize=12)
        ax2.set_ylabel('Sila (N)', fontsize=12)
        ax2.set_title(f'Zoom: Quiet standing segment (0.1-1.0s)', fontsize=11)
        ax2.legend(loc='upper right', fontsize=9)
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, 'Nema segmenta za BW (fallback metoda)', 
                ha='center', va='center', transform=ax2.transAxes, fontsize=12)
        ax2.set_title('Zoom: N/A', fontsize=11)
    
    plt.tight_layout()
    
    # Sačuvaj plot
    output_file = output_dir / f'{filepath.stem}_bw_check.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    return {
        'filename': filepath.stem,
        'bw': bw,
        'bw_sd': bw_sd,
        'method': method,
        'min_idx': idx_abs_min,
        'min_time': t[idx_abs_min],
        'min_force': force[idx_abs_min],
        'segment_start': segment_indices[0] if segment_indices else None,
        'segment_end': segment_indices[1] if segment_indices else None,
    }


def main():
    base_path = Path(__file__).parent.parent
    
    # Input folderi
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from paths_config import SJ_FORCE_PLATES, CMJ_FORCE_PLATES
    sj_fp_dir = SJ_FORCE_PLATES
    cmj_fp_dir = CMJ_FORCE_PLATES
    
    # Output folderi
    sj_bw_dir = base_path / "Output" / "BW_Check" / "SJ_FP"
    cmj_bw_dir = base_path / "Output" / "BW_Check" / "CMJ_FP"
    
    sj_bw_dir.mkdir(parents=True, exist_ok=True)
    cmj_bw_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 90)
    print("PROVERA BW I SD_BW DETEKCIJE")
    print("=" * 90)
    
    results_sj = []
    results_cmj = []
    
    # SJ - uzmi prvih 5 fajlova za proveru
    print(f"\n[SJ] Analiza prvih 5 fajlova...")
    sj_files = sorted(list(sj_fp_dir.glob("*.txt")))[:5]
    
    for filepath in sj_files:
        result = analyze_bw_detection(filepath, jump_type=1, output_dir=sj_bw_dir)
        if result:
            results_sj.append(result)
            print(f"  [OK] {filepath.stem}: BW={result['bw']:.1f}N, SD={result['bw_sd']:.1f}N, Method={result['method']}")
    
    # CMJ - uzmi prvih 5 fajlova za proveru
    print(f"\n[CMJ] Analiza prvih 5 fajlova...")
    cmj_files = sorted(list(cmj_fp_dir.glob("*.txt")))[:5]
    
    for filepath in cmj_files:
        result = analyze_bw_detection(filepath, jump_type=2, output_dir=cmj_bw_dir)
        if result:
            results_cmj.append(result)
            print(f"  [OK] {filepath.stem}: BW={result['bw']:.1f}N, SD={result['bw_sd']:.1f}N, Method={result['method']}")
    
    # Statistike
    print("\n" + "=" * 90)
    print("STATISTIKE BW DETEKCIJE")
    print("=" * 90)
    
    if results_sj:
        df_sj = pd.DataFrame(results_sj)
        print(f"\n[SJ] ({len(results_sj)} fajlova):")
        print(f"  BW Mean: {df_sj['bw'].mean():.2f} N")
        print(f"  BW Std:  {df_sj['bw'].std():.2f} N")
        print(f"  BW Min:  {df_sj['bw'].min():.2f} N")
        print(f"  BW Max:  {df_sj['bw'].max():.2f} N")
        print(f"  SD Mean: {df_sj['bw_sd'].mean():.2f} N")
        print(f"  SD Std:  {df_sj['bw_sd'].std():.2f} N")
        print(f"\n  Metode:")
        print(df_sj['method'].value_counts().to_string())
    
    if results_cmj:
        df_cmj = pd.DataFrame(results_cmj)
        print(f"\n[CMJ] ({len(results_cmj)} fajlova):")
        print(f"  BW Mean: {df_cmj['bw'].mean():.2f} N")
        print(f"  BW Std:  {df_cmj['bw'].std():.2f} N")
        print(f"  BW Min:  {df_cmj['bw'].min():.2f} N")
        print(f"  BW Max:  {df_cmj['bw'].max():.2f} N")
        print(f"  SD Mean: {df_cmj['bw_sd'].mean():.2f} N")
        print(f"  SD Std:  {df_cmj['bw_sd'].std():.2f} N")
        print(f"\n  Metode:")
        print(df_cmj['method'].value_counts().to_string())
    
    print("\n" + "=" * 90)
    print("PLOTOVI SAČUVANI U:")
    print(f"  SJ:  {sj_bw_dir}")
    print(f"  CMJ: {cmj_bw_dir}")
    print("=" * 90)
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
