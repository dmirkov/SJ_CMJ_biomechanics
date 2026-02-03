#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST: Provera CMJ onset logike za 03_4_3
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import butter, filtfilt


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
    """Simplifikovana BW detekcija za test."""
    n_samples = len(force)
    CONTACT_THRESHOLD = 100.0
    search_end = min(int(3.0 * fs), n_samples)
    contact_mask = force[:search_end] > CONTACT_THRESHOLD
    
    if np.sum(contact_mask) < 100:
        CONTACT_THRESHOLD = 50.0
        contact_mask = force[:search_end] > CONTACT_THRESHOLD
    
    contact_indices = np.where(contact_mask)[0]
    if len(contact_indices) == 0:
        return np.mean(force[:int(0.5*fs)]), np.std(force[:int(0.5*fs)], ddof=1)
    
    first_contact = contact_indices[0]
    quiet_period_start = first_contact + int(0.1 * fs)
    quiet_period_end = min(first_contact + int(1.5 * fs), n_samples)
    
    quiet_segment = force[quiet_period_start:quiet_period_end]
    bw = np.mean(quiet_segment)
    bw_sd = np.std(quiet_segment, ddof=1)
    
    return bw, bw_sd


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


def test_cmj_onset(filepath: Path):
    """Test CMJ onset logike."""
    
    force, force_L, force_R, fs = read_force_file(filepath)
    if force is None:
        return
    
    force = butter_lowpass_filter(force, 50.0, fs, 2)
    
    # Nađi apsolutni minimum
    idx_abs_min = np.argmin(force)
    
    # Izračunaj BW
    bw, bw_sd = calculate_body_weight_robust(force, fs, idx_abs_min)
    
    print(f"\n{'='*90}")
    print(f"TEST CMJ ONSET: {filepath.name}")
    print(f"{'='*90}")
    print(f"\nOsnovne informacije:")
    print(f"  Dužina signala: {len(force)} samples ({len(force)/fs:.2f}s)")
    print(f"  BW: {bw:.2f} N")
    print(f"  BW_SD: {bw_sd:.2f} N")
    print(f"  BW - 5*SD: {bw - 5*bw_sd:.2f} N")
    print(f"  Minimum @ sample {idx_abs_min} ({idx_abs_min/fs:.3f}s), force = {force[idx_abs_min]:.2f} N")
    
    # Korak 2: Nađi maksimum od početka do minimuma
    if idx_abs_min > 0 and idx_abs_min < len(force):
        segment_to_min = force[:idx_abs_min]
        if len(segment_to_min) > 0:
            max_before_min_abs = np.argmax(segment_to_min)
        else:
            max_before_min_abs = 0
    else:
        max_before_min_abs = 0
    
    print(f"\nKorak 2: Maksimum od početka do minimuma (propulsion peak):")
    print(f"  Propulsion peak @ sample {max_before_min_abs} ({max_before_min_abs/fs:.3f}s), force = {force[max_before_min_abs]:.2f} N")
    
    # Korak 3: Nađi minimum između početka i propulsion peak-a (unweighting/unloading minimum)
    if max_before_min_abs > 0:
        segment_to_peak = force[:max_before_min_abs]
        if len(segment_to_peak) > 0:
            unweighting_min_abs = np.argmin(segment_to_peak)
        else:
            unweighting_min_abs = 0
    else:
        unweighting_min_abs = 0
    
    print(f"\nKorak 3: Minimum između početka i propulsion peak-a (unweighting/unloading min):")
    print(f"  Unweighting min @ sample {unweighting_min_abs} ({unweighting_min_abs/fs:.3f}s), force = {force[unweighting_min_abs]:.2f} N")
    
    # Korak 4: Od unweighting/unloading minimuma idi unazad (ka početku) i nađi prvu tačku gde je F >= BW - 5*SD
    threshold_cmj = bw - (5 * bw_sd)
    idx_A_abs = unweighting_min_abs
    
    print(f"\nKorak 4: Traženje onset-a (unazad od unweighting min ka početku):")
    print(f"  Threshold: BW - 5*SD = {threshold_cmj:.2f} N")
    print(f"  Počinjem od unweighting min @ {unweighting_min_abs/fs:.3f}s")
    print(f"  Tražim unazad do početka signala (sample 0)")
    
    found = False
    for i in range(unweighting_min_abs, -1, -1):
        if force[i] >= threshold_cmj:
            idx_A_abs = i
            found = True
            print(f"  [OK] Naden onset @ sample {i} ({i/fs:.3f}s), force = {force[i]:.2f} N")
            break
    
    if not found:
        print(f"  [ERROR] Nije naden onset! Koristim pocetak signala.")
        idx_A_abs = 0
    
    # Proveri redosled
    print(f"\nRedosled dogadjaja:")
    print(f"  1. Onset @ {idx_A_abs/fs:.3f}s, force = {force[idx_A_abs]:.2f} N")
    print(f"  2. Unweighting/unloading min @ {unweighting_min_abs/fs:.3f}s, force = {force[unweighting_min_abs]:.2f} N")
    print(f"  3. Propulsion peak @ {max_before_min_abs/fs:.3f}s, force = {force[max_before_min_abs]:.2f} N")
    print(f"  4. Flight min (apsolutni) @ {idx_abs_min/fs:.3f}s, force = {force[idx_abs_min]:.2f} N")
    
    if not (idx_A_abs < unweighting_min_abs < max_before_min_abs < idx_abs_min):
        print(f"  [WARNING] Redosled nije ispravan!")
    else:
        print(f"  [OK] Redosled je ispravan!")
    
    # Prikaži force vrednosti oko onset-a
    print(f"\nForce vrednosti oko onset-a:")
    start_show = max(0, idx_A_abs - int(0.2*fs))
    end_show = min(len(force), idx_A_abs + int(0.5*fs))
    
    for i in range(start_show, end_show, int(0.1*fs)):
        marker = " <-- ONSET" if i == idx_A_abs else ""
        print(f"  @ {i/fs:.3f}s: force = {force[i]:.2f} N (threshold = {threshold_cmj:.2f} N){marker}")
    
    return idx_A_abs, bw, bw_sd, threshold_cmj


def main():
    filepath = Path(r"C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI\CMJ_ForcePlates\03_4_3.txt")
    
    if filepath.exists():
        test_cmj_onset(filepath)
    else:
        print(f"[ERROR] Fajl nije pronađen: {filepath}")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
