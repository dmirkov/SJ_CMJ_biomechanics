#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KONTROLNI PLOTOVI UGLOVA (segmenti i zglobovi)
==============================================
a) Uglovi segmenata vs vertikalna (foot, shank, thigh, trunk) L/R
b) Uglovi u zglobovima (ankle, knee, hip) L/R

Za svaki ugao posebno:
- Onset (iz |ω|, isti kriterijum za sve) – redosled „ko prvi kreće”
- T_ecc = t_zmin - t_onset (za CMJ)
- Peak fleksija u fazi odskoka, obeležena + dt_peakFlex_to_zmin (relativno na najdublje spuštanje)
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Optional, Tuple
import importlib.util

# Import iz SJ_CMJ_Qualisys_AMTI
sys.path.insert(0, r"C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI")
from file_discovery import discover_processed_files, load_processed_file
from kpi_calculator import calculate_kpis

# Marker kolone (XZ za sagitalnu ravan)
MARKERS = {
    'heel_L': ('left_heel_pos_X', 'left_heel_pos_Z'),
    'small_toe_L': ('left_small_toe_pos_X', 'left_small_toe_pos_Z'),
    'ankle_L': ('left_ankle_pos_X', 'left_ankle_pos_Z'),
    'knee_L': ('left_knee_pos_X', 'left_knee_pos_Z'),
    'hip_L': ('left_hip_pos_X', 'left_hip_pos_Z'),
    'shoulder_L': ('left_shoulder_pos_X', 'left_shoulder_pos_Z'),
    'heel_R': ('right_heel_pos_X', 'right_heel_pos_Z'),
    'small_toe_R': ('right_small_toe_pos_X', 'right_small_toe_pos_Z'),
    'ankle_R': ('right_ankle_pos_X', 'right_ankle_pos_Z'),
    'knee_R': ('right_knee_pos_X', 'right_knee_pos_Z'),
    'hip_R': ('right_hip_pos_X', 'right_hip_pos_Z'),
    'shoulder_R': ('right_shoulder_pos_X', 'right_shoulder_pos_Z'),
}

# Segment definicije: (proksimalni marker, distalni marker) -> vektor od proks ka dist
# θ = atan2(Δx, Δz) - ugao od vertikale (0 = vertikalno)
SEGMENTS = {
    'foot_L': ('heel_L', 'small_toe_L'),
    'shank_L': ('ankle_L', 'knee_L'),
    'thigh_L': ('knee_L', 'hip_L'),
    'trunk_L': ('hip_L', 'shoulder_L'),
    'foot_R': ('heel_R', 'small_toe_R'),
    'shank_R': ('ankle_R', 'knee_R'),
    'thigh_R': ('knee_R', 'hip_R'),
    'trunk_R': ('hip_R', 'shoulder_R'),
}

# Joint = razlika susednih segmenata
JOINTS = {
    'ankle_L': ('foot_L', 'shank_L'),   # φ = θ_shank - θ_foot
    'knee_L': ('shank_L', 'thigh_L'),   # φ = θ_thigh - θ_shank
    'hip_L': ('thigh_L', 'trunk_L'),    # φ = θ_trunk - θ_thigh
    'ankle_R': ('foot_R', 'shank_R'),
    'knee_R': ('shank_R', 'thigh_R'),
    'hip_R': ('thigh_R', 'trunk_R'),
}


def _get_marker_pos(df: pd.DataFrame, name: str) -> Tuple[np.ndarray, np.ndarray]:
    """Vraća (x, z) za marker. Ako kolone ne postoje, vraća NaN array."""
    cx, cz = MARKERS[name]
    if cx not in df.columns or cz not in df.columns:
        n = len(df)
        return np.full(n, np.nan), np.full(n, np.nan)
    x = pd.Series(df[cx].values).ffill().bfill().values
    z = pd.Series(df[cz].values).ffill().bfill().values
    return x, z


def compute_segment_angle(df: pd.DataFrame, seg_name: str) -> np.ndarray:
    """θ(t) = atan2(Δx, Δz) u radijanima. Segment od prox -> dist."""
    prox, dist = SEGMENTS[seg_name]
    xp, zp = _get_marker_pos(df, prox)
    xd, zd = _get_marker_pos(df, dist)
    dx = xd - xp
    dz = zd - zp
    theta = np.arctan2(dx, dz)
    return theta


def wrap_angle(phi: np.ndarray) -> np.ndarray:
    """wrap na [-π, π]"""
    return np.arctan2(np.sin(phi), np.cos(phi))


def compute_joint_angle(df: pd.DataFrame, theta: Dict[str, np.ndarray],
                        baseline_n: int) -> Dict[str, np.ndarray]:
    """Joint uglovi sa baseline reference. φ* = φ - median(φ_baseline)."""
    phi_out = {}
    for jname, (seg1, seg2) in JOINTS.items():
        if seg1 not in theta or seg2 not in theta:
            phi_out[jname] = np.full(len(df), np.nan)
            continue
        # φ = θ_distal - θ_proximal (prema spec)
        phi = theta[seg2] - theta[seg1]
        phi = wrap_angle(phi)
        base = phi[:min(baseline_n, len(phi))]
        base = base[~np.isnan(base)]
        if len(base) > 0:
            phi = phi - np.median(base)
        phi_out[jname] = wrap_angle(phi)
    return phi_out


def rad2deg(x: np.ndarray) -> np.ndarray:
    return np.degrees(x)


def detect_onset_for_signal(s: np.ndarray, time: np.ndarray, fs: float,
                            search_end: Optional[float] = None,
                            baseline_start_s: float = 0.2,
                            baseline_window_s: float = 1.0,
                            persistence_ms: float = 80.0,
                            k_sigma: float = 6.0) -> Optional[float]:
    """
    Onset iz signala s(t) (npr. |ω|) – isti kriterijum za sve kandidate.
    Baseline, prag (MAD), persistence 80 ms.
    Vraća t_onset ili None.
    """
    n_persist = max(1, int(persistence_ms / 1000.0 * fs))
    n_base_start = int(baseline_start_s * fs)
    n_base_len = int(baseline_window_s * fs)
    n_base_end = min(n_base_start + n_base_len, len(s) // 2)
    if n_base_end < 10:
        return None
    base = s[n_base_start:n_base_end]
    base = base[~np.isnan(base)]
    if len(base) < 5:
        return None
    med = np.median(base)
    mad = np.median(np.abs(base - med))
    sigma = 1.4826 * mad if mad > 1e-10 else np.std(base)
    s_post = s[n_base_end:] if n_base_end < len(s) else np.array([0])
    s_post = s_post[~np.isnan(s_post)]
    max_post = np.max(s_post) if len(s_post) > 0 else 0
    T_s = max(k_sigma * sigma, 0.02 * max_post)
    if search_end is not None:
        idx_end = np.argmin(np.abs(time - search_end))
    else:
        idx_end = len(s) - n_persist
    search_start = n_base_end
    for i in range(search_start, min(idx_end, len(s) - n_persist)):
        if np.all(s[i:i + n_persist] > T_s):
            return float(time[i])
    return None


def compute_omega(angle: np.ndarray, time: np.ndarray) -> np.ndarray:
    """ω = d(angle)/dt (rad/s)"""
    dt = np.gradient(time)
    dt[dt < 1e-9] = 1e-9
    return np.gradient(angle, time)


def find_peak_flexion_in_interval(arr: np.ndarray, time: np.ndarray,
                                   t_start: float, t_end: float,
                                   maximize: bool = True) -> Tuple[Optional[float], Optional[float]]:
    """Nađi vreme i vrednost max/min u intervalu [t_start, t_end]."""
    mask = (time >= t_start) & (time <= t_end)
    if not np.any(mask):
        return None, None
    sub = arr[mask]
    sub_t = time[mask]
    valid = ~np.isnan(sub)
    if not np.any(valid):
        return None, None
    sub = sub[valid]
    sub_t = sub_t[valid]
    idx = np.argmax(sub) if maximize else np.argmin(sub)
    return float(sub_t[idx]), float(sub[idx])


def plot_segment_angles(df: pd.DataFrame, time: np.ndarray, theta: Dict[str, np.ndarray],
                        events: Dict[str, float],
                        onset_per: Dict[str, Optional[float]],
                        T_ecc_per: Dict[str, Optional[float]],
                        peaks_takeoff: Dict[str, Tuple[Optional[float], Optional[float], Optional[float]]],
                        peaks_landing: Dict[str, Tuple[Optional[float], Optional[float]]],
                        jump_type: str, filename: str, output_path: Path):
    """Jedan plot sa subplots za uglove segmenata. Za svaki: onset, T_ecc, peak flexion + dt_to_zmin."""
    segs = ['foot_L', 'shank_L', 'thigh_L', 'trunk_L', 'foot_R', 'shank_R', 'thigh_R', 'trunk_R']
    t_zmin = events.get('t_zmin', np.nan)
    fig, axes = plt.subplots(4, 2, figsize=(12, 10), sharex=True)
    axes = axes.flatten()
    for i, seg in enumerate(segs):
        ax = axes[i]
        if seg not in theta:
            ax.set_title(seg)
            continue
        ang_deg = rad2deg(theta[seg])
        ax.axhline(0, color='gray', ls='-', alpha=0.4, lw=0.5)
        ax.plot(time, ang_deg, 'b-', lw=1, label=seg)
        # t_zmin (najdublje spuštanje), t_TO, t_LAND
        for ev_name, t in events.items():
            if np.isnan(t) or t < time[0] or t > time[-1]:
                continue
            color = {'t_zmin': 'orange', 't_TO': 'red', 't_LAND': 'purple', 't_zmin_land': 'brown'}.get(ev_name, 'gray')
            ax.axvline(t, color=color, ls='--', alpha=0.6, label=ev_name if i == 0 else None)
        # Onset za ovaj segment
        t_on = onset_per.get(seg)
        if t_on is not None and not np.isnan(t_on):
            ax.axvline(t_on, color='green', ls='-', alpha=0.8, lw=1.2, label='onset' if i == 0 else None)
        # T_ecc u naslovu
        T_ecc = T_ecc_per.get(seg)
        title = seg
        if T_ecc is not None and not np.isnan(T_ecc) and jump_type == 'CMJ':
            title += f" | T_ecc={1000*T_ecc:.0f}ms"
        if t_on is not None and not np.isnan(t_on):
            title += f"\nonset={t_on:.2f}s"
        ax.set_title(title, fontsize=9)
        # Peak flexion takeoff + dt_to_zmin
        if seg in peaks_takeoff:
            t_p, v_p, dt_z = peaks_takeoff[seg]
            if t_p is not None and v_p is not None:
                ax.axvline(t_p, color='cyan', ls=':', alpha=0.8)
                ax.plot(t_p, np.degrees(v_p), 'co', ms=7)
                if dt_z is not None and not np.isnan(dt_z) and jump_type == 'CMJ':
                    ax.annotate(f"Δt_zmin={1000*dt_z:.0f}ms", xy=(t_p, np.degrees(v_p)), xytext=(5, 5),
                                textcoords='offset points', fontsize=7, color='darkblue')
        # Peak landing
        if seg in peaks_landing and peaks_landing[seg][0] is not None:
            t_p, v_p = peaks_landing[seg]
            if v_p is not None:
                ax.axvline(t_p, color='magenta', ls=':', alpha=0.8)
                ax.plot(t_p, np.degrees(v_p), 'mo', ms=6)
        ax.set_ylabel('deg')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=5)
    fig.suptitle(f'Segment angles vs vertical (0° = straight/vertical) — {jump_type} — {filename}', fontsize=12)
    plt.tight_layout()
    basename = filename.replace('.tsv', '').replace('.csv', '')
    out = output_path / f"segments_{jump_type}_{basename}.png"
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out.name}")


def plot_joint_angles(df: pd.DataFrame, time: np.ndarray, phi: Dict[str, np.ndarray],
                      events: Dict[str, float],
                      onset_per: Dict[str, Optional[float]],
                      T_ecc_per: Dict[str, Optional[float]],
                      peaks_takeoff: Dict[str, Tuple[Optional[float], Optional[float], Optional[float]]],
                      peaks_landing: Dict[str, Tuple[Optional[float], Optional[float]]],
                      jump_type: str, filename: str, output_path: Path):
    """Jedan plot sa subplots za uglove zglobova. Za svaki: onset, T_ecc, peak flexion + dt_to_zmin."""
    joints = ['ankle_L', 'knee_L', 'hip_L', 'ankle_R', 'knee_R', 'hip_R']
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True)
    axes = axes.flatten()
    for i, jname in enumerate(joints):
        ax = axes[i]
        if jname not in phi:
            ax.set_title(jname)
            continue
        ang_deg = rad2deg(phi[jname])
        ax.axhline(0, color='gray', ls='-', alpha=0.4, lw=0.5)
        ax.plot(time, ang_deg, 'b-', lw=1, label=jname)
        for ev_name, t in events.items():
            if np.isnan(t) or t < time[0] or t > time[-1]:
                continue
            color = {'t_zmin': 'orange', 't_TO': 'red', 't_LAND': 'purple', 't_zmin_land': 'brown'}.get(ev_name, 'gray')
            ax.axvline(t, color=color, ls='--', alpha=0.6, label=ev_name if i == 0 else None)
        t_on = onset_per.get(jname)
        if t_on is not None and not np.isnan(t_on):
            ax.axvline(t_on, color='green', ls='-', alpha=0.8, lw=1.2, label='onset' if i == 0 else None)
        title = jname
        T_ecc = T_ecc_per.get(jname)
        if T_ecc is not None and not np.isnan(T_ecc) and jump_type == 'CMJ':
            title += f" | T_ecc={1000*T_ecc:.0f}ms"
        if t_on is not None and not np.isnan(t_on):
            title += f"\nonset={t_on:.2f}s"
        ax.set_title(title, fontsize=9)
        if jname in peaks_takeoff:
            t_p, v_p, dt_z = peaks_takeoff[jname]
            if t_p is not None and v_p is not None:
                ax.axvline(t_p, color='cyan', ls=':', alpha=0.8)
                ax.plot(t_p, np.degrees(v_p), 'co', ms=7)
                if dt_z is not None and not np.isnan(dt_z) and jump_type == 'CMJ':
                    ax.annotate(f"Δt_zmin={1000*dt_z:.0f}ms", xy=(t_p, np.degrees(v_p)), xytext=(5, 5),
                                textcoords='offset points', fontsize=7, color='darkblue')
        if jname in peaks_landing and peaks_landing[jname][0] is not None:
            t_p, v_p = peaks_landing[jname]
            if v_p is not None:
                ax.axvline(t_p, color='magenta', ls=':', alpha=0.8)
                ax.plot(t_p, np.degrees(v_p), 'mo', ms=6)
        ax.set_ylabel('deg')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=5)
    fig.suptitle(f'Joint angles (baseline ref, 0° = standing) — {jump_type} — {filename}', fontsize=12)
    plt.tight_layout()
    basename = filename.replace('.tsv', '').replace('.csv', '')
    out = output_path / f"joints_{jump_type}_{basename}.png"
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out.name}")


def process_one_file(file_info: dict, output_path: Path):
    """Obrada jednog fajla: ugao -> peak flexion -> plot."""
    df = load_processed_file(file_info['filepath'])
    if df is None:
        return False
    jump_type = file_info['JumpType']
    filename = file_info['filename']
    # Proveri da li imamo potrebne markere
    req = ['left_hip_pos_X', 'left_knee_pos_X', 'left_ankle_pos_X', 'left_heel_pos_X',
           'left_small_toe_pos_X', 'left_shoulder_pos_X']
    if not all(c in df.columns for c in req):
        print(f"  [SKIP] {filename}: nedostaju marker kolone")
        return False
    # Time
    if 'Time' in df.columns:
        time = df['Time'].values
        valid = ~np.isnan(time)
        if np.sum(valid) > 1:
            fs = 1.0 / np.mean(np.diff(time[valid]))
        else:
            fs = 300.0
            time = np.arange(len(df)) / fs
    else:
        fs = 300.0
        time = np.arange(len(df)) / fs
    # KPIs za evente (globalni)
    kpis = calculate_kpis(df, jump_type, '3D', file_info)
    t_zmin = kpis.get('t_zmin', np.nan)
    t_to = kpis.get('t_TO', np.nan)
    t_land = kpis.get('t_LAND', np.nan)
    t_zmin_land = kpis.get('t_zmin_land', np.nan)
    if jump_type == 'SJ':
        t_zmin = kpis.get('t_start', np.nan)  # SJ nema zmin
    events = {'t_zmin': t_zmin, 't_TO': t_to, 't_LAND': t_land, 't_zmin_land': t_zmin_land}
    t_to_s = t_to if not np.isnan(t_to) else time[-1]
    t_land_s = t_land if not np.isnan(t_land) else time[-1]
    t_zmin_land_s = t_zmin_land if not np.isnan(t_zmin_land) else time[-1]
    search_end = min(2.2, t_to_s - 0.1) if not np.isnan(t_to) else 2.2

    # Segment uglovi
    theta = {}
    for seg in SEGMENTS:
        theta[seg] = compute_segment_angle(df, seg)
    baseline_n = int(0.4 * fs)
    phi = compute_joint_angle(df, theta, baseline_n)

    # Onset i T_ecc za svaki ugao (iz |ω|)
    onset_seg = {}
    T_ecc_seg = {}
    onset_joint = {}
    T_ecc_joint = {}
    for seg in theta:
        omega = compute_omega(theta[seg], time)
        s = np.abs(omega)
        t_on = detect_onset_for_signal(s, time, fs, search_end=search_end)
        onset_seg[seg] = t_on
        if t_on is not None and not np.isnan(t_zmin) and jump_type == 'CMJ':
            T_ecc_seg[seg] = t_zmin - t_on
        else:
            T_ecc_seg[seg] = None
    for jname in phi:
        omega = compute_omega(phi[jname], time)
        s = np.abs(omega)
        t_on = detect_onset_for_signal(s, time, fs, search_end=search_end)
        onset_joint[jname] = t_on
        if t_on is not None and not np.isnan(t_zmin) and jump_type == 'CMJ':
            T_ecc_joint[jname] = t_zmin - t_on
        else:
            T_ecc_joint[jname] = None

    # Peak flexion po uglu – interval [t_onset_angle .. t_TO]
    peaks_takeoff_seg = {}
    peaks_landing_seg = {}
    peaks_takeoff_joint = {}
    peaks_landing_joint = {}
    for seg in theta:
        t_start_seg = onset_seg.get(seg) or time[0]
        if t_start_seg is not None and t_start_seg > t_to_s:
            t_start_seg = time[0]
        tp, vp = find_peak_flexion_in_interval(theta[seg], time, t_start_seg, t_to_s, maximize=False)
        dt_z = (tp - t_zmin) if tp is not None and not np.isnan(t_zmin) and jump_type == 'CMJ' else None
        peaks_takeoff_seg[seg] = (tp, vp, dt_z)
        tp2, vp2 = find_peak_flexion_in_interval(theta[seg], time, t_land_s, t_zmin_land_s, maximize=False)
        peaks_landing_seg[seg] = (tp2, vp2)
    for jname in phi:
        t_start_j = onset_joint.get(jname) or time[0]
        if t_start_j is not None and t_start_j > t_to_s:
            t_start_j = time[0]
        tp, vp = find_peak_flexion_in_interval(phi[jname], time, t_start_j, t_to_s, maximize=True)
        dt_z = (tp - t_zmin) if tp is not None and not np.isnan(t_zmin) and jump_type == 'CMJ' else None
        peaks_takeoff_joint[jname] = (tp, vp, dt_z)
        tp2, vp2 = find_peak_flexion_in_interval(phi[jname], time, t_land_s, t_zmin_land_s, maximize=True)
        peaks_landing_joint[jname] = (tp2, vp2)

    plot_segment_angles(df, time, theta, events, onset_seg, T_ecc_seg,
                        peaks_takeoff_seg, peaks_landing_seg,
                        jump_type, filename, output_path)
    plot_joint_angles(df, time, phi, events, onset_joint, T_ecc_joint,
                      peaks_takeoff_joint, peaks_landing_joint,
                      jump_type, filename, output_path)
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kontrolni plotovi uglova (segmenti, zglobovi)")
    parser.add_argument("--limit", type=int, default=None, help="Max broj fajlova (default: svi)")
    parser.add_argument("--sj-only", action="store_true", help="Samo SJ fajlovi")
    parser.add_argument("--cmj-only", action="store_true", help="Samo CMJ fajlovi")
    args = parser.parse_args()

    base = Path(__file__).parent
    proc_dir = base / "processed_data"
    if not proc_dir.exists():
        proc_dir = Path(r"C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI\processed_data")
    if not proc_dir.exists():
        print("[ERROR] processed_data nije pronađen")
        return 1
    import config as qconfig
    qconfig.PROCESSED_DATA_DIR = proc_dir
    output_path = base / "Output" / "Plots_Angles"
    output_path.mkdir(parents=True, exist_ok=True)
    print(f"Output: {output_path}")
    files = discover_processed_files(proc_dir)
    all_files = []
    if not args.cmj_only:
        all_files.extend(files['SJ'])
    if not args.sj_only:
        all_files.extend(files['CMJ'])
    if args.limit:
        # Interleave SJ i CMJ da oba budu zastupljena
        sj_list = files['SJ'] if not args.cmj_only else []
        cmj_list = files['CMJ'] if not args.sj_only else []
        interleaved = []
        for i in range(max(len(sj_list), len(cmj_list))):
            if i < len(sj_list):
                interleaved.append(sj_list[i])
            if i < len(cmj_list):
                interleaved.append(cmj_list[i])
        all_files = interleaved[:args.limit]
    n_ok = 0
    for fi in all_files:
        print(f"Processing {fi['filename']}...")
        if process_one_file(fi, output_path):
            n_ok += 1
    print(f"\nZavršeno: {n_ok}/{len(all_files)} fajlova")
    return 0


if __name__ == "__main__":
    sys.exit(main())
