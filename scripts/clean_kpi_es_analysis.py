#!/usr/bin/env python3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


PAIR_MAP = [
    ("V_Takeoff_ms", "vTO", "vTO"),
    ("Height_V_m", "hv", "height_velocity"),
    ("Height_Impulse_m", "hv", "height_impulse_velocity"),
    ("Height_T_m", "hFT", "height_flight_time"),
    ("Height_V_m", "hCoM_max_TO", "height_com_max_minus_to"),
    ("Height_V_m", "hCoM_ankle_corr", "height_ankle_corrected"),
    ("Depth_Max_m", "Depth_CMJ", "depth"),
]


def iqr_mask(series: pd.Series, k: float = 1.5) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr == 0:
        return pd.Series(False, index=s.index)
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return (s < lo) | (s > hi)


def descriptive_all_numeric(df: pd.DataFrame, source: str, jump_type: str) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        rows.append(
            {
                "source": source,
                "jump_type": jump_type,
                "kpi": col,
                "n": int(len(vals)),
                "mean": float(vals.mean()),
                "sd": float(vals.std(ddof=1)) if len(vals) > 1 else np.nan,
                "min": float(vals.min()),
                "max": float(vals.max()),
            }
        )
    return pd.DataFrame(rows)


def paired_effect_sizes(fp_df: pd.DataFrame, q_df: pd.DataFrame, jump_type: str, model: str) -> pd.DataFrame:
    merged = fp_df.merge(q_df, on="TrialID", how="inner", suffixes=("_FP", "_Q"))
    out = []
    for fp_col, q_col, pair_name in PAIR_MAP:
        if fp_col not in merged.columns or q_col not in merged.columns:
            continue
        sub = merged[["TrialID", fp_col, q_col]].copy()
        sub = sub.replace([np.inf, -np.inf], np.nan).dropna()
        if len(sub) < 4:
            continue

        diff = sub[fp_col] - sub[q_col]
        outlier = iqr_mask(diff, 1.5)
        sub_clean = sub.loc[~outlier].copy()
        if len(sub_clean) < 4:
            continue

        d = sub_clean[fp_col] - sub_clean[q_col]
        d_mean = float(d.mean())
        d_sd = float(d.std(ddof=1)) if len(d) > 1 else np.nan
        dz = d_mean / d_sd if d_sd and not np.isnan(d_sd) and d_sd != 0 else np.nan

        out.append(
            {
                "jump_type": jump_type,
                "model": model,
                "pair": pair_name,
                "fp_kpi": fp_col,
                "q_kpi": q_col,
                "n_raw": int(len(sub)),
                "n_clean": int(len(sub_clean)),
                "n_outliers_removed": int(len(sub) - len(sub_clean)),
                "mean_diff_fp_minus_q": d_mean,
                "sd_diff": d_sd,
                "cohens_dz": dz,
            }
        )
    return pd.DataFrame(out)


def make_es_plot(es_df: pd.DataFrame, jump_type: str, out_png: Path) -> None:
    sub = es_df[es_df["jump_type"] == jump_type].copy()
    if sub.empty:
        return
    sub["label"] = sub["pair"] + " (" + sub["model"] + ")"
    sub = sub.sort_values(["pair", "model"])

    plt.figure(figsize=(10, 4))
    bars = plt.bar(sub["label"], sub["cohens_dz"])
    plt.axhline(0, color="black", linewidth=0.8)
    plt.ylabel("Cohen's dz (FP - Qualisys)")
    plt.title(f"{jump_type}: effect size per KPI pair (cleaned)")
    plt.xticks(rotation=40, ha="right")
    for b, v in zip(bars, sub["cohens_dz"]):
        if pd.notna(v):
            plt.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    excel = base / "Output" / "Excel" / "MoCap_KPIs.xlsx"
    out_excel = base / "Output" / "Excel" / "Cleaned_KPI_Descriptive_and_ES.xlsx"
    out_plot_dir = base / "Output" / "Final_Plots" / "ES_KPI_Pairs"

    sj_fp = pd.read_excel(excel, sheet_name="SJ_FP")
    cmj_fp = pd.read_excel(excel, sheet_name="CMJ_FP")
    sj3d = pd.read_excel(excel, sheet_name="SJ3D")
    sj2dl = pd.read_excel(excel, sheet_name="SJ2DL")
    sj2dr = pd.read_excel(excel, sheet_name="SJ2DR")
    cmj3d = pd.read_excel(excel, sheet_name="CMJ3D")
    cmj2dl = pd.read_excel(excel, sheet_name="CMJ2DL")
    cmj2dr = pd.read_excel(excel, sheet_name="CMJ2DR")

    # Clean trial sets:
    # SJ: exclude FP countermovement/invalid and Qualisys cmj_like.
    # CMJ: exclude invalid_jump in FP only (keep broad CMJ coverage).
    sj_fp_map = sj_fp[["TrialID", "has_countermovement", "invalid_jump"]].copy()
    sj_q_map = sj3d[["TrialID", "cmj_like"]].copy()
    sj_clean_map = sj_fp_map.merge(sj_q_map, on="TrialID", how="inner")
    sj_clean_ids = sj_clean_map.loc[
        ~(sj_clean_map["has_countermovement"].fillna(False))
        & ~(sj_clean_map["invalid_jump"].fillna(False))
        & ~(sj_clean_map["cmj_like"].fillna(False)),
        "TrialID",
    ].astype(str)

    cmj_clean_ids = cmj_fp.loc[~cmj_fp["invalid_jump"].fillna(False), "TrialID"].astype(str)

    sj_fp_c = sj_fp[sj_fp["TrialID"].astype(str).isin(sj_clean_ids)].copy()
    sj3d_c = sj3d[sj3d["TrialID"].astype(str).isin(sj_clean_ids)].copy()
    sj2dl_c = sj2dl[sj2dl["TrialID"].astype(str).isin(sj_clean_ids)].copy()
    sj2dr_c = sj2dr[sj2dr["TrialID"].astype(str).isin(sj_clean_ids)].copy()

    cmj_fp_c = cmj_fp[cmj_fp["TrialID"].astype(str).isin(cmj_clean_ids)].copy()
    cmj3d_c = cmj3d[cmj3d["TrialID"].astype(str).isin(cmj_clean_ids)].copy()
    cmj2dl_c = cmj2dl[cmj2dl["TrialID"].astype(str).isin(cmj_clean_ids)].copy()
    cmj2dr_c = cmj2dr[cmj2dr["TrialID"].astype(str).isin(cmj_clean_ids)].copy()

    # Descriptive stats for all numeric KPIs.
    desc = pd.concat(
        [
            descriptive_all_numeric(sj_fp_c, "FP", "SJ"),
            descriptive_all_numeric(cmj_fp_c, "FP", "CMJ"),
            descriptive_all_numeric(sj3d_c, "Q3D", "SJ"),
            descriptive_all_numeric(sj2dl_c, "Q2DL", "SJ"),
            descriptive_all_numeric(sj2dr_c, "Q2DR", "SJ"),
            descriptive_all_numeric(cmj3d_c, "Q3D", "CMJ"),
            descriptive_all_numeric(cmj2dl_c, "Q2DL", "CMJ"),
            descriptive_all_numeric(cmj2dr_c, "Q2DR", "CMJ"),
        ],
        ignore_index=True,
    )

    # Effect sizes for comparable pairs.
    es = pd.concat(
        [
            paired_effect_sizes(sj_fp_c, sj3d_c, "SJ", "3D"),
            paired_effect_sizes(sj_fp_c, sj2dl_c, "SJ", "2DL"),
            paired_effect_sizes(sj_fp_c, sj2dr_c, "SJ", "2DR"),
            paired_effect_sizes(cmj_fp_c, cmj3d_c, "CMJ", "3D"),
            paired_effect_sizes(cmj_fp_c, cmj2dl_c, "CMJ", "2DL"),
            paired_effect_sizes(cmj_fp_c, cmj2dr_c, "CMJ", "2DR"),
        ],
        ignore_index=True,
    )

    make_es_plot(es, "SJ", out_plot_dir / "SJ_ES_per_KPI_pair.png")
    make_es_plot(es, "CMJ", out_plot_dir / "CMJ_ES_per_KPI_pair.png")

    clean_summary = pd.DataFrame(
        [
            {"jump_type": "SJ", "n_raw_fp": len(sj_fp), "n_clean_trials": len(sj_clean_ids)},
            {"jump_type": "CMJ", "n_raw_fp": len(cmj_fp), "n_clean_trials": len(cmj_clean_ids)},
        ]
    )
    sj_excluded = sj_fp.loc[~sj_fp["TrialID"].astype(str).isin(sj_clean_ids), ["TrialID", "has_countermovement", "invalid_jump", "qc_notes"]]
    cmj_excluded = cmj_fp.loc[~cmj_fp["TrialID"].astype(str).isin(cmj_clean_ids), ["TrialID", "invalid_jump", "qc_notes"]]

    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        clean_summary.to_excel(writer, sheet_name="clean_summary", index=False)
        desc.to_excel(writer, sheet_name="descriptive_all_kpis", index=False)
        es.to_excel(writer, sheet_name="effect_sizes_kpi_pairs", index=False)
        sj_excluded.to_excel(writer, sheet_name="SJ_excluded_trials", index=False)
        cmj_excluded.to_excel(writer, sheet_name="CMJ_excluded_trials", index=False)

    print(f"[OK] {out_excel}")
    print(f"[OK] {out_plot_dir / 'SJ_ES_per_KPI_pair.png'}")
    print(f"[OK] {out_plot_dir / 'CMJ_ES_per_KPI_pair.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
