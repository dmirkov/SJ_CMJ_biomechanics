#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST: Uparivanje FP i Qualisys brzine na JEDNOM primeru
========================================================
Logika: FP ima onset i LAND (iz sile). Iz FP uzimamo:
  - T1 = vreme od onseta do pika brzine
  - T2 = vreme od pika do LAND
Qualisys: pun signal, nađemo PIK. Od pika idemo UNAZAD T1 i UNAPRED T2.
Oba signala imaju ISTE vremenske delove (relativno na pik t=0).
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from calculate_fp_kpis import (
    read_force_file, analyze_jump, butter_lowpass_filter,
    calculate_body_weight_robust, CONFIG
)
from scipy.integrate import cumulative_trapezoid


def get_fp_velocity_with_timings(fp_path: Path, jump_type: int):
    """
    FP brzina od onseta do LAND.
    Vraca: t (od onseta), vel, t_onset_to_peak, t_peak_to_land, vto
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
    bw = bw[0] if isinstance(bw, tuple) else bw
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

    start_crop = max(0, idx_A_abs - 50)
    end_crop = idx_H_abs + 50

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
    peak_rel = np.argmax(vel_seg_land)
    t_onset_to_peak = t_seg_land[peak_rel]
    t_peak_to_land = t_seg_land[-1] - t_seg_land[peak_rel]
    t_peak_to_end = t_peak_to_land + 0.5
    vto = vel_seg_land[peak_rel]

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

    if len(t_seg) < 10:
        return None

    vto = vel_seg[peak_rel]

    return {
        't': t_seg, 'vel': vel_seg,
        't_onset_to_peak': t_onset_to_peak,
        't_peak_to_land': t_peak_to_land,
        't_peak_to_end': t_peak_to_end,
        'idx_peak': peak_rel, 'vto': vto
    }


def read_qualisys_full(tsv_path: Path):
    """Pun Qualisys signal: t, vel, fs."""
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


def get_qualisys_segment_to_zero(tsv_path: Path, t_onset_to_peak: float, t_peak_to_land: float):
    """
    Qualisys: pun signal. Nađemo PIK brzine.
    Od pika UNAZAD t_onset_to_peak. UNAPRED do prelaza kroz nulu.
    """
    t_q, vel_q, fs_q = read_qualisys_full(tsv_path)
    if t_q is None or len(t_q) < 10:
        return None

    peak_idx = np.argmax(vel_q)
    t_peak = t_q[peak_idx]
    t_start = t_peak - t_onset_to_peak

    if peak_idx < len(vel_q) - 1:
        post_peak = vel_q[peak_idx:]
        land_min_rel = np.argmin(post_peak)
        land_idx = peak_idx + land_min_rel
        end_idx = land_idx + 1
        for i in range(land_idx + 1, len(vel_q) - 1):
            if vel_q[i] >= 0 and vel_q[i - 1] < 0:
                end_idx = i
                break
        end_idx = min(end_idx + 1, len(vel_q) - 1)
    else:
        end_idx = len(vel_q) - 1

    t_end = t_q[end_idx]
    mask = (t_q >= t_start) & (t_q <= t_end)
    if np.sum(mask) < 5:
        return None

    t_seg = t_q[mask] - t_peak
    vel_seg = vel_q[mask]
    vto = vel_q[peak_idx]

    return {'t': t_seg, 'vel': vel_seg, 'vto': vto}


def main():
    base = Path(__file__).parent
    # Primer: CMJ 02_4_1
    basename = "02_4_1"
    jump_type = 2  # CMJ
    fp_path = base / "CMJ_ForcePlates" / f"{basename}.txt"
    q_path = base / "CMJ_Qualisys_CoM" / f"{basename}.tsv"

    if not fp_path.exists() or not q_path.exists():
        print(f"Fajlovi ne postoje: {fp_path}, {q_path}")
        return 1

    print("=" * 70)
    print(f"TEST: {basename} (CMJ)")
    print("=" * 70)

    fp = get_fp_velocity_with_timings(fp_path, jump_type)
    if fp is None:
        print("[ERROR] FP ekstrakcija neuspesna")
        return 1

    print(f"\nFP:")
    print(f"  T1 (onset do pik)  = {fp['t_onset_to_peak']:.4f} s")
    print(f"  T2 (pik do LAND)   = {fp['t_peak_to_land']:.4f} s")
    print(f"  Do nule (ukupno)   = {fp['t'][-1]:.4f} s")
    print(f"  vTO                = {fp['vto']:.4f} m/s")
    print(f"  Broj tacaka        = {len(fp['t'])}")

    q = get_qualisys_segment_to_zero(
        q_path, fp['t_onset_to_peak'], fp['t_peak_to_land']
    )
    if q is None:
        print("[ERROR] Qualisys ekstrakcija neuspesna")
        return 1

    print(f"\nQualisys (onset do nule):")
    print(f"  t od {q['t'][0]:.4f} do {q['t'][-1]:.4f} s (relativno na pik)")
    print(f"  vTO                = {q['vto']:.4f} m/s")
    print(f"  Broj tacaka        = {len(q['t'])}")

    t_fp_rel = fp['t'] - fp['t_onset_to_peak']
    t_q_rel = q['t']

    t_min = max(t_fp_rel[0], t_q_rel[0])
    t_max = min(t_fp_rel[-1], t_q_rel[-1])
    t_common = np.linspace(t_min, t_max, 201)

    v_fp_i = interp1d(t_fp_rel, fp['vel'], kind='linear', bounds_error=False, fill_value=np.nan)(t_common)
    v_q_i = interp1d(t_q_rel, q['vel'], kind='linear', bounds_error=False, fill_value=np.nan)(t_common)

    valid = ~(np.isnan(v_fp_i) | np.isnan(v_q_i))
    r = np.corrcoef(v_fp_i[valid], v_q_i[valid])[0, 1] if np.sum(valid) > 10 else np.nan
    print(f"\nKorelacija (nakon interpolacije): r = {r:.4f}")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(t_fp_rel, fp['vel'], 'b-', lw=2, label=f'FP (vTO={fp["vto"]:.3f})')
    ax.plot(t_q_rel, q['vel'], 'r-', lw=2, label=f'Qualisys (vTO={q["vto"]:.3f})')
    ax.axvline(0, color='gray', ls='--', lw=2, label='Peak (t=0)')
    ax.axhline(0, color='gray', ls=':', lw=0.8)
    ax.set_xlabel('Vreme (s, relativno na pik brzine)')
    ax.set_ylabel('Brzina (m/s)')
    ax.set_title(f'{basename}: FP vs Qualisys (onset do nule) | r={r:.4f}')
    ax.legend()
    ax.grid(True, alpha=0.3)

    out_dir = base / "Output" / "Velocity_Comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / f"{basename}_test_pair.png", dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n[OK] Plot sacuvan: {out_dir / f'{basename}_test_pair.png'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
