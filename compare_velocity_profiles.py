#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UPOREDNI PLOTOVI BRZINE - QUALISYS vs FORCE PLATE
==================================================
Poravnava profile brzine po piku brzine i prikazuje 1.5s pre i 1.5s posle pika.
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt
from scipy.stats import pearsonr
import re

# Import funkcije iz calculate_fp_kpis.py
sys.path.insert(0, str(Path(__file__).parent))
from calculate_fp_kpis import (
    read_force_file, calculate_body_weight_robust,
    butter_lowpass_filter, CONFIG, analyze_jump
)

# Import funkcije za Qualisys
sys.path.insert(0, r"C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI")
try:
    import config as qualisys_config
except:
    qualisys_config = type('obj', (object,), {'FS_DEFAULT': 300.0})()


def read_qualisys_tsv(filepath: Path, filter_position=False):
    """Učitaj Qualisys TSV fajl i izračunaj brzinu iz CoM3D_Z.
    
    Args:
        filter_position: Ako je True, filtrira poziciju pre izračunavanja brzine.
                        Ako je False, koristi nefiltriranu poziciju.
    """
    try:
        # Pročitaj header
        header_lines = []
        data_start_idx = None
        
        with filepath.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                stripped = line.rstrip("\n\r")
                header_lines.append(stripped)
                if line.startswith("Frame\tTime\t"):
                    data_start_idx = i
                    break
        
        if data_start_idx is None:
            return None, None, None
        
        # Pročitaj DataFrame
        df = pd.read_csv(filepath, sep="\t", skiprows=data_start_idx, header=0)
        
        # Pročitaj FREQUENCY iz header-a
        fs = 300.0  # Default
        for line in header_lines:
            if line.startswith("FREQUENCY"):
                try:
                    fs = float(line.split("\t")[1])
                except:
                    pass
        
        # Proveri da li postoje CoM kolone
        if 'CoM3D_Z' not in df.columns:
            return None, None, None
        
        # Učitaj vreme i poziciju
        time = df['Time'].values
        com_z = df['CoM3D_Z'].values
        
        # Opciono filtriranje pozicije
        if filter_position:
            from scipy.signal import butter, filtfilt
            # Butterworth lowpass filter (ako je potrebno)
            # Za sada, ne filtriramo jer korisnik želi nefiltriranu verziju
            pass
        
        # Izračunaj brzinu (vertikalna brzina) - direktno iz pozicije
        dt = 1.0 / fs
        velocity = np.gradient(com_z, dt)
        
        return time, velocity, fs
    
    except Exception as e:
        print(f"[ERROR] Greška pri čitanju {filepath.name}: {e}")
        return None, None, None


def get_fp_velocity_direct(force, force_L, force_R, fs, jump_type, use_filter=True):
    """Direktno izračunaj brzinu iz Force Plate podataka (bez pozivanja analyze_jump).
    
    Args:
        use_filter: Ako je True, koristi filtriranu silu. Ako je False, koristi nefiltriranu silu.
    """
    try:
        # Filtering (opciono)
        force_original = force.copy()
        if use_filter:
            force = butter_lowpass_filter(force, CONFIG['FILTER_FREQ'], fs, CONFIG['FILTER_ORDER'])
        
        # Nađi apsolutni minimum
        idx_abs_min = np.argmin(force)
        
        # Body Weight
        bw, bw_sd = calculate_body_weight_robust(force, fs, idx_abs_min)
        bm = bw / CONFIG['GRAVITY']
        
        # Detekcija događaja (pojednostavljena verzija)
        # Nađi pike oko minimuma
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
        
        # Detekcija TO i LAND (pojednostavljena)
        idx_F_abs = propulsion_peak_abs
        for i in range(propulsion_peak_abs, min(len(force), propulsion_peak_abs + int(0.5 * fs))):
            if force[i] < 50.0:
                idx_F_abs = i
                if i + 1 < len(force) and force[i + 1] > 10.0:
                    idx_F_abs = i + 1
                break
        
        idx_H_abs = landing_peak_abs
        for i in range(landing_peak_abs, max(0, landing_peak_abs - int(0.5 * fs)), -1):
            if force[i] < 50.0:
                idx_H_abs = i
                if i - 1 >= 0 and force[i - 1] > 10.0:
                    idx_H_abs = i - 1
                break
        
        # Onset detekcija - Sinhronizovano sa calculate_fp_kpis.py (CMJ pristup za SJ sa CM)
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
            
            # NOVA LOGIKA: Detekcija countermovement-a koristeći CMJ pristup
            # Ako postoji countermovement, postoji unweighting minimum (kao u CMJ)
            cm_threshold = bw - (5 * bw_sd)  # 5*SD jer je SD mali ako je BW dobro određen
            min_stable_period = int(0.5 * fs)
            
            if max_before_min_abs > min_stable_period:
                segment_before_max = force[min_stable_period:max_before_min_abs]
                cm_indices = np.where(segment_before_max < cm_threshold)[0]
                
                if len(cm_indices) > 0:
                    # Postoji countermovement - koristi CMJ logiku
                    # Nađi unweighting minimum između početka i maksimuma
                    if max_before_min_abs > min_stable_period:
                        segment_to_max = force[min_stable_period:max_before_min_abs]
                        if len(segment_to_max) > 0:
                            unweighting_min_rel = np.argmin(segment_to_max)
                            unweighting_min_abs = unweighting_min_rel + min_stable_period
                        else:
                            unweighting_min_abs = min_stable_period
                    else:
                        unweighting_min_abs = min_stable_period
                    
                    # Od unweighting minimuma idi unazad i nađi prvu tačku gde je F >= BW - 5*SD
                    threshold_cmj = bw - (5 * bw_sd)
                    idx_A_abs = unweighting_min_abs
                    for i in range(unweighting_min_abs, -1, -1):
                        if force[i] >= threshold_cmj:
                            idx_A_abs = i
                            break
                    
                    if idx_A_abs == unweighting_min_abs:
                        idx_A_abs = max(0, min_stable_period)
        else:  # CMJ
            if idx_abs_min > 0 and idx_abs_min < len(force):
                segment_to_min = force[:idx_abs_min]
                propulsion_peak_abs = np.argmax(segment_to_min) if len(segment_to_min) > 0 else 0
            else:
                propulsion_peak_abs = 0
            
            if propulsion_peak_abs > 0:
                segment_to_peak = force[:propulsion_peak_abs]
                unweighting_min_abs = np.argmin(segment_to_peak) if len(segment_to_peak) > 0 else 0
            else:
                unweighting_min_abs = 0
            
            threshold_cmj = bw - (5 * bw_sd)
            idx_A_abs = unweighting_min_abs
            for i in range(unweighting_min_abs, -1, -1):
                if force[i] >= threshold_cmj:
                    idx_A_abs = i
                    break
            if idx_A_abs == unweighting_min_abs:
                idx_A_abs = 0
        
        # Cropping
        pad_pre, pad_post = 1000, 1500
        start_crop = max(0, idx_A_abs - pad_pre)
        end_crop = min(len(force), idx_H_abs + pad_post)
        
        f_crop = force[start_crop:end_crop]
        t_crop = np.arange(len(f_crop)) / fs
        
        idx_A_crop = idx_A_abs - start_crop
        
        # Integracija
        acc = (f_crop - bw) / bm
        
        # Velocity
        # Proveri da li postoji countermovement (proveri da li je sila padla ispod BW-5*SD pre maksimuma)
        has_cm = False
        if jump_type == 1 and max_before_min_abs > min_stable_period:
            segment_before_max = force[min_stable_period:max_before_min_abs]
            cm_indices = np.where(segment_before_max < (bw - 5 * bw_sd))[0]  # 5*SD jer je SD mali ako je BW dobro određen
            has_cm = len(cm_indices) > 0
        
        if jump_type == 1 and has_cm and idx_A_crop > 0:
            # Za SJ SA COUNTERMOVEMENT-OM: integracija počinje direktno od onset-a
            acc_segment = acc[idx_A_crop:]
            t_segment = t_crop[idx_A_crop:] - t_crop[idx_A_crop]
            if len(acc_segment) > 0 and len(t_segment) > 0:
                vel_segment = cumulative_trapezoid(acc_segment, t_segment, initial=0)
                vel = np.zeros_like(acc)
                vel[idx_A_crop:] = vel_segment
                # EKSPLICITNO: Osiguraj da je brzina na onset-u tačno 0
                if idx_A_crop >= 0 and idx_A_crop < len(vel):
                    vel[idx_A_crop] = 0.0
            else:
                vel = cumulative_trapezoid(acc, t_crop, initial=0)
                if idx_A_crop >= 0 and idx_A_crop < len(vel):
                    vel = vel - vel[idx_A_crop]
                    vel[idx_A_crop] = 0.0
        else:
            # Za CMJ ili SJ BEZ countermovement-a: standardna integracija
            vel = cumulative_trapezoid(acc, t_crop, initial=0)
            if idx_A_crop >= 0 and idx_A_crop < len(vel):
                vel = vel - vel[idx_A_crop]
                vel[idx_A_crop] = 0.0  # Eksplicitno postavi na 0
        
        # Drift correction (pojednostavljena)
        # VAŽNO: Osiguraj da brzina na onset-u ostane 0 i posle drift correction
        if CONFIG.get('CORRECT_DRIFT', True):
            landing_buffer = int(CONFIG.get('DRIFT_ZERO_PERIOD', 0.5) * fs)
            idx_H_crop = idx_H_abs - start_crop
            if idx_H_crop + landing_buffer < len(vel):
                v_landing_observed = np.mean(vel[idx_H_crop:idx_H_crop + landing_buffer])
                duration = t_crop[idx_H_crop] - t_crop[idx_A_crop] if idx_H_crop > idx_A_crop else t_crop[-1] - t_crop[idx_A_crop]
                if duration > 0 and abs(v_landing_observed) < 10.0:
                    drift_slope = v_landing_observed / duration
                    correction = np.zeros_like(vel)
                    correction[idx_A_crop:] = drift_slope * (t_crop[idx_A_crop:] - t_crop[idx_A_crop])
                    vel = vel - correction
                    # EKSPLICITNO: Osiguraj da je brzina na onset-u tačno 0 i posle drift correction
                    if idx_A_crop >= 0 and idx_A_crop < len(vel):
                        vel[idx_A_crop] = 0.0
        
        return t_crop, vel, fs, idx_A_crop, start_crop
    
    except Exception as e:
        print(f"[ERROR] Greška pri obradi FP: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def get_fp_velocity(filepath: Path, jump_type: int, use_filter=True):
    """Izračunaj brzinu iz Force Plate podataka.
    
    Args:
        use_filter: Ako je True, koristi filtriranu silu. Ako je False, koristi nefiltriranu silu.
    """
    try:
        force_L, force_R = read_force_file(filepath)
        if force_L is None or len(force_L) == 0:
            return None, None, None, None, None
        
        force = force_L + force_R
        fs = CONFIG['SAMPLE_RATE_AMTI']
        
        # Koristi direktnu funkciju za izračunavanje brzine
        return get_fp_velocity_direct(force, force_L, force_R, fs, jump_type, use_filter=use_filter)
    
    except Exception as e:
        print(f"[ERROR] Greška pri obradi FP {filepath.name}: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None


def find_velocity_peak(time, velocity):
    """Pronađi pik brzine (maksimum pozitivne brzine)."""
    if len(velocity) == 0:
        return None, None
    
    # Pronađi maksimum pozitivne brzine
    positive_mask = velocity > 0
    if np.sum(positive_mask) == 0:
        return None, None
    
    positive_vel = velocity.copy()
    positive_vel[~positive_mask] = -np.inf
    
    peak_idx = np.argmax(positive_vel)
    peak_time = time[peak_idx]
    peak_velocity = velocity[peak_idx]
    
    return peak_idx, peak_time


def find_velocity_onset_original(time, velocity, fs):
    """Pronađi početak kretanja u ORIGINALNOM signalu (gde brzina počinje da se menja od nule).
    
    Traži gde brzina počinje da se menja od nule u originalnom signalu.
    Ovo je onset - tačka gde brzina = 0 i počinje da se menja.
    """
    if len(velocity) == 0:
        return None, None
    
    # Pronađi period stabilnosti na početku (brzina blizu 0)
    # Traži prvih 0.5s gde je brzina blizu 0
    stable_period = int(0.5 * fs)
    if len(velocity) < stable_period:
        stable_period = len(velocity) // 2
    
    if stable_period == 0:
        return 0, time[0] if len(time) > 0 else None
    
    # Izračunaj SD brzine u stabilnom periodu
    stable_vel = velocity[:stable_period]
    vel_mean = np.mean(stable_vel)
    vel_sd = np.std(stable_vel)
    
    # Threshold: brzina počinje da se menja kada pređe 3*SD ili 0.1 m/s (što je veće)
    threshold = max(abs(vel_mean) + (3 * vel_sd), 0.1)
    
    # Traži prvu tačku gde brzina pređe threshold (u bilo kom pravcu)
    # Zatim traži unazad da nađeš poslednju tačku gde je brzina blizu nule (to je početak)
    for i in range(stable_period, len(velocity)):
        if abs(velocity[i] - vel_mean) > threshold:
            # Pronađi poslednju tačku PRE ove gde je brzina blizu nule
            # (to je pravi početak - gde brzina počinje da se menja)
            for j in range(i - 1, max(0, i - int(0.2 * fs)), -1):
                if abs(velocity[j] - vel_mean) <= threshold * 0.3:  # Blizu nule
                    onset_idx = j
                    onset_time = time[j]
                    return onset_idx, onset_time
            # Ako nismo našli, koristi tačku pre promene
            if i > 0:
                onset_idx = i - 1
                onset_time = time[i - 1]
                return onset_idx, onset_time
    
    # Fallback: ako nismo našli promenu, koristi prvi sample
    return 0, time[0] if len(time) > 0 else None


def align_and_crop(time, velocity, peak_idx, peak_time, fs, window_before=1.5, window_after=1.5):
    """Poravnaj signal po piku brzine i cropuj window_before pre i window_after posle."""
    if peak_idx is None:
        return None, None
    
    # Indeksi za cropovanje
    samples_before = int(window_before * fs)
    samples_after = int(window_after * fs)
    
    start_idx = max(0, peak_idx - samples_before)
    end_idx = min(len(velocity), peak_idx + samples_after + 1)
    
    # Cropuj signale
    time_crop = time[start_idx:end_idx] - peak_time  # Relativno vreme (pik je na 0)
    vel_crop = velocity[start_idx:end_idx]
    
    return time_crop, vel_crop


def parse_filename(filename: str):
    """Parsira ime fajla u formatu: "##_#_#.tsv" ili "##_#_#.txt"."""
    basename = Path(filename).stem
    pattern = r'^(\d+)_(\d+)_(\d+)$'
    match = re.match(pattern, basename)
    
    if not match:
        return None
    
    subject_id = match.group(1)
    jump_type_code = int(match.group(2))
    trial_no = int(match.group(3))
    
    # Mapiranje: 3 = SJ, 4 = CMJ
    jump_type = 1 if jump_type_code == 3 else 2
    
    return {
        'SubjectID': subject_id,
        'TrialNo': trial_no,
        'JumpType': jump_type,
        'JumpTypeCode': jump_type_code
    }


def plot_velocity_comparison(qualisys_file: Path, fp_file: Path, output_dir: Path):
    """Kreiraj uporedni plot brzine za jedan par fajlova."""
    
    # Parsiraj imena fajlova
    q_info = parse_filename(qualisys_file.name)
    fp_info = parse_filename(fp_file.name)
    
    if q_info is None or fp_info is None:
        return False
    
    if q_info['SubjectID'] != fp_info['SubjectID'] or q_info['TrialNo'] != fp_info['TrialNo']:
        return False
    
    jump_type = q_info['JumpType']
    jump_name = 'SJ' if jump_type == 1 else 'CMJ'
    
    # Učitaj Qualisys brzinu
    t_q, vel_q, fs_q = read_qualisys_tsv(qualisys_file)
    if t_q is None or vel_q is None:
        return False
    
    # Učitaj Qualisys poziciju direktno za nefiltriranu brzinu
    # (za poređenje sa eventualno filtriranom verzijom)
    vel_q_unfiltered = None
    vel_q_from_unfiltered_markers = None
    
    try:
        header_lines_q = []
        data_start_idx_q = None
        with qualisys_file.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                stripped = line.rstrip("\n\r")
                header_lines_q.append(stripped)
                if line.startswith("Frame\tTime\t"):
                    data_start_idx_q = i
                    break
        
        if data_start_idx_q is not None:
            df_q_raw = pd.read_csv(qualisys_file, sep="\t", skiprows=data_start_idx_q, header=0)
            
            # 1. Brzina iz postojećeg CoM3D_Z (koji je možda izračunat iz filtriranih marker-a)
            if 'CoM3D_Z' in df_q_raw.columns:
                com_z_q_raw = df_q_raw['CoM3D_Z'].values
                # Izračunaj brzinu direktno iz nefiltrirane pozicije (bez ikakvog filtriranja)
                dt_q_raw = 1.0 / fs_q
                vel_q_unfiltered = np.gradient(com_z_q_raw, dt_q_raw)
            
            # 2. Izračunaj CoM direktno iz NEFILTRIRANIH marker pozicija
            # Pokušaj da importuje modul za izračunavanje CoM-a
            try:
                import sys
                sys.path.insert(0, r"C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI")
                from mocap_com_v2_sexmap import add_com_columns, parse_subject_id_from_filename
                
                # Ekstraktuj SubjectID iz imena fajla
                subject_id = parse_subject_id_from_filename(qualisys_file.name)
                
                # Izračunaj CoM iz nefiltriranih marker pozicija (bez filtriranja marker-a)
                # add_com_columns koristi raw marker pozicije iz df_raw
                df_with_com_unfiltered, qc_unf = add_com_columns(
                    df_raw=df_q_raw,
                    subject_id=subject_id,
                    default_sex_if_unknown="male",
                    auto_units=True,
                )
                
                if 'CoM3D_Z' in df_with_com_unfiltered.columns:
                    com_z_unfiltered_markers = df_with_com_unfiltered['CoM3D_Z'].values
                    # Izračunaj brzinu iz CoM-a izračunatog iz nefiltriranih marker-a
                    dt_q_unf = 1.0 / fs_q
                    vel_q_from_unfiltered_markers = np.gradient(com_z_unfiltered_markers, dt_q_unf)
                    print(f"  [INFO] CoM izračunat iz nefiltriranih marker pozicija")
            except ImportError as e:
                print(f"  [WARNING] Neuspešan import mocap_com_v2_sexmap: {e}")
                vel_q_from_unfiltered_markers = None
            except Exception as e:
                print(f"  [WARNING] Neuspešno izračunavanje CoM iz nefiltriranih marker-a: {e}")
                vel_q_from_unfiltered_markers = None
                
    except Exception as e:
        print(f"  [WARNING] Neuspešno učitavanje nefiltrirane Qualisys brzine: {e}")
        vel_q_unfiltered = None
        vel_q_from_unfiltered_markers = None
    
    # Učitaj Force Plate brzinu (filtrirana)
    t_fp, vel_fp, fs_fp, idx_A_crop_fp, start_crop_fp = get_fp_velocity(fp_file, jump_type, use_filter=True)
    if t_fp is None or vel_fp is None:
        return False
    
    # Učitaj Force Plate brzinu (NEFILTRIRANA) za poređenje
    t_fp_unfiltered, vel_fp_unfiltered, fs_fp_unf, _, _ = get_fp_velocity(fp_file, jump_type, use_filter=False)
    if t_fp_unfiltered is None or vel_fp_unfiltered is None:
        vel_fp_unfiltered = None  # Ako ne uspe, nastavi bez nefiltrirane verzije
    
    # Pronađi pike brzine
    peak_idx_q, peak_time_q = find_velocity_peak(t_q, vel_q)
    peak_idx_fp, peak_time_fp = find_velocity_peak(t_fp, vel_fp)
    
    if peak_idx_q is None or peak_idx_fp is None:
        return False
    
    # VAŽNO: Prvo nađi onset u ORIGINALNIM signalima (gde je brzina = 0)
    # Zatim izračunaj relativno vreme u odnosu na pik brzine
    
    # Za Qualisys: nađi onset u originalnom signalu (gde brzina počinje da se menja od nule)
    onset_idx_q, onset_time_q = find_velocity_onset_original(t_q, vel_q, fs_q)
    
    # Za Force Plate: koristimo ISTU LOGIKU - nađi onset u originalnom signalu brzine
    # (gde brzina počinje da se menja od nule)
    onset_idx_fp, onset_time_fp = find_velocity_onset_original(t_fp, vel_fp, fs_fp)
    
    # Poravnaj i cropuj signale po piku brzine (za poređenje)
    t_q_aligned, vel_q_aligned = align_and_crop(t_q, vel_q, peak_idx_q, peak_time_q, fs_q)
    t_fp_aligned, vel_fp_aligned = align_and_crop(t_fp, vel_fp, peak_idx_fp, peak_time_fp, fs_fp)
    
    if t_q_aligned is None or t_fp_aligned is None:
        return False
    
    # Izračunaj RELATIVNO vreme onset-a u odnosu na pik brzine
    # Onset u originalnom signalu minus pik brzine u originalnom signalu = relativno vreme u poravnatom signalu
    onset_rel_q = None
    onset_rel_fp = None
    
    if onset_time_q is not None:
        onset_rel_q = onset_time_q - peak_time_q  # Negativno vreme (npr. -0.4s)
    
    if onset_time_fp is not None:
        onset_rel_fp = onset_time_fp - peak_time_fp  # Negativno vreme (npr. -0.4s)
    
    # Interpolacija za bolje poređenje (resample na istu frekvenciju)
    # Koristi nižu frekvenciju za resampling
    target_fs = min(fs_q, fs_fp)
    target_dt = 1.0 / target_fs
    
    # Kreiraj zajednički vremenski vektor
    t_min = min(t_q_aligned[0], t_fp_aligned[0])
    t_max = max(t_q_aligned[-1], t_fp_aligned[-1])
    t_common = np.arange(t_min, t_max + target_dt, target_dt)
    
    # Interpoliraj oba signala na zajednički vremenski vektor
    from scipy.interpolate import interp1d
    
    vel_q_interp = interp1d(t_q_aligned, vel_q_aligned, kind='linear', 
                           bounds_error=False, fill_value=np.nan)(t_common)
    vel_fp_interp = interp1d(t_fp_aligned, vel_fp_aligned, kind='linear',
                            bounds_error=False, fill_value=np.nan)(t_common)
    
    # Ukloni NaN vrednosti
    valid_mask = ~(np.isnan(vel_q_interp) | np.isnan(vel_fp_interp))
    t_common = t_common[valid_mask]
    vel_q_interp = vel_q_interp[valid_mask]
    vel_fp_interp = vel_fp_interp[valid_mask]
    
    if len(t_common) < 10:
        return False
    
    # Izračunaj korelaciju
    if len(vel_q_interp) > 2 and len(vel_fp_interp) > 2:
        r, p = pearsonr(vel_q_interp, vel_fp_interp)
    else:
        r, p = 0, 1
    
    # Kreiraj plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot Qualisys brzine (standardna - iz nefiltrirane pozicije)
    ax.plot(t_q_aligned, vel_q_aligned, 'b-', linewidth=2, label=f'Qualisys (vmax={vel_q[peak_idx_q]:.3f} m/s)', alpha=0.7)
    
    # Plot Qualisys brzine NEFILTRIRANE (direktno iz nefiltrirane pozicije, bez ikakvog filtriranja)
    if vel_q_unfiltered is not None:
        # Poravnaj po piku brzine
        peak_idx_q_unf, peak_time_q_unf = find_velocity_peak(t_q, vel_q_unfiltered)
        if peak_idx_q_unf is not None:
            t_q_unf_aligned, vel_q_unf_aligned = align_and_crop(t_q, vel_q_unfiltered, peak_idx_q_unf, peak_time_q_unf, fs_q)
            if t_q_unf_aligned is not None:
                ax.plot(t_q_unf_aligned, vel_q_unf_aligned, 'b--', linewidth=1.5, label=f'Qualisys unfiltered CoM (vmax={vel_q_unfiltered[peak_idx_q_unf]:.3f} m/s)', alpha=0.6)
    
    # Plot Qualisys brzine iz CoM-a izračunatog iz NEFILTRIRANIH marker pozicija
    if vel_q_from_unfiltered_markers is not None:
        # Poravnaj po piku brzine
        peak_idx_q_unf_markers, peak_time_q_unf_markers = find_velocity_peak(t_q, vel_q_from_unfiltered_markers)
        if peak_idx_q_unf_markers is not None:
            t_q_unf_markers_aligned, vel_q_unf_markers_aligned = align_and_crop(t_q, vel_q_from_unfiltered_markers, peak_idx_q_unf_markers, peak_time_q_unf_markers, fs_q)
            if t_q_unf_markers_aligned is not None:
                ax.plot(t_q_unf_markers_aligned, vel_q_unf_markers_aligned, 'b:', linewidth=1.5, label=f'Qualisys CoM from unfiltered markers (vmax={vel_q_from_unfiltered_markers[peak_idx_q_unf_markers]:.3f} m/s)', alpha=0.6)
    
    # Plot Force Plate brzine (filtrirana)
    ax.plot(t_fp_aligned, vel_fp_aligned, 'r-', linewidth=2, label=f'Force Plate (vmax={vel_fp[peak_idx_fp]:.3f} m/s)', alpha=0.7)
    
    # Obeleži pike brzine
    ax.axvline(x=0, color='green', linestyle='--', linewidth=2, label='Peak Velocity (aligned)')
    ax.plot(0, vel_q[peak_idx_q], 'bo', markersize=10, markeredgecolor='black', markeredgewidth=2)
    ax.plot(0, vel_fp[peak_idx_fp], 'ro', markersize=10, markeredgecolor='black', markeredgewidth=2)
    
    # Obeleži početak kretanja (onset)
    if onset_rel_q is not None:
        # Pronađi najbližu tačku u poravnatom signalu
        onset_idx_q_aligned = np.argmin(np.abs(t_q_aligned - onset_rel_q))
        if 0 <= onset_idx_q_aligned < len(vel_q_aligned):
            ax.axvline(x=onset_rel_q, color='blue', linestyle=':', linewidth=2, alpha=0.7, label=f'Q Onset ({onset_rel_q:.3f}s)')
            ax.plot(onset_rel_q, vel_q_aligned[onset_idx_q_aligned], 'b^', markersize=12, markeredgecolor='black', markeredgewidth=2)
    
    if onset_rel_fp is not None:
        # Pronađi najbližu tačku u poravnatom signalu
        onset_idx_fp_aligned = np.argmin(np.abs(t_fp_aligned - onset_rel_fp))
        if 0 <= onset_idx_fp_aligned < len(vel_fp_aligned):
            ax.axvline(x=onset_rel_fp, color='red', linestyle=':', linewidth=2, alpha=0.7, label=f'FP Onset ({onset_rel_fp:.3f}s)')
            ax.plot(onset_rel_fp, vel_fp_aligned[onset_idx_fp_aligned], 'r^', markersize=12, markeredgecolor='black', markeredgewidth=2)
    
    # Dodaj informacije o početku u title
    onset_info = ""
    if onset_rel_q is not None and onset_rel_fp is not None:
        onset_diff = abs(onset_rel_q - onset_rel_fp)
        onset_info = f" | Onset diff: {onset_diff:.3f}s"
    
    # Formatiranje
    ax.set_xlabel('Vreme relativno na pik brzine (s)', fontsize=12)
    ax.set_ylabel('Vertikalna brzina (m/s)', fontsize=12)
    ax.set_title(f'{jump_name} - {qualisys_file.stem}\n'
                 f'Korelacija: r={r:.3f}, p={p:.4f} | '
                 f'vTO_Q={vel_q[peak_idx_q]:.3f} m/s, vTO_FP={vel_fp[peak_idx_fp]:.3f} m/s{onset_info}',
                 fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    ax.axhline(y=0, color='gray', linestyle=':', linewidth=0.8)
    
    plt.tight_layout()
    
    # Sačuvaj plot sa timestamp-om da se osigura da je novi
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f'{qualisys_file.stem}_velocity_comparison_{timestamp}.png'
    try:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        # Takođe sačuvaj bez timestamp-a za lakši pristup
        output_file_main = output_dir / f'{qualisys_file.stem}_velocity_comparison.png'
        import shutil
        shutil.copy2(output_file, output_file_main)
        # Proveri da li je fajl zaista kreiran
        if output_file.exists() and output_file_main.exists():
            print(f"  [DEBUG] Plot uspešno sačuvan: {output_file_main} (i {output_file})")
            return True
        else:
            print(f"  [ERROR] Plot nije sačuvan na: {output_file_main}")
            return False
    except Exception as e:
        print(f"  [ERROR] Greška pri čuvanju plot-a: {e}")
        import traceback
        traceback.print_exc()
        plt.close()
        return False


def main():
    base_path = Path(__file__).parent
    
    # Input folderi
    sj_qualisys_dir = base_path / "SJ_Qualisys_CoM"
    cmj_qualisys_dir = base_path / "CMJ_Qualisys_CoM"
    
    sj_fp_dir = base_path / "SJ_ForcePlates"
    cmj_fp_dir = base_path / "CMJ_ForcePlates"
    
    # Output folderi
    sj_output_dir = base_path / "Output" / "Velocity_Comparison" / "SJ"
    cmj_output_dir = base_path / "Output" / "Velocity_Comparison" / "CMJ"
    
    sj_output_dir.mkdir(parents=True, exist_ok=True)
    cmj_output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 90)
    print("UPOREDNI PLOTOVI BRZINE - QUALISYS vs FORCE PLATE")
    print("=" * 90)
    
    # TEST: Napravi samo jedan primer za SJ
    print(f"\n[TEST] Kreiranje primer plot-a za SJ...")
    sj_q_files = list(sj_qualisys_dir.glob("*.tsv"))
    sj_fp_files = list(sj_fp_dir.glob("*.txt"))
    
    if len(sj_q_files) > 0 and len(sj_fp_files) > 0:
        # Uzmi prvi par koji se poklapa
        test_q_file = sj_q_files[0]
        test_fp_file = None
        
        for fp_file in sj_fp_files:
            if fp_file.stem == test_q_file.stem:
                test_fp_file = fp_file
                break
        
        if test_fp_file:
            print(f"  Test fajl: {test_q_file.name} <-> {test_fp_file.name}")
            if plot_velocity_comparison(test_q_file, test_fp_file, sj_output_dir):
                print(f"[OK] Primer plot kreiran: {sj_output_dir / (test_q_file.stem + '_velocity_comparison.png')}")
            else:
                print("[ERROR] Neuspešno kreiranje primer plot-a")
        else:
            print(f"[WARNING] Nema odgovarajućeg FP fajla za {test_q_file.name}")
    else:
        print("[ERROR] Nema dostupnih fajlova")
    
    print("\n" + "=" * 90)
    print("TEST ZAVRSEN")
    print("=" * 90)
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
