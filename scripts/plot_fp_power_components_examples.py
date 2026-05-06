#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot component signals used to compute net power for one SJ and one CMJ FP example:
  - Total force Fz
  - Body weight BW (constant line)
  - Net force Fnet = Fz - BW
  - Velocity v
  - Net power Pnet = Fnet * v
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import sys


def _load_metrics(base: Path, fp_file: Path):
    sys.path.insert(0, str(base))
    import calculate_fp_kpis as fp  # type: ignore

    info = fp.parse_filename(fp_file.name)
    if info is None:
        raise ValueError(f"Invalid filename: {fp_file.name}")
    f_l, f_r = fp.read_force_file(fp_file)
    if f_l is None or f_r is None:
        raise ValueError(f"Failed reading file: {fp_file}")
    m = fp.analyze_jump(
        f_l + f_r,
        f_l,
        f_r,
        fp.CONFIG["SAMPLE_RATE_AMTI"],
        info["JumpType"],
        info["SubjectID"],
        return_timeseries=True,
    )
    if m is None:
        raise ValueError(f"Analysis failed for: {fp_file.name}")
    return m


def _plot_set(axs, title: str, m: dict):
    ts = m["_timeseries"]
    t = ts["time"]
    f = ts["force"]
    v = ts["vel"]
    idx = ts["idx"]
    bw = float(m["BW"])

    fnet = f - bw
    pnet = fnet * v

    iA, iF, iH = int(idx["A"]), int(idx["F"]), int(idx["H"])

    # 1) Force & BW
    axs[0].plot(t, f, label="Fz", color="tab:blue", linewidth=1.4)
    axs[0].axhline(bw, label="BW", color="tab:gray", linestyle="--", linewidth=1.2)
    axs[0].set_ylabel("Force (N)")
    axs[0].set_title(title)
    axs[0].grid(True, alpha=0.25)

    # 2) Net force
    axs[1].plot(t, fnet, label="Fnet = Fz-BW", color="tab:orange", linewidth=1.4)
    axs[1].axhline(0, color="0.4", linewidth=0.8)
    axs[1].set_ylabel("Net force (N)")
    axs[1].grid(True, alpha=0.25)

    # 3) Velocity
    axs[2].plot(t, v, label="v", color="tab:green", linewidth=1.4)
    axs[2].axhline(0, color="0.4", linewidth=0.8)
    axs[2].set_ylabel("Velocity (m/s)")
    axs[2].grid(True, alpha=0.25)

    # 4) Net power
    axs[3].plot(t, pnet, label="Pnet = (Fz-BW)*v", color="tab:red", linewidth=1.4)
    axs[3].axhline(0, color="0.4", linewidth=0.8)
    axs[3].set_ylabel("Power (W)")
    axs[3].set_xlabel("Time (s)")
    axs[3].grid(True, alpha=0.25)

    # Event markers on all subplots
    for ax in axs:
        for i, c, n in [(iA, "tab:purple", "A"), (iF, "tab:orange", "F"), (iH, "tab:red", "H")]:
            if 0 <= i < len(t):
                ax.axvline(t[i], color=c, linestyle=":", linewidth=0.9)
        ax.legend(loc="upper right", fontsize=8)


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    sj_file = base / "SJ_ForcePlates" / "08_3_5.txt"
    cmj_file = base / "CMJ_ForcePlates" / "09_4_5.txt"

    sj = _load_metrics(base, sj_file)
    cmj = _load_metrics(base, cmj_file)

    fig, axes = plt.subplots(4, 2, figsize=(14, 10), sharex="col")
    _plot_set(axes[:, 0], f"SJ components: {sj_file.name}", sj)
    _plot_set(axes[:, 1], f"CMJ components: {cmj_file.name}", cmj)

    fig.tight_layout()
    out_dir = base / "Output" / "Final_Plots" / "Height_Corrections"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / "Example_SJ_CMJ_power_components.png"
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved: {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

