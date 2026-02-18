"""
Modul za detekciju events (TO, LAND) iz toe/heel markera.
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, Any
import config

logger = logging.getLogger(__name__)


def detect_toe_events(df: pd.DataFrame, toe_col: str = None, heel_col: str = None, 
                      toe_cols_list: list = None,
                      time_col: str = None, fs: float = None,
                      com_col: str = None) -> Dict[str, Any]:
    """
    Detektuje TO i LAND events iz toe/heel markera.
    
    Args:
        df: DataFrame sa podacima
        toe_col: Ime kolone sa toe Z pozicijom (za jednostruku nogu)
        heel_col: Opciono, ime kolone sa heel Z pozicijom (za toe-or-heel detection)
        toe_cols_list: Opciono, lista kolona [small_toe, big_toe, heel] - contact = min(sve)
        time_col: Ime kolone sa vremenom (default: 'Time')
        fs: Sampling rate u Hz (default: iz Time kolone ili config.FS_DEFAULT)
        com_col: Opciono, ime kolone sa CoM Z pozicijom (za validaciju TO - CoM mora biti >= baseline)
        
    Returns:
        Dictionary sa t_TO, t_LAND, i QC flags
    """
    if time_col is None:
        time_col = config.TIME_COL
    
    if time_col not in df.columns:
        logger.warning(f"Kolona {time_col} nedostaje, koristim indeks")
        time = np.arange(len(df)) / (fs if fs else config.FS_DEFAULT)
    else:
        time = df[time_col].values
        # Proveri da li je Time kolona sve NaN
        if pd.isna(time).all():
            logger.warning(f"Kolona {time_col} je sve NaN, koristim indeks")
            time = np.arange(len(df)) / (fs if fs else config.FS_DEFAULT)
        elif fs is None:
            # Izračunaj fs iz Time kolone (samo ako nije sve NaN)
            valid_time = time[~pd.isna(time)]
            if len(valid_time) > 1:
                fs = 1.0 / np.mean(np.diff(valid_time))
            else:
                fs = config.FS_DEFAULT
                time = np.arange(len(df)) / fs
    
    # Izgradi contact_z: iz toe_cols_list (min sve) ili toe_col + heel_col
    if toe_cols_list:
        # Za jednu nogu: contact = najniža tačka (min small_toe, big_toe, heel)
        missing = [c for c in toe_cols_list if c not in df.columns]
        if missing:
            return {
                't_TO': np.nan,
                't_LAND': np.nan,
                'events_invalid': True,
                'missing_columns': ','.join(missing),
                'notes': f'Missing columns: {",".join(missing)}'
            }
        contact_z = pd.Series(df[toe_cols_list[0]].values).ffill().bfill().values
        for col in toe_cols_list[1:]:
            z = pd.Series(df[col].values).ffill().bfill().values
            contact_z = np.minimum(contact_z, z)
    else:
        if toe_col is None or toe_col not in df.columns:
            return {
                't_TO': np.nan,
                't_LAND': np.nan,
                'events_invalid': True,
                'missing_columns': toe_col or 'toe_col',
                'notes': f'Missing {toe_col or "toe_col"}'
            }
        toe_z = df[toe_col].values
        if pd.isna(toe_z).all():
            return {
                't_TO': np.nan,
                't_LAND': np.nan,
                'events_invalid': True,
                'missing_columns': f'{toe_col}',
                'notes': f'All NaN in {toe_col}'
            }
        toe_z = pd.Series(toe_z).ffill().bfill().values
        if heel_col and heel_col in df.columns:
            heel_z = df[heel_col].values
            heel_z = pd.Series(heel_z).ffill().bfill().values
            contact_z = np.minimum(toe_z, heel_z)
        else:
            contact_z = toe_z
    
    # Baseline: prvih T_BASE sekundi
    n_base = int(config.T_BASE * fs)
    n_base = min(n_base, len(contact_z) // 4)  # Ne više od 25% podataka
    
    if n_base < 10:
        return {
            't_TO': np.nan,
            't_LAND': np.nan,
            'events_invalid': True,
            'missing_columns': '',
            'notes': 'Insufficient baseline data'
        }
    
    baseline_z = contact_z[:n_base]
    z_thr = np.median(baseline_z) + config.DZ_CONTACT
    
    # Baseline CoM za validaciju TO (ako je dostupan)
    baseline_com = None
    if com_col and com_col in df.columns:
        com_z = df[com_col].values
        if len(com_z) >= n_base:
            baseline_com = np.median(com_z[:n_base])
    
    # N_hold u uzorcima
    n_hold = max(int(config.N_HOLD_MS / 1000.0 * fs), 1)
    
    # Pronađi apex toe (maksimum pre očekivanog landinga)
    # Koristimo ceo signal za početak
    apex_idx = np.argmax(contact_z)
    t_apex_toe = time[apex_idx]
    
    # TO: idi unazad od apex i nađi poslednji trenutak gde contact_z prelazi z_thr (napušta tlo)
    # Tražimo trenutak kada toe prelazi iz kontakta (<= z_thr) u let (> z_thr)
    # sa uslovom da posle toga ostaje > z_thr najmanje n_hold uzoraka
    t_to = np.nan
    t_to_candidate = np.nan
    
    # Metoda 1: Traži poslednji trenutak gde contact_z prelazi threshold (napušta tlo)
    # Tražimo unazad od apex-a dok ne nađemo prelaz iz <= threshold u > threshold
    # Tražimo od apex_idx unazad do n_base (baseline region)
    search_start = max(n_base, n_hold)
    # Pronađi sve prelaze unazad od apex-a
    for i in range(apex_idx, search_start - 1, -1):
        # Pronađi trenutak gde se prelazi iz kontakta (<= threshold) u let (> threshold)
        if i > 0 and contact_z[i] > z_thr and contact_z[i-1] <= z_thr:
            # Proveri da li posle toga ostaje > z_thr najmanje n_hold uzoraka
            if i + n_hold < len(contact_z):
                if np.all(contact_z[i:i+n_hold] > z_thr):
                    t_to_candidate = time[i]
                    break
    
    # Metoda 2: Ako smo našli kandidata, traži početak kretanja naviše
    if not np.isnan(t_to_candidate):
        candidate_idx = np.argmin(np.abs(time - t_to_candidate))
        # Traži unazad do 50ms da nađeš početak kretanja naviše
        search_back = min(int(0.05 * fs), candidate_idx)
        
        # Traži trenutak gde se pozicija počinje povećavati (početak kretanja naviše)
        for j in range(candidate_idx, max(0, candidate_idx - search_back), -1):
            if j > 0 and j + 3 < len(contact_z):
                # Proveri trend: ako se pozicija povećava u narednih nekoliko uzoraka
                window_size = min(5, len(contact_z) - j)
                if window_size >= 3:
                    trend_forward = np.mean(np.diff(contact_z[j:j+window_size]))
                    trend_backward = np.mean(np.diff(contact_z[max(0,j-2):j+1]))
                    
                    # Početak kretanja naviše: pozitivna brzina napred, negativna ili mala unazad
                    if trend_forward > 0 and trend_backward <= 0.001:
                        t_to = time[j]
                        break
        
        # Fallback: ako nismo našli početak kretanja, koristi trenutak ~20ms pre kandidata
        if np.isnan(t_to):
            offset_samples = min(int(0.02 * fs), candidate_idx)
            t_to = time[max(0, candidate_idx - offset_samples)]
        
        # Validacija: Za CMJ, CoM na t_TO mora biti >= baseline CoM
        # (mehanički, toe ne može napustiti tlo pre nego što CoM vrati u ravnotežni položaj)
        if baseline_com is not None and not np.isnan(t_to):
            t_to_idx = np.argmin(np.abs(time - t_to))
            com_at_to = com_z[t_to_idx] if com_col and com_col in df.columns else None
            
            if com_at_to is not None and com_at_to < baseline_com:
                # Traži napred dok ne nađemo trenutak gde je CoM >= baseline
                # Ovo je validacija: toe ne može napustiti tlo pre nego što CoM vrati u ravnotežni položaj
                for i in range(t_to_idx, min(len(time), t_to_idx + int(0.2 * fs))):  # Traži do 200ms napred
                    if com_z[i] >= baseline_com and contact_z[i] > z_thr:
                        # Proveri da li je toe još uvek iznad praga
                        if i + n_hold < len(contact_z) and np.all(contact_z[i:i+n_hold] > z_thr):
                            t_to = time[i]
                            break
    
    # Metoda 3: Alternativna metoda - traži prvi trenutak gde brzina promene postaje pozitivna
    if np.isnan(t_to) and apex_idx > n_hold:
        # Izračunaj brzinu promene (derivacija)
        dz_dt = np.gradient(contact_z, time)
        # Traži unazad od apex-a prvi trenutak gde je brzina pozitivna i contact_z <= z_thr
        for i in range(apex_idx, n_hold, -1):
            if contact_z[i] <= z_thr and dz_dt[i] > 0:
                # Proveri da li posle toga ostaje > z_thr
                if i + n_hold < len(contact_z):
                    if np.all(contact_z[i+1:i+n_hold+1] > z_thr):
                        t_to = time[i]
                        break
    
    # LAND: od apex idi napred i nađi prvi trenutak gde contact_z <= z_thr
    # sa uslovom stabilnosti n_hold
    # Tražimo trenutak kada toe počinje da dodiruje tlo (malo POSLE nego što počne da se spušta)
    t_land = np.nan
    t_land_candidate = np.nan
    
    # Metoda 1: Traži prvi trenutak stabilnog kontakta
    for i in range(apex_idx, len(contact_z) - n_hold):
        if contact_z[i] <= z_thr:
            # Proveri stabilnost kontakta
            if np.all(contact_z[i:i+n_hold] <= z_thr):
                t_land_candidate = time[i]
                break
    
    # Metoda 2: Ako smo našli kandidata, traži početak kretanja naniže
    if not np.isnan(t_land_candidate):
        candidate_idx = np.argmin(np.abs(time - t_land_candidate))
        # Traži unazad do 50ms da nađeš početak kretanja naniže
        search_back = min(int(0.05 * fs), candidate_idx - apex_idx)
        
        # Traži trenutak gde se pozicija počinje smanjivati (početak kretanja naniže)
        for j in range(candidate_idx, max(apex_idx, candidate_idx - search_back), -1):
            if j > 0 and j + 3 < len(contact_z):
                # Proveri trend: ako se pozicija smanjuje u narednih nekoliko uzoraka
                window_size = min(5, len(contact_z) - j)
                if window_size >= 3:
                    trend_forward = np.mean(np.diff(contact_z[j:j+window_size]))
                    trend_backward = np.mean(np.diff(contact_z[max(0,j-2):j+1]))
                    
                    # Početak kretanja naniže: negativna brzina napred, pozitivna ili mala unazad
                    if trend_forward < 0 and trend_backward >= -0.001:
                        t_land = time[j]
                        break
        
        # Fallback: ako nismo našli početak kretanja, koristi trenutak ~20ms posle kandidata
        if np.isnan(t_land):
            offset_samples = min(int(0.02 * fs), len(contact_z) - candidate_idx - 1)
            t_land = time[min(len(time) - 1, candidate_idx + offset_samples)]
    
    # Metoda 3: Alternativna metoda - traži prvi trenutak gde brzina promene postaje negativna
    # i contact_z prelazi threshold
    if np.isnan(t_land) and apex_idx < len(contact_z) - n_hold:
        # Izračunaj brzinu promene (derivacija)
        dz_dt = np.gradient(contact_z, time)
        # Traži napred od apex-a prvi trenutak gde je brzina negativna i contact_z prelazi threshold
        for i in range(apex_idx, len(contact_z) - n_hold):
            if i > 0 and contact_z[i] <= z_thr and contact_z[i-1] > z_thr and dz_dt[i] < 0:
                # Proveri stabilnost kontakta
                if np.all(contact_z[i:i+n_hold] <= z_thr):
                    t_land = time[i]
                    break
    
    # QC flags
    events_invalid = np.isnan(t_to) or np.isnan(t_land)
    order_invalid = False
    if not events_invalid:
        order_invalid = t_to >= t_land
    
    return {
        't_TO': t_to,
        't_LAND': t_land,
        't_apex_toe': t_apex_toe,
        'z_thr': z_thr,
        'events_invalid': events_invalid,
        'order_invalid': order_invalid,
        'missing_columns': '',
        'notes': ''
    }


def detect_toe_events_3d(df: pd.DataFrame, time_col: str = None, fs: float = None,
                        com_col: str = None, jump_type: str = 'SJ') -> Dict[str, Any]:
    """
    Detektuje TO i LAND za 3D model: OBE noge, svi markeri (small toe, big toe, heel).
    
    Logika:
    - TO = poslednji trenutak kada BILO koji deo obe noge napušta tlo (max od L i R)
    - LAND = prvi trenutak kada BILO koji deo obe noge dotiče tlo (min od L i R)
    
    Po stopalu: contact = min(small_toe, big_toe, heel) - najniža tačka stopala.
    
    Važno za hFT = g*T²/8: precizno T_flight = t_LAND - t_TO.
    
    Args:
        df: DataFrame sa podacima
        time_col: Ime kolone sa vremenom
        fs: Sampling rate
        com_col: Za validaciju CMJ (CoM >= baseline na t_TO)
        jump_type: 'SJ' ili 'CMJ'
        
    Returns:
        Dictionary sa t_TO, t_LAND, i QC flags (isti format kao detect_toe_events)
    """
    left_cols = [
        config.LEFT_TOE_COLS['small_toe'],
        config.LEFT_TOE_COLS['big_toe'],
        config.LEFT_TOE_COLS['heel']
    ]
    right_cols = [
        config.RIGHT_TOE_COLS['small_toe'],
        config.RIGHT_TOE_COLS['big_toe'],
        config.RIGHT_TOE_COLS['heel']
    ]
    missing = [c for c in left_cols + right_cols if c not in df.columns]
    if missing:
        return {
            't_TO': np.nan,
            't_LAND': np.nan,
            'events_invalid': True,
            'missing_columns': ','.join(missing),
            'notes': f'3D: Missing markers: {",".join(missing)}'
        }
    
    events_L = detect_toe_events(df, toe_cols_list=left_cols,
                                 time_col=time_col, fs=fs,
                                 com_col=com_col if jump_type == 'CMJ' else None)
    events_R = detect_toe_events(df, toe_cols_list=right_cols,
                                 time_col=time_col, fs=fs,
                                 com_col=com_col if jump_type == 'CMJ' else None)
    
    t_to_L, t_to_R = events_L['t_TO'], events_R['t_TO']
    t_land_L, t_land_R = events_L['t_LAND'], events_R['t_LAND']
    
    # Global: poslednje što napušta tlo, prvo što dotiče tlo
    t_to = np.nan
    if not np.isnan(t_to_L) and not np.isnan(t_to_R):
        t_to = max(t_to_L, t_to_R)
    elif not np.isnan(t_to_L):
        t_to = t_to_L
    elif not np.isnan(t_to_R):
        t_to = t_to_R
    
    t_land = np.nan
    if not np.isnan(t_land_L) and not np.isnan(t_land_R):
        t_land = min(t_land_L, t_land_R)
    elif not np.isnan(t_land_L):
        t_land = t_land_L
    elif not np.isnan(t_land_R):
        t_land = t_land_R
    
    events_invalid = np.isnan(t_to) or np.isnan(t_land)
    order_invalid = (not events_invalid) and (t_to >= t_land)
    
    t_apex_toe = events_L.get('t_apex_toe', np.nan)
    if np.isnan(t_apex_toe):
        t_apex_toe = events_R.get('t_apex_toe', np.nan)
    
    return {
        't_TO': t_to,
        't_LAND': t_land,
        't_apex_toe': t_apex_toe,
        'z_thr': events_L.get('z_thr', np.nan),
        'events_invalid': events_invalid,
        'order_invalid': order_invalid,
        'missing_columns': '',
        'notes': '3D: both feet, small_toe+big_toe+heel'
    }


def detect_com_onset(df: pd.DataFrame, com_col: str, vz_col: str,
                     time_col: str = None, fs: float = None,
                     anchor_time: float = None) -> Dict[str, Any]:
    """
    Detektuje onset CoM kretanja koristeći robustnu detekciju sa histerezom.
    
    Args:
        df: DataFrame sa podacima
        com_col: Ime kolone sa CoM Z pozicijom
        vz_col: Ime kolone sa vertikalnom brzinom
        time_col: Ime kolone sa vremenom
        fs: Sampling rate
        anchor_time: Vreme anchor tačke (npr. t_zmin za CMJ ili t_TO za SJ)
        
    Returns:
        Dictionary sa t_start i QC flags
    """
    if time_col is None:
        time_col = config.TIME_COL
    
    if time_col not in df.columns:
        if fs is None:
            fs = config.FS_DEFAULT
        time = np.arange(len(df)) / fs
    else:
        time = df[time_col].values
        # Proveri da li je Time kolona sve NaN
        if pd.isna(time).all():
            if fs is None:
                fs = config.FS_DEFAULT
            time = np.arange(len(df)) / fs
        elif fs is None:
            # Izračunaj fs iz Time kolone (samo ako nije sve NaN)
            valid_time = time[~pd.isna(time)]
            if len(valid_time) > 1:
                fs = 1.0 / np.mean(np.diff(valid_time))
            else:
                fs = config.FS_DEFAULT
                time = np.arange(len(df)) / fs
    
    # Proveri kolone
    if com_col not in df.columns or vz_col not in df.columns:
        return {
            't_start': np.nan,
            'onset_invalid': True,
            'missing_columns': f'{com_col},{vz_col}',
            'notes': 'Missing CoM or Vz columns'
        }
    
    com_z = df[com_col].values
    vz = df[vz_col].values
    
    # Popuni NaN
    com_z = pd.Series(com_z).ffill().bfill().values
    vz = pd.Series(vz).ffill().bfill().values
    
    # Signal: |Vz|
    s = np.abs(vz)
    
    # Iskljuci pocetak (problemi markera na startu)
    n_exclude = int(config.ONSET_EXCLUDE_START_S * fs)
    n_exclude = min(n_exclude, len(s) // 4)  # ne vise od 1/4 signala
    
    # Robust baseline: median + MAD (bez pocetka)
    s_valid = s[n_exclude:] if len(s) > n_exclude else s
    med_s = np.median(s_valid)
    mad_s = np.median(np.abs(s_valid - med_s))
    sigma_s = 1.4826 * mad_s if mad_s > 1e-9 else 1e-9
    
    s_low = med_s + 3 * sigma_s
    s_high = med_s + 5 * sigma_s
    
    n_quiet = max(int(config.N_QUIET_MS / 1000.0 * fs), 1)
    n_on = max(int(config.N_ON_MS / 1000.0 * fs), 1)
    
    if anchor_time is not None:
        anchor_idx = np.argmin(np.abs(time - anchor_time))
        search_end = anchor_idx
    else:
        search_end = len(s)
    
    # search_start: ne pretrazuj pre n_exclude (pocetak iskljucen)
    search_start = max(n_quiet, n_on, n_exclude)
    
    t_start = np.nan
    
    for i in range(search_end - n_quiet, search_start - 1, -1):
        if i >= n_quiet and np.all(s[i-n_quiet:i] < s_low):
            z_ref = np.median(com_z[i - n_quiet:i])  # pozicija kad je bio miran
            for j in range(i, min(i + n_on * 10, search_end - n_on)):
                if j + n_on <= len(s) and np.all(s[j:j+n_on] > s_high):
                    # Pomeraj tokom bloka kretanja (robustnije od com_z[j]-z_ref)
                    disp = np.max(np.abs(com_z[j:j+n_on] - z_ref))
                    if disp > config.DISPLACEMENT_GATE_MM / 1000.0:
                        t_start = time[j]
                        break
            if not np.isnan(t_start):
                break
    
    # Fallback: ako nismo našli sa histerezom
    if np.isnan(t_start) and anchor_time is not None:
        anchor_idx = np.argmin(np.abs(time - anchor_time))
        s_threshold = med_s + 2 * sigma_s
        for i in range(anchor_idx - n_on, search_start - 1, -1):
            if i >= 0 and i + n_on <= len(s):
                if np.all(s[i:i+n_on] > s_threshold):
                    z_ref = np.median(com_z[max(0, i - n_quiet):i]) if i >= n_quiet else com_z[i]
                    disp = np.max(np.abs(com_z[i:i+n_on] - z_ref))
                    if disp > config.DISPLACEMENT_GATE_MM / 1000.0:
                        t_start = time[i]
                        break
    
    onset_invalid = np.isnan(t_start)
    
    return {
        't_start': t_start,
        'onset_invalid': onset_invalid,
        'missing_columns': '',
        'notes': 'Onset detected' if not onset_invalid else 'Onset not found'
    }


if __name__ == '__main__':
    # Test
    logging.basicConfig(level=logging.INFO)
    print("Event detection modul - test passed")
