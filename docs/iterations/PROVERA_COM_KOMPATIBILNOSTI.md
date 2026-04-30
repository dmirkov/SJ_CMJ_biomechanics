# Provera kompatibilnosti mocap_com_v2_sexmap.py sa TSV fajlovima

**Datum provere:** 2026-02-01

## 📋 ANALIZA SKRIPTE

### Lokacija fajla:
`C:\Users\dmirk\A_Cursor_Projekti\SJ_CMJ_Qualisys_AMTI\mocap_com_v2_sexmap.py`

### Funkcionalnost:
Skripta izračunava Center of Mass (CoM) iz Qualisys TSV fajlova koristeći:
- **3D CoM model**: `CoM3D_X`, `CoM3D_Y`, `CoM3D_Z`
- **2D CoM model (leva strana)**: `CoM2DL_X`, `CoM2DL_Z`
- **2D CoM model (desna strana)**: `CoM2DR_X`, `CoM2DR_Z`

## ✅ PROVERA KOMPATIBILNOSTI

### 1. Tražene kolone u skripti (MARKER_PREFIX):

| Marker | Leva strana | Desna strana | Status u TSV |
|--------|------------|--------------|--------------|
| shoulder | `left_shoulder_pos` | `right_shoulder_pos` | ✅ POSTOJI |
| hip | `left_hip_pos` | `right_hip_pos` | ✅ POSTOJI |
| knee | `left_knee_pos` | `right_knee_pos` | ✅ POSTOJI |
| ankle | `left_ankle_pos` | `right_ankle_pos` | ✅ POSTOJI |
| big_toe | `left_big_toe_pos` | `right_big_toe_pos` | ✅ POSTOJI |
| small_toe | `left_small_toe_pos` | `right_small_toe_pos` | ✅ POSTOJI |
| heel | `left_heel_pos` | `right_heel_pos` | ✅ POSTOJI (ali se ne koristi u required) |

### 2. Potrebne kolone za 3D CoM model:

**Required markers (linija 220-227):**
- ✅ `hip` (L, R) → `left_hip_pos_X/Y/Z`, `right_hip_pos_X/Y/Z`
- ✅ `shoulder` (L, R) → `left_shoulder_pos_X/Y/Z`, `right_shoulder_pos_X/Y/Z`
- ✅ `knee` (L, R) → `left_knee_pos_X/Y/Z`, `right_knee_pos_X/Y/Z`
- ✅ `ankle` (L, R) → `left_ankle_pos_X/Y/Z`, `right_ankle_pos_X/Y/Z`
- ✅ `big_toe` (L, R) → `left_big_toe_pos_X/Y/Z`, `right_big_toe_pos_X/Y/Z`
- ✅ `small_toe` (L, R) → `left_small_toe_pos_X/Y/Z`, `right_small_toe_pos_X/Y/Z`

**Napomena:** `heel` marker je definisan u MARKER_PREFIX ali se **ne koristi** u required listi za 3D model.

### 3. Potrebne kolone za 2D CoM model:

**Required markers (linija 335):**
- ✅ `hip` (jedna strana) → `left_hip_pos_X/Y/Z` ili `right_hip_pos_X/Y/Z`
- ✅ `shoulder` (jedna strana) → `left_shoulder_pos_X/Y/Z` ili `right_shoulder_pos_X/Y/Z`
- ✅ `knee` (jedna strana) → `left_knee_pos_X/Y/Z` ili `right_knee_pos_X/Y/Z`
- ✅ `ankle` (jedna strana) → `left_ankle_pos_X/Y/Z` ili `right_ankle_pos_X/Y/Z`
- ✅ `big_toe` (jedna strana) → `left_big_toe_pos_X/Y/Z` ili `right_big_toe_pos_X/Y/Z`
- ✅ `small_toe` (jedna strana) → `left_small_toe_pos_X/Y/Z` ili `right_small_toe_pos_X/Y/Z`

### 4. Format kolona u TSV fajlovima:

**TSV fajlovi imaju:**
- `left_shoulder_pos_X`, `left_shoulder_pos_Y`, `left_shoulder_pos_Z`
- `right_shoulder_pos_X`, `right_shoulder_pos_Y`, `right_shoulder_pos_Z`
- `left_hip_pos_X`, `left_hip_pos_Y`, `left_hip_pos_Z`
- `right_hip_pos_X`, `right_hip_pos_Y`, `right_hip_pos_Z`
- `left_knee_pos_X`, `left_knee_pos_Y`, `left_knee_pos_Z`
- `right_knee_pos_X`, `right_knee_pos_Y`, `right_knee_pos_Z`
- `left_ankle_pos_X`, `left_ankle_pos_Y`, `left_ankle_pos_Z`
- `right_ankle_pos_X`, `right_ankle_pos_Y`, `right_ankle_pos_Z`
- `left_big_toe_pos_X`, `left_big_toe_pos_Y`, `left_big_toe_pos_Z`
- `right_big_toe_pos_X`, `right_big_toe_pos_Y`, `right_big_toe_pos_Z`
- `left_small_toe_pos_X`, `left_small_toe_pos_Y`, `left_small_toe_pos_Z`
- `right_small_toe_pos_X`, `right_small_toe_pos_Y`, `right_small_toe_pos_Z`

**Skripta očekuje (funkcija `_cols`):**
- Za prefix `left_shoulder_pos` → traži `left_shoulder_pos_X`, `left_shoulder_pos_Y`, `left_shoulder_pos_Z`
- Format je identičan! ✅

### 5. Čitanje TSV fajlova:

**Skripta koristi `read_qualisys_tsv()` funkciju koja:**
- ✅ Traži liniju koja počinje sa `Frame\tTime\t` (linija 130)
- ✅ Ekstraktuje FREQUENCY iz header-a (linija 123)
- ✅ Koristi `pd.read_csv()` sa `skiprows=header_idx` (linija 137)

**TSV fajlovi imaju:**
- ✅ Liniju `Frame\tTime\t...` na liniji 8
- ✅ `FREQUENCY\t300` u header-u
- ✅ Format je kompatibilan!

### 6. Konverzija jedinica:

**Skripta ima `ensure_meters()` funkciju koja:**
- ✅ Automatski detektuje da li su podaci u milimetrima ili metrima
- ✅ Konvertuje iz mm u m ako je potrebno (heuristic: median > 10)
- ✅ TSV fajlovi su u milimetrima (vrednosti su tipično > 100), tako da će se konvertovati

### 7. Mapiranje subjekata po polu:

**Skripta koristi:**
- `FEMALE_SUBJECT_IDS = {6, 8, 9, 10, 12, 14}`
- `MALE_SUBJECT_IDS = {1, 2, 3, 5, 7, 13}`
- Funkcija `parse_subject_id_from_filename()` ekstraktuje SubjectID iz imena fajla (npr. `02_4_1.tsv` → SubjectID = 2)

**TSV fajlovi:**
- ✅ Format imenovanja: `XX_Y_Z.tsv` gde je XX SubjectID
- ✅ Kompatibilno sa regex patternom u skripti (linija 72-74)

## ✅ ZAKLJUČAK

### **SKRIPTA JE POTPUNO KOMPATIBILNA SA TSV FAJLOVIMA!**

**Sve potrebne kolone postoje:**
- ✅ Svi markeri potrebni za 3D CoM model su prisutni
- ✅ Svi markeri potrebni za 2D CoM model su prisutni
- ✅ Format naziva kolona je identičan
- ✅ Format TSV fajlova je kompatibilan sa `read_qualisys_tsv()` funkcijom
- ✅ Mapiranje subjekata po polu će raditi sa trenutnim imenima fajlova

**Skripta će moći da:**
1. ✅ Pročita TSV fajlove
2. ✅ Ekstraktuje sve potrebne markere
3. ✅ Izračuna CoM3D_X, CoM3D_Y, CoM3D_Z
4. ✅ Izračuna CoM2DL_X, CoM2DL_Z (leva strana)
5. ✅ Izračuna CoM2DR_X, CoM2DR_Z (desna strana)
6. ✅ Automatski konvertuje iz mm u m
7. ✅ Mapira subjekte po polu na osnovu SubjectID iz imena fajla

**Nema nedostajućih kolona ili nekompatibilnosti!**
