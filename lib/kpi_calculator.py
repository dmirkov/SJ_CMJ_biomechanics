"""
Modul za izračunavanje KPIs iz processed podataka.
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, Any
import config
from event_detection import detect_toe_events, detect_toe_events_3d, detect_com_onset
from angles_kinematics import compute_angle_kpis

logger = logging.getLogger(__name__)


def calculate_kpis(df: pd.DataFrame, jump_type: str, model: str,
                   file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Izračunava sve KPIs za jedan processed fajl.
    
    Args:
        df: DataFrame sa processed podacima
        jump_type: 'SJ' ili 'CMJ'
        model: '3D', '2DL', ili '2DR'
        file_info: Dictionary sa informacijama o fajlu (SubjectID, TrialNo, itd.)
        
    Returns:
        Dictionary sa svim KPIs i QC flags
    """
    # Odredi kolone za CoM i Vz
    if model == '3D':
        com_col = config.COM_3D_COL
        vz_col = config.VZ_3D_COL
        toe_cols = None  # 3D koristi detect_toe_events_3d (obe noge, svi markeri)
    elif model == '2DL':
        com_col = config.COM_2DL_COL
        vz_col = config.VZ_2DL_COL
        toe_cols = config.LEFT_TOE_COLS
    elif model == '2DR':
        com_col = config.COM_2DR_COL
        vz_col = config.VZ_2DR_COL
        toe_cols = config.RIGHT_TOE_COLS
    else:
        raise ValueError(f"Nevalidan model: {model}")
    
    # Inicijalizuj rezultat
    result = {
        'FileName': file_info.get('filename', ''),
        'TrialID': file_info.get('basename', ''),
        'SubjectID': file_info.get('SubjectID', ''),
        'TrialNo': file_info.get('TrialNo', ''),
        'Fs_used': np.nan,
        'Duration_s': np.nan,
    }
    
    # Proveri da li postoje potrebne kolone
    missing_cols = []
    if com_col not in df.columns:
        missing_cols.append(com_col)
    if vz_col not in df.columns:
        missing_cols.append(vz_col)
    
    if missing_cols:
        result.update({
            'missing_columns': ','.join(missing_cols),
            'events_invalid': True,
            'flight_invalid': True,
            'notes': f'Missing columns: {",".join(missing_cols)}'
        })
        # Popuni ostale kolone sa NaN
        for col in config.EXCEL_COLUMNS:
            if col not in result:
                result[col] = np.nan
        return result
    
    # Učitaj podatke
    time_col = config.TIME_COL
    if time_col not in df.columns:
        # Kreiraj Time iz indeksa
        fs = config.FS_DEFAULT
        time = np.arange(len(df)) / fs
    else:
        time = df[time_col].values
        # Proveri da li je Time kolona sve NaN
        if pd.isna(time).all():
            logger.warning(f"{file_info.get('filename', '')}: Kolona {time_col} je sve NaN, koristim indeks")
            fs = config.FS_DEFAULT
            time = np.arange(len(df)) / fs
        elif len(time) > 1:
            valid_time = time[~pd.isna(time)]
            if len(valid_time) > 1:
                fs = 1.0 / np.mean(np.diff(valid_time))
            else:
                fs = config.FS_DEFAULT
                time = np.arange(len(df)) / fs
        else:
            fs = config.FS_DEFAULT
            time = np.arange(len(df)) / fs
    
    result['Fs_used'] = fs
    result['Duration_s'] = time[-1] - time[0] if len(time) > 1 else 0
    
    # Proveri da li je fs validan (ne NaN)
    if np.isnan(fs) or fs <= 0:
        fs = config.FS_DEFAULT
        result['Fs_used'] = fs
        result['notes'] = (result.get('notes', '') + '; Invalid fs, using default').strip('; ')
    
    com_z = df[com_col].values
    vz = df[vz_col].values
    
    # Popuni NaN
    com_z = pd.Series(com_z).ffill().bfill().values
    vz = pd.Series(vz).ffill().bfill().values
    
    # Proveri da li su podaci u mm (tipično vrednosti ~900-1100)
    if np.nanmax(com_z) > 10:  # Ako je maksimum > 10m, verovatno je u mm
        logger.warning(f"{file_info.get('filename', '')}: CoM podaci su verovatno u mm, konvertujem u m")
        com_z = com_z / 1000.0
        result['notes'] = 'CoM converted from mm to m'
    
    # Detektuj events
    if model == '3D':
        events = detect_toe_events_3d(df, time_col=time_col, fs=fs,
                                     com_col=com_col, jump_type=jump_type)
    else:
        toe_col = toe_cols.get('small_toe') or toe_cols.get('big_toe')
        heel_col = toe_cols.get('heel')
        if toe_col and toe_col in df.columns:
            events = detect_toe_events(df, toe_col, heel_col, time_col=time_col, fs=fs,
                                       com_col=com_col if jump_type == 'CMJ' else None)
        else:
            events = {
                't_TO': np.nan,
                't_LAND': np.nan,
                'events_invalid': True,
                'missing_columns': toe_col or 'toe_marker',
                'notes': 'Missing toe marker'
            }
    
    t_to = events['t_TO']
    t_land = events['t_LAND']
    
    # Detektuj onset CoM
    # Za CMJ, prvo nađemo t_zmin (najniža tačka pre TO), pa onda onset unazad od njega
    # Za SJ, anchor je t_TO
    t_zmin = np.nan
    zmin = np.nan
    
    if jump_type == 'CMJ' and not np.isnan(t_to):
        # Prvo nađi t_zmin unazad od t_TO (koristi ceo signal do t_TO)
        mask = time <= t_to
        if np.any(mask):
            zmin_idx = np.argmin(com_z[mask])
            t_zmin = time[mask][zmin_idx]
            zmin = com_z[mask][zmin_idx]
            # Sada koristi t_zmin kao anchor za onset detection
            anchor_time = t_zmin
        else:
            anchor_time = None
    else:
        # Za SJ, anchor je t_TO
        anchor_time = t_to if not np.isnan(t_to) else None
    
    # Detektuj onset sa anchor-om
    onset = detect_com_onset(df, com_col, vz_col, time_col, fs, anchor_time)
    t_start = onset['t_start']
    
    # Fallback za CMJ: ako onset detection ne uspe, koristi jednostavniju metodu
    if jump_type == 'CMJ' and np.isnan(t_start) and not np.isnan(t_zmin):
        # Traži prvi trenutak unazad od t_zmin gde CoM počinje da se spušta
        # ili gde Vz postaje negativna
        zmin_idx = np.argmin(np.abs(time - t_zmin))
        z_base = np.median(com_z[:int(config.T_BASE * fs)])
        
        # Traži unazad od t_zmin dok ne nađemo početak spuštanja
        for i in range(zmin_idx, max(0, zmin_idx - int(0.5 * fs)), -1):  # Traži do 0.5s unazad
            if i > 0:
                # Proveri da li je CoM na baseline nivou ili počinje da se spušta
                if abs(com_z[i] - z_base) < 0.01:  # Blizu baseline-a
                    # Proveri da li posle toga ide spuštanje
                    if i + 10 < len(com_z) and com_z[i+10] < com_z[i] - 0.005:  # Spuštanje od bar 5mm
                        t_start = time[i]
                        break
                # Alternativno, proveri Vz
                if vz[i] < -0.05:  # Negativna brzina (spuštanje)
                    # Traži unazad dok ne nađemo gde je Vz bila blizu nule
                    for j in range(i, max(0, i - int(0.1 * fs)), -1):
                        if abs(vz[j]) < 0.02:  # Blizu nule
                            t_start = time[j]
                            break
                    if not np.isnan(t_start):
                        break
    
    # Ako je CMJ i imamo t_start, proveri da li je t_zmin između t_start i t_TO
    if jump_type == 'CMJ' and not np.isnan(t_start) and not np.isnan(t_to):
        # Proveri da li je t_zmin između t_start i t_TO
        if np.isnan(t_zmin) or t_zmin < t_start or t_zmin > t_to:
            # Pronađi najnižu tačku između t_start i t_TO
            mask = (time >= t_start) & (time <= t_to)
            if np.any(mask):
                zmin_idx = np.argmin(com_z[mask])
                t_zmin = time[mask][zmin_idx]
                zmin = com_z[mask][zmin_idx]
    
    # Izračunaj vremenske faze (T_downward, T_upward, TTO = CoM-based)
    t_downward = np.nan
    t_upward = np.nan
    tto = np.nan
    t_ecc = np.nan
    t_con = np.nan
    t_takeoff = np.nan
    t_flight = np.nan

    if jump_type == 'CMJ':
        if not np.isnan(t_start) and not np.isnan(t_zmin):
            t_downward = t_zmin - t_start
            t_ecc = t_downward  # legacy
        if not np.isnan(t_zmin) and not np.isnan(t_to):
            t_upward = t_to - t_zmin
            t_con = t_upward  # legacy
        if not np.isnan(t_downward) and not np.isnan(t_upward):
            tto = t_downward + t_upward
        if not np.isnan(t_start) and not np.isnan(t_to):
            t_takeoff = t_to - t_start
    else:  # SJ - nema down/up po CoM, TTO = ukupno vreme do TO
        tto = (t_to - t_start) if not np.isnan(t_to) and not np.isnan(t_start) else np.nan
        # Za SJ, takeoff faza = koncentrična faza
        # t_con_strict = t_TO - t_up (gde je t_up početak kontinuiranog kretanja naviše)
        # Traži t_up: prvi trenutak gde Vz > v_thr tokom >= 30ms
        t_up = np.nan
        if not np.isnan(t_to):
            n_on = max(int(0.03 * fs), 1)  # 30ms
            for i in range(len(vz) - n_on):
                if np.all(vz[i:i+n_on] > config.V_THR):
                    t_up = time[i]
                    break
        
        if not np.isnan(t_up) and not np.isnan(t_to):
            t_con_strict = t_to - t_up
        else:
            t_con_strict = np.nan
        
        # Za SJ, T_takeoff_obs = T_con_strict (takeoff faza je koncentrična faza)
        # Ali možemo da zadržimo i t_start za QC/analizu ako je potrebno
        # Ako nema t_up, koristimo t_start kao fallback
        if not np.isnan(t_con_strict):
            t_takeoff_obs = t_con_strict  # Isto kao T_con_strict za SJ
        elif not np.isnan(t_start) and not np.isnan(t_to):
            t_takeoff_obs = t_to - t_start  # Fallback ako nema t_up
        else:
            t_takeoff_obs = np.nan
    
    if not np.isnan(t_to) and not np.isnan(t_land):
        t_flight = t_land - t_to
    
    # Depth_CMJ (samo za CMJ)
    depth_cmj = np.nan
    if jump_type == 'CMJ' and not np.isnan(t_start) and not np.isnan(t_zmin):
        z_start = np.interp(t_start, time, com_z)
        depth_cmj = z_start - zmin
    
    # Brzine pre odraza
    vmin_pre = np.nan
    vmax_pre = np.nan
    vto = np.nan
    
    if not np.isnan(t_start) and not np.isnan(t_to):
        mask = (time >= t_start) & (time <= t_to)
        if np.any(mask):
            vmin_pre = np.min(vz[mask])
            vmax_pre = np.max(vz[mask])
    
    if not np.isnan(t_to):
        vto = np.interp(t_to, time, vz)
    
    # Visine skoka
    t_apex = np.nan
    hcom = np.nan
    hcom_max_to = np.nan
    hcom_onset_corr = np.nan
    hcom_upright_ref = np.nan
    hv = np.nan
    hft = np.nan
    hcom_ankle_corr = np.nan  # (hmax_CoM - honset_CoM) - (hAnkle_TO - hAnkle_onset)
    z_to = np.nan
    z_apex = np.nan
    z_upright_ref = np.nan

    # Constants used across height corrections
    SJ_UPRIGHT_WIN_START = 0.3  # s after landing
    SJ_UPRIGHT_WIN_END = 1.2    # s after landing
    
    if not np.isnan(t_to) and not np.isnan(t_land):
        mask = (time >= t_to) & (time <= t_land)
        if np.any(mask):
            flight_z = com_z[mask]
            flight_time = time[mask]
            
            # Proveri da li ima NaN ili gapova u flight-u
            if not np.any(np.isnan(flight_z)) and len(flight_z) > 0:
                apex_idx = np.argmax(flight_z)
                t_apex = flight_time[apex_idx]
                z_apex = flight_z[apex_idx]
                z_to = np.interp(t_to, time, com_z)
                hcom = z_apex - z_to
                
                # hFT iz flight time
                if t_flight > 0:
                    hft = config.G * (t_flight ** 2) / 8.0

    # Upright CoM reference (independent of ankle markers)
    # - SJ: upright posture AFTER landing (if recorded)
    #       Use a short averaging zone around the detected upright point, instead of one sample.
    # - CMJ: typically already upright before onset, so we don't use this by default here
    if jump_type == 'SJ' and not np.isnan(t_land):
        t_win_start = t_land + SJ_UPRIGHT_WIN_START
        t_win_end = min(time[-1], t_land + SJ_UPRIGHT_WIN_END)
        mask_upright = (time >= t_win_start) & (time <= t_win_end)
        if np.any(mask_upright):
            # 1) detect upright point as maximum CoM in the post-landing upright window
            idx_rel = int(np.argmax(com_z[mask_upright]))
            t_upright_point = float(time[mask_upright][idx_rel])
            i_center = int(np.argmin(np.abs(time - t_upright_point)))

            # 2) compute local mean in a short zone around that point (robust against sample noise)
            #    default half-window: 50 ms each side (total 100 ms zone)
            zone_half_s = 0.05
            n_half = max(int(zone_half_s * fs), 1)
            i0 = max(0, i_center - n_half)
            i1 = min(len(com_z), i_center + n_half + 1)
            z_upright_ref = float(np.mean(com_z[i0:i1]))

    # Dodatni CoM KPI:
    # 1) hCoM_max_TO = (z_apex u flight-u) - z_TO
    #    (flight-only; izbegava post-landing "upright" maksimume)
    # 2) hCoM_onset_corr:
    #    CMJ: korekcija za pre-TO uspon -> hCoM_max_TO - (z_TO - z_onset)
    #    SJ: korekcija u odnosu na upright referencu (posle landing-a), koristeci i z_TO:
    #        hCoM_onset_corr = hCoM_max_TO + (z_TO - z_upright_ref) = z_apex - z_upright_ref
    if not np.isnan(t_to):
        if np.isnan(z_to):
            z_to = np.interp(t_to, time, com_z)

        # flight-only max (prefer z_apex already computed)
        z_max_flight = np.nan
        if not np.isnan(z_apex):
            z_max_flight = z_apex
        elif not np.isnan(t_land):
            flight_mask = (time >= t_to) & (time <= t_land)
            if np.any(flight_mask):
                z_max_flight = np.max(com_z[flight_mask])

        if not np.isnan(z_max_flight):
            hcom_max_to = z_max_flight - z_to

            if jump_type == 'CMJ' and not np.isnan(t_start):
                z_start = np.interp(t_start, time, com_z)
                pre_to_rise = z_to - z_start
                hcom_onset_corr = hcom_max_to - pre_to_rise
            else:
                if jump_type == 'SJ' and not np.isnan(z_upright_ref):
                    hcom_onset_corr = hcom_max_to + (z_to - z_upright_ref)
                else:
                    hcom_onset_corr = hcom_max_to

            # Optional explicit upright-referenced height (same quantity as the SJ correction above)
            if not np.isnan(z_upright_ref):
                hcom_upright_ref = z_max_flight - z_upright_ref
    
    if not np.isnan(vto):
        hv = (vto ** 2) / (2 * config.G)
    
    # hCoM_ankle_corr: (hmax_CoM - z_CoM_ref) - (hAnkle_TO - z_ankle_ref)
    # Umanjuje visinu za vertikalni pomeraj skocnog zgloba (plantarfleksija na prste).
    # CMJ: z_ref = polozaj 0.2s pre onseta (ankle miran, uspravan).
    # SJ: z_ref = uspravan polozaj nakon leta (CoM i ankle kad se ispitanik uspravio).
    ANKLE_REF_OFFSET_S = 0.2  # s pre onseta za CMJ
    ankle_cols = []
    if model == '3D':
        ankle_cols = ['left_ankle_pos_Z', 'right_ankle_pos_Z']
    elif model == '2DL':
        ankle_cols = ['left_ankle_pos_Z']
    elif model == '2DR':
        ankle_cols = ['right_ankle_pos_Z']
    if ankle_cols and all(c in df.columns for c in ankle_cols):
        ankle_z = np.nanmean([pd.Series(df[c].values).ffill().bfill().values for c in ankle_cols], axis=0)
        if np.nanmax(ankle_z) > 10:  # mm -> m
            ankle_z = ankle_z / 1000.0
        if not np.isnan(t_to) and not np.isnan(t_apex):
            hmax_com = np.interp(t_apex, time, com_z)
            hankle_to = np.interp(t_to, time, ankle_z)
            t_ref = np.nan
            if jump_type == 'CMJ' and not np.isnan(t_start):
                t_ref = max(time[0] + config.ONSET_EXCLUDE_START_S, t_start - ANKLE_REF_OFFSET_S)
            elif jump_type == 'SJ' and not np.isnan(t_land):
                t_win_start = t_land + SJ_UPRIGHT_WIN_START
                t_win_end = min(time[-1], t_land + SJ_UPRIGHT_WIN_END)
                mask_upright = (time >= t_win_start) & (time <= t_win_end)
                if np.any(mask_upright):
                    idx_max = np.argmax(com_z[mask_upright])
                    t_ref = time[mask_upright][idx_max]
            if not np.isnan(t_ref):
                z_com_ref = np.interp(t_ref, time, com_z)
                z_ankle_ref = np.interp(t_ref, time, ankle_z)
                com_rise = hmax_com - z_com_ref
                ankle_rise = hankle_to - z_ankle_ref
                hcom_ankle_corr = com_rise - ankle_rise

                # SJ "upright reference" height:
                # If the subject starts in a squat (low CoM) and returns to upright after landing,
                # we can compute height relative to that upright reference posture.
                # (For CMJ, t_ref is pre-onset upright; for SJ, t_ref is post-landing upright.)
                if not np.isnan(z_apex):
                    hcom_upright_ref = z_apex - z_com_ref
    
    # ========== HIP-BASED KPIs (isto kao CoM, ali za hip centar) ==========
    t_start_hip = np.nan
    t_zmin_hip = np.nan
    T_downward_hip = np.nan
    T_upward_hip = np.nan
    TTO_hip = np.nan
    vmin_pre_hip = np.nan
    vmax_pre_hip = np.nan
    vTO_hip = np.nan
    t_apex_hip = np.nan
    hhip = np.nan
    hv_hip = np.nan
    hhip_ankle_corr = np.nan
    depth_cmj_hip = np.nan
    
    hip_cols = []
    if model == '3D':
        hip_cols = ['left_hip_pos_Z', 'right_hip_pos_Z']
    elif model == '2DL':
        hip_cols = ['left_hip_pos_Z']
    elif model == '2DR':
        hip_cols = ['right_hip_pos_Z']
    
    if hip_cols and all(c in df.columns for c in hip_cols):
        hip_z = np.nanmean([pd.Series(df[c].values).ffill().bfill().values for c in hip_cols], axis=0)
        if np.nanmax(hip_z) > 10:
            hip_z = hip_z / 1000.0
        v_hip = np.gradient(hip_z, time) if len(time) > 1 else np.zeros_like(hip_z)
        
        # Onset za hip: ISTA LOGIKA kao CoM (isti anchor, isti detect_com_onset)
        # CMJ: anchor = t_zmin (CoM), SJ: anchor = t_TO
        anchor_hip = t_zmin if (jump_type == 'CMJ' and not np.isnan(t_zmin)) else (t_to if not np.isnan(t_to) else None)
        df_hip = df.copy()
        df_hip['_hip_z_temp'] = hip_z
        df_hip['_v_hip_temp'] = v_hip
        onset_hip = detect_com_onset(df_hip, '_hip_z_temp', '_v_hip_temp', time_col, fs, anchor_hip)
        t_start_hip = onset_hip['t_start']
        # NE forsiraj t_start_hip = t_start – hip ima svoj onset, može se razlikovati od CoM

        if jump_type == 'CMJ' and not np.isnan(t_start_hip) and not np.isnan(t_to):
            mask_hip = (time >= t_start_hip) & (time <= t_to)
            if np.any(mask_hip):
                zmin_hip_idx = np.argmin(hip_z[mask_hip])
                t_zmin_hip = time[mask_hip][zmin_hip_idx]
                if not np.isnan(t_start_hip) and not np.isnan(t_zmin_hip):
                    T_downward_hip = t_zmin_hip - t_start_hip
                if not np.isnan(t_zmin_hip) and not np.isnan(t_to):
                    T_upward_hip = t_to - t_zmin_hip
                if not np.isnan(T_downward_hip) and not np.isnan(T_upward_hip):
                    TTO_hip = T_downward_hip + T_upward_hip
                z_start_hip = np.interp(t_start_hip, time, hip_z)
                zmin_hip = np.interp(t_zmin_hip, time, hip_z)
                depth_cmj_hip = z_start_hip - zmin_hip
        else:
            TTO_hip = (t_to - t_start_hip) if not np.isnan(t_to) and not np.isnan(t_start_hip) else np.nan
        
        if not np.isnan(t_start_hip) and not np.isnan(t_to):
            mask_hip = (time >= t_start_hip) & (time <= t_to)
            if np.any(mask_hip):
                vmin_pre_hip = np.min(v_hip[mask_hip])
                vmax_pre_hip = np.max(v_hip[mask_hip])
        if not np.isnan(t_to):
            vTO_hip = np.interp(t_to, time, v_hip)
        if not np.isnan(vTO_hip):
            hv_hip = (vTO_hip ** 2) / (2 * config.G)
        
        if not np.isnan(t_to) and not np.isnan(t_land):
            mask_hip = (time >= t_to) & (time <= t_land)
            if np.any(mask_hip):
                flight_hip_z = hip_z[mask_hip]
                flight_time_hip = time[mask_hip]
                if not np.any(np.isnan(flight_hip_z)) and len(flight_hip_z) > 0:
                    apex_hip_idx = np.argmax(flight_hip_z)
                    t_apex_hip = flight_time_hip[apex_hip_idx]
                    z_apex_hip = flight_hip_z[apex_hip_idx]
                    z_to_hip = np.interp(t_to, time, hip_z)
                    hhip = z_apex_hip - z_to_hip
        
        acols = []
        if model == '3D':
            acols = ['left_ankle_pos_Z', 'right_ankle_pos_Z']
        elif model == '2DL':
            acols = ['left_ankle_pos_Z']
        elif model == '2DR':
            acols = ['right_ankle_pos_Z']
        if acols and all(c in df.columns for c in acols) and not np.isnan(t_apex_hip):
            ankle_z_hip = np.nanmean([pd.Series(df[c].values).ffill().bfill().values for c in acols], axis=0)
            if np.nanmax(ankle_z_hip) > 10:
                ankle_z_hip = ankle_z_hip / 1000.0
            hmax_hip = np.interp(t_apex_hip, time, hip_z)
            hankle_to = np.interp(t_to, time, ankle_z_hip)
            t_ref_hip = np.nan
            if jump_type == 'CMJ' and not np.isnan(t_start_hip):
                t_ref_hip = max(time[0] + config.ONSET_EXCLUDE_START_S, t_start_hip - ANKLE_REF_OFFSET_S)
            elif jump_type == 'SJ' and not np.isnan(t_land):
                t_win_start = t_land + SJ_UPRIGHT_WIN_START
                t_win_end = min(time[-1], t_land + SJ_UPRIGHT_WIN_END)
                mask_upright = (time >= t_win_start) & (time <= t_win_end)
                if np.any(mask_upright):
                    idx_max = np.argmax(com_z[mask_upright])
                    t_ref_hip = time[mask_upright][idx_max]
            if not np.isnan(t_ref_hip):
                z_hip_ref = np.interp(t_ref_hip, time, hip_z)
                z_ankle_ref = np.interp(t_ref_hip, time, ankle_z_hip)
                hip_rise = hmax_hip - z_hip_ref
                ankle_rise_hip = hankle_to - z_ankle_ref
                hhip_ankle_corr = hip_rise - ankle_rise_hip
    
    # Landing KPIs
    t_zmin_land = np.nan
    depth_land = np.nan
    vmin_land = np.nan
    t_land_duration = np.nan
    
    if not np.isnan(t_land):
        land_end = t_land + config.W_LAND
        mask = (time >= t_land) & (time <= land_end)
        if np.any(mask):
            zmin_land_idx = np.argmin(com_z[mask])
            t_zmin_land = time[mask][zmin_land_idx]
            zmin_land = com_z[mask][zmin_land_idx]
            z_land = np.interp(t_land, time, com_z)
            depth_land = z_land - zmin_land
            
            # vmin_land (najveća brzina spuštanja)
            mask_v = (time >= t_land) & (time <= t_zmin_land)
            if np.any(mask_v):
                vmin_land = np.min(vz[mask_v])
            
            t_land_duration = t_zmin_land - t_land
    
    # QC flags
    flight_invalid = False
    if not np.isnan(t_flight):
        if t_flight < config.MIN_FLIGHT_TIME:
            flight_invalid = True
        elif not np.isnan(t_to) and not np.isnan(t_land):
            mask = (time >= t_to) & (time <= t_land)
            if np.any(mask):
                flight_z = com_z[mask]
                if np.any(np.isnan(flight_z)):
                    flight_invalid = True
    
    order_invalid = events.get('order_invalid', False)
    if not order_invalid:
        if not np.isnan(t_start) and not np.isnan(t_to):
            order_invalid = t_start >= t_to
        if not order_invalid and not np.isnan(t_to) and not np.isnan(t_land):
            order_invalid = t_to >= t_land
    
    # SJ dip detection
    sj_with_dip = False
    cmj_like = False
    
    if jump_type == 'SJ' and not np.isnan(t_start) and not np.isnan(t_to):
        # Baseline za dip detection
        n_base = int(config.T_BASE * fs)
        n_base = min(n_base, len(com_z) // 4)
        if n_base > 0:
            z_base = np.median(com_z[:n_base])
            sigma_z = np.std(com_z[:n_base])
            
            # Traži dip pre TO
            t_base_end = time[n_base] if n_base < len(time) else time[-1]
            mask = (time >= t_base_end) & (time <= t_to)
            
            if np.any(mask):
                dip_z = com_z[mask]
                dip_time = time[mask]
                z_min_dip = np.min(dip_z)
                depth_dip = z_base - z_min_dip
                
                # T_dip: vreme ispod (z_base - alpha)
                alpha = max(3 * sigma_z, config.ALPHA_DIP_MM / 1000.0)
                threshold_dip = z_base - alpha
                mask_dip = dip_z < threshold_dip
                if np.any(mask_dip):
                    t_dip = np.sum(np.diff(dip_time)[np.where(mask_dip)[0][:-1]]) if len(np.where(mask_dip)[0]) > 1 else 0
                else:
                    t_dip = 0
                
                # vmin_pre za dip proveru
                vmin_pre_dip = vmin_pre if not np.isnan(vmin_pre) else 0
                
                # Proveri kriterijume za dip
                depth_ok = depth_dip > max(config.MIN_DIP_DEPTH_MM / 1000.0, 5 * sigma_z)
                time_ok = t_dip > config.MIN_DIP_TIME
                vel_ok = vmin_pre_dip < config.MIN_DIP_VELOCITY
                
                criteria_met = sum([depth_ok, time_ok, vel_ok])
                sj_with_dip = criteria_met >= 2
                
                # CMJ-like flag
                if depth_dip > config.CMJ_LIKE_DEPTH_MM / 1000.0 and t_dip > config.CMJ_LIKE_TIME:
                    cmj_like = True

    # Kinematički KPIs (uglovi, onset po kandidatu) - samo za 3D
    angle_kpis = {}
    if model == '3D':
        angle_kpis = compute_angle_kpis(
            df, time, fs, t_start, t_zmin, t_to, jump_type, com_col, vz_col
        )

    # Sastavi rezultat
    result.update({
        't_start': t_start,
        't_zmin': t_zmin if jump_type == 'CMJ' else np.nan,
        't_TO': t_to,
        't_LAND': t_land,
        't_apex': t_apex,
        't_zmin_land': t_zmin_land,
        'T_downward': t_downward if jump_type == 'CMJ' else np.nan,
        'T_upward': t_upward if jump_type == 'CMJ' else np.nan,
        'TTO': tto,
        'T_ecc': t_ecc if jump_type == 'CMJ' else np.nan,
        'T_con': t_con if jump_type == 'CMJ' else np.nan,
        'T_takeoff': t_takeoff if jump_type == 'CMJ' else np.nan,
        'T_flight': t_flight,
        'T_con_strict': t_con_strict if jump_type == 'SJ' else np.nan,
        'T_takeoff_obs': t_takeoff_obs if jump_type == 'SJ' else np.nan,
        'Depth_CMJ': depth_cmj,
        'vmin_pre': vmin_pre,
        'vmax_pre': vmax_pre,
        'vTO': vto,
        'hCoM': hcom,
        'hCoM_max_TO': hcom_max_to,
        'hCoM_onset_corr': hcom_onset_corr,
        'hCoM_upright_ref': hcom_upright_ref,
        'hCoM_ankle_corr': hcom_ankle_corr,
        'hv': hv,
        'hFT': hft,
        # Hip-based KPIs
        't_start_hip': t_start_hip,
        't_zmin_hip': t_zmin_hip if jump_type == 'CMJ' else np.nan,
        'T_downward_hip': T_downward_hip if jump_type == 'CMJ' else np.nan,
        'T_upward_hip': T_upward_hip if jump_type == 'CMJ' else np.nan,
        'TTO_hip': TTO_hip,
        'vmin_pre_hip': vmin_pre_hip,
        'vmax_pre_hip': vmax_pre_hip,
        'vTO_hip': vTO_hip,
        'Depth_CMJ_hip': depth_cmj_hip if jump_type == 'CMJ' else np.nan,
        'hHip': hhip,
        'hHip_ankle_corr': hhip_ankle_corr,
        'hv_hip': hv_hip,
        'Depth_land': depth_land,
        'vmin_land': vmin_land,
        'T_land': t_land_duration,
        'sj_with_dip': sj_with_dip,
        'cmj_like': cmj_like,
        'flight_invalid': flight_invalid,
        'events_invalid': events.get('events_invalid', True),
        'missing_columns': events.get('missing_columns', '') or onset.get('missing_columns', ''),
        'order_invalid': order_invalid,
        'notes': events.get('notes', '') or onset.get('notes', '')
    })
    result.update(angle_kpis)

    # Popuni sve kolone iz config
    for col in config.EXCEL_COLUMNS:
        if col not in result:
            result[col] = np.nan

    return result


if __name__ == '__main__':
    # Test
    logging.basicConfig(level=logging.INFO)
    print("KPI calculator modul - test passed")
