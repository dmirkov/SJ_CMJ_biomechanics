"""
Modul za otkrivanje i parsiranje processed fajlova.
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd
import config

logger = logging.getLogger(__name__)


def parse_filename(filename: str) -> Optional[Dict[str, any]]:
    """
    Parsira ime fajla u formatu: "##_#_#_processed.csv"
    
    Args:
        filename: Ime fajla (npr. "2189_3_2_processed.csv")
        
    Returns:
        Dictionary sa SubjectID, JumpTypeCode, TrialNo, JumpType, ili None ako ne može da se parsira
    """
    # Ukloni ekstenziju
    basename = filename.replace('_processed.csv', '').replace('_processed.tsv', '')
    
    # Regex pattern: broj_broj_broj
    pattern = r'^(\d+)_(\d+)_(\d+)$'
    match = re.match(pattern, basename)
    
    if not match:
        return None
    
    subject_id = match.group(1)
    jump_type_code = int(match.group(2))
    trial_no = int(match.group(3))
    
    # Mapiranje JumpTypeCode na JumpType
    if jump_type_code == 3:
        jump_type = 'SJ'
    elif jump_type_code == 4:
        jump_type = 'CMJ'
    else:
        return None  # Nevalidan JumpTypeCode
    
    return {
        'SubjectID': subject_id,
        'JumpTypeCode': jump_type_code,
        'TrialNo': trial_no,
        'JumpType': jump_type,
        'basename': basename,
        'filename': filename
    }


def discover_processed_files(data_dir: Path = None) -> Dict[str, List[Dict]]:
    """
    Skenira processed_data folder i pronalazi sve processed fajlove.
    
    Args:
        data_dir: Direktorijum sa processed fajlovima (default: config.PROCESSED_DATA_DIR)
        
    Returns:
        Dictionary sa ključevima 'SJ' i 'CMJ', svaki sadrži listu parsed fajlova
    """
    if data_dir is None:
        data_dir = config.PROCESSED_DATA_DIR
    
    if not data_dir.exists():
        logger.error(f"Direktorijum {data_dir} ne postoji!")
        return {'SJ': [], 'CMJ': []}
    
    sj_files = []
    cmj_files = []
    skipped_files = []
    
    # Skeniraj sve CSV i TSV fajlove
    for ext in ['*.csv', '*.tsv']:
        for filepath in data_dir.glob(ext):
            filename = filepath.name
            
            # Proveri da li je processed fajl
            if not filename.endswith('_processed.csv') and not filename.endswith('_processed.tsv'):
                continue
            
            # Parsiraj ime
            parsed = parse_filename(filename)
            
            if parsed is None:
                skipped_files.append(filename)
                logger.warning(f"Ne može da se parsira: {filename} - preskačem")
                continue
            
            # Dodaj putanju
            parsed['filepath'] = filepath
            
            # Grupiši po tipu skoka
            if parsed['JumpType'] == 'SJ':
                sj_files.append(parsed)
            elif parsed['JumpType'] == 'CMJ':
                cmj_files.append(parsed)
    
    # Sortiraj po SubjectID pa TrialNo
    sj_files.sort(key=lambda x: (x['SubjectID'], x['TrialNo']))
    cmj_files.sort(key=lambda x: (x['SubjectID'], x['TrialNo']))
    
    logger.info(f"Pronađeno {len(sj_files)} SJ fajlova, {len(cmj_files)} CMJ fajlova")
    if skipped_files:
        logger.warning(f"Preskočeno {len(skipped_files)} fajlova sa nevalidnim imenima")
    
    return {
        'SJ': sj_files,
        'CMJ': cmj_files
    }


def load_processed_file(filepath: Path) -> Optional[pd.DataFrame]:
    """
    Učitava processed CSV ili TSV fajl.
    
    Args:
        filepath: Putanja do fajla
        
    Returns:
        DataFrame sa podacima ili None ako ne može da se učita
    """
    try:
        # Odredi delimiter
        if filepath.suffix == '.tsv':
            delimiter = '\t'
        else:
            delimiter = ','  # CSV default, ali probaj da detektuješ
        
        # Učitaj fajl
        df = pd.read_csv(filepath, delimiter=delimiter, encoding='utf-8')
        
        logger.debug(f"Učitano {len(df)} redova iz {filepath.name}")
        return df
        
    except Exception as e:
        logger.error(f"Greška pri učitavanju {filepath}: {e}")
        return None


if __name__ == '__main__':
    # Test
    logging.basicConfig(level=logging.INFO)
    files = discover_processed_files()
    print(f"\nSJ fajlovi: {len(files['SJ'])}")
    print(f"CMJ fajlovi: {len(files['CMJ'])}")
    if files['SJ']:
        print(f"\nPrimer SJ fajla: {files['SJ'][0]}")
    if files['CMJ']:
        print(f"Primer CMJ fajla: {files['CMJ'][0]}")
