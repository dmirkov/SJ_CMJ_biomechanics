#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot cumulative net work over time for one SJ and one CMJ FP example,
and report work-energy jump height estimate:

    h_work = W_to / (m * g)

where W_to is cumulative net work at take-off.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

import sys


def _get_example_metrics(base: Path, fp_file: Path):
    # Reuse existing validated FP pipeline logic.
    sys.path.insert(0, str(base))
    import calculate_fp_kpis as fp  # type: ignore

    file_info = fp.parse_filename(fp_file.name)
    if file_info is None:
        raise ValueError(f"Invalid FP filename format: {fp_file.name}")

    f_l, f_r = fp.read_force_file(fp_file)
    if f_l is None or f_r is None or len(f_l) == 0:
        raise ValueError(f"Cannot read force data from: {fp_file}")

    f_tot = f_l + f_r
    metrics = fp.analyze_jump(
        f_tot,
        f_l,
        f_r,
        fp.CONFIG["SAMPLE_RATE_AMTI"],
        file_info["JumpType"],
        file_info["SubjectID"],
        return_timeseries=True,
    )
    if metrics is None:
        raise ValueError(f"Analysis failed for: {fp_file.name}")
    return metrics, file_info


def _compute_work_timeseries(metrics: dict):
    ts = metrics["_timeseries"]
    t = ts["time"]
    f = ts["force"]
    v = ts["vel"]
    idx = ts["idx"]

    bw = float(metrics["BW"])
    bm = float(metrics["BM"])
    g = 9.81

    f_net = f - bw
    p_net = f_net * v

    # Cumulative work from start of cropped signal.
    dt = np.diff(t)
    work = np.zeros_like(t)
    if len(t) > 1:
        work[1:] = np.cumsum(0.5 * (p_net[1:] + p_net[:-1]) * dt)

    i_a = int(idx["A"])
    i_f = int(idx["F"])
    i_h = int(idx["H"])

    # Re-zero work at movement onset.
    work_from_onset = work - work[i_a]
    w_to = float(work_from_onset[i_f])
    h_work = w_to / (bm * g) if bm > 0 else np.nan

    return {
        "t": t,
        "work": work_from_onset,
        "idx_A": i_a,
        "idx_F": i_f,
        "idx_H": i_h,
        "W_to": w_to,
        "h_work": h_work,
    }


def _plot_one(ax: plt.Axes, label: str, w: dict):
    t = w["t"]
    work = w["work"]
    i_a, i_f, i_h = w["idx_A"], w["idx_F"], w["idx_H"]

    ax.plot(t, work, color="tab:blue", linewidth=1.6, label="Cumulative net work")
    ax.axhline(0, color="0.4", linewidth=0.8)

    for i, c, n in [(i_a, "tab:purple", "A (onset)"), (i_f, "tab:orange", "F (take-off)"), (i_h, "tab:red", "H (landing)")]:
        if 0 <= i < len(t):
            ax.axvline(t[i], color=c, linestyle="--", linewidth=1.1, label=n)
            ax.scatter([t[i]], [work[i]], color=c, zorder=5)

    ax.set_title(label)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Work from onset (J)")
    ax.grid(True, alpha=0.25)
    ax.text(
        0.02,
        0.97,
        f"W_to = {w['W_to']:.2f} J\nh_work = {w['h_work']:.3f} m",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.75, edgecolor="0.7"),
    )


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    sj_file = base / "SJ_ForcePlates" / "08_3_5.txt"
    cmj_file = base / "CMJ_ForcePlates" / "09_4_5.txt"

    for p in [sj_file, cmj_file]:
        if not p.exists():
            raise FileNotFoundError(f"Missing example FP file: {p}")

    sj_metrics, _ = _get_example_metrics(base, sj_file)
    cmj_metrics, _ = _get_example_metrics(base, cmj_file)

    sj_w = _compute_work_timeseries(sj_metrics)
    cmj_w = _compute_work_timeseries(cmj_metrics)

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=False)
    _plot_one(axes[0], f"SJ work-time example: {sj_file.name}", sj_w)
    _plot_one(axes[1], f"CMJ work-time example: {cmj_file.name}", cmj_w)

    handles, labels = [], []
    for ax in axes:
        h, l = ax.get_legend_handles_labels()
        handles.extend(h)
        labels.extend(l)
    uniq = {}
    for h, l in zip(handles, labels):
        if l not in uniq:
            uniq[l] = h
    fig.legend(list(uniq.values()), list(uniq.keys()), loc="lower center", bbox_to_anchor=(0.5, -0.03), ncol=4, frameon=True)
    fig.tight_layout(rect=(0, 0.07, 1, 1))

    out_dir = base / "Output" / "Final_Plots" / "Height_Corrections"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / "Example_SJ_CMJ_work_time.png"
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    plt.close(fig)

    print(f"[OK] Saved: {out_png}")
    print(f"[INFO] SJ h_work: {sj_w['h_work']:.4f} m")
    print(f"[INFO] CMJ h_work: {cmj_w['h_work']:.4f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

