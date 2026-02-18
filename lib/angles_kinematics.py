"""
Modul za računanje kinematičkih KPIs: uglovi, ω, onset po kandidatu, ROM, peak flexion.
Koristi se u kpi_calculator za 3D model (zahteva markere).
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
import config

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

JOINTS = {
    'ankle_L': ('foot_L', 'shank_L'),
    'knee_L': ('shank_L', 'thigh_L'),
    'hip_L': ('thigh_L', 'trunk_L'),
    'ankle_R': ('foot_R', 'shank_R'),
    'knee_R': ('shank_R', 'thigh_R'),
    'hip_R': ('thigh_R', 'trunk_R'),
}

JOINT_NAMES = ['ankle_L', 'knee_L', 'hip_L', 'ankle_R', 'knee_R', 'hip_R']
SEGMENT_NAMES = list(SEGMENTS.keys())


def _get_marker_pos(df: pd.DataFrame, name: str) -> Tuple[np.ndarray, np.ndarray]:
    cx, cz = MARKERS[name]
    if cx not in df.columns or cz not in df.columns:
        return np.full(len(df), np.nan), np.full(len(df), np.nan)
    x = pd.Series(df[cx].values).ffill().bfill().values
    z = pd.Series(df[cz].values).ffill().bfill().values
    return x, z


def _segment_angle(df: pd.DataFrame, seg_name: str) -> np.ndarray:
    prox, dist = SEGMENTS[seg_name]
    xp, zp = _get_marker_pos(df, prox)
    xd, zd = _get_marker_pos(df, dist)
    dx, dz = xd - xp, zd - zp
    return np.arctan2(dx, dz)


def _wrap(phi: np.ndarray) -> np.ndarray:
    return np.arctan2(np.sin(phi), np.cos(phi))


def _joint_angle(theta: Dict[str, np.ndarray], baseline_n: int, n: int) -> Dict[str, np.ndarray]:
    out = {}
    for jname, (seg1, seg2) in JOINTS.items():
        if seg1 not in theta or seg2 not in theta:
            out[jname] = np.full(n, np.nan)
            continue
        phi = theta[seg2] - theta[seg1]
        phi = _wrap(phi)
        base = phi[:min(baseline_n, len(phi))]
        base = base[~np.isnan(base)]
        if len(base) > 0:
            phi = phi - np.median(base)
        out[jname] = _wrap(phi)
    return out


def _omega(angle: np.ndarray, time: np.ndarray) -> np.ndarray:
    return np.gradient(angle, time)


def _detect_onset(s: np.ndarray, time: np.ndarray, fs: float,
                  search_end: Optional[float] = None) -> Optional[float]:
    n_persist = max(1, int(0.08 * fs))
    n_base_start = int(config.ONSET_EXCLUDE_START_S * fs)  # preskoci pocetak (problemi markera)
    n_base_len = int(1.0 * fs)
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
    s_post = s[n_base_end:]
    s_post = s_post[~np.isnan(s_post)]
    max_post = np.max(s_post) if len(s_post) > 0 else 0
    T_s = max(6 * sigma, 0.02 * max_post)
    idx_end = np.argmin(np.abs(time - search_end)) if search_end else len(s) - n_persist
    for i in range(n_base_end, min(idx_end, len(s) - n_persist)):
        if np.all(s[i:i + n_persist] > T_s):
            return float(time[i])
    return None


def _angle_at_time(angle_arr: np.ndarray, time: np.ndarray, t: float) -> Optional[float]:
    if t is None or (isinstance(t, float) and np.isnan(t)):
        return None
    idx = np.argmin(np.abs(time - t))
    return float(angle_arr[idx])


def _find_peak(arr: np.ndarray, time: np.ndarray, t_start: float, t_end: float,
               maximize: bool) -> Tuple[Optional[float], Optional[float]]:
    mask = (time >= t_start) & (time <= t_end)
    if not np.any(mask):
        return None, None
    sub = arr[mask]
    sub_t = time[mask]
    valid = ~np.isnan(sub)
    if not np.any(valid):
        return None, None
    sub, sub_t = sub[valid], sub_t[valid]
    idx = np.argmax(sub) if maximize else np.argmin(sub)
    return float(sub_t[idx]), float(sub[idx])


def compute_angle_kpis(df: pd.DataFrame, time: np.ndarray, fs: float,
                       t_start: float, t_zmin: float, t_to: float,
                       jump_type: str, com_col: str, vz_col: str) -> Dict[str, Any]:
    """
    Računa sve kinematičke KPIs za 3D model.
    Vraća dict sa ključevima za Excel (deg gde je ugao).
    """
    req = ['left_hip_pos_X', 'left_knee_pos_X', 'left_ankle_pos_X', 'left_heel_pos_X',
           'left_small_toe_pos_X', 'left_shoulder_pos_X']
    if not all(c in df.columns for c in req):
        return {}

    baseline_n = int(0.4 * fs)
    search_end = min(2.2, t_to - 0.1) if not np.isnan(t_to) else 2.2

    # Segment i joint uglovi
    theta = {s: _segment_angle(df, s) for s in SEGMENT_NAMES}
    phi = _joint_angle(theta, baseline_n, len(df))

    # vCoM (sagitalna brzina)
    vcom_s = np.full(len(time), np.nan)
    if 'CoM3D_X' in df.columns and 'CoM3D_Z' in df.columns:
        com_x = pd.Series(df['CoM3D_X'].values).ffill().bfill().values
        com_z = pd.Series(df['CoM3D_Z'].values).ffill().bfill().values
        if np.nanmax(np.abs(com_x)) > 10 or np.nanmax(np.abs(com_z)) > 10:
            com_x, com_z = com_x / 1000.0, com_z / 1000.0
        vx = np.gradient(com_x, time)
        vz = np.gradient(com_z, time)
        vcom_s = np.sqrt(vx**2 + vz**2)

    # vPelvis
    vpelvis_s = np.full(len(time), np.nan)
    xl, zl = _get_marker_pos(df, 'hip_L')
    xr, zr = _get_marker_pos(df, 'hip_R')
    if not (np.all(np.isnan(xl)) or np.all(np.isnan(xr))):
        if np.nanmax(np.abs(xl)) > 10:
            xl, zl, xr, zr = xl/1000, zl/1000, xr/1000, zr/1000
        px = 0.5 * (xl + xr)
        pz = 0.5 * (zl + zr)
        vpx = np.gradient(px, time)
        vpz = np.gradient(pz, time)
        vpelvis_s = np.sqrt(vpx**2 + vpz**2)

    # Onset po kandidatu
    out = {}
    candidates = {}

    if not np.all(np.isnan(vcom_s)):
        t_on = _detect_onset(vcom_s, time, fs, search_end)
        candidates['vCoM'] = t_on
    t_on_vz = _detect_onset(np.abs(df[vz_col].values), time, fs, search_end)
    candidates['vzCoM'] = t_on_vz
    if not np.all(np.isnan(vpelvis_s)):
        t_on = _detect_onset(vpelvis_s, time, fs, search_end)
        candidates['vPelvis'] = t_on

    for seg in SEGMENT_NAMES:
        omega = _omega(theta[seg], time)
        t_on = _detect_onset(np.abs(omega), time, fs, search_end)
        candidates[f'omega_{seg}'] = t_on
    for jname in JOINT_NAMES:
        omega = _omega(phi[jname], time)
        t_on = _detect_onset(np.abs(omega), time, fs, search_end)
        candidates[f'omega_{jname}'] = t_on

    for k, v in candidates.items():
        out[f't_onset_{k}'] = v

    # T_downward, T_upward, TTO (CoM-based)
    out['T_downward'] = (t_zmin - t_start) if not np.isnan(t_zmin) and not np.isnan(t_start) and jump_type == 'CMJ' else np.nan
    out['T_upward'] = (t_to - t_zmin) if not np.isnan(t_zmin) and not np.isnan(t_to) and jump_type == 'CMJ' else np.nan
    if jump_type == 'CMJ' and not np.isnan(out.get('T_downward', np.nan)) and not np.isnan(out.get('T_upward', np.nan)):
        out['TTO'] = out['T_downward'] + out['T_upward']
    else:
        out['TTO'] = (t_to - t_start) if not np.isnan(t_to) and not np.isnan(t_start) else np.nan

    t_to_s = t_to if not np.isnan(t_to) else time[-1]
    t_zmin_s = t_zmin if not np.isnan(t_zmin) else t_start

    # t_peakFlex, ROM_onset_to_peak, angles at events
    for jname in JOINT_NAMES:
        t_on = candidates.get(f'omega_{jname}') or time[0]
        if t_on is None:
            t_on = time[0]
        t_start_j = max(t_on, time[0])
        tp, vp = _find_peak(phi[jname], time, t_start_j, t_to_s, maximize=True)
        out[f't_peakFlex_{jname}'] = tp
        out[f'peakFlex_{jname}_deg'] = np.degrees(vp) if vp is not None else np.nan
        out[f'dt_peak_to_zmin_{jname}'] = (tp - t_zmin) if tp is not None and not np.isnan(t_zmin) and jump_type == 'CMJ' else np.nan
        ang_on = _angle_at_time(phi[jname], time, t_on) if t_on else None
        ang_peak = vp
        rom = np.abs(ang_peak - ang_on) if ang_peak is not None and ang_on is not None else np.nan
        out[f'ROM_onset_to_peak_{jname}_deg'] = np.degrees(rom) if not np.isnan(rom) else np.nan
        out[f'angle_at_onset_{jname}_deg'] = np.degrees(ang_on) if ang_on is not None else np.nan
        out[f'angle_at_zmin_{jname}_deg'] = np.degrees(_angle_at_time(phi[jname], time, t_zmin)) if not np.isnan(t_zmin) else np.nan
        out[f'angle_at_TO_{jname}_deg'] = np.degrees(_angle_at_time(phi[jname], time, t_to)) if not np.isnan(t_to) else np.nan

    # Segment angles at events
    for seg in SEGMENT_NAMES:
        out[f'seg_at_zmin_{seg}_deg'] = np.degrees(_angle_at_time(theta[seg], time, t_zmin)) if not np.isnan(t_zmin) else np.nan
        out[f'seg_at_TO_{seg}_deg'] = np.degrees(_angle_at_time(theta[seg], time, t_to)) if not np.isnan(t_to) else np.nan

    return out
