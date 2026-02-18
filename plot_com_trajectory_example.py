#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grafički primer: CoM putanja i toe/heel markeri na CMJ
- CoM Z (vertikalna pozicija)
- Small toe, Big toe, Heel (L i R) - Z pozicija
- Vertikalne linije: onset, t_zmin, t_TO, t_LAND, t_zmin_land
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from file_discovery import discover_processed_files, load_processed_file
from kpi_calculator import calculate_kpis


def plot_com_trajectory(file_info: dict, output_path: Path) -> bool:
    df = load_processed_file(file_info['filepath'])
    if df is None:
        return False
    filename = file_info['filename']
    req = ['CoM3D_Z', 'left_small_toe_pos_Z', 'left_big_toe_pos_Z', 'left_heel_pos_Z',
           'right_small_toe_pos_Z', 'right_big_toe_pos_Z', 'right_heel_pos_Z']
    if not all(c in df.columns for c in req):
        print(f"[SKIP] Nedostaju kolone: {filename}")
        return False

    time = df['Time'].values
    if np.all(np.isnan(time)):
        time = np.arange(len(df)) / 300.0

    # Konvertuj u m ako je u mm
    com_z = df['CoM3D_Z'].values.copy()
    if np.nanmax(np.abs(com_z)) > 10:
        com_z = com_z / 1000.0

    def get_z(col):
        z = pd.Series(df[col].values).ffill().bfill().values
        if np.nanmax(np.abs(z)) > 10:
            z = z / 1000.0
        return z

    small_L = get_z('left_small_toe_pos_Z')
    big_L = get_z('left_big_toe_pos_Z')
    heel_L = get_z('left_heel_pos_Z')
    small_R = get_z('right_small_toe_pos_Z')
    big_R = get_z('right_big_toe_pos_Z')
    heel_R = get_z('right_heel_pos_Z')

    kpis = calculate_kpis(df, 'CMJ', '3D', file_info)
    t_start = kpis.get('t_start', np.nan)
    t_zmin = kpis.get('t_zmin', np.nan)
    t_to = kpis.get('t_TO', np.nan)
    t_land = kpis.get('t_LAND', np.nan)
    t_zmin_land = kpis.get('t_zmin_land', np.nan)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(time, com_z, 'k-', lw=2, label='CoM Z')
    ax.plot(time, small_L, 'b-', lw=1, alpha=0.8, label='Small toe L')
    ax.plot(time, big_L, 'b--', lw=1, alpha=0.6, label='Big toe L')
    ax.plot(time, heel_L, 'b:', lw=1, alpha=0.6, label='Heel L')
    ax.plot(time, small_R, 'r-', lw=1, alpha=0.8, label='Small toe R')
    ax.plot(time, big_R, 'r--', lw=1, alpha=0.6, label='Big toe R')
    ax.plot(time, heel_R, 'r:', lw=1, alpha=0.6, label='Heel R')

    events = [
        (t_start, 'green', 'onset'),
        (t_zmin, 'orange', 'zmin (CoM najniže)'),
        (t_to, 'red', 't_TO (početak leta)'),
        (t_land, 'purple', 't_LAND (kraj leta)'),
        (t_zmin_land, 'brown', 'zmin_land'),
    ]
    for t, color, lbl in events:
        if not np.isnan(t) and time[0] <= t <= time[-1]:
            ax.axvline(t, color=color, ls='--', alpha=0.8, lw=1.5, label=lbl)

    ax.set_xlabel('Vreme (s)')
    ax.set_ylabel('Z pozicija (m)')
    ax.set_title(f'CMJ: CoM i toe/heel putanje — {filename}')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)

    out = output_path / f"com_trajectory_CMJ_{filename.replace('.tsv', '').replace('.csv', '')}.png"
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out.name}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CoM i toe/heel putanje za CMJ")
    parser.add_argument("--idx", type=int, default=0, help="Indeks CMJ fajla (0-based)")
    args = parser.parse_args()

    from paths_config import PROCESSED_DATA_DIR, OUTPUT_DIR
    proc_dir = PROCESSED_DATA_DIR
    if not proc_dir.exists():
        print("[ERROR] processed_data nije pronađen:", proc_dir)
        return 1
    import config as qconfig
    qconfig.PROCESSED_DATA_DIR = proc_dir
    output_path = OUTPUT_DIR / "Plots"
    output_path.mkdir(parents=True, exist_ok=True)

    files = discover_processed_files(proc_dir)
    cmj_files = files['CMJ']
    if not cmj_files:
        print("[ERROR] Nema CMJ fajlova")
        return 1

    idx = min(args.idx, len(cmj_files) - 1)
    plot_com_trajectory(cmj_files[idx], output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
