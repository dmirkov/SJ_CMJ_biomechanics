"""
Glavna skripta za izračunavanje KPIs iz processed fajlova.
CLI: python main_kpi.py --mode sj|cmj|all --out Output/Excel/MoCap_KPIs.xlsx --limit N --verbose
"""
import argparse
import logging
import sys
from pathlib import Path
import numpy as np
import config
from file_discovery import discover_processed_files, load_processed_file
from kpi_calculator import calculate_kpis
from export_excel import export_to_excel

# Konfiguracija logovanja
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def process_files(mode: str = 'all', limit: int = None, step: str = None, 
                  model: str = None, verbose: bool = False):
    """
    Glavna funkcija za obradu fajlova i izračunavanje KPIs.
    
    Args:
        mode: 'sj', 'cmj', ili 'all'
        limit: Ograniči broj fajlova za obradu (za testiranje)
        step: Korak za izvršavanje ('discover', 'kpi', 'export', ili None za sve)
        model: Model za KPI izračunavanje ('3d', '2dl', '2dr', ili None za sve)
        verbose: Detaljno logovanje
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # KORAK 0: File discovery
    if step is None or step == 'discover':
        logger.info("=== KORAK 0: File Discovery ===")
        files = discover_processed_files()
        
        sj_count = len(files['SJ'])
        cmj_count = len(files['CMJ'])
        
        logger.info(f"Pronađeno {sj_count} SJ fajlova, {cmj_count} CMJ fajlova")
        
        if sj_count > 0:
            logger.info(f"Primer SJ fajla: {files['SJ'][0]['filename']}")
        if cmj_count > 0:
            logger.info(f"Primer CMJ fajla: {files['CMJ'][0]['filename']}")
        
        if step == 'discover':
            return
    
    # Filtriranje po modu
    if mode == 'sj':
        files_to_process = {'SJ': files['SJ'], 'CMJ': []}
    elif mode == 'cmj':
        files_to_process = {'SJ': [], 'CMJ': files['CMJ']}
    else:
        files_to_process = files
    
    # Limit za testiranje
    if limit:
        files_to_process['SJ'] = files_to_process['SJ'][:limit]
        files_to_process['CMJ'] = files_to_process['CMJ'][:limit]
    
    # KORAK 1-3: KPI izračunavanje
    if step is None or step == 'kpi':
        logger.info("=== KORAK 1-3: KPI Calculation ===")
        
        # Struktura: all_kpis[jump_type][model] = lista KPI dictionaries
        all_kpis = {
            'SJ': {'3D': [], '2DL': [], '2DR': []},
            'CMJ': {'3D': [], '2DL': [], '2DR': []}
        }
        
        models_to_process = ['3D', '2DL', '2DR']
        if model:
            models_to_process = [model.upper()]
        
        for jump_type in ['SJ', 'CMJ']:
            for file_info in files_to_process[jump_type]:
                filepath = file_info['filepath']
                logger.info(f"Obrađujem {file_info['filename']} ({jump_type})...")
                
                # Učitaj fajl
                df = load_processed_file(filepath)
                if df is None:
                    logger.warning(f"Ne može da se učita {file_info['filename']}, preskačem")
                    continue
                
                # Izračunaj KPIs za svaki model
                for model_name in models_to_process:
                    try:
                        kpis = calculate_kpis(df, jump_type, model_name, file_info)
                        all_kpis[jump_type][model_name].append(kpis)
                        
                        if verbose:
                            logger.debug(f"  {model_name}: t_TO={kpis.get('t_TO', 'NaN'):.3f}, "
                                       f"t_LAND={kpis.get('t_LAND', 'NaN'):.3f}, "
                                       f"T_flight={kpis.get('T_flight', 'NaN'):.3f}")
                    except Exception as e:
                        logger.error(f"Greška pri izračunavanju KPIs za {file_info['filename']} ({model_name}): {e}")
                        # Dodaj prazan rezultat sa error flagom
                        error_kpis = {
                            'FileName': file_info['filename'],
                            'TrialID': file_info['basename'],
                            'SubjectID': file_info['SubjectID'],
                            'TrialNo': file_info['TrialNo'],
                            'missing_columns': '',
                            'events_invalid': True,
                            'flight_invalid': True,
                            'notes': f'Error: {str(e)}'
                        }
                        for col in config.EXCEL_COLUMNS:
                            if col not in error_kpis:
                                error_kpis[col] = np.nan
                        all_kpis[jump_type][model_name].append(error_kpis)
        
        if step == 'kpi':
            return all_kpis
    
    # KORAK 4: Export u Excel
    if step is None or step == 'export':
        logger.info("=== KORAK 4: Export to Excel ===")
        
        if step == 'export' and 'all_kpis' not in locals():
            logger.error("Nema KPI podataka za export. Pokrenite prvo 'kpi' korak.")
            return
        
        export_to_excel(all_kpis)
        
        # QC summary
        total_files = sum(
            sum(len(all_kpis[k][m]) for m in all_kpis[k])
            for k in all_kpis
        )
        total_invalid = sum(
            sum(
                sum(1 for kpi in all_kpis[k][m] if kpi.get('events_invalid', False))
                for m in all_kpis[k]
            )
            for k in all_kpis
        )
        logger.info(f"Ukupno obrađeno: {total_files} fajlova")
        logger.info(f"Sa invalid events: {total_invalid}")
    
    logger.info("Obrada završena!")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Izračunaj KPIs iz processed fajlova',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--mode', choices=['sj', 'cmj', 'all'], default='all',
                       help='Tip skoka za obradu (default: all)')
    parser.add_argument('--out', type=str, default=None,
                       help='Output Excel fajl (default: Output/Excel/MoCap_KPIs.xlsx)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Ograniči broj fajlova za obradu (za testiranje)')
    parser.add_argument('--step', choices=['discover', 'kpi', 'export'], default=None,
                       help='Izvrši samo određeni korak')
    parser.add_argument('--model', choices=['3d', '2dl', '2dr'], default=None,
                       help='Model za KPI izračunavanje (samo za step=kpi)')
    parser.add_argument('--verbose', action='store_true',
                       help='Detaljno logovanje')
    
    args = parser.parse_args()
    
    if args.out:
        config.EXCEL_OUTPUT_FILE = Path(args.out)
    
    try:
        process_files(
            mode=args.mode,
            limit=args.limit,
            step=args.step,
            model=args.model,
            verbose=args.verbose
        )
    except Exception as e:
        logger.error(f"Kritična greška: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
