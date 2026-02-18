#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST SJ COUNTERMOVEMENT ONSET DETECTION
========================================
Testira novu logiku za detekciju početka countermovement-a kod SJ.
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt

# Import funkcije iz calculate_fp_kpis.py
<<<<<<<< HEAD:scripts/test_sj_cm_onset.py
sys.path.insert(0, str(Path(__file__).parent.parent))
========
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
>>>>>>>> 9c7a2f8b1e9489b24e56233d9c5101d03482699a:tests/test_sj_cm_onset.py
from calculate_fp_kpis import (
    read_force_file, calculate_body_weight_robust,
    butter_lowpass_filter, CONFIG
)

def test_sj_cm_onset(filepath: Path):
    """Testira SJ countermovement onset detekciju."""
    
    force_L, force_R = read_force_file(filepath)
    if force_L is None or len(force_L) == 0:
        return None
    
    force = force_L + force_R
    fs = CONFIG['SAMPLE_RATE_AMTI']
    
    # Filtering
    force = butter_lowpass_filter(force, CONFIG['FILTER_FREQ'], fs, CONFIG['FILTER_ORDER'])
    
    # Nađi apsolutni minimum
    idx_abs_min = np.argmin(force)
    
    # Body Weight
    bw, bw_sd = calculate_body_weight_robust(force, fs, idx_abs_min)
    bm = bw / CONFIG['GRAVITY']
    
    print("=" * 90)
    print(f"TEST SJ COUNTERMOVEMENT ONSET: {filepath.name}")
    print("=" * 90)
    print(f"\nOsnovne informacije:")
    print(f"  Dužina signala: {len(force)} samples ({len(force)/fs:.2f}s)")
    print(f"  BW: {bw:.2f} N")
    print(f"  BW_SD: {bw_sd:.2f} N")
    print(f"  Minimum @ sample {idx_abs_min} ({idx_abs_min/fs:.3f}s), force = {force[idx_abs_min]:.2f} N")
    
    # SJ LOGIKA
    # Korak 1: Nađi maksimum od početka do minimuma
    if idx_abs_min > 0 and idx_abs_min < len(force):
        segment_to_min = force[:idx_abs_min]
        if len(segment_to_min) > 0:
            max_before_min_abs = np.argmax(segment_to_min)
        else:
            max_before_min_abs = 0
    else:
        max_before_min_abs = 0
    
    print(f"\nKorak 1: Maksimum od početka do minimuma:")
    print(f"  Maksimum @ sample {max_before_min_abs} ({max_before_min_abs/fs:.3f}s), force = {force[max_before_min_abs]:.2f} N")
    
    # Korak 2: Standardna logika (od maksimuma unazad)
    threshold_sj = bw + (5 * bw_sd)
    idx_A_standard = max_before_min_abs
    
    for i in range(max_before_min_abs, -1, -1):
        if force[i] < threshold_sj:
            idx_A_standard = i
            break
    
    print(f"\nKorak 2: Standardna logika (od maksimuma unazad):")
    print(f"  Threshold: BW + 5*SD = {threshold_sj:.2f} N")
    print(f"  Onset @ sample {idx_A_standard} ({idx_A_standard/fs:.3f}s), force = {force[idx_A_standard]:.2f} N")
    
    # Korak 3: Detekcija countermovement-a
    cm_threshold = bw - (2 * bw_sd)
    cm_indices = None
    cm_start_idx = None
    idx_A_corrected = idx_A_standard
    
    if max_before_min_abs > 0:
        segment_before_max = force[:max_before_min_abs]
        cm_indices = np.where(segment_before_max < cm_threshold)[0]
        
        if len(cm_indices) > 0:
            print(f"\nKorak 3: Detekcija countermovement-a:")
            print(f"  Threshold: BW - 2*SD = {cm_threshold:.2f} N")
            print(f"  Pronađeno {len(cm_indices)} tačaka sa countermovement-om")
            print(f"  Prva tačka CM @ sample {cm_indices[0]} ({cm_indices[0]/fs:.3f}s), force = {force[cm_indices[0]]:.2f} N")
            
            cm_start_idx = cm_indices[0]
            
            # Traži početak countermovement-a (poslednja stabilna tačka pre pada)
            if cm_start_idx > 0:
                stable_threshold_low = bw - (0.5 * bw_sd)
                stable_threshold_high = bw + (0.5 * bw_sd)
                
                true_start_idx = None
                for i in range(cm_start_idx - 1, -1, -1):
                    if stable_threshold_low <= force[i] <= stable_threshold_high:
                        true_start_idx = i
                        # Nastavi da tražiš unazad dok je sila stabilna
                        for j in range(i - 1, max(0, i - int(0.1 * fs)), -1):
                            if stable_threshold_low <= force[j] <= stable_threshold_high:
                                true_start_idx = j
                            else:
                                break
                        break
                
                if true_start_idx is not None:
                    idx_A_corrected = true_start_idx
                    print(f"\nKorak 4: Ispravljeni onset (početak countermovement-a):")
                    print(f"  Pravi početak @ sample {true_start_idx} ({true_start_idx/fs:.3f}s), force = {force[true_start_idx]:.2f} N")
                    print(f"  [OK] Onset je pomeren sa {idx_A_standard} na {true_start_idx} (razlika: {true_start_idx - idx_A_standard} samples)")
                else:
                    idx_A_corrected = cm_start_idx
                    print(f"\nKorak 4: Fallback - koristi CM start:")
                    print(f"  Onset @ sample {cm_start_idx} ({cm_start_idx/fs:.3f}s), force = {force[cm_start_idx]:.2f} N")
        else:
            print(f"\nKorak 3: Nema countermovement-a")
    
    # Test integracije
    print(f"\n" + "=" * 90)
    print("TEST INTEGRACIJE BRZINE")
    print("=" * 90)
    
    # Crop oko skoka
    pad_pre, pad_post = 1000, 1500
    start_crop = max(0, idx_A_corrected - pad_pre)
    end_crop = min(len(force), idx_abs_min + pad_post)
    
    f_crop = force[start_crop:end_crop]
    t_crop = np.arange(len(f_crop)) / fs
    idx_A_crop = idx_A_corrected - start_crop
    
    # Integracija
    acc = (f_crop - bw) / bm
    vel = cumulative_trapezoid(acc, t_crop, initial=0)
    
    # Postavi brzinu na onset-u na 0
    if idx_A_crop >= 0 and idx_A_crop < len(vel):
        vel_before = vel[idx_A_crop]
        vel = vel - vel[idx_A_crop]
        vel_after = vel[idx_A_crop]
        
        print(f"\nBrzina na onset-u:")
        print(f"  Pre korekcije: {vel_before:.6f} m/s")
        print(f"  Posle korekcije: {vel_after:.6f} m/s")
        print(f"  [{'OK' if abs(vel_after) < 0.001 else 'ERROR'}] Brzina na onset-u je {'nula' if abs(vel_after) < 0.001 else 'NISU nula'}!")
    
    # Prikaži vrednosti oko onset-a
    print(f"\nForce vrednosti oko onset-a:")
    for offset in [-5, -3, -1, 0, 1, 3, 5]:
        idx_check = idx_A_corrected + offset
        if 0 <= idx_check < len(force):
            print(f"  @ {idx_check/fs:.3f}s: force = {force[idx_check]:.2f} N (BW = {bw:.2f} N)")
    
    return {
        'idx_A_standard': idx_A_standard,
        'idx_A_corrected': idx_A_corrected,
        'has_cm': len(cm_indices) > 0 if cm_indices is not None else False,
        'vel_at_onset': vel[idx_A_crop] if idx_A_crop >= 0 and idx_A_crop < len(vel) else None
    }


def main():
    base_path = Path(__file__).parent.parent
    sj_fp_dir = base_path / "SJ_ForcePlates"
    
    # Testiraj nekoliko SJ fajlova sa countermovement-om
    sj_files = list(sj_fp_dir.glob("*.txt"))
    
    print("Traženje SJ fajlova sa countermovement-om...")
    print(f"Pronađeno {len(sj_files)} SJ fajlova\n")
    
    # Testiraj prvih 5 fajlova
    for i, filepath in enumerate(sj_files[:5], 1):
        try:
            result = test_sj_cm_onset(filepath)
            if result:
                print(f"\n{'='*90}\n")
        except Exception as e:
            print(f"[ERROR] Greška pri obradi {filepath.name}: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n{'='*90}\n")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
