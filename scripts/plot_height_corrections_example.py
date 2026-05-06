#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create an illustrative plot (one SJ + one CMJ trial) that marks the exact
timepoints/windows used for the CoM-based height correction methods.

Outputs:
  Output/Final_Plots/Height_Corrections/Example_SJ_CMJ_height_corrections.png
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _nearest(time: np.ndarray, t: float) -> int:
    return int(np.argmin(np.abs(time - t)))


def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return np.nan


def _plot_trial(
    ax: plt.Axes,
    *,
    label: str,
    jump_type: str,
    df: pd.DataFrame,
    kpi: dict,
) -> None:
    time = df["Time"].to_numpy()
    com_z = df["CoM3D_Z"].to_numpy()
    left_contact = np.minimum.reduce(
        [
            df["left_small_toe_pos_Z"].to_numpy(),
            df["left_big_toe_pos_Z"].to_numpy(),
            df["left_heel_pos_Z"].to_numpy(),
        ]
    )
    right_contact = np.minimum.reduce(
        [
            df["right_small_toe_pos_Z"].to_numpy(),
            df["right_big_toe_pos_Z"].to_numpy(),
            df["right_heel_pos_Z"].to_numpy(),
        ]
    )
    global_contact = np.minimum(left_contact, right_contact)

    ax.plot(time, com_z, linewidth=1.5, label="CoM3D_Z")
    ax.set_title(label)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("CoM Z (m)")
    ax.grid(True, alpha=0.25)

    # Overlay toe/contact vertical movement on a secondary axis so TO/LAND is visible.
    ax2 = ax.twinx()
    ax2.plot(time, global_contact, color="tab:blue", linewidth=1.2, alpha=0.8, label="global_contact_Z (min L/R)")
    ax2.plot(time, left_contact, color="tab:blue", linewidth=0.8, alpha=0.35, linestyle="--", label="left_contact_Z")
    ax2.plot(time, right_contact, color="tab:blue", linewidth=0.8, alpha=0.35, linestyle=":", label="right_contact_Z")
    ax2.set_ylabel("Toe/foot contact Z (m)", color="tab:blue")
    ax2.tick_params(axis="y", colors="tab:blue")
    ax._ax2 = ax2  # stash for legend collection

    t_to = _safe_float(kpi.get("t_TO"))
    t_land = _safe_float(kpi.get("t_LAND"))
    t_apex = _safe_float(kpi.get("t_apex"))
    t_start = _safe_float(kpi.get("t_start"))

    # Mark TO / LAND / APEX
    if np.isfinite(t_to):
        ax.axvline(t_to, color="tab:orange", linestyle="--", linewidth=1.25, label="t_TO")
        i_to = _nearest(time, t_to)
        ax.scatter([t_to], [com_z[i_to]], color="tab:orange", zorder=5)
        ax.annotate("TO", (t_to, com_z[i_to]), xytext=(6, 6), textcoords="offset points")

    if np.isfinite(t_land):
        ax.axvline(t_land, color="tab:red", linestyle="--", linewidth=1.25, label="t_LAND")
        i_land = _nearest(time, t_land)
        ax.scatter([t_land], [com_z[i_land]], color="tab:red", zorder=5)
        ax.annotate("LAND", (t_land, com_z[i_land]), xytext=(6, 6), textcoords="offset points")

    if np.isfinite(t_apex):
        ax.axvline(t_apex, color="tab:green", linestyle=":", linewidth=1.25, label="t_apex (flight)")
        i_apex = _nearest(time, t_apex)
        ax.scatter([t_apex], [com_z[i_apex]], color="tab:green", zorder=6)
        ax.annotate("APEX", (t_apex, com_z[i_apex]), xytext=(6, 6), textcoords="offset points")

    # CMJ: onset point used in correction
    if jump_type == "CMJ" and np.isfinite(t_start):
        ax.axvline(t_start, color="tab:purple", linestyle="-.", linewidth=1.1, label="t_start (CMJ onset)")
        i_start = _nearest(time, t_start)
        ax.scatter([t_start], [com_z[i_start]], color="tab:purple", zorder=6)
        ax.annotate("ONSET", (t_start, com_z[i_start]), xytext=(6, 6), textcoords="offset points")

    # SJ: upright reference window + point used in correction
    if jump_type == "SJ" and np.isfinite(t_land):
        # match constants in kpi_calculator.py
        SJ_UPRIGHT_WIN_START = 0.3
        SJ_UPRIGHT_WIN_END = 1.2
        zone_half_s = 0.05
        t0 = t_land + SJ_UPRIGHT_WIN_START
        t1 = min(float(time[-1]), t_land + SJ_UPRIGHT_WIN_END)
        if t1 > t0:
            ax.axvspan(t0, t1, color="tab:cyan", alpha=0.12, label="SJ upright window")
            mask = (time >= t0) & (time <= t1)
            if np.any(mask):
                idx = int(np.argmax(com_z[mask]))
                t_ref = float(time[mask][idx])
                i_center = _nearest(time, t_ref)
                n_half = max(int(zone_half_s / max(np.mean(np.diff(time)), 1e-6)), 1)
                i0 = max(0, i_center - n_half)
                i1 = min(len(com_z), i_center + n_half + 1)
                z_ref = float(np.mean(com_z[i0:i1]))
                tz0 = float(time[i0])
                tz1 = float(time[i1 - 1])

                ax.axvspan(tz0, tz1, color="tab:cyan", alpha=0.28, label="SJ upright avg zone")
                ax.scatter([t_ref], [float(com_z[i_center])], color="tab:cyan", zorder=7)
                ax.hlines(z_ref, tz0, tz1, colors="tab:cyan", linestyles="-", linewidth=2.0, label="SJ upright mean")
                ax.annotate("upright_mean", (t_ref, z_ref), xytext=(6, -12), textcoords="offset points")

    # Add a compact text box with the KPI values used
    lines = []
    for k in ["hCoM_max_TO", "hCoM_onset_corr", "hCoM_upright_ref", "hv", "hFT"]:
        if k in kpi:
            v = kpi.get(k)
            if v is not None and np.isfinite(_safe_float(v)):
                lines.append(f"{k}={_safe_float(v):.3f}")
    if lines:
        ax.text(
            0.02,
            0.98,
            "\n".join(lines),
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=9,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.75, edgecolor="0.7"),
        )


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    # Ensure local imports work (lib/ uses absolute imports like `import config`)
    sys.path.insert(0, str(base / "lib"))

    import kpi_calculator  # type: ignore

    sj_path = base / "processed_data" / "08_3_5_processed.tsv"
    cmj_path = base / "processed_data" / "09_4_5_processed.tsv"

    if not sj_path.exists():
        raise FileNotFoundError(f"Missing SJ example file: {sj_path}")
    if not cmj_path.exists():
        raise FileNotFoundError(f"Missing CMJ example file: {cmj_path}")

    sj_df = pd.read_csv(sj_path, sep="\t")
    cmj_df = pd.read_csv(cmj_path, sep="\t")

    sj_kpi = kpi_calculator.calculate_kpis(
        sj_df,
        "SJ",
        "3D",
        {"filename": sj_path.name, "basename": sj_path.stem},
    )
    cmj_kpi = kpi_calculator.calculate_kpis(
        cmj_df,
        "CMJ",
        "3D",
        {"filename": cmj_path.name, "basename": cmj_path.stem},
    )

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=False)

    _plot_trial(
        axes[0],
        label=f"SJ example: {sj_path.name}",
        jump_type="SJ",
        df=sj_df,
        kpi=sj_kpi,
    )
    _plot_trial(
        axes[1],
        label=f"CMJ example: {cmj_path.name}",
        jump_type="CMJ",
        df=cmj_df,
        kpi=cmj_kpi,
    )

    # Single legend for both (collect from both y-axes)
    handles, labels = [], []
    for ax in axes:
        h, l = ax.get_legend_handles_labels()
        handles.extend(h)
        labels.extend(l)
        ax2 = getattr(ax, "_ax2", None)
        if ax2 is not None:
            h2, l2 = ax2.get_legend_handles_labels()
            handles.extend(h2)
            labels.extend(l2)
    # de-duplicate legend labels in order
    uniq = {}
    for h, l in zip(handles, labels):
        if l not in uniq:
            uniq[l] = h
    fig.legend(
        list(uniq.values()),
        list(uniq.keys()),
        loc="lower center",
        bbox_to_anchor=(0.5, -0.06),
        ncol=3,
        frameon=True,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))

    out_dir = base / "Output" / "Final_Plots" / "Height_Corrections"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / "Example_SJ_CMJ_height_corrections.png"
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    plt.close(fig)

    print(f"[OK] Saved: {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

