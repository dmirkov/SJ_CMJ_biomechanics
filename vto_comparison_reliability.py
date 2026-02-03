#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POREĐENJE vTO I POUZDANOST SIGNALA - FP vs QUALISYS
==================================================
1. Korelacije vTO između Force Plate i Qualisys
2. Parametri pouzdanosti na nivou signala brzine (onset → najniža tačka landing-a)
"""

import sys
import re
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import pearsonr, spearmanr
from scipy.interpolate import interp1d
from datetime import datetime
import matplotlib.pyplot as plt

# Import iz calculate_fp_kpis
sys.path.insert(0, str(Path(__file__).parent))
from calculate_fp_kpis import (
    read_force_file, analyze_jump, butter_lowpass_filter,
    calculate_body_weight_robust, CONFIG
)
from scipy.integrate import cumulative_trapezoid

# ICC (Intraclass Correlation) - jednostavna implementacija
try:
    from pingouin import intraclass_corr
    HAS_PINGOUIN = True
except ImportError:
    HAS_PINGOUIN = False


def icc_agreement(x1, x2):
    """ICC(2,1) - two-way random, absolute agreement. x1, x2 su isti trials."""
    n = len(x1)
    if n < 2:
        return np.nan
    x1, x2 = np.asarray(x1), np.asarray(x2)
    m = np.column_stack([x1, x2])
    ms = np.mean(m, axis=1)
    mr = np.mean(m, axis=0)
    gm = np.mean(m)
    ssb = n * np.sum((mr - gm)**2)
    ssw = np.sum((m - mr)**2)
    ssm = np.sum((ms - gm)**2)
    sse = ssw - ssm
    msb = ssb / 1
    mse = sse / (n - 1)
    icc = (msb - mse) / (msb + mse) if (msb + mse) > 0 else np.nan
    return icc


def load_and_merge_data(excel_file: Path):
    """Učitaj i upari podatke iz FP i Qualisys sheetova."""
    merged = {}
    
    for jump_type, jump_name in [('SJ', 'SJ'), ('CMJ', 'CMJ')]:
        fp_sheet = f'{jump_name}_FP'
        q_sheets = [f'{jump_name}3D', f'{jump_name}2DL', f'{jump_name}2DR']
        
        try:
            fp_df = pd.read_excel(excel_file, sheet_name=fp_sheet)
        except Exception as e:
            print(f"  [WARNING] Nema sheet {fp_sheet}: {e}")
            continue
            
        fp_df['TrialID'] = fp_df['SubjectID'].astype(str) + '_' + fp_df['TrialNo'].astype(str)
        merged[jump_type] = {}
        
        for model in ['3D', '2DL', '2DR']:
            q_sheet = f'{jump_name}3D' if model == '3D' else (f'{jump_name}2DL' if model == '2DL' else f'{jump_name}2DR')
            try:
                q_df = pd.read_excel(excel_file, sheet_name=q_sheet)
                q_df['TrialID'] = q_df['SubjectID'].astype(str) + '_' + q_df['TrialNo'].astype(str)
                m = fp_df.merge(q_df[['TrialID', 'vTO']], on='TrialID', how='inner')
                merged[jump_type][model] = m
            except Exception:
                merged[jump_type][model] = pd.DataFrame()
    
    return merged


def calculate_vto_correlations(merged_data: dict):
    """Korelacije vTO FP vs Qualisys."""
    results = {}
    for jump_type in ['SJ', 'CMJ']:
        results[jump_type] = {}
        for model in ['3D', '2DL', '2DR']:
            df = merged_data.get(jump_type, {}).get(model, pd.DataFrame())
            if len(df) < 3:
                results[jump_type][model] = {'n': len(df), 'error': 'Nedovoljno podataka'}
                continue
            
            valid = df['V_Takeoff_ms'].notna() & df['vTO'].notna() & np.isfinite(df['V_Takeoff_ms']) & np.isfinite(df['vTO'])
            dfv = df[valid]
            if len(dfv) < 3:
                results[jump_type][model] = {'n': len(dfv), 'error': 'Nedovoljno validnih'}
                continue
            
            vto_fp, vto_q = dfv['V_Takeoff_ms'].values, dfv['vTO'].values
            r_p, p_p = pearsonr(vto_fp, vto_q)
            r_s, p_s = spearmanr(vto_fp, vto_q)
            
            results[jump_type][model] = {
                'n': len(dfv),
                'pearson_r': r_p, 'pearson_p': p_p,
                'spearman_r': r_s, 'spearman_p': p_s,
                'mae': np.mean(np.abs(vto_fp - vto_q)),
                'rmse': np.sqrt(np.mean((vto_fp - vto_q)**2)),
                'bias': np.mean(vto_fp - vto_q),
                'vto_fp_mean': np.mean(vto_fp), 'vto_fp_std': np.std(vto_fp),
                'vto_q_mean': np.mean(vto_q), 'vto_q_std': np.std(vto_q),
                'df': dfv
            }
    return results


def get_fp_velocity_segment(fp_path: Path, jump_type: int):
    """
    Izračunaj brzinu iz FP i vrati segment: onset → kraj landing faze (H + buffer).
    Returns: (t_rel, vel, idx_A, idx_H) ili None
    """
    raw_L, raw_R = read_force_file(fp_path)
    if raw_L is None or len(raw_L) == 0:
        return None
    
    force = raw_L + raw_R
    fs = CONFIG['SAMPLE_RATE_AMTI']
    force = butter_lowpass_filter(force, CONFIG['FILTER_FREQ'], fs, CONFIG['FILTER_ORDER'])
    
    m = analyze_jump(force, raw_L, raw_R, fs, jump_type, fp_path.stem)
    if m is None:
        return None
    
    # Ponovo izračunaj sa idx - analyze_jump ne vraća idx, pa koristimo get_fp_velocity_direct logiku
    idx_abs_min = np.argmin(force)
    bw, bw_sd = calculate_body_weight_robust(force, fs, idx_abs_min)
    if isinstance(bw, tuple):
        bw = bw[0]
    bm = bw / CONFIG['GRAVITY']
    
    if bw < 300 or bw > 1500:
        return None
    
    # Pike
    if idx_abs_min > 0:
        propulsion_peak_abs = np.argmax(force[:idx_abs_min])
    else:
        propulsion_peak_abs = 0
    if idx_abs_min < len(force) - 1:
        landing_peak_abs = idx_abs_min + 1 + np.argmax(force[idx_abs_min + 1:])
    else:
        landing_peak_abs = len(force) - 1
    
    idx_F_abs = propulsion_peak_abs
    for i in range(propulsion_peak_abs, min(len(force), propulsion_peak_abs + int(0.5 * fs))):
        if force[i] < 50.0:
            idx_F_abs = i
            break
    
    idx_H_abs = landing_peak_abs
    for i in range(landing_peak_abs, max(0, landing_peak_abs - int(0.5 * fs)), -1):
        if force[i] < 50.0:
            idx_H_abs = i
            break
    
    # Onset
    if jump_type == 1:  # SJ
        max_before_min = np.argmax(force[:idx_abs_min]) if idx_abs_min > 0 else 0
        thresh = bw + 5 * bw_sd
        idx_A_abs = max_before_min
        for i in range(max_before_min, -1, -1):
            if force[i] < thresh:
                idx_A_abs = i
                break
    else:  # CMJ
        if propulsion_peak_abs > 0:
            unweight_min = np.argmin(force[:propulsion_peak_abs])
        else:
            unweight_min = 0
        thresh = bw - 5 * bw_sd
        idx_A_abs = unweight_min
        for i in range(unweight_min, -1, -1):
            if force[i] >= thresh:
                idx_A_abs = i
                break
    
    # Crop: onset do landing + 0.3s (najniža tačka landing-a)
    pad_post = int(0.3 * fs)
    start_crop = max(0, idx_A_abs - 100)
    end_crop = min(len(force), idx_H_abs + pad_post)
    
    f_crop = force[start_crop:end_crop]
    t_crop = np.arange(len(f_crop)) / fs
    
    idx_A = idx_A_abs - start_crop
    idx_H = idx_H_abs - start_crop
    
    acc = (f_crop - bw) / bm
    vel = cumulative_trapezoid(acc, t_crop, initial=0)
    if idx_A < len(vel):
        vel = vel - vel[idx_A]
        vel[idx_A] = 0.0
    
    # Drift correction
    if CONFIG.get('CORRECT_DRIFT', True) and idx_H + int(0.3 * fs) < len(vel):
        v_land = np.mean(vel[idx_H:idx_H + int(0.2 * fs)])
        dur = t_crop[idx_H] - t_crop[idx_A]
        if dur > 0 and abs(v_land) < 10:
            drift = v_land / dur
            corr = np.zeros_like(vel)
            corr[idx_A:] = drift * (t_crop[idx_A:] - t_crop[idx_A])
            vel = vel - corr
            vel[idx_A] = 0.0
    
    # Segment: onset do kraj (najniža tačka landing = do kraja crop-a)
    t_seg = t_crop[idx_A:] - t_crop[idx_A]
    vel_seg = vel[idx_A:]
    
    return t_seg, vel_seg, 0, min(idx_H - idx_A, len(vel_seg) - 1)


def read_qualisys_velocity(tsv_path: Path):
    """Učitaj Qualisys TSV sa CoM i izračunaj brzinu."""
    try:
        header = []
        data_start = None
        with tsv_path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                header.append(line.rstrip())
                if line.startswith("Frame\tTime\t"):
                    data_start = i
                    break
        if data_start is None:
            return None, None, None
        
        df = pd.read_csv(tsv_path, sep="\t", skiprows=data_start, header=0)
        if 'CoM3D_Z' not in df.columns:
            return None, None, None
        
        fs = 300.0
        for h in header:
            if h.startswith("FREQUENCY"):
                try:
                    fs = float(h.split("\t")[1])
                except:
                    pass
        
        t = df['Time'].values
        com_z = df['CoM3D_Z'].values
        vel = np.gradient(com_z, 1.0/fs)
        return t, vel, fs
    except Exception:
        return None, None, None


def get_qualisys_velocity_segment(tsv_path: Path):
    """
    Izračunaj Qualisys brzinu i ekstraktuj segment: onset → najniža tačka landing-a.
    Onset = gde brzina počinje da se menja od nule.
    Kraj = posle peak brzine, tačka gde brzina padne na min (landing).
    """
    t_q, vel_q, fs_q = read_qualisys_velocity(tsv_path)
    if t_q is None or len(t_q) < 10:
        return None
    
    # Nađi peak brzine (maksimum - takeoff)
    peak_idx = np.argmax(vel_q)
    t_peak = t_q[peak_idx]
    
    # Onset: traži unazad od peaka - prva tačka gde je brzina blizu 0
    onset_idx = 0
    vel_sd = np.std(vel_q[:min(int(0.5*fs_q), len(vel_q)//2)])
    thresh = max(0.1, 3 * vel_sd) if vel_sd > 0 else 0.1
    for i in range(peak_idx, 0, -1):
        if abs(vel_q[i]) < thresh:
            onset_idx = i
            break
    
    # Kraj (najniža tačka landing-a): posle peaka, minimum brzine (maks. downward)
    if peak_idx < len(vel_q) - 1:
        post_peak = vel_q[peak_idx:]
        land_min_idx = peak_idx + np.argmin(post_peak)
        # Ako je min blizu kraja, uzmi do peak + 1s
        if t_q[land_min_idx] - t_peak > 1.5:
            land_min_idx = np.searchsorted(t_q, t_peak + 1.0)
        end_idx = min(land_min_idx + int(0.2 * fs_q), len(vel_q) - 1)  # +200ms za cushioning
    else:
        end_idx = len(vel_q) - 1
    
    t_seg = t_q[onset_idx:end_idx] - t_q[onset_idx]
    vel_seg = vel_q[onset_idx:end_idx]
    
    if len(t_seg) < 20:
        return None
    
    return t_seg, vel_seg


def time_normalize_and_compare(t_fp, vel_fp, t_q, vel_q, n_points=101):
    """
    Time-normalizuj oba signala na 0-100% i interpoliraj na n_points.
    Vraća (vel_fp_norm, vel_q_norm) ili None.
    """
    if len(t_fp) < 5 or len(vel_fp) < 5 or len(t_q) < 5 or len(vel_q) < 5:
        return None
    
    # Normalizuj vreme na 0-1
    t_fp_n = (t_fp - t_fp[0]) / (t_fp[-1] - t_fp[0]) if t_fp[-1] > t_fp[0] else np.linspace(0, 1, len(t_fp))
    t_q_n = (t_q - t_q[0]) / (t_q[-1] - t_q[0]) if t_q[-1] > t_q[0] else np.linspace(0, 1, len(t_q))
    
    # Zajednički vremenski vektor 0-1
    t_common = np.linspace(0, 1, n_points)
    
    try:
        f_fp = interp1d(t_fp_n, vel_fp, kind='linear', bounds_error=False, fill_value='extrapolate')
        f_q = interp1d(t_q_n, vel_q, kind='linear', bounds_error=False, fill_value='extrapolate')
        v_fp_i = f_fp(t_common)
        v_q_i = f_q(t_common)
    except Exception:
        return None
    
    return v_fp_i, v_q_i


def signal_reliability_metrics(v_fp, v_q):
    """Izračunaj sve parametre pouzdanosti za par signala."""
    if len(v_fp) != len(v_q) or len(v_fp) < 3:
        return None
    
    diff = v_fp - v_q
    n = len(v_fp)
    
    # Pearson i Spearman
    r_p, p_p = pearsonr(v_fp, v_q)
    r_s, p_s = spearmanr(v_fp, v_q)
    
    # RMSE, MAE
    rmse = np.sqrt(np.mean(diff**2))
    mae = np.mean(np.abs(diff))
    
    # Bland-Altman
    mean_diff = np.mean(diff)
    std_diff = np.std(diff)
    loa_low = mean_diff - 1.96 * std_diff
    loa_high = mean_diff + 1.96 * std_diff
    
    # ICC
    icc = icc_agreement(v_fp, v_q)
    
    # SEM (Standard Error of Measurement)
    sem = std_diff / np.sqrt(2)  # za dva merenja
    
    # CV% (Coefficient of Variation za razlike)
    mean_vals = (np.mean(np.abs(v_fp)) + np.mean(np.abs(v_q))) / 2
    cv = (std_diff / mean_vals * 100) if mean_vals > 0.01 else np.nan
    
    return {
        'pearson_r': r_p, 'pearson_p': p_p,
        'spearman_r': r_s, 'spearman_p': p_s,
        'rmse': rmse, 'mae': mae,
        'bias': mean_diff, 'std_diff': std_diff,
        'loa_95_low': loa_low, 'loa_95_high': loa_high,
        'icc': icc, 'sem': sem, 'cv_pct': cv
    }


def run_signal_reliability(base_path: Path):
    """Izračunaj pouzdanost signala za parove FP–Qualisys (onset → landing)."""
    sj_fp_dir = base_path / "SJ_ForcePlates"
    cmj_fp_dir = base_path / "CMJ_ForcePlates"
    sj_q_dir = base_path / "SJ_Qualisys_CoM"
    cmj_q_dir = base_path / "CMJ_Qualisys_CoM"
    
    all_results = []
    
    for jump_name, jump_type, fp_dir, q_dir in [
        ('SJ', 1, sj_fp_dir, sj_q_dir),
        ('CMJ', 2, cmj_fp_dir, cmj_q_dir)
    ]:
        if not fp_dir.exists() or not q_dir.exists():
            continue
        
        fp_files = {f.stem: f for f in fp_dir.glob("*.txt")}
        q_files = {f.stem: f for f in q_dir.glob("*.tsv")}
        common = set(fp_files.keys()) & set(q_files.keys())
        
        for basename in sorted(common):
            fp_res = get_fp_velocity_segment(fp_files[basename], jump_type)
            if fp_res is None:
                continue
            
            t_fp, vel_fp, _, _ = fp_res
            q_res = get_qualisys_velocity_segment(q_files[basename])
            if q_res is None:
                continue
            
            t_q, vel_q = q_res
            norm = time_normalize_and_compare(t_fp, vel_fp, t_q, vel_q, n_points=101)
            if norm is None:
                continue
            
            v_fp_n, v_q_n = norm
            met = signal_reliability_metrics(v_fp_n, v_q_n)
            if met is None:
                continue
            
            met['jump_type'] = jump_name
            met['trial'] = basename
            all_results.append(met)
    
    return pd.DataFrame(all_results)


def main():
    base_path = Path(__file__).parent
    excel_file = base_path / "Output" / "Excel" / "MoCap_KPIs.xlsx"
    output_dir = base_path / "Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 90)
    print("POREĐENJE vTO I POUZDANOST SIGNALA - FP vs QUALISYS")
    print("=" * 90)
    print(f"Vreme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    
    # ========== 1. vTO KORELACIJE ==========
    print("\n" + "=" * 90)
    print("1. KORELACIJE vTO (FP vs Qualisys)")
    print("=" * 90)
    
    if not excel_file.exists():
        print(f"[ERROR] Excel ne postoji: {excel_file}")
        print("Pokrenite prvo calculate_fp_kpis.py i calculate_kpis.py")
        return 1
    
    merged = load_and_merge_data(excel_file)
    vto_results = calculate_vto_correlations(merged)
    
    for jump_type in ['SJ', 'CMJ']:
        print(f"\n--- {jump_type} ---")
        for model in ['3D', '2DL', '2DR']:
            r = vto_results.get(jump_type, {}).get(model, {})
            if 'error' in r:
                print(f"  {model}: {r['error']}")
                continue
            sig = "***" if r['pearson_p'] < 0.001 else "**" if r['pearson_p'] < 0.01 else "*" if r['pearson_p'] < 0.05 else ""
            print(f"  {model}: N={r['n']} | r={r['pearson_r']:.4f}{sig} | MAE={r['mae']:.4f} m/s | Bias={r['bias']:.4f} m/s")
            print(f"         vTO_FP: {r['vto_fp_mean']:.3f}+/-{r['vto_fp_std']:.3f} | vTO_Q: {r['vto_q_mean']:.3f}+/-{r['vto_q_std']:.3f} m/s")
    
    # vTO scatter plotovi
    fig, axes = plt.subplots(2, 3, figsize=(14, 10))
    for row, jump_type in enumerate(['SJ', 'CMJ']):
        for col, model in enumerate(['3D', '2DL', '2DR']):
            ax = axes[row, col]
            r = vto_results.get(jump_type, {}).get(model, {})
            if 'df' in r:
                df = r['df']
                ax.scatter(df['vTO'], df['V_Takeoff_ms'], alpha=0.7)
                lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]), max(ax.get_xlim()[1], ax.get_ylim()[1])]
                ax.plot(lims, lims, 'k--', alpha=0.5)
                ax.set_xlabel('vTO Qualisys (m/s)')
                ax.set_ylabel('vTO Force Plate (m/s)')
                ax.set_title(f'{jump_type} {model}\nr={r["pearson_r"]:.3f}, N={r["n"]}')
            ax.set_aspect('equal', adjustable='box')
    plt.tight_layout()
    plt.savefig(output_dir / "vTO_comparison_scatter.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[OK] Scatter sačuvan: {output_dir / 'vTO_comparison_scatter.png'}")
    
    # ========== 2. POUZDANOST SIGNALA ==========
    print("\n" + "=" * 90)
    print("2. POUZDANOST NA NIVOU SIGNALA BRZINE (onset do najniza tacka landing-a)")
    print("=" * 90)
    
    rel_df = run_signal_reliability(base_path)
    
    if len(rel_df) == 0:
        print("[WARNING] Nema parova FP–Qualisys za analizu signala")
    else:
        for jt in ['SJ', 'CMJ']:
            sub = rel_df[rel_df['jump_type'] == jt]
            if len(sub) < 2:
                continue
            print(f"\n--- {jt} (N={len(sub)} parova) ---")
            print(f"  Pearson r:   {sub['pearson_r'].mean():.4f} +/- {sub['pearson_r'].std():.4f}")
            print(f"  Spearman r:  {sub['spearman_r'].mean():.4f} +/- {sub['spearman_r'].std():.4f}")
            print(f"  RMSE:        {sub['rmse'].mean():.4f} +/- {sub['rmse'].std():.4f} m/s")
            print(f"  MAE:         {sub['mae'].mean():.4f} +/- {sub['mae'].std():.4f} m/s")
            print(f"  Bias:        {sub['bias'].mean():.4f} +/- {sub['bias'].std():.4f} m/s")
            print(f"  95% LoA:     [{sub['loa_95_low'].mean():.4f}, {sub['loa_95_high'].mean():.4f}] m/s")
            if 'icc' in sub.columns and sub['icc'].notna().any():
                print(f"  ICC:         {sub['icc'].mean():.4f} +/- {sub['icc'].std():.4f}")
            print(f"  SEM:         {sub['sem'].mean():.4f} m/s")
        
        # Sačuvaj u Excel
        out_excel = output_dir / "Excel" / "Signal_Reliability.xlsx"
        out_excel.parent.mkdir(parents=True, exist_ok=True)
        rel_df.to_excel(out_excel, index=False)
        print(f"\n[OK] Pouzdanost signala sačuvana: {out_excel}")
    
    # Sačuvaj vTO korelacije u Excel
    summary_rows = []
    for jt in ['SJ', 'CMJ']:
        for model in ['3D', '2DL', '2DR']:
            r = vto_results.get(jt, {}).get(model, {})
            if 'error' not in r:
                summary_rows.append({
                    'Tip': jt, 'Model': model, 'N': r['n'],
                    'Pearson_r': r['pearson_r'], 'Pearson_p': r['pearson_p'],
                    'MAE': r['mae'], 'Bias': r['bias'],
                    'vTO_FP_mean': r['vto_fp_mean'], 'vTO_Q_mean': r['vto_q_mean']
                })
    if summary_rows:
        pd.DataFrame(summary_rows).to_excel(output_dir / "Excel" / "vTO_Correlations.xlsx", index=False)
        print(f"[OK] vTO korelacije sačuvane: {output_dir / 'Excel' / 'vTO_Correlations.xlsx'}")
    
    print("\n" + "=" * 90)
    print("ZAVRŠENO")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
