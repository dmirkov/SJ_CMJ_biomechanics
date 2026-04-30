# Project Main Aim Flow

This repository is organized around one main objective:
build a robust, comparable biomechanics pipeline for `SJ` and `CMJ` using both AMTI force-plate and Qualisys data.

## 1) Ingest and standardize inputs
- Prepare and standardize source files (force-plate and mocap/CoM).
- Keep subject/trial metadata consistent across sources.

## 2) Detect events robustly
- Detect onset, propulsion, take-off, flight, and landing.
- Use source-specific logic with edge-case handling and fallbacks.

## 3) Compute source-specific KPIs
- AMTI FP: force-, impulse-, velocity-, and power-based KPIs.
- Qualisys: CoM/kinematics-derived KPIs with equivalent biomechanical meaning.

## 4) Harmonize for comparison
- Map outputs to a shared KPI space for cross-system comparison.
- Keep method labels explicit where formulas differ by source.

## 5) Apply QC and invalid-trial filtering
- Flag invalid events and implausible outputs.
- Exclude problematic trials from final comparative summaries.

## 6) Compare systems and export results
- Run FP vs Qualisys agreement/correlation analyses.
- Export comparison-ready tables and plots.

## Core scripts (kept at root)
- `batch_amti_cmj_analysis.py`
- `calculate_fp_kpis.py`
- `add_com_columns.py`
- `calculate_kpis.py`
- `prepare_kpi_data.py`
- `compare_mocap_fp.py`
- `compare_fp_qualisys.py`
- `calculate_correlations.py`
- `create_final_plots.py`

## Documentation layout
- `README_PYTHON_SKRIPTI.md` and `SETUP_PUTANJE.md`: active usage/setup docs
- `docs/iterations/`: historical analyses and iteration reports

## Archive layout
- `archive/legacy_scripts/`: scripts not part of the main current flow
