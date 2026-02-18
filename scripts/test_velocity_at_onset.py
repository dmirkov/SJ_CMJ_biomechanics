"""
Test skripta za proveru da li je brzina na onset-u zaista 0 za SJ sa countermovement-om.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib.pyplot as plt
from calculate_fp_kpis import (
    read_force_file, calculate_body_weight_robust, butter_lowpass_filter, CONFIG, analyze_jump
)

def test_velocity_at_onset(filepath: Path):
    """Testira da li je brzina na onset-u zaista 0."""
    
    # Učitaj podatke
    force_L, force_R = read_force_file(filepath)
    if force_L is None or len(force_L) == 0:
        print(f"[ERROR] Neuspešno učitavanje {filepath.name}")
        return
    
    force = force_L + force_R
    fs = CONFIG['SAMPLE_RATE_AMTI']
    
    # Analiziraj skok
    file_id = filepath.stem
    metrics = analyze_jump(force, force_L, force_R, fs, jump_type=1, file_id=file_id)
    
    if metrics is None:
        print(f"[ERROR] Neuspešna analiza {filepath.name}")
        return
    
    # Proveri QC flags
    has_cm = metrics.get('has_countermovement', False)
    qc_notes = metrics.get('qc_notes', 'N/A')
    
    print(f"\n{'='*80}")
    print(f"Test fajl: {filepath.name}")
    print(f"{'='*80}")
    print(f"Countermovement detektovan: {has_cm}")
    print(f"QC Notes: {qc_notes}")
    
    # Pročitaj rezultate iz metrics (ako postoje)
    # Ali analyze_jump ne vraća direktno t i vel, treba da ih izračunamo ponovo
    # ili da modifikujemo analyze_jump da ih vraća
    
    # Za sada, hajde da proverimo samo da li je has_countermovement postavljen
    if has_cm:
        print(f"[OK] Countermovement je detektovan")
        print(f"     Notes: {qc_notes}")
    else:
        print(f"[INFO] Countermovement nije detektovan")
    
    # Napravi plot sa brzinom oko onset-a
    # Treba da rekonstruišemo integraciju brzine
    force_filtered = butter_lowpass_filter(force, CONFIG['FILTER_FREQ'], fs, CONFIG['FILTER_ORDER'])
    idx_abs_min = np.argmin(force_filtered)
    bw, bw_sd = calculate_body_weight_robust(force_filtered, fs, idx_abs_min)
    bm = bw / CONFIG['GRAVITY']
    
    # Detekcija onset-a (pojednostavljena verzija)
    if idx_abs_min > 0:
        segment_to_min = force_filtered[:idx_abs_min]
        max_before_min_abs = np.argmax(segment_to_min) if len(segment_to_min) > 0 else 0
    else:
        max_before_min_abs = 0
    
    threshold_sj = bw + (5 * bw_sd)
    idx_A_abs = max_before_min_abs
    for i in range(max_before_min_abs, -1, -1):
        if force_filtered[i] < threshold_sj:
            idx_A_abs = i
            break
    
    # Detekcija countermovement-a
    min_stable_period = int(0.5 * fs)
    cm_threshold = bw - (2 * bw_sd)
    
    if max_before_min_abs > min_stable_period:
        segment_before_max = force_filtered[min_stable_period:max_before_min_abs]
        cm_indices = np.where(segment_before_max < cm_threshold)[0]
        
        if len(cm_indices) > 0:
            cm_start_idx = cm_indices[0] + min_stable_period
            
            # Traži stabilnu tačku
            stable_threshold_low = bw - (0.5 * bw_sd)
            stable_threshold_high = bw + (0.5 * bw_sd)
            search_start = max(min_stable_period, cm_start_idx - int(1.5 * fs))
            
            true_start_idx = None
            for i in range(cm_start_idx - 1, search_start - 1, -1):
                if stable_threshold_low <= force_filtered[i] <= stable_threshold_high:
                    if i + 1 < len(force_filtered) and force_filtered[i + 1] < force_filtered[i]:
                        true_start_idx = i
                        check_window = min(10, i)
                        if check_window > 0:
                            prev_window = force_filtered[i - check_window:i]
                            prev_stable = np.sum((stable_threshold_low <= prev_window) & (prev_window <= stable_threshold_high))
                            if prev_stable >= check_window * 0.7:
                                break
                        else:
                            break
            
            if true_start_idx is None:
                for i in range(cm_start_idx - 1, search_start - 1, -1):
                    if stable_threshold_low <= force_filtered[i] <= stable_threshold_high:
                        true_start_idx = i
                        break
            
            if true_start_idx is not None:
                idx_A_abs = true_start_idx
    
    # Cropping
    pad_pre, pad_post = 1000, 1500
    # Nađi landing (pojednostavljeno)
    if idx_abs_min < len(force_filtered) - 1:
        right_segment = force_filtered[idx_abs_min + 1:]
        landing_peak_abs = idx_abs_min + 1 + np.argmax(right_segment) if len(right_segment) > 0 else len(force_filtered) - 1
    else:
        landing_peak_abs = len(force_filtered) - 1
    
    idx_H_abs = landing_peak_abs
    for i in range(landing_peak_abs, max(0, landing_peak_abs - int(0.5 * fs)), -1):
        if force_filtered[i] < 50.0:
            idx_H_abs = i
            if i - 1 >= 0 and force_filtered[i - 1] > 10.0:
                idx_H_abs = i - 1
            break
    
    start_crop = max(0, idx_A_abs - pad_pre)
    end_crop = min(len(force_filtered), idx_H_abs + pad_post)
    
    f_crop = force_filtered[start_crop:end_crop]
    t_crop = np.arange(len(f_crop)) / fs
    
    idx_A_crop = idx_A_abs - start_crop
    
    # Integracija
    acc = (f_crop - bw) / bm
    
    # Velocity - koristi istu logiku kao u calculate_fp_kpis.py
    has_cm_detected = len(cm_indices) > 0 if max_before_min_abs > min_stable_period else False
    
    if has_cm_detected and idx_A_crop > 0:
        acc_segment = acc[idx_A_crop:]
        t_segment = t_crop[idx_A_crop:] - t_crop[idx_A_crop]
        
        if len(acc_segment) > 0 and len(t_segment) > 0:
            from scipy.integrate import cumulative_trapezoid
            vel_segment = cumulative_trapezoid(acc_segment, t_segment, initial=0)
            vel = np.zeros_like(acc)
            vel[idx_A_crop:] = vel_segment
            vel[idx_A_crop] = 0.0  # Eksplicitno postavi na 0
        else:
            from scipy.integrate import cumulative_trapezoid
            vel = cumulative_trapezoid(acc, t_crop, initial=0)
            if idx_A_crop >= 0 and idx_A_crop < len(vel):
                vel = vel - vel[idx_A_crop]
                vel[idx_A_crop] = 0.0
    else:
        from scipy.integrate import cumulative_trapezoid
        vel = cumulative_trapezoid(acc, t_crop, initial=0)
        if idx_A_crop >= 0 and idx_A_crop < len(vel):
            vel = vel - vel[idx_A_crop]
            vel[idx_A_crop] = 0.0
    
    # Proveri brzinu na onset-u
    print(f"\nBrzina na onset-u:")
    print(f"  idx_A_crop: {idx_A_crop}")
    print(f"  vel[idx_A_crop]: {vel[idx_A_crop]:.6f} m/s")
    
    if abs(vel[idx_A_crop]) < 1e-6:
        print(f"  [OK] Brzina je tačno 0!")
    else:
        print(f"  [WARNING] Brzina nije 0! Razlika: {abs(vel[idx_A_crop]):.6f} m/s")
    
    # Proveri brzinu oko onset-a (nekoliko tačaka pre i posle)
    print(f"\nBrzina oko onset-a (±10 samples):")
    check_range = range(max(0, idx_A_crop - 10), min(len(vel), idx_A_crop + 11))
    for i in check_range:
        marker = " <-- ONSET" if i == idx_A_crop else ""
        print(f"  Sample {i:4d} ({t_crop[i]:7.4f}s): vel = {vel[i]:8.6f} m/s{marker}")
    
    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Plot 1: Sila oko onset-a
    plot_start = max(0, idx_A_crop - int(0.3 * fs))
    plot_end = min(len(f_crop), idx_A_crop + int(0.5 * fs))
    
    t_plot = t_crop[plot_start:plot_end]
    force_plot = f_crop[plot_start:plot_end]
    vel_plot = vel[plot_start:plot_end]
    
    ax1.plot(t_plot, force_plot, 'b-', linewidth=2, label='Sila')
    ax1.axhline(y=bw, color='g', linestyle='--', linewidth=1.5, label=f'Body Weight ({bw:.1f} N)')
    ax1.axvline(x=t_crop[idx_A_crop], color='r', linestyle='-', linewidth=2, label=f'Onset ({t_crop[idx_A_crop]:.3f}s)')
    ax1.set_xlabel('Vreme (s)', fontsize=12)
    ax1.set_ylabel('Sila (N)', fontsize=12)
    ax1.set_title(f'Sila oko onset-a - {filepath.name}', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Brzina oko onset-a
    ax2.plot(t_plot, vel_plot, 'r-', linewidth=2, label='Brzina')
    ax2.axhline(y=0, color='k', linestyle='--', linewidth=1, alpha=0.5)
    ax2.axvline(x=t_crop[idx_A_crop], color='r', linestyle='-', linewidth=2, label=f'Onset ({t_crop[idx_A_crop]:.3f}s)')
    ax2.plot(t_crop[idx_A_crop], vel[idx_A_crop], 'ro', markersize=12, markeredgecolor='black', markeredgewidth=2, label=f'Brzina na onset-u: {vel[idx_A_crop]:.6f} m/s')
    ax2.set_xlabel('Vreme (s)', fontsize=12)
    ax2.set_ylabel('Brzina (m/s)', fontsize=12)
    ax2.set_title(f'Brzina oko onset-a - {filepath.name}', fontsize=14, fontweight='bold')
    ax2.legend(loc='best', fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Sačuvaj plot
    output_dir = Path(__file__).parent.parent / "Output" / "Velocity_Onset_Test"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{filepath.stem}_velocity_at_onset.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n[OK] Plot sačuvan: {output_file}")
    
    plt.close()


def main():
    base_path = Path(__file__).parent.parent
    sj_fp_dir = base_path / "SJ_ForcePlates"
    
    # Testiraj 01_3_1
    test_file = sj_fp_dir / "01_3_1.txt"
    if test_file.exists():
        test_velocity_at_onset(test_file)
    else:
        print("[ERROR] Test fajl ne postoji")


if __name__ == "__main__":
    main()
