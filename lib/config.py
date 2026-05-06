"""
Konfiguracija za KPI izračunavanje iz processed fajlova.
Putanje: iz paths_config u korenu projekta (DATA_ROOT = cloud, PROJECT_ROOT).
"""
import os
import sys
from pathlib import Path

# Ukljuci koren projekta u path da može import paths_config
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from paths_config import (
        DATA_ROOT, PROJECT_ROOT,
        PROCESSED_DATA_DIR, OUTPUT_DIR, EXCEL_DIR,
    )
    LOG_DIR = OUTPUT_DIR / "Logs"
except ImportError:
    # Fallback: sve u korenu projekta (za prvu instalaciju pre kopiranja paths_config)
    PROJECT_ROOT = _PROJECT_ROOT
    DATA_ROOT = _PROJECT_ROOT
    PROCESSED_DATA_DIR = DATA_ROOT / "processed_data"
    OUTPUT_DIR = PROJECT_ROOT / "Output"
    EXCEL_DIR = OUTPUT_DIR / "Excel"
    LOG_DIR = OUTPUT_DIR / "Logs"

# Kreiraj direktorijume ako ne postoje
EXCEL_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Output fajlovi
EXCEL_OUTPUT_FILE = EXCEL_DIR / "MoCap_KPIs.xlsx"
LOG_FILE = LOG_DIR / "run.log"

# ==================== EVENT DETECTION PARAMETERS ====================
T_BASE = 0.4
DZ_CONTACT = 0.015
N_HOLD_MS = 20
FS_DEFAULT = 300

N_QUIET_MS = 50
N_ON_MS = 30
DISPLACEMENT_GATE_MM = 2
ONSET_EXCLUDE_START_S = 0.2

V_THR = 0.05
MIN_FLIGHT_TIME = 0.10
W_LAND = 0.6

ALPHA_DIP_MM = 3
MIN_DIP_DEPTH_MM = 10
MIN_DIP_TIME = 0.08
MIN_DIP_VELOCITY = -0.10
CMJ_LIKE_DEPTH_MM = 20
CMJ_LIKE_TIME = 0.12

G = 9.81

# ==================== COLUMN NAMES ====================
COM_3D_COL = "CoM3D_Z"
COM_2DL_COL = "CoM2DL_Z"
COM_2DR_COL = "CoM2DR_Z"

VZ_3D_COL = "V_z_3D"
VZ_2DL_COL = "V_z_2DL"
VZ_2DR_COL = "V_z_2DR"

TIME_COL = "Time"

LEFT_TOE_COLS = {
    'small_toe': 'left_small_toe_pos_Z',
    'big_toe': 'left_big_toe_pos_Z',
    'heel': 'left_heel_pos_Z'
}

RIGHT_TOE_COLS = {
    'small_toe': 'right_small_toe_pos_Z',
    'big_toe': 'right_big_toe_pos_Z',
    'heel': 'right_heel_pos_Z'
}

# ==================== EXCEL SETTINGS ====================
SHEET_NAMES = {
    'SJ': ['SJ3D', 'SJ2DL', 'SJ2DR'],
    'CMJ': ['CMJ3D', 'CMJ2DL', 'CMJ2DR']
}

EXCEL_COLUMNS_BASE = [
    'FileName', 'TrialID', 'SubjectID', 'TrialNo', 'Fs_used', 'Duration_s',
    't_start', 't_zmin', 't_TO', 't_LAND', 't_apex', 't_zmin_land',
    'T_downward', 'T_upward', 'TTO', 'T_flight',
    'T_ecc', 'T_con', 'T_takeoff', 'T_con_strict', 'T_takeoff_obs',
    'Depth_CMJ', 'vmin_pre', 'vmax_pre', 'vTO',
    'hCoM', 'hCoM_max_TO', 'hCoM_onset_corr', 'hCoM_upright_ref', 'hCoM_ankle_corr', 'hv', 'hFT',
    't_start_hip', 't_zmin_hip', 'T_downward_hip', 'T_upward_hip', 'TTO_hip',
    'vmin_pre_hip', 'vmax_pre_hip', 'vTO_hip', 'Depth_CMJ_hip',
    'hHip', 'hHip_ankle_corr', 'hv_hip',
    'Depth_land', 'vmin_land', 'T_land',
    'sj_with_dip', 'cmj_like', 'flight_invalid', 'events_invalid',
    'missing_columns', 'order_invalid', 'notes'
]

EXCEL_ONSET_COLS = [
    't_onset_vCoM', 't_onset_vzCoM', 't_onset_vPelvis',
    't_onset_omega_ankle_L', 't_onset_omega_knee_L', 't_onset_omega_hip_L',
    't_onset_omega_ankle_R', 't_onset_omega_knee_R', 't_onset_omega_hip_R',
]

EXCEL_ANGLE_COLS = []
for j in ['ankle_L', 'knee_L', 'hip_L', 'ankle_R', 'knee_R', 'hip_R']:
    EXCEL_ANGLE_COLS.extend([
        f't_peakFlex_{j}', f'peakFlex_{j}_deg', f'dt_peak_to_zmin_{j}',
        f'ROM_onset_to_peak_{j}_deg', f'angle_at_onset_{j}_deg',
        f'angle_at_zmin_{j}_deg', f'angle_at_TO_{j}_deg',
    ])

EXCEL_COLUMNS = EXCEL_COLUMNS_BASE + EXCEL_ONSET_COLS + EXCEL_ANGLE_COLS
