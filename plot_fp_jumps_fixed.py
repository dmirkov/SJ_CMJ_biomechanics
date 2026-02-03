#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PLOTOVANJE FORCE PLATE SKOKOVA - NOVA LOGIKA
=============================================
Kreira plotove sa novom logikom za detekciju događaja.
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt


# Konfiguracija
CONFIG = {
    'GRAVITY': 9.81,
    'CORRECT_DRIFT': True,
    'DRIFT_ZERO_PERIOD': 0.5,
    'BUTTER_LOWPASS_FREQ': 50.0,
    'BUTTER_ORDER': 4,
    'SAMPLE_RATE_AMTI': 1000.0,
    'FILTER_FREQ': 50.0,
    'FILTER_ORDER': 2,
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
    """Robustniji algoritam za izračunavanje body weight-a - NOVA LOGIKA."""
    n_samples = len(force)
    if n_samples < 100:
        quiet_period = int(0.5 * fs)
        return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
    
    try:
        # Prvo nađi period sa stvarnim kontaktom sa force plate-om
        CONTACT_THRESHOLD = 100.0
        search_end = min(int(3.0 * fs), n_samples)
        contact_mask = force[:search_end] > CONTACT_THRESHOLD
        
        if np.sum(contact_mask) < 100:
            CONTACT_THRESHOLD = 50.0
            contact_mask = force[:search_end] > CONTACT_THRESHOLD
            if np.sum(contact_mask) < 100:
                quiet_period = int(0.5 * fs)
                return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
        
        contact_indices = np.where(contact_mask)[0]
        if len(contact_indices) == 0 or len(contact_indices) < 100:
            quiet_period = int(0.5 * fs)
            return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
        
        first_contact = contact_indices[0]
        last_contact = contact_indices[-1]
        
        # Koristi stabilan period za BW (od first_contact + 0.1s do first_contact + 1.5s)
        quiet_period_start = first_contact + int(0.1 * fs)
        quiet_period_end = min(first_contact + int(1.5 * fs), last_contact + int(0.1 * fs), n_samples)
        
        if quiet_period_end <= quiet_period_start or quiet_period_end - quiet_period_start < 100:
            quiet_period_start = first_contact
            quiet_period_end = min(first_contact + int(1.0 * fs), n_samples)
            if quiet_period_end <= quiet_period_start or quiet_period_end - quiet_period_start < 100:
                quiet_period = int(0.5 * fs)
                return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
        
        quiet_segment = force[quiet_period_start:quiet_period_end]
        if np.mean(quiet_segment) < CONTACT_THRESHOLD:
            quiet_period = int(0.5 * fs)
            return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
        
        # Median i SD za filtriranje
        bw_est = np.median(quiet_segment)
        bw_std_est = np.std(quiet_segment, ddof=1)
        
        if np.isnan(bw_est) or np.isnan(bw_std_est) or bw_std_est == 0:
            quiet_period = int(0.5 * fs)
            return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
        
        # Filtriranje (2*SD)
        mask = (quiet_segment > bw_est - 2 * bw_std_est) & (quiet_segment < bw_est + 2 * bw_std_est)
        clean_indices = np.where(mask)[0]
        
        if len(clean_indices) > 50:
            final_bw = np.mean(quiet_segment[clean_indices])
            final_sd = np.std(quiet_segment[clean_indices], ddof=1)
        else:
            final_bw = np.mean(quiet_segment)
            final_sd = np.std(quiet_segment, ddof=1)
        
        if np.isnan(final_bw) or np.isnan(final_sd) or final_sd == 0:
            quiet_period = int(0.5 * fs)
            return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
        
        # Validacija: 300-1500N za odraslu osobu
        if final_bw < 300 or final_bw > 1500:
            quiet_period = int(0.5 * fs)
            return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)
        
        return final_bw, final_sd
    except:
        quiet_period = int(0.5 * fs)
        return np.mean(force[:quiet_period]), np.std(force[:quiet_period], ddof=1)


def read_force_file(filepath: Path):
    """Učitaj Force Plate fajl."""
    try:
        fs = CONFIG['SAMPLE_RATE_AMTI']
        
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


def analyze_jump(force, force_L, force_R, fs, jump_type):
    """Analiziraj skok sa NOVOM logikom."""
    
    # A. Filtering
    force = butter_lowpass_filter(force, CONFIG['FILTER_FREQ'], fs, CONFIG['FILTER_ORDER'])
    
    # B. Nađi apsolutni minimum u celom signalu
    idx_abs_min = np.argmin(force)
    
    # C. Robustniji Body Weight
    bw, bw_sd = calculate_body_weight_robust(force, fs, idx_abs_min)
    bm = bw / CONFIG['GRAVITY']
    
    # D. Nađi pike oko minimuma
    if idx_abs_min > 0:
        left_segment = force[:idx_abs_min]
        propulsion_peak_abs = np.argmax(left_segment) if len(left_segment) > 0 else 0
    else:
        propulsion_peak_abs = 0
    
    if idx_abs_min < len(force) - 1:
        right_segment = force[idx_abs_min + 1:]
        landing_peak_abs = idx_abs_min + 1 + np.argmax(right_segment) if len(right_segment) > 0 else len(force) - 1
    else:
        landing_peak_abs = len(force) - 1
    
    # Validacija pika
    if not (propulsion_peak_abs < idx_abs_min < landing_peak_abs):
        return None
    
    # Precizna detekcija take-off (F)
    idx_F_abs = propulsion_peak_abs
    for i in range(propulsion_peak_abs, min(len(force), propulsion_peak_abs + int(0.5 * fs))):
        if force[i] < 50.0:
            idx_F_abs = i
            if i + 1 < len(force) and force[i + 1] > 10.0:
                idx_F_abs = i + 1
            break
    
    # Precizna detekcija landing (H)
    idx_H_abs = landing_peak_abs
    for i in range(landing_peak_abs, max(0, landing_peak_abs - int(0.5 * fs)), -1):
        if force[i] < 50.0:
            idx_H_abs = i
            if i - 1 >= 0 and force[i - 1] > 10.0:
                idx_H_abs = i - 1
            break
    
    # Onset (A) - NOVA LOGIKA
    if jump_type == 1:  # SJ
        if idx_abs_min > 0 and idx_abs_min < len(force):
            segment_to_min = force[:idx_abs_min]
            max_before_min_abs = np.argmax(segment_to_min) if len(segment_to_min) > 0 else 0
        else:
            max_before_min_abs = 0
        
        threshold_sj = bw + (5 * bw_sd)
        idx_A_abs = max_before_min_abs
        for i in range(max_before_min_abs, -1, -1):
            if force[i] < threshold_sj:
                idx_A_abs = i
                break
    else:  # CMJ - NOVA LOGIKA
        # Redosled: početak signala (quiet) → onset → unweighting/unloading min → propulsion peak → TO → flight min
        # 1. Apsolutni minimum je već pronađen (idx_abs_min) - to je flight faza
        # 2. Nađi maksimum od početka signala do minimuma (propulsion peak)
        # 3. Nađi minimum između početka i propulsion peak-a (unweighting/unloading minimum)
        # 4. Od unweighting/unloading minimuma idi unazad (ka početku) i nađi prvu tačku gde je F >= BW - 5*SD
        
        # Korak 2: Nađi maksimum od početka do minimuma (propulsion peak)
        if idx_abs_min > 0 and idx_abs_min < len(force):
            segment_to_min = force[:idx_abs_min]
            if len(segment_to_min) > 0:
                propulsion_peak_abs = np.argmax(segment_to_min)
            else:
                propulsion_peak_abs = 0
        else:
            propulsion_peak_abs = 0
        
        # Korak 3: Nađi minimum između početka i propulsion peak-a (unweighting/unloading minimum)
        if propulsion_peak_abs > 0:
            segment_to_peak = force[:propulsion_peak_abs]
            if len(segment_to_peak) > 0:
                unweighting_min_abs = np.argmin(segment_to_peak)
            else:
                unweighting_min_abs = 0
        else:
            unweighting_min_abs = 0
        
        # Korak 4: Od unweighting/unloading minimuma idi unazad (ka početku signala)
        # i nađi prvu tačku gde je F >= BW - 5*SD
        threshold_cmj = bw - (5 * bw_sd)
        idx_A_abs = unweighting_min_abs  # Počni od unweighting/unloading minimuma
        
        # Traži unazad od unweighting/unloading minimuma do početka signala
        for i in range(unweighting_min_abs, -1, -1):
            if force[i] >= threshold_cmj:
                idx_A_abs = i
                break
        
        # Ako nismo našli, koristi početak signala
        if idx_A_abs == unweighting_min_abs:
            idx_A_abs = 0
    
    # E. Cropping
    pad_pre, pad_post = 1000, 1500
    start_crop = max(0, idx_A_abs - pad_pre)
    end_crop = min(len(force), idx_H_abs + pad_post)
    
    f_crop = force[start_crop:end_crop]
    t_crop = np.arange(len(f_crop)) / fs
    
    # Prilagodi indekse
    idx = {}
    idx['A'] = idx_A_abs - start_crop
    idx['F'] = idx_F_abs - start_crop
    idx['H'] = idx_H_abs - start_crop
    idx['min'] = idx_abs_min - start_crop
    idx['propulsion_peak'] = propulsion_peak_abs - start_crop
    idx['landing_peak'] = landing_peak_abs - start_crop
    
    # Dodatne karakteristične tačke za CMJ
    if jump_type != 1:  # CMJ
        if 'unweighting_min_abs' in locals() and unweighting_min_abs is not None:
            idx['unweighting_min'] = unweighting_min_abs - start_crop
        else:
            idx['unweighting_min'] = idx['A']  # Fallback
    else:
        idx['unweighting_min'] = idx['A']  # Za SJ nema unweighting min
    
    # Integration
    acc = (f_crop - bw) / bm
    vel = cumulative_trapezoid(acc, t_crop, initial=0)
    if idx['A'] < len(vel):
        vel = vel - vel[idx['A']]
    
    # Drift Correction
    if CONFIG.get('CORRECT_DRIFT', True):
        landing_buffer = int(CONFIG.get('DRIFT_ZERO_PERIOD', 0.5) * fs)
        if idx['H'] + landing_buffer < len(vel):
            v_landing_observed = np.mean(vel[idx['H']:idx['H'] + landing_buffer])
            duration = t_crop[idx['H']] - t_crop[idx['A']] if idx['H'] > idx['A'] else t_crop[-1] - t_crop[idx['A']]
            if duration > 0 and abs(v_landing_observed) < 10.0:
                drift_slope = v_landing_observed / duration
                correction = np.zeros_like(vel)
                correction[idx['A']:] = drift_slope * (t_crop[idx['A']:] - t_crop[idx['A']])
                vel = vel - correction
    
    disp = cumulative_trapezoid(vel, t_crop, initial=0)
    if idx['A'] < len(disp):
        disp = disp - disp[idx['A']]
    
    # Phase Landmarks
    slice_end = idx['F']
    if idx['A'] < slice_end and slice_end <= len(vel):
        vel_segment = vel[idx['A']:slice_end]
        idx['E'] = idx['A'] + np.argmax(vel_segment) if len(vel_segment) > 0 else idx['A']
    else:
        idx['E'] = idx['A']
    
    if jump_type != 1:  # CMJ
        if idx['E'] > idx['A']:
            idx['C'] = idx['A'] + np.argmin(vel[idx['A']:idx['E']])
        else:
            idx['C'] = idx['A']
        vel_search = vel[idx['C']:idx['E']]
        zc = np.where(np.diff(np.sign(vel_search)) > 0)[0]
        idx['D'] = idx['C'] + zc[0] if len(zc) > 0 else idx['C']
    else:  # SJ
        idx['C'] = idx['A']
        idx['D'] = idx['A']
    
    # Dodatne karakteristične tačke
    idx['vmax'] = idx['A'] + np.argmax(vel[idx['A']:idx['F']]) if idx['F'] > idx['A'] and idx['F'] <= len(vel) else idx['A']
    idx['vmin'] = idx['A'] + np.argmin(vel[idx['A']:idx['F']]) if idx['F'] > idx['A'] and idx['F'] <= len(vel) else idx['A']
    idx['hmin'] = idx['A'] + np.argmin(disp[idx['A']:idx['F']]) if idx['F'] > idx['A'] and idx['F'] <= len(disp) else idx['A']
    
    return {
        't': t_crop,
        'acc': acc,
        'vel': vel,
        'disp': disp,
        'force': f_crop,
        'idx': idx,
        'bw': bw,
        'bm': bm
    }


def plot_jump(filepath: Path, output_dir: Path, jump_type: int):
    """Kreiraj plot za jedan skok."""
    
    force, force_L, force_R, fs = read_force_file(filepath)
    if force is None:
        return False
    
    result = analyze_jump(force, force_L, force_R, fs, jump_type)
    if result is None:
        return False
    
    t = result['t']
    acc = result['acc']
    vel = result['vel']
    idx = result['idx']
    
    # Kreiraj plot
    fig, ax1 = plt.subplots(figsize=(14, 8))
    
    # Leva Y osa - ubrzanje
    color_acc = 'tab:blue'
    ax1.set_xlabel('Vreme (s)', fontsize=12)
    ax1.set_ylabel('Vertikalno ubrzanje (m/s²)', color=color_acc, fontsize=12)
    line1 = ax1.plot(t, acc, color=color_acc, linewidth=1.5, label='az(t)', alpha=0.7)
    ax1.tick_params(axis='y', labelcolor=color_acc)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
    
    # Desna Y osa - brzina
    ax2 = ax1.twinx()
    color_vel = 'tab:red'
    ax2.set_ylabel('Vertikalna brzina (m/s)', color=color_vel, fontsize=12)
    line2 = ax2.plot(t, vel, color=color_vel, linewidth=1.5, label='vz(t)', alpha=0.7)
    ax2.tick_params(axis='y', labelcolor=color_vel)
    ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
    
    # Obeleži karakteristične tačke
    markers = {
        'START (A)': (idx['A'], 'green', 'o', 8),
        'vmin': (idx['vmin'], 'purple', 's', 7),
        'vmax': (idx['vmax'], 'orange', '^', 8),
        'TO (F)': (idx['F'], 'red', 'D', 10),
        'LAND (H)': (idx['H'], 'brown', 'X', 10),
        'hmin': (idx['hmin'], 'darkblue', '*', 8),
        'Prop Peak': (idx['propulsion_peak'], 'darkgreen', '^', 9),
        'Flight Min': (idx['min'], 'navy', 'v', 9),
    }
    
    # Dodaj C i D za CMJ
    if jump_type != 1:
        markers['C'] = (idx['C'], 'cyan', 'v', 7)
        markers['D'] = (idx['D'], 'magenta', 'p', 7)
        if 'unweighting_min' in idx:
            markers['Unw Min'] = (idx['unweighting_min'], 'teal', 's', 8)
    
    for label, (i, color, marker, size) in markers.items():
        if 0 <= i < len(t):
            # Ubrzanje na levoj osi
            ax1.plot(t[i], acc[i], color=color, marker=marker, markersize=size, 
                    markeredgewidth=2, markeredgecolor='black', label=f'{label} (az={acc[i]:.2f})')
            # Brzina na desnoj osi
            ax2.plot(t[i], vel[i], color=color, marker=marker, markersize=size, 
                    markeredgewidth=2, markeredgecolor='black', label=f'{label} (vz={vel[i]:.2f})')
    
    # Dodaj vrednosti na tačkama (samo za glavne tačke da ne bude previše)
    main_markers = ['START (A)', 'TO (F)', 'LAND (H)', 'vmax']
    if jump_type != 1:
        main_markers.extend(['Unw Min', 'Prop Peak'])
    
    for label, (i, color, marker, size) in markers.items():
        if 0 <= i < len(t) and label in main_markers:
            # Anotacija za brzinu (desna osa)
            ax2.annotate(f'{label}\nvz={vel[i]:.3f}', 
                        xy=(t[i], vel[i]), 
                        xytext=(10, 10), 
                        textcoords='offset points',
                        fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', lw=1))
    
    # Legenda
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
    
    # Naslov
    jump_name = 'SJ' if jump_type == 1 else 'CMJ'
    filename = filepath.stem
    vto = vel[idx['F']] if idx['F'] < len(vel) else 0
    vmax_val = vel[idx['vmax']] if idx['vmax'] < len(vel) else 0
    plt.title(f'{jump_name} - {filename}\n'
              f'START={t[idx["A"]]:.3f}s, TO={t[idx["F"]]:.3f}s (vTO={vto:.3f}m/s), '
              f'LAND={t[idx["H"]]:.3f}s, vmax={vmax_val:.3f}m/s @ {t[idx["vmax"]]:.3f}s',
              fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    
    # Sačuvaj plot
    output_file = output_dir / f'{filename}_plot.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    return True


def main():
    base_path = Path(__file__).parent
    
    # Input folderi
    sj_fp_dir = base_path.parent / "SJ_Force_Plate"
    cmj_fp_dir = base_path.parent / "CMJ_Force_Plate"
    
    # Ako ne postoje na tom mestu, probaj alternativne putanje
    if not sj_fp_dir.exists():
        sj_fp_dir = Path(r"C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI\SJ_ForcePlates")
    if not cmj_fp_dir.exists():
        cmj_fp_dir = Path(r"C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI\CMJ_ForcePlates")
    
    # Output folderi
    sj_plot_dir = base_path / "Output" / "Plots" / "SJ_FP"
    cmj_plot_dir = base_path / "Output" / "Plots" / "CMJ_FP"
    
    sj_plot_dir.mkdir(parents=True, exist_ok=True)
    cmj_plot_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 90)
    print("PLOTOVANJE FORCE PLATE SKOKOVA - NOVA LOGIKA")
    print("=" * 90)
    
    # SJ
    print(f"\n[SJ] Obrada fajlova iz: {sj_fp_dir}")
    sj_files = list(sj_fp_dir.glob("*.txt"))
    print(f"Pronađeno {len(sj_files)} fajlova")
    
    success_sj = 0
    for i, filepath in enumerate(sj_files, 1):
        if plot_jump(filepath, sj_plot_dir, jump_type=1):
            success_sj += 1
        if i % 10 == 0:
            print(f"  Obradjeno {i}/{len(sj_files)}...")
    
    print(f"[OK] SJ: {success_sj}/{len(sj_files)} plotova kreirano")
    print(f"     Output: {sj_plot_dir}")
    
    # CMJ
    print(f"\n[CMJ] Obrada fajlova iz: {cmj_fp_dir}")
    cmj_files = list(cmj_fp_dir.glob("*.txt"))
    print(f"Pronađeno {len(cmj_files)} fajlova")
    
    success_cmj = 0
    for i, filepath in enumerate(cmj_files, 1):
        if plot_jump(filepath, cmj_plot_dir, jump_type=2):
            success_cmj += 1
        if i % 10 == 0:
            print(f"  Obradjeno {i}/{len(cmj_files)}...")
    
    print(f"[OK] CMJ: {success_cmj}/{len(cmj_files)} plotova kreirano")
    print(f"     Output: {cmj_plot_dir}")
    
    print("\n" + "=" * 90)
    print("ZAVRSENO")
    print("=" * 90)
    print(f"Ukupno kreirano plotova: {success_sj + success_cmj}")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
