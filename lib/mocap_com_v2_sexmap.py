"""
mocap_com.py
------------
Compute whole-body Center of Mass (CoM) from Qualisys-exported marker TSVs
using a reduced de Leva (1996) segmental model that matches the marker set:

- Upper body (UB) as one lumped segment: HipMid -> ShoulderMid
- Lower limbs (L/R): thigh (Hip->Knee), shank (Knee->Ankle), foot (Ankle->ToeMid)

Outputs:
- CoM3D_X, CoM3D_Y, CoM3D_Z
- CoM2DL_X, CoM2DL_Z  (planar model using left side + mirrored mass)
- CoM2DR_X, CoM2DR_Z  (planar model using right side + mirrored mass)

Notes:
- Qualisys markers are typically in millimeters; this module auto-detects and converts to meters.
- 2D models are computed in the sagittal plane (X-Z), assuming Y is mediolateral.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import re
import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Anthropometric parameters (de Leva, 1996; Adjusted Zatsiorsky–Seluyanov as in Visual3D)
# Stored as mass fractions (mu) and COM location fractions (lambda) from proximal to distal.
# -----------------------------------------------------------------------------
DELEVA: Dict[str, Dict[str, Dict[str, float]]] = {
    "female": {
        "mass": {"trunk": 0.4257, "thigh": 0.1478, "shank": 0.0481, "foot": 0.0129},
        "com":  {"trunk": 0.4964, "thigh": 0.3612, "shank": 0.4352, "foot": 0.4014},
    },
    "male": {
        "mass": {"trunk": 0.4346, "thigh": 0.1416, "shank": 0.0433, "foot": 0.0137},
        "com":  {"trunk": 0.5138, "thigh": 0.4095, "shank": 0.4395, "foot": 0.4415},
    },
}



# -----------------------------------------------------------------------------
# Subject sex mapping (provided by user)
# - Files use two-digit SubjectID in filename (e.g., 02_4_1.tsv -> SubjectID=2).
# - If SubjectID is not in either set, the code will fall back to a default and flag it.
# -----------------------------------------------------------------------------
FEMALE_SUBJECT_IDS = {6, 8, 9, 10, 12, 14}
MALE_SUBJECT_IDS   = {1, 2, 3, 5, 7, 13}

def sex_from_subject_id(subject_id: int | str):
    """Map SubjectID -> sex using the provided groups.
    Returns 'female', 'male', or None (unknown).
    """
    try:
        sid = int(str(subject_id).lstrip('0') or '0')
    except Exception:
        return None
    if sid in FEMALE_SUBJECT_IDS:
        return 'female'
    if sid in MALE_SUBJECT_IDS:
        return 'male'
    return None

def parse_subject_id_from_filename(name: str):
    """Parse SubjectID from filenames like '02_4_1.tsv' or '02_4_1_processed.csv'."""
    m = re.match(r'^(?P<id>\d+)_\d+_\d+_processed\.(csv|tsv)$', name)
    if not m:
        m = re.match(r'^(?P<id>\d+)_\d+_\d+\.(csv|tsv)$', name)
    if not m:
        return None
    try:
        return int(m.group('id').lstrip('0') or '0')
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Column mapping for your Qualisys TSV
# -----------------------------------------------------------------------------
MARKER_PREFIX = {
    "shoulder": {"L": "left_shoulder_pos", "R": "right_shoulder_pos"},
    "hip":      {"L": "left_hip_pos",      "R": "right_hip_pos"},
    "knee":     {"L": "left_knee_pos",     "R": "right_knee_pos"},
    "ankle":    {"L": "left_ankle_pos",    "R": "right_ankle_pos"},
    "big_toe":  {"L": "left_big_toe_pos",  "R": "right_big_toe_pos"},
    "small_toe":{"L": "left_small_toe_pos","R": "right_small_toe_pos"},
    "heel":     {"L": "left_heel_pos",     "R": "right_heel_pos"},
}

AXES_3D = ("X", "Y", "Z")


@dataclass(frozen=True)
class QualisysMeta:
    fs_hz: Optional[float] = None
    header_line_idx: Optional[int] = None  # 0-based index of the "Frame\tTime..." line


def _cols(prefix: str, axes=AXES_3D) -> List[str]:
    return [f"{prefix}_{a}" for a in axes]


def read_qualisys_tsv(path: str | Path) -> Tuple[pd.DataFrame, QualisysMeta]:
    """
    Reads a Qualisys-exported TSV with a metadata header.
    Automatically finds the header line starting with "Frame\tTime\t"
    and extracts FREQUENCY as sampling rate (fs).

    Returns: (df, meta)
    """
    path = Path(path)
    header_idx: Optional[int] = None
    fs: Optional[float] = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if line.startswith("FREQUENCY"):
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    try:
                        fs = float(parts[1])
                    except Exception:
                        fs = fs
            if line.startswith("Frame\tTime\t"):
                header_idx = i
                break

    if header_idx is None:
        raise ValueError(f"Cannot find Qualisys column header in: {path.name}")

    df = pd.read_csv(path, sep="\t", skiprows=header_idx, header=0)
    meta = QualisysMeta(fs_hz=fs, header_line_idx=header_idx)
    return df, meta


def ensure_meters(df: pd.DataFrame, marker_like: str = "_pos_") -> Tuple[pd.DataFrame, bool]:
    """
    Convert marker coordinates from mm to m if needed.
    Heuristic: if median(|pos|) across *_pos_[XYZ] columns > 10, assume mm.

    Returns: (df_out, converted_bool)
    """
    out = df.copy()
    pos_cols = [c for c in out.columns if marker_like in c and c.endswith(("_X", "_Y", "_Z"))]
    if not pos_cols:
        return out, False

    arr = out[pos_cols].to_numpy(dtype=float)
    med = float(np.nanmedian(np.abs(arr)))
    if med > 10.0:  # likely mm
        out[pos_cols] = out[pos_cols] / 1000.0
        return out, True
    return out, False


def _marker_exists(df: pd.DataFrame, marker: str, side: str) -> bool:
    prefix = MARKER_PREFIX[marker][side]
    cols = _cols(prefix, AXES_3D)
    return all(c in df.columns for c in cols)


def get_marker(df: pd.DataFrame, marker: str, side: str) -> np.ndarray:
    """
    Return Nx3 marker coordinates for marker + side.
    Raises KeyError if missing.
    """
    prefix = MARKER_PREFIX[marker][side]
    cols = _cols(prefix, AXES_3D)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for {marker}_{side}: {missing}")
    return df[cols].to_numpy(dtype=float)


def midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return 0.5 * (a + b)


def segment_com(P: np.ndarray, D: np.ndarray, lam: float) -> np.ndarray:
    return P + lam * (D - P)


def compute_com_3d(
    df_in: pd.DataFrame,
    sex: str = "male",
    ub_lambda: Optional[float] = None,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Compute 3D CoM (reduced model: UB + both legs).

    UB is defined along HipMid -> ShoulderMid (lumped upper body).
    ub_lambda defaults to trunk lambda (de Leva) unless overridden.
    UB mass is the remainder: 1 - 2*(mu_thigh + mu_shank + mu_foot).

    Returns: (df_out, qc_flags)
    """
    qc: Dict[str, str] = {}
    sex = sex.lower().strip()
    if sex not in DELEVA:
        raise ValueError("sex must be 'male' or 'female'")

    p = DELEVA[sex]
    mu_th = p["mass"]["thigh"]
    mu_sh = p["mass"]["shank"]
    mu_ft = p["mass"]["foot"]
    lam_th = p["com"]["thigh"]
    lam_sh = p["com"]["shank"]
    lam_ft = p["com"]["foot"]

    mu_ub = 1.0 - 2.0 * (mu_th + mu_sh + mu_ft)
    lam_ub = p["com"]["trunk"] if ub_lambda is None else float(ub_lambda)

    # Required markers for 3D model
    required = [
        ("hip", "L"), ("hip", "R"),
        ("shoulder", "L"), ("shoulder", "R"),
        ("knee", "L"), ("knee", "R"),
        ("ankle", "L"), ("ankle", "R"),
        ("big_toe", "L"), ("big_toe", "R"),
        ("small_toe", "L"), ("small_toe", "R"),
    ]
    missing = [(m, s) for (m, s) in required if not _marker_exists(df_in, m, s)]
    if missing:
        qc["missing_markers_3d"] = ", ".join([f"{m}{s}" for (m, s) in missing])
        # output NaNs
        out = df_in.copy()
        out["CoM3D_X"] = np.nan
        out["CoM3D_Y"] = np.nan
        out["CoM3D_Z"] = np.nan
        return out, qc

    hip_L = get_marker(df_in, "hip", "L")
    hip_R = get_marker(df_in, "hip", "R")
    sh_L  = get_marker(df_in, "shoulder", "L")
    sh_R  = get_marker(df_in, "shoulder", "R")
    knee_L  = get_marker(df_in, "knee", "L")
    knee_R  = get_marker(df_in, "knee", "R")
    ankle_L = get_marker(df_in, "ankle", "L")
    ankle_R = get_marker(df_in, "ankle", "R")

    bt_L = get_marker(df_in, "big_toe", "L")
    st_L = get_marker(df_in, "small_toe", "L")
    bt_R = get_marker(df_in, "big_toe", "R")
    st_R = get_marker(df_in, "small_toe", "R")

    hip_mid = midpoint(hip_L, hip_R)
    sh_mid  = midpoint(sh_L, sh_R)
    toe_mid_L = midpoint(bt_L, st_L)
    toe_mid_R = midpoint(bt_R, st_R)

    r_ub   = segment_com(hip_mid, sh_mid, lam_ub)
    r_th_L = segment_com(hip_L, knee_L, lam_th)
    r_th_R = segment_com(hip_R, knee_R, lam_th)
    r_sh_L = segment_com(knee_L, ankle_L, lam_sh)
    r_sh_R = segment_com(knee_R, ankle_R, lam_sh)
    r_ft_L = segment_com(ankle_L, toe_mid_L, lam_ft)
    r_ft_R = segment_com(ankle_R, toe_mid_R, lam_ft)

    mu_sum = mu_ub + 2.0 * (mu_th + mu_sh + mu_ft)
    com3d = (
        mu_ub * r_ub
        + mu_th * (r_th_L + r_th_R)
        + mu_sh * (r_sh_L + r_sh_R)
        + mu_ft * (r_ft_L + r_ft_R)
    ) / mu_sum

    out = df_in.copy()
    out["CoM3D_X"] = com3d[:, 0]
    out["CoM3D_Y"] = com3d[:, 1]
    out["CoM3D_Z"] = com3d[:, 2]
    return out, qc


def compute_com_2d_one_side(
    df_in: pd.DataFrame,
    side: str,
    sex: str = "male",
    ub_lambda: Optional[float] = None,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Compute 2D CoM (sagittal plane X-Z) using one side + mirrored mass (symmetry).
    UB is still computed from HipMid->ShoulderMid if both sides exist;
    if not, falls back to that side's Hip->Shoulder.

    Outputs:
      - For side 'L': CoM2DL_X, CoM2DL_Z
      - For side 'R': CoM2DR_X, CoM2DR_Z
    """
    qc: Dict[str, str] = {}
    side = side.upper().strip()
    if side not in ("L", "R"):
        raise ValueError("side must be 'L' or 'R'")
    sex = sex.lower().strip()
    if sex not in DELEVA:
        raise ValueError("sex must be 'male' or 'female'")

    p = DELEVA[sex]
    mu_th = p["mass"]["thigh"]
    mu_sh = p["mass"]["shank"]
    mu_ft = p["mass"]["foot"]
    lam_th = p["com"]["thigh"]
    lam_sh = p["com"]["shank"]
    lam_ft = p["com"]["foot"]

    mu_ub = 1.0 - 2.0 * (mu_th + mu_sh + mu_ft)
    lam_ub = p["com"]["trunk"] if ub_lambda is None else float(ub_lambda)

    # UB: prefer midpoints (more stable); fallback to chosen side if needed
    use_midpoints = _marker_exists(df_in, "hip", "L") and _marker_exists(df_in, "hip", "R") and \
                    _marker_exists(df_in, "shoulder", "L") and _marker_exists(df_in, "shoulder", "R")

    if use_midpoints:
        hip_mid = midpoint(get_marker(df_in, "hip", "L"), get_marker(df_in, "hip", "R"))
        sh_mid  = midpoint(get_marker(df_in, "shoulder", "L"), get_marker(df_in, "shoulder", "R"))
        r_ub = segment_com(hip_mid, sh_mid, lam_ub)
    else:
        # fallback: UB approximated from that side Hip->Shoulder
        if not (_marker_exists(df_in, "hip", side) and _marker_exists(df_in, "shoulder", side)):
            qc["missing_markers_ub_2d"] = f"hip{side}/shoulder{side}"
            out = df_in.copy()
            colx = "CoM2DL_X" if side == "L" else "CoM2DR_X"
            colz = "CoM2DL_Z" if side == "L" else "CoM2DR_Z"
            out[colx] = np.nan
            out[colz] = np.nan
            return out, qc
        r_ub = segment_com(get_marker(df_in, "hip", side), get_marker(df_in, "shoulder", side), lam_ub)

    # Required one-side lower-limb markers
    required = [("hip", side), ("knee", side), ("ankle", side), ("big_toe", side), ("small_toe", side)]
    missing = [(m, s) for (m, s) in required if not _marker_exists(df_in, m, s)]
    if missing:
        qc["missing_markers_2d"] = ", ".join([f"{m}{s}" for (m, s) in missing])
        out = df_in.copy()
        colx = "CoM2DL_X" if side == "L" else "CoM2DR_X"
        colz = "CoM2DL_Z" if side == "L" else "CoM2DR_Z"
        out[colx] = np.nan
        out[colz] = np.nan
        return out, qc

    hip   = get_marker(df_in, "hip", side)
    knee  = get_marker(df_in, "knee", side)
    ankle = get_marker(df_in, "ankle", side)
    bt    = get_marker(df_in, "big_toe", side)
    st    = get_marker(df_in, "small_toe", side)
    toe_mid = midpoint(bt, st)

    r_th = segment_com(hip, knee, lam_th)
    r_sh = segment_com(knee, ankle, lam_sh)
    r_ft = segment_com(ankle, toe_mid, lam_ft)

    mu_sum = mu_ub + 2.0 * (mu_th + mu_sh + mu_ft)
    com = (mu_ub * r_ub + 2.0 * (mu_th * r_th + mu_sh * r_sh + mu_ft * r_ft)) / mu_sum

    # Keep only X and Z for 2D outputs
    out = df_in.copy()
    colx = "CoM2DL_X" if side == "L" else "CoM2DR_X"
    colz = "CoM2DL_Z" if side == "L" else "CoM2DR_Z"
    out[colx] = com[:, 0]
    out[colz] = com[:, 2]
    return out, qc


def add_com_columns(
    df_raw: pd.DataFrame,
    sex: str = "male",
    ub_lambda: Optional[float] = None,
    auto_units: bool = True,
    subject_id: int | str | None = None,
    default_sex_if_unknown: str = "male",
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Convenience wrapper:
      - optional mm->m conversion
      - CoM3D + CoM2DL + CoM2DR

    Returns: (df_out, qc_flags)
    """
    qc: Dict[str, str] = {}

    # If subject_id is provided, override sex using the user-provided mapping.
    if subject_id is not None:
        mapped = sex_from_subject_id(subject_id)
        if mapped is None:
            sex = default_sex_if_unknown
            qc["sex_source"] = "default_unknown"
        else:
            sex = mapped
            qc["sex_source"] = "subject_map"
        qc["sex_used"] = sex

    df = df_raw.copy()
    if auto_units:
        df, converted = ensure_meters(df)
        qc["units_mm_to_m"] = "1" if converted else "0"

    df, qc3d = compute_com_3d(df, sex=sex, ub_lambda=ub_lambda)
    qc.update({f"3d_{k}": v for k, v in qc3d.items()})

    df, qc2dl = compute_com_2d_one_side(df, side="L", sex=sex, ub_lambda=ub_lambda)
    qc.update({f"2dl_{k}": v for k, v in qc2dl.items()})

    df, qc2dr = compute_com_2d_one_side(df, side="R", sex=sex, ub_lambda=ub_lambda)
    qc.update({f"2dr_{k}": v for k, v in qc2dr.items()})

    return df, qc


if __name__ == "__main__":
    # Simple sanity check on the provided sample file path (edit as needed)
    sample = Path("02_4_1.tsv")
    if sample.exists():
        df0, meta = read_qualisys_tsv(sample)
        sid = parse_subject_id_from_filename(sample.name)
        df1, qc = add_com_columns(df0, subject_id=sid, default_sex_if_unknown="male")
        print("Fs:", meta.fs_hz, "rows:", len(df1))
        print("QC:", qc)
        print(df1[["Time", "CoM3D_Z", "CoM2DL_Z", "CoM2DR_Z"]].head())
