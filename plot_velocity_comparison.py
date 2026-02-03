#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UPOREDNI PLOT BRZINE - QUALISYS vs FP
=====================================
- Segment: onset do nule (oba signala se prikazuju do povratka na nulu)
- vTO se NE menja (crop ostaje isti, samo duzina prikaza)
- Poravnanje: PIK BRZINE (t=0)
- Parametri pouzdanosti: Pearson, Spearman, RMSE, MAE, Bias, LoA, ICC, SEM, CV%
"""

import sys
import re
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.interpolate import interp1d
from scipy.stats import pearsonr, spearmanr
from datetime import datetime
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from calculate_fp_kpis import (
    read_force_file, analyze_jump, butter_lowpass_filter,
    calculate_body_weight_robust, CONFIG
)
from scipy.integrate import cumulative_trapezoid


def icc_agreement(x1, x2):
    """ICC(2,1) - two-way random, absolute agreement."""
    n = len(x1)
    if n < 2:
        return np.nan
    x1, x2 = np.asarray(x1, dtype=float), np.asarray(x2, dtype=float)
    m = np.column_stack([x1, x2])
    mr = np.mean(m, axis=0)
    gm = np.mean(m)
    ssb = n * np.sum((mr - gm) ** 2)
    ssw = np.sum((m - mr) ** 2)
    ms = np.mean(m, axis=1)
    ssm = np.sum((ms - gm) ** 2)
    sse = ssw - ssm
    msb = ssb / 1
    mse = sse / (n - 1) if n > 1 else 0
    icc = (msb - mse) / (msb + mse) if (msb + mse) > 0 else np.nan
    return icc


def parse_basename(basename: str):
    """Basename XX_Y_Z -> SubjectID, JumpType (3=SJ, 4=CMJ), TrialNo."""
    m = re.match(r'^(\d+)_(\d+)_(\d+)$', basename)
    if not m:
        return None
    return {
        'SubjectID': m.group(1),
        'JumpTypeCode': int(m.group(2)),
        'TrialNo': int(m.group(3)),
        'basename': basename,
        'JumpType': 'SJ' if m.group(2) == '3' else 'CMJ'
    }


def get_fp_velocity_onset_to_land(fp_path: Path, jump_type: int):
    """
    Brzina od onseta do LAND. Vraca (t, vel, idx_peak_rel, vto).
    t je u sekundama od pocetka segmenta.
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

    idx_abs_min = np.argmin(force)
    bw, bw_sd = calculate_body_weight_robust(force, fs, idx_abs_min)
    if isinstance(bw, tuple):
        bw = bw[0]
    bm = bw / CONFIG['GRAVITY']
    if bw < 300 or bw > 1500:
        return None

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

    if jump_type == 1:
        max_before_min = np.argmax(force[:idx_abs_min]) if idx_abs_min > 0 else 0
        thresh = bw + 5 * bw_sd
        idx_A_abs = max_before_min
        for i in range(max_before_min, -1, -1):
            if force[i] < thresh:
                idx_A_abs = i
                break
    else:
        unweight_min = np.argmin(force[:propulsion_peak_abs]) if propulsion_peak_abs > 0 else 0
        thresh = bw - 5 * bw_sd
        idx_A_abs = unweight_min
        for i in range(unweight_min, -1, -1):
            if force[i] >= thresh:
                idx_A_abs = i
                break

    # Segment: ONSET do LAND (ne posle)
    start_crop = max(0, idx_A_abs - 50)
    end_crop = idx_H_abs + 50  # LAND + mali buffer

    f_crop = force[start_crop:end_crop]
    t_crop = np.arange(len(f_crop)) / fs
    idx_A = idx_A_abs - start_crop
    idx_H = idx_H_abs - start_crop

    acc = (f_crop - bw) / bm
    vel = cumulative_trapezoid(acc, t_crop, initial=0)
    if idx_A < len(vel):
        vel = vel - vel[idx_A]
        vel[idx_A] = 0.0

    if CONFIG.get('CORRECT_DRIFT', True) and idx_H + int(0.3 * fs) < len(vel):
        v_land = np.mean(vel[idx_H:idx_H + int(0.2 * fs)])
        dur = t_crop[idx_H] - t_crop[idx_A]
        if dur > 0 and abs(v_land) < 10:
            drift = v_land / dur
            corr = np.zeros_like(vel)
            corr[idx_A:] = drift * (t_crop[idx_A:] - t_crop[idx_A])
            vel = vel - corr
            vel[idx_A] = 0.0

    t_seg_land = t_crop[idx_A:idx_H + 1] - t_crop[idx_A]
    vel_seg_land = vel[idx_A:idx_H + 1]

    if len(t_seg_land) < 10:
        return None

    peak_rel = np.argmax(vel_seg_land)
    vto = vel_seg_land[peak_rel]

    # Produzeni deo do nule: append integracija od LAND (vTO se ne menja)
    max_ext = int(2.5 * fs)
    n_ext = min(max_ext, len(force) - idx_H_abs - 50)
    t_seg = t_seg_land
    vel_seg = vel_seg_land.copy()
    if n_ext > 0:
        f_ext = force[idx_H_abs:idx_H_abs + n_ext + 1]
        t_ext = np.arange(len(f_ext)) / fs
        acc_ext = (f_ext - bw) / bm
        v_init = vel_seg_land[-1]
        vel_ext = np.concatenate([[v_init], v_init + np.cumsum((acc_ext[:-1] + acc_ext[1:]) / 2 * np.diff(t_ext))])
        idx_zero = None
        for i in range(1, len(vel_ext)):
            if vel_ext[i] >= 0 and vel_ext[i - 1] < 0:
                idx_zero = i
                break
        if idx_zero is None:
            idx_zero = min(np.argmin(np.abs(vel_ext)) + 1, len(vel_ext))
        n_use = min(idx_zero, len(vel_ext) - 1)
        if n_use < 1:
            n_use = len(vel_ext) - 1
        t_seg = np.concatenate([t_seg_land, t_seg_land[-1] + t_ext[1:n_use + 1] - t_ext[0]])
        vel_seg = np.concatenate([vel_seg_land, vel_ext[1:n_use + 1]])

    return {'t': t_seg, 'vel': vel_seg, 'idx_peak': peak_rel, 'vto': vto, 'fs': fs}


def read_qualisys_velocity(tsv_path: Path):
    try:
        header, data_start = [], None
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
        vel = np.gradient(df['CoM3D_Z'].values, 1.0 / fs)
        return t, vel, fs
    except Exception:
        return None, None, None


def get_qualisys_velocity_onset_to_land(tsv_path: Path):
    """
    Qualisys segment: onset do nule.
    Onset = unazad od peaka, prva blizu 0.
    Kraj = posle landing-a, prvi prelaz brzine kroz nulu.
    """
    t_q, vel_q, fs_q = read_qualisys_velocity(tsv_path)
    if t_q is None or len(t_q) < 10:
        return None

    peak_idx = np.argmax(vel_q)
    vel_sd = np.std(vel_q[:min(int(0.5 * fs_q), len(vel_q) // 2)])
    thresh = max(0.1, 3 * vel_sd) if vel_sd > 0 else 0.1

    onset_idx = 0
    for i in range(peak_idx, 0, -1):
        if abs(vel_q[i]) < thresh:
            onset_idx = i
            break

    if peak_idx < len(vel_q) - 1:
        post_peak = vel_q[peak_idx:]
        land_min_rel = np.argmin(post_peak)
        land_idx = peak_idx + land_min_rel
        end_idx = min(land_idx + int(0.15 * fs_q), len(vel_q) - 1)
        for i in range(land_idx + 1, len(vel_q) - 1):
            if vel_q[i] >= 0 and vel_q[i - 1] < 0:
                end_idx = i
                break
        end_idx = min(end_idx + 1, len(vel_q) - 1)
    else:
        end_idx = len(vel_q) - 1

    t_seg = t_q[onset_idx:end_idx + 1] - t_q[onset_idx]
    vel_seg = vel_q[onset_idx:end_idx + 1]
    if len(t_seg) < 10:
        return None

    peak_rel = np.argmax(vel_seg)
    vto = vel_seg[peak_rel]

    return {'t': t_seg, 'vel': vel_seg, 'idx_peak': peak_rel, 'vto': vto, 'fs': fs_q}


def align_by_peak(t_fp, vel_fp, t_q, vel_q, idx_peak_fp, idx_peak_q, n_pts=301):
    """
    Poravnaj oba signala tako da pik brzine bude na t=0.
    Opseg: od min do max kraja (oba do nule).
    """
    t_peak_fp = t_fp[idx_peak_fp]
    t_peak_q = t_q[idx_peak_q]

    t_fp_rel = t_fp - t_peak_fp
    t_q_rel = t_q - t_peak_q

    t_min = max(t_fp_rel[0], t_q_rel[0])
    t_max = min(t_fp_rel[-1], t_q_rel[-1])
    if t_max <= t_min:
        t_min = min(t_fp_rel[0], t_q_rel[0])
        t_max = max(t_fp_rel[-1], t_q_rel[-1])
    t_common = np.linspace(t_min, t_max, n_pts)

    try:
        f_fp = interp1d(t_fp_rel, vel_fp, kind='linear', bounds_error=False, fill_value=np.nan)
        f_q = interp1d(t_q_rel, vel_q, kind='linear', bounds_error=False, fill_value=np.nan)
        v_fp = f_fp(t_common)
        v_q = f_q(t_common)
    except Exception:
        return None, None, None

    valid = ~(np.isnan(v_fp) | np.isnan(v_q))
    if np.sum(valid) < 20:
        return None, None, None

    return t_common, v_fp, v_q


def detect_outliers_iqr(series, k=1.5):
    """Outlieri prema IQR (|x - median| > k*IQR)."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return pd.Series([False] * len(series), index=series.index)
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return (series < lower) | (series > upper)


def main():
    base = Path(__file__).parent
    fp_dirs = {'SJ': base / "SJ_ForcePlates", 'CMJ': base / "CMJ_ForcePlates"}
    q_dirs = {'SJ': base / "SJ_Qualisys_CoM", 'CMJ': base / "CMJ_Qualisys_CoM"}
    out_dir = base / "Output" / "Velocity_Comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_excel = base / "Output" / "Excel"
    out_excel.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("UPOREDNI PLOT BRZINE: QUALISYS vs FP (onset do nule, poravnano po piku)")
    print("=" * 90)
    print(f"Vreme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    # 1. PROVERA PAROVA
    print("\n--- PROVERA PAROVA (isti ID skok i pokusaj) ---")
    print("Format basename: SubjectID_JumpType_TrialNo (npr. 01_3_1 = Subj 01, SJ, Trial 1)\n")

    all_pairs = []
    all_signals = []
    plot_data = {'SJ': [], 'CMJ': []}

    for jump_name in ['SJ', 'CMJ']:
        jump_type = 1 if jump_name == 'SJ' else 2
        fp_dir = fp_dirs[jump_name]
        q_dir = q_dirs[jump_name]
        if not fp_dir.exists() or not q_dir.exists():
            print(f"[WARNING] Nedostaje {fp_dir} ili {q_dir}")
            continue

        fp_files = {f.stem: f for f in fp_dir.glob("*.txt")}
        q_files = {f.stem: f for f in q_dir.glob("*.tsv")}
        common = sorted(set(fp_files.keys()) & set(q_files.keys()))
        only_fp = sorted(set(fp_files.keys()) - set(q_files.keys()))
        only_q = sorted(set(q_files.keys()) - set(fp_files.keys()))

        print(f"{jump_name}:")
        print(f"  UPARENO (oba fajla): {len(common)} parova")
        if only_fp:
            print(f"  Samo FP (nema Q): {len(only_fp)} - {only_fp[:5]}{'...' if len(only_fp)>5 else ''}")
        if only_q:
            print(f"  Samo Qualisys (nema FP): {len(only_q)} - {only_q[:5]}{'...' if len(only_q)>5 else ''}")

        for basename in common:
            info = parse_basename(basename)
            if info is None:
                continue

            fp_res = get_fp_velocity_onset_to_land(fp_files[basename], jump_type)
            q_res = get_qualisys_velocity_onset_to_land(q_files[basename])
            if fp_res is None or q_res is None:
                all_pairs.append({
                    'basename': basename, 'SubjectID': info['SubjectID'], 'TrialNo': info['TrialNo'],
                    'JumpType': jump_name, 'status': 'fail_extract'
                })
                continue

            t_aligned, v_fp_i, v_q_i = align_by_peak(
                fp_res['t'], fp_res['vel'], q_res['t'], q_res['vel'],
                fp_res['idx_peak'], q_res['idx_peak']
            )
            if t_aligned is None:
                all_pairs.append({
                    'basename': basename, 'SubjectID': info['SubjectID'], 'TrialNo': info['TrialNo'],
                    'JumpType': jump_name, 'status': 'fail_align'
                })
                continue

            # Ukloni NaN za korelaciju i RMSE
            valid = ~(np.isnan(v_fp_i) | np.isnan(v_q_i))
            if np.sum(valid) < 20:
                all_pairs.append({
                    'basename': basename, 'SubjectID': info['SubjectID'], 'TrialNo': info['TrialNo'],
                    'JumpType': jump_name, 'status': 'fail_align'
                })
                continue
            v_fp_v = v_fp_i[valid]
            v_q_v = v_q_i[valid]

            r_p, _ = pearsonr(v_fp_v, v_q_v)
            r_s, _ = spearmanr(v_fp_v, v_q_v)
            diff = v_fp_v - v_q_v
            rmse = np.sqrt(np.mean(diff ** 2))
            mae = np.mean(np.abs(diff))
            bias = np.mean(diff)
            std_diff = np.std(diff)
            loa_95_low = bias - 1.96 * std_diff
            loa_95_high = bias + 1.96 * std_diff
            icc = icc_agreement(v_fp_v, v_q_v)
            sem = std_diff / np.sqrt(2)
            mean_vals = (np.mean(np.abs(v_fp_v)) + np.mean(np.abs(v_q_v))) / 2
            cv_pct = (std_diff / mean_vals * 100) if mean_vals > 0.01 else np.nan

            all_pairs.append({
                'basename': basename, 'SubjectID': info['SubjectID'], 'TrialNo': info['TrialNo'],
                'JumpType': jump_name, 'status': 'ok',
                'vTO_FP': fp_res['vto'], 'vTO_Q': q_res['vto'],
                'pearson_r': r_p, 'spearman_r': r_s, 'rmse': rmse, 'mae': mae, 'bias': bias,
                'loa_95_low': loa_95_low, 'loa_95_high': loa_95_high,
                'icc': icc, 'sem': sem, 'cv_pct': cv_pct
            })
            all_signals.append({
                'basename': basename, 'JumpType': jump_name,
                't': t_aligned, 'vel_fp': v_fp_i, 'vel_q': v_q_i,
                'pearson_r': r_p, 'rmse': rmse
            })
            plot_data[jump_name].append({
                'basename': basename, 't': t_aligned, 'vel_fp': v_fp_i, 'vel_q': v_q_i,
                'r': r_p, 'vto_fp': fp_res['vto'], 'vto_q': q_res['vto']
            })

    pairs_df = pd.DataFrame(all_pairs)
    pairs_ok = pairs_df[pairs_df['status'] == 'ok']

    if len(pairs_ok) == 0:
        print("\n[ERROR] Nema uspesno uparenih parova")
        return 1

    # Tabela parova sa svim parametrima pouzdanosti
    rel_cols = ['basename', 'SubjectID', 'TrialNo', 'JumpType', 'status', 'vTO_FP', 'vTO_Q',
                'pearson_r', 'spearman_r', 'rmse', 'mae', 'bias', 'loa_95_low', 'loa_95_high',
                'icc', 'sem', 'cv_pct']
    pairs_ok[[c for c in rel_cols if c in pairs_ok.columns]].to_excel(
        out_excel / "Velocity_Comparison_Pairs.xlsx", index=False)
    print(f"\n[OK] Tabela parova: {out_excel / 'Velocity_Comparison_Pairs.xlsx'}")

    # 2. OUTLIERI
    print("\n--- DETEKCIJA OUTLIERA (IQR, k=1.5) ---")
    for jt in ['SJ', 'CMJ']:
        sub = pairs_ok[pairs_ok['JumpType'] == jt]
        if len(sub) < 4:
            continue
        for col in ['pearson_r', 'rmse', 'mae', 'vTO_FP', 'vTO_Q']:
            if col not in sub.columns:
                continue
            out_mask = detect_outliers_iqr(sub[col])
            if out_mask.any():
                bnames = list(sub.loc[out_mask, 'basename'])
                print(f"  {jt} {col}: {out_mask.sum()} outliera - {bnames}")
        if 'vTO_FP' in sub.columns and 'vTO_Q' in sub.columns:
            vto_diff = sub['vTO_FP'] - sub['vTO_Q']
            out_vto = detect_outliers_iqr(vto_diff)
            if out_vto.any():
                bnames = list(sub.loc[out_vto, 'basename'])
                print(f"  {jt} vTO_diff (FP-Q): {out_vto.sum()} outliera - {bnames}")

    # 3. PROSECNI PLOT (svi signali) + pojedinacni
    print("\n--- KREIRANJE PLOTOVA ---")
    for jt in ['SJ', 'CMJ']:
        data = plot_data[jt]
        if len(data) == 0:
            continue

        fig, axes = plt.subplots(2, 1, figsize=(12, 10))

        # Gore: prosecni signal (mean +/- std)
        t_common = data[0]['t']
        v_fp_all = np.array([d['vel_fp'] for d in data])
        v_q_all = np.array([d['vel_q'] for d in data])
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean_fp = np.nanmean(v_fp_all, axis=0)
            std_fp = np.nanstd(v_fp_all, axis=0)
            mean_q = np.nanmean(v_q_all, axis=0)
            std_q = np.nanstd(v_q_all, axis=0)
        if np.all(np.isnan(mean_fp)) or np.all(np.isnan(mean_q)):
            continue

        ax = axes[0]
        ax.plot(t_common, mean_fp, 'b-', lw=2, label='FP (mean)')
        ax.fill_between(t_common, mean_fp - std_fp, mean_fp + std_fp, alpha=0.3, color='blue')
        ax.plot(t_common, mean_q, 'r-', lw=2, label='Qualisys (mean)')
        ax.fill_between(t_common, mean_q - std_q, mean_q + std_q, alpha=0.3, color='red')
        ax.axvline(0, color='gray', ls='--', lw=1, label='Peak (t=0)')
        ax.axhline(0, color='gray', ls=':', lw=0.8)
        ax.set_xlabel('Vreme (s, poravnato po piku brzine)')
        ax.set_ylabel('Brzina (m/s)')
        ax.set_title(f'{jt}: Prosecni signal (N={len(data)}, onset do nule, peak-aligned)')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Dole: svi signali transparentno
        ax = axes[1]
        for d in data:
            ax.plot(d['t'], d['vel_fp'], 'b-', alpha=0.15)
            ax.plot(d['t'], d['vel_q'], 'r-', alpha=0.15)
        ax.plot(t_common, mean_fp, 'b-', lw=2, label='FP mean')
        ax.plot(t_common, mean_q, 'r-', lw=2, label='Qualisys mean')
        ax.axvline(0, color='gray', ls='--', lw=1)
        ax.axhline(0, color='gray', ls=':', lw=0.8)
        ax.set_xlabel('Vreme (s)')
        ax.set_ylabel('Brzina (m/s)')
        ax.set_title(f'{jt}: Svi pojedinacni signali')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(out_dir / f"{jt}_velocity_comparison.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [OK] {jt}: {out_dir / f'{jt}_velocity_comparison.png'}")

    # 4. Outlier plotovi (najgore parove)
    for jt in ['SJ', 'CMJ']:
        sub = pairs_ok[pairs_ok['JumpType'] == jt]
        if len(sub) < 2:
            continue
        worst = sub.nsmallest(3, 'pearson_r')
        if len(worst) == 0:
            continue
        fig, axes = plt.subplots(1, min(3, len(worst)), figsize=(5 * len(worst), 5))
        if len(worst) == 1:
            axes = [axes]
        for i, (_, row) in enumerate(worst.iterrows()):
            d = next(x for x in plot_data[jt] if x['basename'] == row['basename'])
            ax = axes[i]
            ax.plot(d['t'], d['vel_fp'], 'b-', lw=2, label=f"FP (vTO={d['vto_fp']:.3f})")
            ax.plot(d['t'], d['vel_q'], 'r-', lw=2, label=f"Q (vTO={d['vto_q']:.3f})")
            ax.axvline(0, color='gray', ls='--')
            ax.axhline(0, color='gray', ls=':')
            ax.set_title(f"{row['basename']} r={row['pearson_r']:.3f}")
            ax.legend()
            ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(out_dir / f"{jt}_worst_pairs.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  [OK] {jt} worst: {out_dir / f'{jt}_worst_pairs.png'}")

    # 5. Rezime - svi parametri pouzdanosti
    print("\n" + "=" * 90)
    print("REZIME SIGNAL POUZDANOSTI (peak-aligned, onset do nule)")
    print("=" * 90)
    for jt in ['SJ', 'CMJ']:
        sub = pairs_ok[pairs_ok['JumpType'] == jt]
        if len(sub) < 2:
            continue
        n_valid = sub['pearson_r'].notna().sum()
        print(f"\n{jt} (N={len(sub)}, valid={n_valid}):")
        if n_valid >= 2:
            print(f"  Pearson r:   {sub['pearson_r'].mean():.4f} +/- {sub['pearson_r'].std():.4f}")
            print(f"  Spearman r:  {sub['spearman_r'].mean():.4f} +/- {sub['spearman_r'].std():.4f}")
            print(f"  RMSE:        {sub['rmse'].mean():.4f} m/s")
            print(f"  MAE:         {sub['mae'].mean():.4f} m/s")
            print(f"  Bias:        {sub['bias'].mean():.4f} m/s")
            if 'loa_95_low' in sub.columns:
                print(f"  95% LoA:     [{sub['loa_95_low'].mean():.4f}, {sub['loa_95_high'].mean():.4f}] m/s")
            if 'icc' in sub.columns:
                print(f"  ICC:         {sub['icc'].mean():.4f} +/- {sub['icc'].std():.4f}")
            if 'sem' in sub.columns:
                print(f"  SEM:         {sub['sem'].mean():.4f} m/s")
            if 'cv_pct' in sub.columns and sub['cv_pct'].notna().any():
                print(f"  CV%:         {sub['cv_pct'].mean():.2f}%")
        print(f"  vTO_FP:      {sub['vTO_FP'].mean():.3f} +/- {sub['vTO_FP'].std():.3f}")
        print(f"  vTO_Q:       {sub['vTO_Q'].mean():.3f} +/- {sub['vTO_Q'].std():.3f}")

    print("\n" + "=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
