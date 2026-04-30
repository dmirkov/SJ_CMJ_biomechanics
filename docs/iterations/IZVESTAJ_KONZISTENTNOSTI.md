# Izveštaj o konzistentnosti TSV fajlova

**Datum provere:** 2026-02-01

## 📊 REZIME PROVERE

### CMJ_Qualisys Folder
- **Ukupno fajlova:** 60
- **Header struktura:** ✅ Identična u svim fajlovima
- **Nazivi kolona:** ✅ Identični u svim fajlovima
- **Broj kolona:** ✅ 42 data kolone + Frame + Time = 44 kolone
- **Frame/Time header:** ✅ Postoji u svim fajlovima

### SJ_Qualisys Folder
- **Ukupno fajlova:** 72
- **Header struktura:** ✅ Identična u svim fajlovima
- **Nazivi kolona:** ✅ Identični u svim fajlovima
- **Broj kolona:** ✅ 42 data kolone + Frame + Time = 44 kolone
- **Frame/Time header:** ✅ Postoji u svim fajlovima

## ✅ PROVERENO

### 1. Header Struktura
Svi fajlovi imaju identičnu strukturu header-a:
```
NO_OF_FRAMES
NO_OF_DATA_TYPES
FREQUENCY
TIME_STAMP
DATA_INCLUDED
DATA_TYPES
(prazan red)
Frame	Time	[42 kolone]
```

### 2. Nazivi Kolona
Svi fajlovi imaju identične nazive kolona u istom redosledu:
```
left_small_toe_pos_X, left_small_toe_pos_Y, left_small_toe_pos_Z,
left_big_toe_pos_X, left_big_toe_pos_Y, left_big_toe_pos_Z,
left_heel_pos_X, left_heel_pos_Y, left_heel_pos_Z,
left_ankle_pos_X, left_ankle_pos_Y, left_ankle_pos_Z,
left_knee_pos_X, left_knee_pos_Y, left_knee_pos_Z,
left_hip_pos_X, left_hip_pos_Y, left_hip_pos_Z,
left_shoulder_pos_X, left_shoulder_pos_Y, left_shoulder_pos_Z,
right_shoulder_pos_X, right_shoulder_pos_Y, right_shoulder_pos_Z,
right_hip_pos_X, right_hip_pos_Y, right_hip_pos_Z,
right_knee_pos_X, right_knee_pos_Y, right_knee_pos_Z,
right_ankle_pos_X, right_ankle_pos_Y, right_ankle_pos_Z,
right_heel_pos_X, right_heel_pos_Y, right_heel_pos_Z,
right_big_toe_pos_X, right_big_toe_pos_Y, right_big_toe_pos_Z,
right_small_toe_pos_X, right_small_toe_pos_Y, right_small_toe_pos_Z
```

### 3. Broj Kolona
- **DATA_TYPES linija:** 42 kolone u svim fajlovima
- **Frame/Time header:** 42 kolone + Frame + Time = 44 kolone
- **Data redovi:** 44 kolone (Frame + Time + 42 data kolone)

### 4. Podaci u Kolonama
Provereni uzorci pokazuju da:
- ✅ Frame kolona sadrži numeričke vrednosti (1, 2, 3...)
- ✅ Time kolona sadrži decimalne vrednosti (0.00000, 0.00333...)
- ✅ Sve data kolone sadrže numeričke vrednosti (npr. -58.332, -264.380, 36.533...)
- ✅ Nema praznih kolona u proverenim redovima

## 📈 STATISTIKA

| Folder | Fajlova | Header Patterni | Column Patterni | Problemi | FREQUENCY |
|--------|---------|----------------|-----------------|----------|-----------|
| CMJ_Qualisys | 60 | 1 (identičan) | 1 (identičan) | 0 | 300 (svi) |
| SJ_Qualisys | 72 | 1 (identičan) | 1 (identičan) | 0 | 300 (svi) |
| **UKUPNO** | **132** | **1** | **1** | **0** | **300 (svi)** |

### Detaljna provera:
- ✅ **60/60 CMJ fajlova** - identična struktura i kolone
- ✅ **72/72 SJ fajlova** - identična struktura i kolone
- ✅ **132/132 fajlova** - svi imaju NO_OF_FRAMES liniju
- ✅ **132/132 fajlova** - svi imaju FREQUENCY 300
- ✅ **132/132 fajlova** - svi imaju NO_OF_DATA_TYPES 42
- ✅ **132/132 fajlova** - svi imaju Frame/Time header
- ✅ **Provereni uzorci** - nema praznih kolona u podacima

## ✅ ZAKLJUČAK

**SVI TSV FAJLOVI SU KONZISTENTNI!**

- ✅ Svi fajlovi imaju identičnu header strukturu
- ✅ Svi fajlovi imaju identične nazive kolona u istom redosledu
- ✅ Svi fajlovi imaju isti broj kolona (42 data + Frame + Time)
- ✅ Svi fajlovi imaju Frame/Time header liniju
- ✅ Podaci su prisutni u svim kolonama u proverenim uzorcima

**Fajlovi su spremni za dalju obradu!**
