#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UPOREDNI PREGLED VISINA - QUALISYS vs FP
========================================
Mean (SD) svih visina iz oba sistema.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def format_mean_sd(mean: float, sd: float, decimals: int = 3) -> str:
    """Format: Mean (SD)"""
    if pd.isna(mean) or pd.isna(sd):
        return "-"
    return f"{mean:.{decimals}f} ({sd:.{decimals}f})"


def safe_mean_sd(series: pd.Series):
    """Izračunaj mean i std uz filtriranje NaN/Inf."""
    valid = series.dropna()
    valid = valid[np.isfinite(valid)]
    if len(valid) == 0:
        return np.nan, np.nan
    return valid.mean(), valid.std(ddof=1)


def main():
    base = Path(__file__).parent
    excel_file = base / "Output" / "Excel" / "MoCap_KPIs.xlsx"
    out_dir = base / "Output"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not excel_file.exists():
        print(f"[ERROR] Excel ne postoji: {excel_file}")
        return 1

    print("=" * 90)
    print("UPOREDNI PREGLED VISINA: QUALISYS vs FP")
    print("Mean (SD) u metrima")
    print("=" * 90)
    print(f"Vreme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    # Učitaj sheetove
    sj_fp = pd.read_excel(excel_file, sheet_name='SJ_FP')
    cmj_fp = pd.read_excel(excel_file, sheet_name='CMJ_FP')
    sj_fp['TrialID'] = sj_fp['SubjectID'].astype(str) + '_' + sj_fp['TrialNo'].astype(str)
    cmj_fp['TrialID'] = cmj_fp['SubjectID'].astype(str) + '_' + cmj_fp['TrialNo'].astype(str)

    q_sheets = {
        'SJ3D': 'SJ', 'SJ2DL': 'SJ', 'SJ2DR': 'SJ',
        'CMJ3D': 'CMJ', 'CMJ2DL': 'CMJ', 'CMJ2DR': 'CMJ'
    }

    # FP visine (filtrirati invalid)
    sj_fp_valid = sj_fp[
        sj_fp['Height_V_m'].notna() & np.isfinite(sj_fp['Height_V_m']) &
        sj_fp['Height_T_m'].notna() & np.isfinite(sj_fp['Height_T_m']) &
        (sj_fp['Height_V_m'] < 5) & (sj_fp['Height_V_m'] > 0)  # realne vrednosti
    ]
    cmj_fp_valid = cmj_fp[
        cmj_fp['Height_V_m'].notna() & np.isfinite(cmj_fp['Height_V_m']) &
        cmj_fp['Height_T_m'].notna() & np.isfinite(cmj_fp['Height_T_m']) &
        (cmj_fp['Height_V_m'] < 5) & (cmj_fp['Height_V_m'] > 0)
    ]

    rows = []

    for jump in ['SJ', 'CMJ']:
        fp_df = sj_fp_valid if jump == 'SJ' else cmj_fp_valid

        m_hv, s_hv = safe_mean_sd(fp_df['Height_V_m'])
        m_ht, s_ht = safe_mean_sd(fp_df['Height_T_m'])
        m_depth, s_depth = safe_mean_sd(fp_df['Depth_Max_m']) if 'Depth_Max_m' in fp_df.columns else (np.nan, np.nan)

        rows.append({
            'Jump': jump,
            'Sistem': 'FP',
            'Varijabla': 'Height_V_m',
            'Opis': 'Visina iz brzine (v²/2g)',
            'N': len(fp_df),
            'Mean_SD': format_mean_sd(m_hv, s_hv),
            'Mean': m_hv,
            'SD': s_hv
        })
        rows.append({
            'Jump': jump,
            'Sistem': 'FP',
            'Varijabla': 'Height_T_m',
            'Opis': 'Visina iz vremena leta (gT²/8)',
            'N': len(fp_df),
            'Mean_SD': format_mean_sd(m_ht, s_ht),
            'Mean': m_ht,
            'SD': s_ht
        })
        rows.append({
            'Jump': jump,
            'Sistem': 'FP',
            'Varijabla': 'Depth_Max_m',
            'Opis': 'Maks. dubina (countermovement)',
            'N': len(fp_df),
            'Mean_SD': format_mean_sd(m_depth, s_depth),
            'Mean': m_depth,
            'SD': s_depth
        })

        for q_sheet, jt in q_sheets.items():
            if jt != jump:
                continue
            q_df = pd.read_excel(excel_file, sheet_name=q_sheet)
            q_df['TrialID'] = q_df['SubjectID'].astype(str) + '_' + q_df['TrialNo'].astype(str)

            for var, opis in [
                ('hCoM', 'Visina CoM (displacement)'),
                ('hv', 'Visina iz brzine (v²/2g)'),
                ('hFT', 'Visina iz vremena leta'),
                ('Depth_CMJ', 'Dubina countermovement')
            ]:
                if var not in q_df.columns:
                    continue
                valid = q_df[var].dropna()
                valid = valid[np.isfinite(valid)]
                valid = valid[(valid < 5) & (valid > -0.5)]
                m, s = valid.mean(), valid.std(ddof=1) if len(valid) > 1 else 0
                rows.append({
                    'Jump': jump,
                    'Sistem': f"Qualisys ({q_sheet.replace('SJ','').replace('CMJ','')})",
                    'Varijabla': var,
                    'Opis': opis,
                    'N': len(valid),
                    'Mean_SD': format_mean_sd(m, s),
                    'Mean': m,
                    'SD': s
                })

    df = pd.DataFrame(rows)

    # Tabela za prikaz
    print("\n--- SJ ---")
    sj_rows = df[df['Jump'] == 'SJ']
    for _, r in sj_rows.iterrows():
        print(f"  {r['Sistem']:20} {r['Varijabla']:15} {r['Mean_SD']:25}  N={r['N']}")

    print("\n--- CMJ ---")
    cmj_rows = df[df['Jump'] == 'CMJ']
    for _, r in cmj_rows.iterrows():
        print(f"  {r['Sistem']:20} {r['Varijabla']:15} {r['Mean_SD']:25}  N={r['N']}")

    # Kompaktna pivot tabela
    print("\n" + "=" * 90)
    print("KOMPAKTNA TABELA (Mean (SD) u m)")
    print("=" * 90)

    pivot_data = []
    for jump in ['SJ', 'CMJ']:
        sub = df[df['Jump'] == jump]
        fp_sub = sub[sub['Sistem'] == 'FP']
        q_sub = sub[sub['Sistem'].str.startswith('Qualisys')]

        row = {'Jump': jump}
        for _, r in fp_sub.iterrows():
            row[r['Varijabla'] + '_FP'] = r['Mean_SD']
        for model in ['3D', '2DL', '2DR']:
            qm = q_sub[q_sub['Sistem'] == f'Qualisys ({model})']
            for var in ['hCoM', 'hv', 'hFT', 'Depth_CMJ']:
                v = qm[qm['Varijabla'] == var]
                if len(v) > 0 and v.iloc[0]['Mean_SD'] != '-':
                    row[f"{var}_Q{model}"] = v.iloc[0]['Mean_SD']
        pivot_data.append(row)

    pivot_df = pd.DataFrame(pivot_data)
    print(pivot_df.to_string(index=False))

    # Excel output
    out_excel = out_dir / "Excel" / "Height_Comparison_Overview.xlsx"
    out_excel.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(out_excel, engine='openpyxl') as w:
        df.to_excel(w, sheet_name='Sve_visine', index=False)
        pivot_df.to_excel(w, sheet_name='Pivot', index=False)

    print(f"\n[OK] Sacuvano: {out_excel}")

    # Markdown izvestaj
    md_path = out_dir / "Height_Comparison_Overview.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Uporedni pregled visina: Qualisys vs FP\n\n")
        f.write(f"*Generisano: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
        f.write("## Mean (SD) u metrima\n\n")
        f.write("### SJ\n\n")
        f.write("| Sistem | Varijabla | Opis | Mean (SD) | N |\n")
        f.write("|--------|-----------|------|-----------|---|\n")
        for _, r in df[df['Jump'] == 'SJ'].iterrows():
            f.write(f"| {r['Sistem']} | {r['Varijabla']} | {r['Opis']} | {r['Mean_SD']} | {r['N']} |\n")
        f.write("\n### CMJ\n\n")
        f.write("| Sistem | Varijabla | Opis | Mean (SD) | N |\n")
        f.write("|--------|-----------|------|-----------|---|\n")
        for _, r in df[df['Jump'] == 'CMJ'].iterrows():
            f.write(f"| {r['Sistem']} | {r['Varijabla']} | {r['Opis']} | {r['Mean_SD']} | {r['N']} |\n")
        f.write("\n### Legenda\n\n")
        f.write("- **Height_V_m** (FP): visina iz brzine (v²/2g)\n")
        f.write("- **Height_T_m** (FP): visina iz vremena leta (gT²/8)\n")
        f.write("- **hCoM** (Q): visina CoM (displacement)\n")
        f.write("- **hv** (Q): visina iz brzine\n")
        f.write("- **hFT** (Q): visina iz vremena leta\n")
        f.write("- **Depth_Max_m** / **Depth_CMJ**: dubina countermovement\n")
    print(f"[OK] Markdown: {md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
