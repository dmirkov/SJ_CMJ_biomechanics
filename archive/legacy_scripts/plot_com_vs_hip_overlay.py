#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoM vs Hip overlay: displacement (leva osa) i brzina (desna osa)
sa oznacenim kritičnim tačkama (t_start, t_start_hip, t_TO, t_LAND, vTO, ...)
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from file_discovery import discover_processed_files, load_processed_file
from kpi_calculator import calculate_kpis
import config


def _get_z(df, cols, time):
    if isinstance(cols, str):
        cols = [cols]
    arr = np.nanmean([pd.Series(df[c].values).ffill().bfill().values for c in cols], axis=0)
    if np.nanmax(np.abs(arr)) > 10:
        arr = arr / 1000.0
    return arr


def plot_com_hip_overlay(df, kpis, jump_type, trial_id, output_path):
    """Overlay CoM i Hip: pomjeraj (leva osa), brzina (desna osa), kritične tačke."""
    time = df["Time"].values
    if np.all(np.isnan(time)):
        fs = config.FS_DEFAULT
        time = np.arange(len(df)) / fs
    else:
        valid = time[~np.isnan(time)]
        fs = 1.0 / np.mean(np.diff(valid)) if len(valid) > 1 else config.FS_DEFAULT

    com_z = _get_z(df, config.COM_3D_COL, time)
    vz = df[config.VZ_3D_COL].values
    vz = pd.Series(vz).ffill().bfill().values

    hip_cols = ["left_hip_pos_Z", "right_hip_pos_Z"]
    if all(c in df.columns for c in hip_cols):
        hip_z = _get_z(df, hip_cols, time)
        v_hip = np.gradient(hip_z, time) if len(time) > 1 else np.zeros_like(hip_z)
    else:
        return False

    t_start = kpis.get("t_start", np.nan)
    t_start_hip = kpis.get("t_start_hip", np.nan)
    t_zmin = kpis.get("t_zmin", np.nan)
    t_to = kpis.get("t_TO", np.nan)
    t_land = kpis.get("t_LAND", np.nan)
    t_apex = kpis.get("t_apex", np.nan)
    vto = kpis.get("vTO", np.nan)
    vto_hip = kpis.get("vTO_hip", np.nan)

    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()

    ax1.plot(time, com_z, "b-", lw=2, label="CoM Z (m)")
    ax1.plot(time, hip_z, "r-", lw=2, alpha=0.8, label="Hip Z (m)")
    ax1.set_ylabel("Vertikalna pozicija (m)", color="black", fontsize=11)
    ax1.tick_params(axis="y", labelcolor="black")
    ax1.set_ylim(
        min(np.nanmin(com_z), np.nanmin(hip_z)) - 0.05,
        max(np.nanmax(com_z), np.nanmax(hip_z)) + 0.1,
    )
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left", fontsize=9)

    ax2.plot(time, vz, "b--", lw=1.5, alpha=0.7, label="vCoM (m/s)")
    ax2.plot(time, v_hip, "r--", lw=1.5, alpha=0.7, label="vHip (m/s)")
    ax2.axhline(0, color="gray", ls=":", alpha=0.5)
    ax2.set_ylabel("Vertikalna brzina (m/s)", color="black", fontsize=11)
    ax2.tick_params(axis="y", labelcolor="black")
    ax2.legend(loc="upper right", fontsize=9)

    events = [
        (t_start, "green", "t_start CoM"),
        (t_start_hip, "lime", "t_start Hip"),
        (t_zmin, "orange", "t_zmin"),
        (t_to, "red", "t_TO"),
        (t_land, "purple", "t_LAND"),
        (t_apex, "darkred", "t_apex"),
    ]
    for t, color, lbl in events:
        if not np.isnan(t) and time[0] <= t <= time[-1]:
            ax1.axvline(t, color=color, ls="--", alpha=0.85, lw=1.2)
            ax2.axvline(t, color=color, ls="--", alpha=0.4, lw=1)

    # vTO vrednosti
    if not np.isnan(t_to) and time[0] <= t_to <= time[-1]:
        vto_val = np.interp(t_to, time, vz)
        vto_hip_val = np.interp(t_to, time, v_hip)
        ax2.plot(t_to, vto_val, "bo", ms=8, zorder=5)
        ax2.plot(t_to, vto_hip_val, "ro", ms=8, zorder=5)
        ax2.annotate(
            f"vTO CoM={vto_val:.2f}" if not np.isnan(vto) else "",
            (t_to, vto_val),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=9,
            color="blue",
        )
        ax2.annotate(
            f"vTO Hip={vto_hip_val:.2f}" if not np.isnan(vto_hip) else "",
            (t_to, vto_hip_val),
            textcoords="offset points",
            xytext=(5, -15),
            fontsize=9,
            color="red",
        )

    ax1.set_xlabel("Vreme (s)", fontsize=11)
    ax1.set_xlim(time[0], time[-1])
    t_s = f"{t_start:.2f}" if not np.isnan(t_start) else "nan"
    t_sh = f"{t_start_hip:.2f}" if not np.isnan(t_start_hip) else "nan"
    v_s = f"{vto:.2f}" if not np.isnan(vto) else "nan"
    v_sh = f"{vto_hip:.2f}" if not np.isnan(vto_hip) else "nan"
    tit = f"{trial_id} {jump_type} | t_start: CoM={t_s}s  Hip={t_sh}s | vTO: CoM={v_s}  Hip={v_sh} m/s"
    ax1.set_title(tit, fontsize=10, wrap=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return True


def main():
    from paths_config import PROCESSED_DATA_DIR, OUTPUT_DIR
    config.PROCESSED_DATA_DIR = PROCESSED_DATA_DIR
    files = discover_processed_files(PROCESSED_DATA_DIR)
    out_dir = OUTPUT_DIR / "Plots" / "CoM_vs_Hip"
    out_dir.mkdir(parents=True, exist_ok=True)

    examples = [
        ("02_4_1", "CMJ"),
        ("02_4_2", "CMJ"),
        ("02_3_1", "SJ"),
        ("02_3_2", "SJ"),
        ("03_4_1", "CMJ"),
    ]

    for basename, jtype in examples:
        flist = files["CMJ"] if jtype == "CMJ" else files["SJ"]
        match = next((f for f in flist if f["basename"] == basename), None)
        if not match:
            print(f"[SKIP] Nije pronadjen: {basename}")
            continue
        df = load_processed_file(match["filepath"])
        if df is None:
            print(f"[SKIP] Ne moze ucitati: {basename}")
            continue
        kpis = calculate_kpis(df, jtype, "3D", match)
        out_path = out_dir / f"com_hip_overlay_{basename}_{jtype}.png"
        if plot_com_hip_overlay(df, kpis, jtype, basename, out_path):
            print(f"[OK] {out_path.name}")
        else:
            print(f"[FAIL] {basename}")

    print(f"\nPlots saved to: {out_dir}")


if __name__ == "__main__":
    main()
