#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch AMTI force plate analysis (CMJ/SJ) with KPI export and acc+vel plots.

- Reads all .txt files recursively from AMTI_FP
- Reuses existing force-plate logic from calculate_fp_kpis.py
- Exports one-row-per-file "raw" KPI table (CSV)
- Saves acceleration and velocity on same plot:
  from 200 ms before contraction onset to 200 ms after lowest COM point in landing
"""

from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from calculate_fp_kpis import read_force_file, analyze_jump, CONFIG


def infer_jump_type(file_path: Path, relative_path: Path) -> int:
    """
    Infer jump type from filename tokens.
    Expected formats often include ..._<jumpType>_<trial>.txt
    Returns:
      2 for CMJ (default),
      1 for SJ when explicitly detected.
    """
    # Expected schema provided by user:
    # <ID3>_SS_<trial>_<jump_type>_<day>.txt
    # Example: 039_SS_1_2_2.txt -> jump_type=2 (CMJ)
    stem = file_path.stem
    m = re.match(r"^(\d{3})_ss_(\d+)_(\d+)_(\d+)$", stem.lower())
    if m:
        jump_type_code = int(m.group(3))
        # In this dataset jump_type==2 means CMJ for all files.
        if jump_type_code == 2:
            return 2
        # Keep compatibility in case other sets appear later.
        if jump_type_code == 1:
            return 1

    # Fallback to folder context if filename does not match expected schema.
    rel_parts = [p.lower() for p in relative_path.parts]
    for part in rel_parts:
        if "cmj" in part:
            return 2
        if re.search(r"\bsj\b", part):
            return 1
    return 2


def save_acc_vel_plot(
    ts: dict,
    out_path: Path,
    title: str,
    pre_ms: float = 200.0,
    post_ms: float = 200.0,
    landing_search_s: float = 1.5,
) -> dict:
    """Save acceleration+velocity plot in requested event-centered window."""
    fs = float(ts["fs"])
    idx = ts["idx"]
    time = ts["time"]
    acc = ts["acc"]
    vel = ts["vel"]
    disp = ts["disp"]

    idx_a = int(idx["A"])
    idx_h = int(idx["H"])

    pre_n = int(round(pre_ms * fs / 1000.0))
    post_n = int(round(post_ms * fs / 1000.0))

    search_end = min(len(disp), idx_h + int(round(landing_search_s * fs)))
    if search_end <= idx_h + 1:
        idx_lowest_com = idx_h
    else:
        idx_lowest_com = idx_h + int(np.argmin(disp[idx_h:search_end]))

    start_idx = max(0, idx_a - pre_n)
    end_idx = min(len(time) - 1, idx_lowest_com + post_n)
    if end_idx <= start_idx:
        start_idx = 0
        end_idx = len(time) - 1

    window = slice(start_idx, end_idx + 1)
    t_rel_ms = (time[window] - time[idx_a]) * 1000.0

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()

    l1 = ax1.plot(t_rel_ms, acc[window], color="tab:blue", lw=1.5, label="Acceleration (m/s^2)")
    l2 = ax2.plot(t_rel_ms, vel[window], color="tab:red", lw=1.5, label="Velocity (m/s)")

    ax1.axvline(0.0, color="k", ls="--", lw=1.0, alpha=0.8, label="Onset")
    ax1.axvline((time[idx_lowest_com] - time[idx_a]) * 1000.0, color="tab:green", ls="--", lw=1.0, alpha=0.8, label="Lowest COM")

    ax1.set_xlabel("Time from onset (ms)")
    ax1.set_ylabel("Acceleration (m/s^2)", color="tab:blue")
    ax2.set_ylabel("Velocity (m/s)", color="tab:red")
    ax1.set_title(title)
    ax1.grid(alpha=0.25)

    lines = l1 + l2
    labels = [x.get_label() for x in lines]
    lines_extra, labels_extra = ax1.get_legend_handles_labels()
    ax1.legend(lines + lines_extra, labels + labels_extra, loc="best")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return {
        "idx_lowest_com": idx_lowest_com,
        "plot_start_idx": start_idx,
        "plot_end_idx": end_idx,
        "plot_start_ms_from_onset": float((time[start_idx] - time[idx_a]) * 1000.0),
        "plot_end_ms_from_onset": float((time[end_idx] - time[idx_a]) * 1000.0),
    }


def main():
    base = Path(__file__).parent
    input_dir = base / "AMTI_FP"
    output_dir = base / "Output" / "AMTI_CMJ_ANALYSIS"
    plots_dir = output_dir / "plots"
    kpi_csv = output_dir / "amti_kpis_raw.csv"

    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder not found: {input_dir}")

    files = sorted(input_dir.rglob("*.txt"))
    print(f"Found {len(files)} AMTI files under: {input_dir}")
    if not files:
        print("No files to process.")
        return 0

    rows = []
    for i, fp in enumerate(files, start=1):
        rel = fp.relative_to(input_dir)
        print(f"[{i}/{len(files)}] {rel}")

        f_l, f_r = read_force_file(fp)
        if f_l is None or len(f_l) == 0:
            print("  -> skipped (read failure)")
            continue

        f_tot = f_l + f_r
        jump_type = infer_jump_type(fp, rel)

        metrics = analyze_jump(
            f_tot,
            f_l,
            f_r,
            CONFIG["SAMPLE_RATE_AMTI"],
            jump_type,
            fp.stem,
            return_timeseries=True,
        )
        if metrics is None:
            print("  -> skipped (analysis failed)")
            continue

        ts = metrics.get("_timeseries")
        if not ts:
            print("  -> skipped (missing timeseries)")
            continue

        plot_subdir = plots_dir / rel.parent
        plot_name = f"{fp.stem}_acc_vel.png"
        plot_path = plot_subdir / plot_name
        plot_info = save_acc_vel_plot(
            ts=ts,
            out_path=plot_path,
            title=f"{fp.stem} | {'CMJ' if jump_type == 2 else 'SJ'}",
        )

        rows.append(
            {
                "FileName": fp.name,
                "RelativePath": str(rel),
                "JumpType": "CMJ" if jump_type == 2 else "SJ",
                "BW_N": metrics.get("BW", np.nan),
                "BM_kg": metrics.get("BM", np.nan),
                "dt_UP_s": metrics.get("dt_UP", np.nan),
                "Fmin_UP_N": metrics.get("Fmin_UP", np.nan),
                "Impulse_UP_Ns": metrics.get("J_UP", np.nan),
                "dt_BP_s": metrics.get("dt_BP", np.nan),
                "Depth_Max_m": metrics.get("hmin_BP", np.nan),
                "Fmax_BP_N": metrics.get("Fmax_BP", np.nan),
                "Stiffness_Nm": metrics.get("LS", np.nan),
                "dt_PP_s": metrics.get("dt_PP", np.nan),
                "V_Takeoff_ms": metrics.get("v_to", np.nan),
                "Height_V_m": metrics.get("h_to_v", np.nan),
                "Height_T_m": metrics.get("h_to_t", np.nan),
                "Power_Max_W": metrics.get("Pmax_PP", np.nan),
                "Power_Avg_W": metrics.get("Pavg_PP", np.nan),
                "Impulse_Tot_Ns": metrics.get("J_tot", np.nan),
                "Impulse_BP_Ns": metrics.get("J_BP", np.nan),
                "Impulse_PP_Ns": metrics.get("J_PP", np.nan),
                "Impulse_Land_Ns": metrics.get("J_LAND", np.nan),
                "Impact_Force_N": metrics.get("F_impact", np.nan),
                "RFD_Landing_Ns": metrics.get("RFD_Land", np.nan),
                "has_countermovement": metrics.get("has_countermovement", False),
                "negative_vto": metrics.get("negative_vto", False),
                "invalid_events": metrics.get("invalid_events", False),
                "invalid_jump": metrics.get("invalid_jump", False),
                "qc_notes": metrics.get("qc_notes", ""),
                "Onset_idx": int(ts["idx"]["A"]),
                "Landing_idx": int(ts["idx"]["H"]),
                "LowestCOM_idx": int(plot_info["idx_lowest_com"]),
                "PlotStart_ms_from_onset": plot_info["plot_start_ms_from_onset"],
                "PlotEnd_ms_from_onset": plot_info["plot_end_ms_from_onset"],
                "PlotPath": str(plot_path.relative_to(base)),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(kpi_csv, index=False)

    print("-" * 80)
    print(f"Processed files: {len(rows)} / {len(files)}")
    print(f"KPI raw file: {kpi_csv}")
    print(f"Plots folder:  {plots_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
