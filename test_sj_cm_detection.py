"""
Test skripta za vizualizaciju poboljšane detekcije početka countermovement-a kod SJ skokova.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from calculate_fp_kpis import (
    read_force_file, calculate_body_weight_robust, butter_lowpass_filter, CONFIG
)

def test_sj_cm_detection(filepath: Path):
    """Testira detekciju početka countermovement-a za SJ skok."""
    
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
    
    # Standardna SJ onset detekcija
    threshold_sj = bw + (5 * bw_sd)
    idx_A_standard = max_before_min_abs
    for i in range(max_before_min_abs, -1, -1):
        if force[i] < threshold_sj:
            idx_A_standard = i
            break
    
    print(f"\nStandardna SJ onset detekcija:")
    print(f"  Onset: sample {idx_A_standard} ({idx_A_standard/fs:.3f}s)")
    print(f"  Threshold: {threshold_sj:.2f} N")
    
    # NOVA LOGIKA: Detekcija countermovement-a
    cm_threshold = bw - (2 * bw_sd)
    print(f"\nCountermovement detekcija:")
    print(f"  CM threshold: {cm_threshold:.2f} N (BW - 2*SD)")
    
    cm_start_idx = None
    idx_A_improved = idx_A_standard
    
    # VAŽNO: Ignoriši countermovement na samom početku signala (pre stabilizacije)
    min_stable_period = int(0.5 * fs)  # Minimum period stabilnosti pre traženja CM
    print(f"  Minimum period stabilnosti: {min_stable_period} samples ({min_stable_period/fs:.2f}s)")
    
    if max_before_min_abs > min_stable_period:
        # Traži countermovement samo posle perioda stabilnosti
        segment_before_max = force[min_stable_period:max_before_min_abs]
        cm_indices = np.where(segment_before_max < cm_threshold)[0]
        
        if len(cm_indices) > 0:
            cm_start_idx = cm_indices[0] + min_stable_period  # Vrati apsolutni indeks
            print(f"  [OK] Countermovement detektovan!")
            print(f"  CM start (prva tačka < threshold posle stabilizacije): sample {cm_start_idx} ({cm_start_idx/fs:.3f}s)")
            print(f"  Sila na CM start: {force[cm_start_idx]:.2f} N")
            
            # Poboljšana detekcija početka
            if cm_start_idx > 0:
                stable_threshold_low = bw - (0.5 * bw_sd)
                stable_threshold_high = bw + (0.5 * bw_sd)
                
                true_start_idx = None
                
                # Traži poslednju tačku gde je sila stabilna pre početka pada
                search_start = max(min_stable_period, cm_start_idx - int(1.5 * fs))
                print(f"\n  Traženje stabilne tačke (traži unazad od CM start):")
                print(f"    Search range: sample {search_start} do {cm_start_idx} ({search_start/fs:.3f}s do {cm_start_idx/fs:.3f}s)")
                
                # Prvo nađi poslednju tačku gde je sila stabilna i gde počinje da pada
                for i in range(cm_start_idx - 1, search_start - 1, -1):
                    if stable_threshold_low <= force[i] <= stable_threshold_high:
                        if i + 1 < len(force) and force[i + 1] < force[i]:
                            true_start_idx = i
                            # Proveri da li je ovo dovoljno stabilna tačka
                            check_window = min(10, i)
                            if check_window > 0:
                                prev_window = force[i - check_window:i]
                                prev_stable = np.sum((stable_threshold_low <= prev_window) & (prev_window <= stable_threshold_high))
                                if prev_stable >= check_window * 0.7:
                                    print(f"    Nađena stabilna tačka (sa padom): sample {true_start_idx} ({true_start_idx/fs:.3f}s)")
                                    print(f"    Sila na stabilnoj tački: {force[true_start_idx]:.2f} N")
                                    print(f"    Sila na sledećoj tački: {force[i+1]:.2f} N (pad)")
                                    break
                            else:
                                print(f"    Nađena stabilna tačka (sa padom): sample {true_start_idx} ({true_start_idx/fs:.3f}s)")
                                break
                
                # Ako nismo našli tačku gde sila počinje da pada, traži poslednju stabilnu tačku
                if true_start_idx is None:
                    print(f"    [INFO] Nije nađena tačka sa padom, tražim poslednju stabilnu tačku...")
                    for i in range(cm_start_idx - 1, search_start - 1, -1):
                        if stable_threshold_low <= force[i] <= stable_threshold_high:
                            true_start_idx = i
                            print(f"    Nađena stabilna tačka: sample {true_start_idx} ({true_start_idx/fs:.3f}s)")
                            print(f"    Sila na stabilnoj tački: {force[true_start_idx]:.2f} N")
                            break
                
                if true_start_idx is not None:
                    idx_A_improved = true_start_idx
                    print(f"\n  [OK] Poboljšani onset: sample {idx_A_improved} ({idx_A_improved/fs:.3f}s)")
                else:
                    # Fallback
                    print(f"  [WARNING] Nije nađena stabilna tačka, koristim fallback")
                    for i in range(cm_start_idx - 1, max(0, cm_start_idx - int(0.5 * fs)), -1):
                        if force[i] >= bw - (1 * bw_sd):
                            idx_A_improved = i
                            print(f"  Fallback onset: sample {idx_A_improved} ({idx_A_improved/fs:.3f}s)")
                            break
                    else:
                        idx_A_improved = cm_start_idx
                        print(f"  Koristim CM start kao onset: sample {idx_A_improved} ({idx_A_improved/fs:.3f}s)")
        else:
            print(f"  [INFO] Nema countermovement-a")
    
    # Plot
    t = np.arange(len(force)) / fs
    
    # Crop za plot (oko relevantnog dela)
    plot_start = max(0, min(idx_A_standard, idx_A_improved if cm_start_idx else idx_A_standard) - int(0.5 * fs))
    plot_end = min(len(force), max_before_min_abs + int(0.5 * fs))
    
    t_plot = t[plot_start:plot_end]
    force_plot = force[plot_start:plot_end]
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    ax.plot(t_plot, force_plot, 'b-', linewidth=2, label='Sila')
    ax.axhline(y=bw, color='g', linestyle='--', linewidth=1.5, label=f'Body Weight ({bw:.1f} N)')
    ax.axhline(y=bw + (5 * bw_sd), color='orange', linestyle='--', linewidth=1, alpha=0.7, label=f'BW + 5*SD ({bw + 5*bw_sd:.1f} N)')
    ax.axhline(y=bw - (2 * bw_sd), color='r', linestyle='--', linewidth=1, alpha=0.7, label=f'BW - 2*SD ({bw - 2*bw_sd:.1f} N)')
    ax.axhline(y=bw - (0.5 * bw_sd), color='purple', linestyle=':', linewidth=1, alpha=0.5, label=f'BW ± 0.5*SD')
    ax.axhline(y=bw + (0.5 * bw_sd), color='purple', linestyle=':', linewidth=1, alpha=0.5)
    
    # Obeleži tačke
    ax.axvline(x=t[idx_A_standard], color='orange', linestyle='-', linewidth=2, alpha=0.7, label=f'Standardni onset ({idx_A_standard/fs:.3f}s)')
    ax.plot(t[idx_A_standard], force[idx_A_standard], 'o', color='orange', markersize=10, markeredgecolor='black', markeredgewidth=1)
    
    if cm_start_idx is not None:
        ax.axvline(x=t[cm_start_idx], color='red', linestyle='-', linewidth=2, alpha=0.7, label=f'CM start ({cm_start_idx/fs:.3f}s)')
        ax.plot(t[cm_start_idx], force[cm_start_idx], 's', color='red', markersize=10, markeredgecolor='black', markeredgewidth=1)
    
    if idx_A_improved != idx_A_standard:
        ax.axvline(x=t[idx_A_improved], color='green', linestyle='-', linewidth=2, alpha=0.7, label=f'Poboljšani onset ({idx_A_improved/fs:.3f}s)')
        ax.plot(t[idx_A_improved], force[idx_A_improved], '^', color='green', markersize=12, markeredgecolor='black', markeredgewidth=1)
    
    ax.axvline(x=t[max_before_min_abs], color='blue', linestyle=':', linewidth=1.5, alpha=0.5, label=f'Max pre min ({max_before_min_abs/fs:.3f}s)')
    ax.plot(t[max_before_min_abs], force[max_before_min_abs], 'd', color='blue', markersize=8, alpha=0.7)
    
    ax.set_xlabel('Vreme (s)', fontsize=12)
    ax.set_ylabel('Sila (N)', fontsize=12)
    ax.set_title(f'SJ Countermovement Detekcija - {filepath.name}', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Sačuvaj plot
    output_dir = Path(__file__).parent / "Output" / "SJ_CM_Detection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{filepath.stem}_cm_detection.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n[OK] Plot sačuvan: {output_file}")
    
    plt.close()
    
    return idx_A_standard, idx_A_improved, cm_start_idx


def main():
    base_path = Path(__file__).parent
    sj_fp_dir = base_path / "SJ_ForcePlates"
    
    # Testiraj prvi fajl koji ima countermovement
    sj_files = list(sj_fp_dir.glob("*.txt"))
    
    if len(sj_files) == 0:
        print("[ERROR] Nema SJ Force Plate fajlova")
        return
    
    # Testiraj 01_3_1 (koji smo videli u plotu)
    test_file = sj_fp_dir / "01_3_1.txt"
    if test_file.exists():
        test_sj_cm_detection(test_file)
    else:
        # Testiraj prvi dostupan fajl
        test_sj_cm_detection(sj_files[0])


if __name__ == "__main__":
    main()
