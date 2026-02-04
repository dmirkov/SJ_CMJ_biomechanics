"""
Test skripta za vizualizaciju detekcije početka kod SJ sa countermovement-om.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib.pyplot as plt
from calculate_fp_kpis import (
    read_force_file, calculate_body_weight_robust, butter_lowpass_filter, CONFIG
)

def test_sj_onset_detection(filepath: Path):
    """Testira detekciju početka za SJ skok sa countermovement-om."""
    
    # Učitaj podatke
    force_L, force_R = read_force_file(filepath)
    if force_L is None or len(force_L) == 0:
        print(f"[ERROR] Neuspešno učitavanje {filepath.name}")
        return
    
    force = force_L + force_R
    fs = CONFIG['SAMPLE_RATE_AMTI']
    
    # Filtering
    force = butter_lowpass_filter(force, CONFIG['FILTER_FREQ'], fs, CONFIG['FILTER_ORDER'])
    
    # Nađi apsolutni minimum
    idx_abs_min = np.argmin(force)
    
    # Body Weight
    bw, bw_sd = calculate_body_weight_robust(force, fs, idx_abs_min)
    bm = bw / CONFIG['GRAVITY']
    
    print(f"\n{'='*80}")
    print(f"Test fajl: {filepath.name}")
    print(f"{'='*80}")
    print(f"Body Weight: {bw:.2f} N (SD: {bw_sd:.2f} N)")
    print(f"Apsolutni minimum: sample {idx_abs_min} ({idx_abs_min/fs:.3f}s)")
    
    # Nađi maksimum pre minimuma
    if idx_abs_min > 0:
        segment_to_min = force[:idx_abs_min]
        max_before_min_abs = np.argmax(segment_to_min) if len(segment_to_min) > 0 else 0
    else:
        max_before_min_abs = 0
    
    print(f"Maksimum pre minimuma: sample {max_before_min_abs} ({max_before_min_abs/fs:.3f}s)")
    print(f"  Sila na maksimumu: {force[max_before_min_abs]:.2f} N")
    
    # Detekcija countermovement-a i unweighting minimuma
    cm_threshold = bw - (2 * bw_sd)
    min_stable_period = int(0.5 * fs)
    
    print(f"\nCountermovement detekcija:")
    print(f"  CM threshold: {cm_threshold:.2f} N (BW - 2*SD)")
    print(f"  Minimum period stabilnosti: {min_stable_period} samples ({min_stable_period/fs:.2f}s)")
    
    unweighting_min_abs = None
    idx_A_abs = max_before_min_abs
    
    if max_before_min_abs > min_stable_period:
        segment_before_max = force[min_stable_period:max_before_min_abs]
        cm_indices = np.where(segment_before_max < cm_threshold)[0]
        
        if len(cm_indices) > 0:
            print(f"  [OK] Countermovement detektovan!")
            
            # Nađi unweighting minimum
            if max_before_min_abs > min_stable_period:
                segment_to_max = force[min_stable_period:max_before_min_abs]
                if len(segment_to_max) > 0:
                    unweighting_min_rel = np.argmin(segment_to_max)
                    unweighting_min_abs = unweighting_min_rel + min_stable_period
                    print(f"  Unweighting minimum: sample {unweighting_min_abs} ({unweighting_min_abs/fs:.3f}s)")
                    print(f"  Sila na unweighting minimumu: {force[unweighting_min_abs]:.2f} N")
                else:
                    unweighting_min_abs = min_stable_period
            else:
                unweighting_min_abs = min_stable_period
            
            # Od unweighting minimuma idi unazad i nađi prvu tačku gde je F >= BW - 5*SD
            threshold_cmj = bw - (5 * bw_sd)
            print(f"\n  Traženje početka (backward od unweighting minimuma):")
            print(f"  Threshold: {threshold_cmj:.2f} N (BW - 5*SD)")
            
            idx_A_abs = unweighting_min_abs
            found_start = False
            for i in range(unweighting_min_abs, -1, -1):
                if force[i] >= threshold_cmj:
                    idx_A_abs = i
                    found_start = True
                    print(f"  [OK] Početak detektovan: sample {idx_A_abs} ({idx_A_abs/fs:.3f}s)")
                    print(f"  Sila na početku: {force[idx_A_abs]:.2f} N")
                    break
            
            if not found_start:
                idx_A_abs = max(0, min_stable_period)
                print(f"  [WARNING] Početak nije nađen, koristim fallback: sample {idx_A_abs}")
        else:
            print(f"  [INFO] Nema countermovement-a")
    
    # Standardna SJ onset detekcija (za poređenje)
    threshold_sj = bw + (5 * bw_sd)
    idx_A_standard = max_before_min_abs
    for i in range(max_before_min_abs, -1, -1):
        if force[i] < threshold_sj:
            idx_A_standard = i
            break
    
    print(f"\nStandardna SJ onset detekcija (za poređenje):")
    print(f"  Onset: sample {idx_A_standard} ({idx_A_standard/fs:.3f}s)")
    print(f"  Threshold: {threshold_sj:.2f} N (BW + 5*SD)")
    
    # Plot
    t = np.arange(len(force)) / fs
    
    # Crop za plot (oko relevantnog dela)
    plot_start = max(0, min(idx_A_standard, idx_A_abs) - int(0.5 * fs))
    plot_end = min(len(force), max_before_min_abs + int(0.5 * fs))
    
    t_plot = t[plot_start:plot_end]
    force_plot = force[plot_start:plot_end]
    
    fig, ax = plt.subplots(figsize=(16, 10))
    
    ax.plot(t_plot, force_plot, 'b-', linewidth=2, label='Sila')
    ax.axhline(y=bw, color='g', linestyle='--', linewidth=1.5, label=f'Body Weight ({bw:.1f} N)')
    ax.axhline(y=bw + (5 * bw_sd), color='orange', linestyle='--', linewidth=1, alpha=0.7, label=f'BW + 5*SD ({bw + 5*bw_sd:.1f} N)')
    ax.axhline(y=bw - (2 * bw_sd), color='r', linestyle='--', linewidth=1, alpha=0.7, label=f'BW - 2*SD ({bw - 2*bw_sd:.1f} N)')
    ax.axhline(y=bw - (5 * bw_sd), color='purple', linestyle='--', linewidth=1, alpha=0.7, label=f'BW - 5*SD ({bw - 5*bw_sd:.1f} N)')
    
    # Obeleži tačke
    ax.axvline(x=t[idx_A_standard], color='orange', linestyle='-', linewidth=2, alpha=0.7, label=f'Standardni onset ({idx_A_standard/fs:.3f}s)')
    ax.plot(t[idx_A_standard], force[idx_A_standard], 'o', color='orange', markersize=12, markeredgecolor='black', markeredgewidth=2)
    
    if unweighting_min_abs is not None:
        ax.axvline(x=t[unweighting_min_abs], color='red', linestyle='-', linewidth=2, alpha=0.7, label=f'Unweighting min ({unweighting_min_abs/fs:.3f}s)')
        ax.plot(t[unweighting_min_abs], force[unweighting_min_abs], 's', color='red', markersize=12, markeredgecolor='black', markeredgewidth=2)
    
    if idx_A_abs != idx_A_standard:
        ax.axvline(x=t[idx_A_abs], color='green', linestyle='-', linewidth=2, alpha=0.7, label=f'Novi onset (CMJ logika) ({idx_A_abs/fs:.3f}s)')
        ax.plot(t[idx_A_abs], force[idx_A_abs], '^', color='green', markersize=14, markeredgecolor='black', markeredgewidth=2)
    
    ax.axvline(x=t[max_before_min_abs], color='blue', linestyle=':', linewidth=1.5, alpha=0.5, label=f'Max pre min ({max_before_min_abs/fs:.3f}s)')
    ax.plot(t[max_before_min_abs], force[max_before_min_abs], 'd', color='blue', markersize=10, alpha=0.7)
    
    ax.set_xlabel('Vreme (s)', fontsize=12)
    ax.set_ylabel('Sila (N)', fontsize=12)
    ax.set_title(f'SJ Onset Detekcija (CMJ logika) - {filepath.name}', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Sačuvaj plot
    output_dir = Path(__file__).parent / "Output" / "SJ_Onset_Detection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{filepath.stem}_onset_detection.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n[OK] Plot sačuvan: {output_file}")
    
    plt.close()
    
    return idx_A_abs, unweighting_min_abs


def main():
    base_path = Path(__file__).parent
    sj_fp_dir = base_path / "SJ_ForcePlates"
    
    # Testiraj 01_3_1
    test_file = sj_fp_dir / "01_3_1.txt"
    if test_file.exists():
        test_sj_onset_detection(test_file)
    else:
        print("[ERROR] Test fajl ne postoji")


if __name__ == "__main__":
    main()
