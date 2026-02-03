#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KREIRANJE FINALNIH PLOTOVA SA SVIM KARAKTERISTIČNIM TAČKAMA
============================================================
Kreira plotove za az (ubrzanje) i vz (brzina) sa svim obeleženim tačkama:
- Onset (A)
- Unweighting minimum (B) - za CMJ
- Propulsion peak (C)
- Takeoff (D)
- Landing (H)
- Minimum absolute (E) - za CMJ
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import importlib.util

# Importuj calculate_fp_kpis modul
base_path = Path(__file__).parent
spec = importlib.util.spec_from_file_location("calculate_fp_kpis", base_path / "calculate_fp_kpis.py")
calc_module = importlib.util.module_from_spec(spec)
sys.modules["calculate_fp_kpis"] = calc_module
spec.loader.exec_module(calc_module)

# Koristi funkcije iz calculate_fp_kpis
analyze_jump = calc_module.analyze_jump
read_force_file = calc_module.read_force_file


def create_final_plot(filepath: Path, jump_type: int, output_dir: Path):
    """
    Kreira finalni plot sa az i vz i svim karakterističnim tačkama.
    
    Args:
        filepath: Putanja do Force Plate TXT fajla
        jump_type: 1 = SJ, 2 = CMJ
        output_dir: Folder gde da se sačuva plot
    """
    try:
        # Učitaj Force Plate podatke
        raw_L, raw_R = read_force_file(filepath)
        if raw_L is None or raw_R is None:
            return False
        
        fs = 1000.0  # AMTI sample rate
        force_total = raw_L + raw_R
        
        # Analiziraj skok - koristi istu logiku kao calculate_fp_kpis
        # Ali treba da dobijemo i idx, pa ćemo koristiti direktnu implementaciju
        metrics = analyze_jump(force_total, raw_L, raw_R, fs, jump_type, filepath.stem)
        
        if metrics is None:
            return False
        
        # Rekonstruiši idx iz metrics - koristimo vremena iz metrics
        # Ali pošto analyze_jump ne vraća idx, treba da rekonstruišemo logiku
        # Najbolje je da koristimo direktnu implementaciju iz calculate_fp_kpis
        
        # Importuj sve potrebne funkcije
        from scipy.signal import butter, filtfilt
        from scipy.integrate import cumulative_trapezoid
        butter_lowpass_filter = calc_module.butter_lowpass_filter
        calculate_body_weight_robust = calc_module.calculate_body_weight_robust
        
        # Filtriranje
        force_filtered = butter_lowpass_filter(force_total, 50.0, fs, 2)
        
        # Nađi apsolutni minimum
        idx_abs_min = np.argmin(force_filtered)
        
        # Body weight
        bw, bw_sd = calculate_body_weight_robust(force_filtered, fs, idx_abs_min)
        bm = bw / 9.81
        
        if bw is None or bm is None or bw < 300 or bw > 1500:
            return False
        
        # Nađi pike oko minimuma (za landing peak)
        if idx_abs_min < len(force_filtered) - 1:
            right_segment = force_filtered[idx_abs_min + 1:]
            landing_peak_abs = idx_abs_min + 1 + np.argmax(right_segment) if len(right_segment) > 0 else len(force_filtered) - 1
        else:
            landing_peak_abs = len(force_filtered) - 1
        
        # Propulsion peak - izračunaj za oba tipa skokova ovde
        propulsion_peak_abs = 0
        if idx_abs_min > 0 and idx_abs_min < len(force_filtered):
            left_segment = force_filtered[:idx_abs_min]
            if len(left_segment) > 0:
                propulsion_peak_abs = np.argmax(left_segment)
            else:
                propulsion_peak_abs = 0
        else:
            propulsion_peak_abs = 0
        
        # Takeoff i Landing
        idx_F_abs = propulsion_peak_abs
        for i in range(propulsion_peak_abs, min(len(force_filtered), propulsion_peak_abs + int(0.5 * fs))):
            if force_filtered[i] < 50.0:
                idx_F_abs = i
                break
        
        idx_H_abs = landing_peak_abs
        for i in range(landing_peak_abs, max(0, landing_peak_abs - int(0.5 * fs)), -1):
            if force_filtered[i] < 50.0:
                idx_H_abs = i
                break
        
        # Onset (A) - KORISTI ISTU LOGIKU KAO U calculate_fp_kpis.py
        # VAŽNO: Za CMJ redosled je: onset → unweighting min → propulsion peak → takeoff
        idx_A_abs = 0
        unweighting_min_abs_sj = None  # Sačuvaj za SJ sa CM
        
        if jump_type == 1:  # SJ
            # Koristi ISTU logiku kao u calculate_fp_kpis.py linija 280-389
            if idx_abs_min > 0 and idx_abs_min < len(force_filtered):
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
            
            # NOVA LOGIKA: Detekcija countermovement-a koristeći CMJ pristup
            cm_threshold = bw - (5 * bw_sd)
            min_stable_period = int(0.5 * fs)
            
            if max_before_min_abs > min_stable_period:
                segment_before_max = force_filtered[min_stable_period:max_before_min_abs]
                cm_indices = np.where(segment_before_max < cm_threshold)[0]
                
                if len(cm_indices) > 0:
                    # Postoji countermovement - koristi CMJ logiku
                    if max_before_min_abs > min_stable_period:
                        segment_to_max = force_filtered[min_stable_period:max_before_min_abs]
                        if len(segment_to_max) > 0:
                            unweighting_min_rel = np.argmin(segment_to_max)
                            unweighting_min_abs_sj = unweighting_min_rel + min_stable_period
                        else:
                            unweighting_min_abs_sj = min_stable_period
                    else:
                        unweighting_min_abs_sj = min_stable_period
                    
                    # Od unweighting minimuma idi unazad i nađi pravi početak
                    threshold_cmj = bw - (5 * bw_sd)
                    stable_threshold_low = bw - (0.5 * bw_sd)
                    stable_threshold_high = bw + (0.5 * bw_sd)
                    
                    idx_A_abs = unweighting_min_abs_sj
                    found_threshold = False
                    for i in range(unweighting_min_abs_sj, -1, -1):
                        if force_filtered[i] >= threshold_cmj:
                            idx_A_abs = i
                            found_threshold = True
                            break
                    
                    # Traži stabilnu tačku pre početka pada
                    if found_threshold and idx_A_abs > min_stable_period:
                        search_start = max(min_stable_period, idx_A_abs - int(1.0 * fs))
                        true_start_idx = None
                        
                        for i in range(idx_A_abs - 1, search_start - 1, -1):
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
                            for i in range(idx_A_abs - 1, search_start - 1, -1):
                                if stable_threshold_low <= force_filtered[i] <= stable_threshold_high:
                                    true_start_idx = i
                                    break
                        
                        if true_start_idx is not None:
                            idx_A_abs = true_start_idx
                    
                    if idx_A_abs == unweighting_min_abs_sj:
                        idx_A_abs = max(0, min_stable_period)
        
        else:  # CMJ
            # KORISTI ISTU LOGIKU KAO U calculate_fp_kpis.py linija 390-433
            # Redosled: početak signala (quiet) → onset → unweighting/unloading min → propulsion peak → TO → flight min
            
            # VAŽNO: propulsion_peak_abs je već izračunat gore (linija 95-102)
            
            # Korak 2: Nađi minimum između početka i propulsion peak-a (unweighting/unloading minimum)
            if propulsion_peak_abs > 0:
                segment_to_peak = force_filtered[:propulsion_peak_abs]
                if len(segment_to_peak) > 0:
                    unweighting_min_abs = np.argmin(segment_to_peak)
                else:
                    unweighting_min_abs = 0
            else:
                unweighting_min_abs = 0
            
            # Korak 3: Od unweighting/unloading minimuma idi unazad i nađi prvu tačku gde je F >= BW - 5*SD
            threshold_cmj = bw - (5 * bw_sd)
            idx_A_abs = unweighting_min_abs
            
            for i in range(unweighting_min_abs, -1, -1):
                if force_filtered[i] >= threshold_cmj:
                    idx_A_abs = i
                    break
            
            if idx_A_abs == unweighting_min_abs:
                idx_A_abs = 0
            
            # Ažuriraj propulsion_peak_abs za kasnije korišćenje
            propulsion_peak_abs = propulsion_peak_abs  # Već izračunato gore
        
        # Crop signal (od onset-a do landing-a + padding)
        start_crop = max(0, idx_A_abs - int(0.5 * fs))
        end_crop = min(len(force_filtered), idx_H_abs + int(0.5 * fs))
        
        force_crop = force_filtered[start_crop:end_crop]
        t_crop = np.arange(len(force_crop)) / fs
        
        # Ažuriraj idx u odnosu na crop
        idx = {}
        idx['A'] = idx_A_abs - start_crop
        idx['F'] = idx_F_abs - start_crop
        idx['H'] = idx_H_abs - start_crop
        idx['min'] = idx_abs_min - start_crop
        idx['propulsion_peak'] = propulsion_peak_abs - start_crop
        idx['landing_peak'] = landing_peak_abs - start_crop
        
        # Za CMJ: B = unweighting min (između onset-a i propulsion peak-a)
        # VAŽNO: Za CMJ, unweighting_min_abs je već izračunat u linijama 209-217
        # Ali moramo proveriti da li je između onset-a i propulsion peak-a
        # Za SJ sa CM: B = unweighting min (ako postoji) - izračunat u linijama 145-146
        if jump_type == 2:  # CMJ
            # Unweighting min je između onset-a i propulsion peak-a
            # Koristimo unweighting_min_abs koji je već izračunat (linija 213)
            # Ali proveravamo da li je između onset-a i propulsion peak-a
            if idx_A_abs >= 0 and propulsion_peak_abs > idx_A_abs:
                # Proveri da li je unweighting_min_abs između onset-a i propulsion peak-a
                if idx_A_abs <= unweighting_min_abs < propulsion_peak_abs:
                    # Koristi postojeći unweighting_min_abs
                    idx['B'] = unweighting_min_abs - start_crop
                else:
                    # Rekalkuliši unweighting min između onset-a i propulsion peak-a
                    segment_between = force_filtered[idx_A_abs:propulsion_peak_abs]
                    if len(segment_between) > 0:
                        unweighting_min_rel = np.argmin(segment_between)
                        unweighting_min_abs_recalc = idx_A_abs + unweighting_min_rel
                        idx['B'] = unweighting_min_abs_recalc - start_crop
                    else:
                        idx['B'] = -1
            else:
                idx['B'] = -1
        else:  # SJ
            # Proveri da li postoji unweighting min (countermovement)
            # Za SJ sa CM, unweighting_min_abs_sj je već izračunat u linijama 145-146
            # Proveravamo da li je između onset-a i propulsion peak-a
            if idx_A_abs >= 0 and propulsion_peak_abs > idx_A_abs:
                # Proveri da li je već izračunat unweighting_min_abs_sj (iz CM detekcije)
                # i da li je između onset-a i propulsion peak-a
                if unweighting_min_abs_sj is not None and idx_A_abs <= unweighting_min_abs_sj < propulsion_peak_abs:
                    # Proveri da li je ovo zaista countermovement (sila < BW - 5*SD)
                    if force_filtered[unweighting_min_abs_sj] < (bw - 5 * bw_sd):
                        idx['B'] = unweighting_min_abs_sj - start_crop
                    else:
                        idx['B'] = -1
                else:
                    # Rekalkuliši unweighting min između onset-a i propulsion peak-a
                    segment_between = force_filtered[idx_A_abs:propulsion_peak_abs]
                    if len(segment_between) > 0:
                        unweighting_min_rel = np.argmin(segment_between)
                        unweighting_min_abs_recalc = idx_A_abs + unweighting_min_rel
                        # Proveri da li je ovo zaista countermovement (sila < BW - 5*SD)
                        if force_filtered[unweighting_min_abs_recalc] < (bw - 5 * bw_sd):
                            idx['B'] = unweighting_min_abs_recalc - start_crop
                        else:
                            idx['B'] = -1
                    else:
                        idx['B'] = -1
            else:
                idx['B'] = -1
        
        idx['C'] = idx.get('propulsion_peak', -1)  # Propulsion peak
        idx['D'] = idx.get('F', -1)  # Takeoff
        idx['E'] = idx.get('min', -1)  # Min absolute (flight phase)
        
        # E. Integration (Kinematics) - ISTA LOGIKA KAO U calculate_fp_kpis.py
        acc = (force_crop - bw) / bm
        
        # Velocity - KORISTI ISTU LOGIKU KAO U compare_velocity_profiles.py
        # VAŽNO: Forward integracija od onset-a sa initial=0 garantuje da brzina počinje od nule
        # Proveri da li postoji countermovement za SJ
        has_cm = False
        if jump_type == 1 and unweighting_min_abs_sj is not None:
            has_cm = True
        
        if jump_type == 1 and has_cm and idx['A'] >= 0:
            # Za SJ SA COUNTERMOVEMENT-OM: integracija počinje direktno od onset-a
            acc_segment = acc[idx['A']:]
            t_segment = t_crop[idx['A']:] - t_crop[idx['A']]  # Relativno vreme od onset-a
            if len(acc_segment) > 0 and len(t_segment) > 0:
                vel_segment = cumulative_trapezoid(acc_segment, t_segment, initial=0)
                vel = np.zeros_like(acc)
                vel[idx['A']:] = vel_segment
                # EKSPLICITNO: Osiguraj da je brzina na onset-u tačno 0
                if idx['A'] >= 0 and idx['A'] < len(vel):
                    vel[idx['A']] = 0.0
            else:
                # Fallback: standard forward integration
                vel = cumulative_trapezoid(acc, t_crop, initial=0)
                if idx['A'] >= 0 and idx['A'] < len(vel):
                    vel = vel - vel[idx['A']]
                    vel[idx['A']] = 0.0
        else:
            # Za CMJ ili SJ BEZ countermovement-a: standardna integracija (ISTA LOGIKA KAO U compare_velocity_profiles.py)
            vel = cumulative_trapezoid(acc, t_crop, initial=0)
            if idx['A'] >= 0 and idx['A'] < len(vel):
                vel = vel - vel[idx['A']]  # Oduzmi offset da bi brzina na onset-u bila 0
                vel[idx['A']] = 0.0  # Eksplicitno postavi na 0
        
        # Drift correction - ISTA LOGIKA KAO U compare_velocity_profiles.py
        # VAŽNO: Osiguraj da brzina na onset-u ostane 0 i posle drift correction
        CORRECT_DRIFT = True  # Default vrednost
        DRIFT_ZERO_PERIOD = 0.5  # Default vrednost u sekundama
        if CORRECT_DRIFT:
            landing_buffer = int(DRIFT_ZERO_PERIOD * fs)
            if idx['H'] >= 0 and idx['H'] + landing_buffer < len(vel):
                v_landing_observed = np.mean(vel[idx['H']:idx['H'] + landing_buffer])
                duration = t_crop[idx['H']] - t_crop[idx['A']] if idx['H'] > idx['A'] else t_crop[-1] - t_crop[idx['A']]
                if duration > 0 and abs(v_landing_observed) < 10.0:
                    drift_slope = v_landing_observed / duration
                    correction = np.zeros_like(vel)
                    correction[idx['A']:] = drift_slope * (t_crop[idx['A']:] - t_crop[idx['A']])
                    vel = vel - correction
                    # EKSPLICITNO: Osiguraj da je brzina na onset-u tačno 0 i posle drift correction
                    if idx['A'] >= 0 and idx['A'] < len(vel):
                        vel[idx['A']] = 0.0
        
        # Displacement (za hmin)
        disp = cumulative_trapezoid(vel, t_crop, initial=0)
        if idx['A'] < len(disp):
            disp = disp - disp[idx['A']]
        
        # Dodatne karakteristične tačke
        if idx['F'] > idx['A'] and idx['F'] <= len(vel):
            idx['vmax'] = idx['A'] + np.argmax(vel[idx['A']:idx['F']])
            idx['vmin'] = idx['A'] + np.argmin(vel[idx['A']:idx['F']])
        else:
            idx['vmax'] = idx['A']
            idx['vmin'] = idx['A']
        if idx['F'] > idx['A'] and idx['F'] <= len(disp):
            idx['hmin'] = idx['A'] + np.argmin(disp[idx['A']:idx['F']])
        else:
            idx['hmin'] = idx['A']
        
        # Kreiraj KOMBINOVANI plot: az-t + vz-t (dual Y-axis)
        fig, ax1 = plt.subplots(figsize=(14, 8))
        
        jump_name = 'SJ' if jump_type == 1 else 'CMJ'
        
        # Leva Y osa: Ubrzanje (az)
        color_acc = 'tab:blue'
        ax1.set_xlabel('Vreme (s)', fontsize=12)
        ax1.set_ylabel('Ubrzanje az (m/s²)', color=color_acc, fontsize=12)
        ax1.plot(t_crop, acc, color=color_acc, linewidth=2, label='az(t)', alpha=0.8)
        ax1.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.tick_params(axis='y', labelcolor=color_acc)
        ax1.grid(True, alpha=0.3)
        
        # Desna Y osa: Brzina (vz)
        ax2 = ax1.twinx()
        color_vel = 'tab:red'
        ax2.set_ylabel('Brzina vz (m/s)', color=color_vel, fontsize=12)
        ax2.plot(t_crop, vel, color=color_vel, linewidth=2, label='vz(t)', alpha=0.8)
        ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
        ax2.tick_params(axis='y', labelcolor=color_vel)
        
        # Sve karakteristične tačke sa labelima
        point_labels = {
            'A': ('A (Onset)', 'green', 'o', 10),
            'B': ('B (Unw min)', 'orange', 's', 8),
            'C': ('C (Prop peak)', 'purple', '^', 10),
            'D': ('D (Takeoff)', 'red', 'D', 10),
            'E': ('E (Flight min)', 'brown', 'v', 8),
            'H': ('H (Landing)', 'blue', 's', 10),
            'vmax': ('vmax', 'darkgreen', '^', 9),
            'vmin': ('vmin', 'darkviolet', 'v', 9),
            'hmin': ('hmin', 'teal', '*', 9),
        }
        
        for point_key, (label, color, marker, size) in point_labels.items():
            idx_val = idx.get(point_key, -1)
            if idx_val >= 0 and idx_val < len(t_crop):
                t_point = t_crop[idx_val]
                acc_val = acc[idx_val] if idx_val < len(acc) else 0
                vel_val = vel[idx_val] if idx_val < len(vel) else 0
                disp_val = disp[idx_val] if idx_val < len(disp) else 0
                
                # Markeri na obe krive
                ax1.plot(t_point, acc_val, color=color, marker=marker, markersize=size,
                        markeredgecolor='black', markeredgewidth=1.5)
                ax2.plot(t_point, vel_val, color=color, marker=marker, markersize=size,
                        markeredgecolor='black', markeredgewidth=1.5)
                ax1.axvline(x=t_point, color=color, linestyle=':', linewidth=1, alpha=0.5)
                
                # Tekstualna anotacija za SVAKU tačku
                label_text = f"{label}\nt={t_point:.3f}s\naz={acc_val:.2f}\nvz={vel_val:.3f}"
                if point_key == 'hmin':
                    label_text += f"\nh={disp_val:.3f}m"
                
                ax2.annotate(label_text,
                    xy=(t_point, vel_val),
                    xytext=(15, 15),
                    textcoords='offset points',
                    fontsize=8,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.25),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', lw=1, color=color))
        
        ax1.set_title(f'{jump_name} - {filepath.stem}  |  az(t) + vz(t)  |  Sve tačke obeležene', fontsize=14, fontweight='bold')
        fig.legend([ax1.get_lines()[0], ax2.get_lines()[0]], ['az(t)', 'vz(t)'], loc='upper right', fontsize=10)
        
        plt.tight_layout()
        
        # Sačuvaj plot
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f'{filepath.stem}_final_plot.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] Greška pri kreiranju plot-a za {filepath.name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    base_path = Path(__file__).parent
    
    # Force Plate folderi (lokalni)
    sj_fp_dir = base_path / "SJ_ForcePlates"
    cmj_fp_dir = base_path / "CMJ_ForcePlates"
    
    # Output folderi
    sj_output_dir = base_path / "Output" / "Final_Plots" / "SJ"
    cmj_output_dir = base_path / "Output" / "Final_Plots" / "CMJ"
    
    print("=" * 90)
    print("KREIRANJE FINALNIH PLOTOVA SA SVIM KARAKTERISTIČNIM TAČKAMA")
    print("=" * 90)
    print(f"Vreme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    
    total_processed = 0
    total_success = 0
    
    # Procesiraj SJ fajlove
    if sj_fp_dir.exists():
        sj_files = sorted(sj_fp_dir.glob("*.txt"))
        print(f"\n[SJ] Obrada {len(sj_files)} fajlova...")
        
        for fp_file in sj_files:
            total_processed += 1
            if create_final_plot(fp_file, 1, sj_output_dir):
                total_success += 1
                if total_processed % 10 == 0:
                    print(f"  Procesirano: {total_processed}/{len(sj_files)}")
            else:
                print(f"  [ERROR] {fp_file.name}")
    else:
        print(f"\n[WARNING] Folder ne postoji: {sj_fp_dir}")
    
    # Procesiraj CMJ fajlove
    if cmj_fp_dir.exists():
        cmj_files = sorted(cmj_fp_dir.glob("*.txt"))
        print(f"\n[CMJ] Obrada {len(cmj_files)} fajlova...")
        
        for fp_file in cmj_files:
            total_processed += 1
            if create_final_plot(fp_file, 2, cmj_output_dir):
                total_success += 1
                if total_processed % 10 == 0:
                    print(f"  Procesirano: {total_processed}/{len(cmj_files)}")
            else:
                print(f"  [ERROR] {fp_file.name}")
    else:
        print(f"\n[WARNING] Folder ne postoji: {cmj_fp_dir}")
    
    # Finalni izveštaj
    print("\n" + "=" * 90)
    print("FINALNI IZVESTAJ")
    print("=" * 90)
    print(f"Vreme završetka: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ukupno obrađeno: {total_processed}")
    print(f"Uspešno: {total_success}")
    print(f"Neuspešno: {total_processed - total_success}")
    
    if total_success > 0:
        print(f"\n[SUCCESS] Plotovi sačuvani u:")
        print(f"  - {sj_output_dir}")
        print(f"  - {cmj_output_dir}")
        return 0
    else:
        print(f"\n[ERROR] Nema uspešno kreiranih plotova")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
