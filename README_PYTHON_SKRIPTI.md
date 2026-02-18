# TSV Standardizacija - Dokumentacija Skripti

## Pregled Skripti

Projekt sadrži **5 Python skripti** koje se koriste za standardizaciju TSV fajlova iz biomehametrijskih mjerenja.

---

## 1. 🚀 `run_standardization.py` - GLAVNI SKRIPT

**Uloga:** Orkestrira sve ostale skripte u logičnom redoslijedu

**Što radi:**
- Pokušava sve korake standardizacije
- Izvještava o statusu svakog koraka
- Daje finalni rezime

**Kako pokrenuti:**
```powershell
C:/Users/dmirk/anaconda3/python.exe run_standardization.py
```

**Redoslijed izvršavanja:**
1. `check_consistency.py` - Analiza fajlova
2. `cleanup_empty_columns.py` - Čišćenje praznih kolona
3. `organize_backups.py` - Organizacija backup-a

---

## 2. 📊 `check_consistency.py` - ANALIZA I PROVJERA

**Uloga:** Provjerava konzistentnost header-a i strukture fajlova

**Što analizira:**
- Broj kolona u svakom fajlu
- Redoslijed i imena kolona
- Prazne kolone na kraju
- Neusaglašenosti između CMJ_Qualisys i SJ_Qualisys

**Izvještaj:**
- Broj jedinstvenih header struktura
- Pronađene probleme
- Status: SVE OK ili problemi

**Koristi se u:** `run_standardization.py` kao prvi korak

---

## 3. 🧹 `cleanup_empty_columns.py` - ČIŠĆENJE KOLONA

**Uloga:** Uklanja prazne tab-delimitirane kolone sa kraja svakog reda

**Što radi:**
1. Kreira backup fajlove sa timestamp-om
2. Čita sve TSV fajlove iz oba foldera
3. Uklanja prazne kolone sa kraja
4. Sprema čiste fajlove

**Rezultat:**
- Svi fajlovi imaju 44 kolone: Frame, Time, + 42 podatkovne kolone
- Bez praznih kolona na kraju

**Koristi se u:** `run_standardization.py` kao drugi korak

---

## 4. 📦 `organize_backups.py` - ORGANIZACIJA BACKUP-A

**Uloga:** Centralizuje sve backup fajlove

**Što radi:**
1. Kreira `Backup_Fajlovi` folder
2. Premješa sve `*_backup_*.tsv` fajlove
3. Očistava originalne foldera

**Rezultat:**
- CMJ_Qualisys: Samo 60 originalnih TSV fajlova
- SJ_Qualisys: Samo 72 originalna TSV fajlova
- Backup_Fajlovi: 132 backup fajlova (svi sa timestamp-ima)

**Koristi se u:** `run_standardization.py` kao treći korak

---

## 5. 📋 `check_files.py` - STARI SKRIP (ZASTARJELI)

**Napomena:** Ovaj skrip je sada zamijenjen sa `check_consistency.py`

**Opis:** Detaljna analiza strukture fajlova

**Stanje:** Čuvan radi referenca, ali se ne koristi u standardnom procesu

---

## 6. 🔧 `fix_06_3_2.py` - SPECIFIČAN SKRIP (OPCIONO)

**Napomena:** Ovaj skrip je bio za specifičan problem s fajlom `06_3_2.tsv`

**Što radi:** 
- Konvertuje `__X` format u `_pos_X` format
- Reorder-a kolone

**Stanje:** Može se koristiti ako trebate posebnu obradu tog fajla

---

## 📁 Struktura Foldera (nakon standardizacije)

```
SJ_CMJ_biomechanics/
├── CMJ_Qualisys/              (60 standardizovanih TSV fajlova)
├── SJ_Qualisys/               (72 standardizovanih TSV fajlova)
├── Backup_Fajlovi/            (132 backup fajlova)
│
├── run_standardization.py      (GLAVNI SKRIPT)
├── check_consistency.py        (Analiza)
├── cleanup_empty_columns.py    (Čišćenje)
├── organize_backups.py         (Organizacija)
├── calculate_fp_kpis.py        (Jezgra analize – koriste je plotovi i ostale skripte)
│
├── tests/                     (Test skripte – development/validacija)
└── archive/                   (Jednokratne provjere – referenca)
```

---

## 🎯 TOK IZVRŠAVANJA

```
run_standardization.py
    ↓
    ├─→ check_consistency.py
    │   └─→ Analiza header-a i strukture
    │
    ├─→ cleanup_empty_columns.py
    │   ├─→ Kreira backup-e
    │   ├─→ Čisti prazne kolone
    │   └─→ Sprema standardizovane fajlove
    │
    └─→ organize_backups.py
        ├─→ Kreira Backup_Fajlovi folder
        ├─→ Premješa backup-e
        └─→ Verificira organizaciju

REZULTAT: Standardizovani TSV fajlovi
```

---

## 💾 Standard Format (nakon standardizacije)

### Header struktura:
```
NO_OF_FRAMES     2735
NO_OF_DATA_TYPES 42
FREQUENCY        300
TIME_STAMP       2024-07-11, 13:35:34
DATA_INCLUDED    Position
DATA_TYPES       [42 kolone sa nazivima]

Frame  Time  [42 podatkovne kolone]
```

### Redoslijed kolona:
1. `Frame` - Redni broj frame-a
2. `Time` - Vremenska pozicija
3. 42 podatkovne kolone:
   - left_small_toe (X, Y, Z)
   - left_big_toe (X, Y, Z)
   - left_heel (X, Y, Z)
   - left_ankle (X, Y, Z)
   - left_knee (X, Y, Z)
   - left_hip (X, Y, Z)
   - left_shoulder (X, Y, Z)
   - right_shoulder (X, Y, Z)
   - right_hip (X, Y, Z)
   - right_knee (X, Y, Z)
   - right_ankle (X, Y, Z)
   - right_heel (X, Y, Z)
   - right_big_toe (X, Y, Z)
   - right_small_toe (X, Y, Z)

### Bez:
- Praznih kolona na kraju
- Wrist kolona (left_wrist, right_wrist)
- Neusaglašenosti u naming-u

---

## ✅ Provjera Status-a

Da provjerite stanje fajlova nakon standardizacije:

```powershell
# Samo pogledati rezultate analiza
C:/Users/dmirk/anaconda3/python.exe check_consistency.py

# Ponovno izvršiti sve korake
C:/Users/dmirk/anaconda3/python.exe run_standardization.py
```

---

## 📝 Napomene

- **Backup-i:** Svi backup fajlovi su sačuvani sa timestamp-om (format: `YYYYMMDD_HHMMSS`)
- **Sigurnost:** Originalni fajlovi se ne brišu - čuva se backup prije svake izmjene
- **Retry:** Ako neki korak ne uspije, možete pokrenuti samo taj skrip da se napravi ispravka

---

Verzija: 1.0
Datum: 2026-02-02
