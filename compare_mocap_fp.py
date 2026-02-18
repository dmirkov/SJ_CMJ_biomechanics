#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POREĐENJE MoCap vs Force Plate REZULTATA
=======================================
Rezultati u metrima (m), uporedo po istoj metodi računanja.
"""

import sys
from pathlib import Path
import pandas as pd

# MoCap
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from file_discovery import discover_processed_files, load_processed_file
from kpi_calculator import calculate_kpis
import config

# FP
from calculate_fp_kpis import read_force_file, analyze_jump, CONFIG, parse_filename


def collect_mocap(processed_dir: Path, subject_id: str = None) -> dict:
    """Sakuplja MoCap KPIs za sve pokušaje (ili za subject_id)."""
    config.PROCESSED_DATA_DIR = processed_dir
    files = discover_processed_files(processed_dir)
    result = {}
    for jump_type, flist in [("SJ", files["SJ"]), ("CMJ", files["CMJ"])]:
        for f in flist:
            if subject_id and f["SubjectID"] != subject_id:
                continue
            df = load_processed_file(f["filepath"])
            if df is None:
                continue
            k = calculate_kpis(df, jump_type, "3D", f)
            tid = f["basename"]
            # Sve visine u m; MoCap već vraća u m
            result[tid] = {
                "Type": jump_type,
                "hFT_m": k.get("hFT"),
                "hv_m": k.get("hv"),
                "hCoM_m": k.get("hCoM"),
                "hCoM_ankle_corr_m": k.get("hCoM_ankle_corr"),
                "hHip_m": k.get("hHip"),
                "hHip_ankle_corr_m": k.get("hHip_ankle_corr"),
                "hv_hip_m": k.get("hv_hip"),
                "vTO": k.get("vTO"),
                "vTO_hip": k.get("vTO_hip"),
                "T_flight": k.get("T_flight"),
                "t_start": k.get("t_start"),
                "t_start_hip": k.get("t_start_hip"),
                "T_downward": k.get("T_downward"),
                "T_upward": k.get("T_upward"),
                "T_downward_hip": k.get("T_downward_hip"),
                "T_upward_hip": k.get("T_upward_hip"),
                "TTO": k.get("TTO"),
                "TTO_hip": k.get("TTO_hip"),
                "Depth_CMJ": k.get("Depth_CMJ"),
                "Depth_CMJ_hip": k.get("Depth_CMJ_hip"),
                "vmin_pre": k.get("vmin_pre"),
                "vmax_pre": k.get("vmax_pre"),
                "vmin_pre_hip": k.get("vmin_pre_hip"),
                "vmax_pre_hip": k.get("vmax_pre_hip"),
            }
    return result


def collect_fp(base_path: Path, subject_id: str = None) -> dict:
    """Sakuplja FP KPIs iz Force Plate fajlova."""
    result = {}
    for fp_dir, jt in [
        (base_path / "CMJ_ForcePlates", 2),
        (base_path / "SJ_ForcePlates", 1),
    ]:
        if not fp_dir.exists():
            continue
        for fp in fp_dir.glob("*.txt"):
            info = parse_filename(fp.name)
            if not info or (subject_id and info["SubjectID"] != subject_id):
                continue
            fL, fR = read_force_file(fp)
            if fL is None or len(fL) == 0:
                continue
            m = analyze_jump(
                fL + fR, fL, fR, CONFIG["SAMPLE_RATE_AMTI"], jt, info["SubjectID"]
            )
            if m is None:
                continue
            if jt == 1 and m.get("has_countermovement"):
                continue
            tid = info["basename"]
            # FP h_to_v, h_to_t su već u m; hCoM ne postoji u FP
            result[tid] = {
                "Type": "CMJ" if jt == 2 else "SJ",
                "hFT_m": m.get("h_to_t"),
                "hv_m": m.get("h_to_v"),
                "hCoM_m": None,
                "hCoM_ankle_corr_m": None,
                "vTO": m.get("v_to"),
                "T_flight": m.get("dt_FP"),
            }
    return result


def fmt(v, decimals=3, plus=False):
    """Formatira vrednost ili vraca '-'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if isinstance(v, float) and v == 0 and not plus:
        return "-"
    try:
        s = f"{float(v):.{decimals}f}"
        if plus and v is not None and not pd.isna(v) and v >= 0:
            s = "+" + s
        return s
    except (TypeError, ValueError):
        return "-"


def build_comparison_table(mocap: dict, fp: dict, subject_id: str = None) -> pd.DataFrame:
    """
    Kreira DataFrame sa svim metodama visine - MoCap i FP uporedo.
    MoCap: hFT, hv, hCoM, hCoM_ankle_corr | FP: hFT, hv (FP nema hCoM metode)
    """
    all_trials = sorted(set(mocap.keys()) | set(fp.keys()))
    if subject_id:
        all_trials = [t for t in all_trials if t.startswith(subject_id + "_")]

    rows = []
    for tid in all_trials:
        mc = mocap.get(tid, {})
        fp_ = fp.get(tid, {})
        t = mc.get("Type") or fp_.get("Type", "")

        row = {
            "Trial": tid,
            "Type": t,
            # MoCap visine - CoM
            "hFT_MoCap_m": mc.get("hFT_m"),
            "hv_MoCap_m": mc.get("hv_m"),
            "hCoM_MoCap_m": mc.get("hCoM_m"),
            "hCoM_ankle_corr_MoCap_m": mc.get("hCoM_ankle_corr_m"),
            # MoCap visine - Hip
            "hHip_MoCap_m": mc.get("hHip_m"),
            "hHip_ankle_corr_MoCap_m": mc.get("hHip_ankle_corr_m"),
            "hv_hip_MoCap_m": mc.get("hv_hip_m"),
            # FP visine
            "hFT_FP_m": fp_.get("hFT_m"),
            "hv_FP_m": fp_.get("hv_m"),
            # Ulazne vrednosti
            "vTO_MoCap": mc.get("vTO"),
            "vTO_hip_MoCap": mc.get("vTO_hip"),
            "vTO_FP": fp_.get("vTO"),
            "T_flight_MoCap_s": mc.get("T_flight"),
            "T_flight_FP_s": fp_.get("T_flight"),
            # CoM vs Hip - onset i faze (samo MoCap)
            "t_start_CoM_s": mc.get("t_start"),
            "t_start_hip_s": mc.get("t_start_hip"),
            "T_downward_CoM_s": mc.get("T_downward"),
            "T_downward_hip_s": mc.get("T_downward_hip"),
            "T_upward_CoM_s": mc.get("T_upward"),
            "T_upward_hip_s": mc.get("T_upward_hip"),
            "TTO_CoM_s": mc.get("TTO"),
            "TTO_hip_s": mc.get("TTO_hip"),
            "Depth_CMJ_m": mc.get("Depth_CMJ"),
            "Depth_CMJ_hip_m": mc.get("Depth_CMJ_hip"),
            "vmin_pre_CoM": mc.get("vmin_pre"),
            "vmax_pre_CoM": mc.get("vmax_pre"),
            "vmin_pre_hip": mc.get("vmin_pre_hip"),
            "vmax_pre_hip": mc.get("vmax_pre_hip"),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def print_comparison(df: pd.DataFrame):
    """Ispisuje tabelu u konzolu - CoM vs Hip vs FP."""
    print("=" * 140)
    print("POREDENJE MoCap (CoM vs Hip) vs Force Plate - REZULTATI U METRIMA")
    print("=" * 140)
    print()

    # Visine - CoM vs Hip vs FP
    print("VISINE (m) - CoM, Hip, FP uporedo")
    print("-" * 140)
    hdr = (
        f"{'Trial':<10} {'Type':<5} "
        f"{'hFT_MC':<8} {'hFT_FP':<8} | "
        f"{'hCoM':<8} {'hHip':<8} | "
        f"{'hCoM_ac':<8} {'hHip_ac':<8} | "
        f"{'hv_MC':<8} {'hv_hip':<8} {'hv_FP':<8}"
    )
    print(hdr)
    print("-" * 140)
    for _, r in df.iterrows():
        ln = (
            f"{r['Trial']:<10} {r['Type']:<5} "
            f"{fmt(r['hFT_MoCap_m']):<8} {fmt(r['hFT_FP_m']):<8} | "
            f"{fmt(r['hCoM_MoCap_m']):<8} {fmt(r['hHip_MoCap_m']):<8} | "
            f"{fmt(r['hCoM_ankle_corr_MoCap_m']):<8} {fmt(r['hHip_ankle_corr_MoCap_m']):<8} | "
            f"{fmt(r['hv_MoCap_m']):<8} {fmt(r['hv_hip_MoCap_m']):<8} {fmt(r['hv_FP_m']):<8}"
        )
        print(ln)
    print()
    print("Legenda: hFT=flight-time | hCoM/hHip=z_apex-z_to | _ac=ankle_corr | hv=v^2/2g | MC=MoCap, FP=ForcePlate")
    print()
    # CoM vs Hip - onset i faze (uzorak prvih 20)
    print("CoM vs Hip - ONSET I FAZE (s) - uzorak")
    print("-" * 100)
    hdr2 = f"{'Trial':<10} {'Type':<5} {'t_start_C':<10} {'t_start_H':<10} {'T_down_C':<8} {'T_down_H':<8} {'T_up_C':<8} {'T_up_H':<8} {'Depth_C':<8} {'Depth_H':<8}"
    print(hdr2)
    print("-" * 100)
    for i, (_, r) in enumerate(df.iterrows()):
        if i >= 25:
            print("...")
            break
        ln = (
            f"{r['Trial']:<10} {r['Type']:<5} "
            f"{fmt(r.get('t_start_CoM_s'),2):<10} {fmt(r.get('t_start_hip_s'),2):<10} "
            f"{fmt(r.get('T_downward_CoM_s'),3):<8} {fmt(r.get('T_downward_hip_s'),3):<8} "
            f"{fmt(r.get('T_upward_CoM_s'),3):<8} {fmt(r.get('T_upward_hip_s'),3):<8} "
            f"{fmt(r.get('Depth_CMJ_m'),3):<8} {fmt(r.get('Depth_CMJ_hip_m'),3):<8}"
        )
        print(ln)
    print("Legenda: C=CoM, H=Hip | t_start=onset | T_down/T_up=faze | Depth=dubina CMJ")
    print()
    print("NAPOMENA - Da li ima smisla posmatrati Hip?")
    print("  - hCoM vs hHip: obicno bliske (hip je deo tela blizu CoM); male razlike zbog kretanja ruku/trupa.")
    print("  - hv_hip < hv_CoM: hip brzina na TO je niza jer CoM ukljucuje gornji deo tela.")
    print("  - Onset/faze: mogu se razlikovati ako se hip i CoM ne pomjeraju istovremeno.")
    print("  - Hip je jednostavniji marker; CoM je fizikalno relevantniji za visinu skoka.")
    print("=" * 140)


def main():
    from paths_config import PROCESSED_DATA_DIR, DATA_ROOT, EXCEL_DIR
    proc = PROCESSED_DATA_DIR
    fp_base = DATA_ROOT
    mocap = collect_mocap(proc)
    fp_data = collect_fp(fp_base)

    if not mocap and not fp_data:
        print("[ERROR] Nema podataka za poređenje.")
        return 1

    # Kreiraj DataFrame
    df = build_comparison_table(mocap, fp_data)

    # Ispis u konzolu
    print_comparison(df)

    # Export u Excel
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    excel_path = EXCEL_DIR / "MoCap_FP_Comparison.xlsx"
    cm_hip_cols = [c for c in df.columns if any(x in c for x in ["CoM", "hip", "Hip", "Depth", "t_start", "T_down", "T_up", "TTO", "vmin_pre", "vmax_pre"])]
    df_sj = df[df["Type"] == "SJ"].copy()
    df_cmj = df[df["Type"] == "CMJ"].copy()
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_sj.to_excel(writer, sheet_name="SJ", index=False)
        df_cmj.to_excel(writer, sheet_name="CMJ", index=False)
        df_sj[["Trial", "Type"] + cm_hip_cols].to_excel(writer, sheet_name="SJ_CoM_vs_Hip", index=False)
        df_cmj[["Trial", "Type"] + cm_hip_cols].to_excel(writer, sheet_name="CMJ_CoM_vs_Hip", index=False)
    print(f"\n[OK] Excel sačuvan: {excel_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
