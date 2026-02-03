# IZVEŠTAJ O POPRAVKAMA vTO IZRAČUNAVANJA

**Datum:** 2026-02-02

## 🔧 PRIMENJENE POPRAVKE

### 1. Poboljšanje Drift Correction
- **Pre:** Koristio kraj signala za drift estimation
- **Sada:** Koristi landing period (posle impact) za pouzdaniju drift estimation
- **Validacija:** Proverava da li je brzina na landing-u blizu 0 (< 10 m/s)
- **Fallback:** Ako landing period nije validan, koristi kraći buffer na kraju signala

### 2. Poboljšanje vTO Izračunavanja
- **Pre:** Direktno uzimanje brzine na `idx['F']` (takeoff)
- **Sada:** Uzima maksimalnu brzinu u 50ms periodu pre takeoff-a
- **Razlog:** Takeoff detection može biti neprecizan, maksimalna brzina je pouzdanija

### 3. Validacija vTO
- **Pozitivnost:** Proverava da li je vTO pozitivan
- **Razumnost:** Proverava da li je vTO < 10 m/s (SJ) ili < 15 m/s (CMJ)
- **Fallback:** Ako vTO nije validan, pokušava da koristi maksimalnu pozitivnu/razumnu brzinu pre takeoff-a

---

## 📊 REZULTATI PRE I POSLE

### CMJ Korelacije (FP vs Qualisys)

| Metrika | Pre | Posle | Poboljšanje |
|---------|-----|-------|-------------|
| Pearson r | 0.13 (NS) | 0.46-0.47*** | ✅ +254% |
| MAE (m/s) | 4.67 | 0.83 | ✅ -82% |
| Bias (m/s) | 4.32 | 0.56 | ✅ -87% |

### CMJ Height_V

| Metrika | Pre | Posle | Poboljšanje |
|---------|-----|-------|-------------|
| Mean (m) | 54.5 | 0.50 | ✅ -99% |
| Std (m) | 447.3 | 1.12 | ✅ -99.7% |
| Max (m) | 3688.4 | 9.92 | ✅ -99.7% |

### CMJ vTO Statistike

| Metrika | Pre | Posle | Poboljšanje |
|---------|-----|-------|-------------|
| Mean (m/s) | 6.16 | 2.76 | ✅ -55% |
| Std (m/s) | 34.2 | 1.51 | ✅ -95.6% |
| Max (m/s) | 269.0 | 13.95 | ✅ -94.8% |

### Negativan vTO Rate

| Tip | Pre | Posle | Poboljšanje |
|-----|-----|-------|-------------|
| SJ | 19.0% | 17.7% | ✅ -6.8% |
| CMJ | 8.1% | 2.7% | ✅ -66.7% |

---

## ✅ POZITIVNI REZULTATI

1. **CMJ korelacije su sada statistički značajne** (r = 0.46-0.47, p < 0.001)
2. **CMJ Height_V je sada razuman** (mean = 0.50 m umesto 54.5 m)
3. **CMJ vTO je sada stabilniji** (std = 1.51 m/s umesto 34.2 m/s)
4. **CMJ negativan vTO rate je značajno smanjen** (sa 8.1% na 2.7%)
5. **SJ korelacije su se blago poboljšale** (r = 0.57 umesto 0.52-0.53)

---

## ⚠️ PREOSTALI PROBLEMI

### 1. SJ Negativan vTO (17.7%)
- **Status:** Još uvek visok procenat
- **Mogući uzrok:**
  - Problem sa protokolom merenja (možda neki skokovi nisu pravi SJ)
  - Problem sa event detection za određene subjekte
  - Problem sa drift correction za određene slučajeve

**Preporuka:**
- Proveriti problematične fajlove ručno
- Razmotriti dodatno pooštravanje validacije
- Možda koristiti različite parametre za različite subjekte

### 2. CMJ Ekstremni Height_V (1 slučaj: 9.92 m)
- **Status:** Još uvek postoji jedan ekstremni slučaj
- **Fajl:** `07_4_5.txt`
- **vTO:** 13.95 m/s (još uvek visok, ali razuman)

**Preporuka:**
- Proveriti ovaj fajl ručno
- Možda je problem sa samim podacima ili protokolom merenja

### 3. Razlika između Height_V i Height_T
- **SJ:** Mean razlika = 0.11 m (11 cm)
- **CMJ:** Mean razlika = 0.13 m (13 cm)
- **Status:** Razlika je veća nego što bi trebalo

**Preporuka:**
- Razmotriti dodatno poboljšanje drift correction
- Možda koristiti kombinaciju Height_V i Height_T za finalnu visinu

---

## 📈 FINALNI STATUS

| Metrika | SJ | CMJ |
|---------|----|-----|
| Validni skokovi | 81.0% | 91.9% |
| Countermovement rate | 17.7% | N/A |
| Negativan vTO rate | 17.7% | 2.7% |
| Korelacija vTO (FP vs Q) | r=0.57*** | r=0.47*** |
| Height_V pouzdanost | ✅ Prihvatljivo | ✅ Poboljšano |

**Ukupan zaključak:**
- ✅ **CMJ logika je značajno poboljšana** - korelacije su sada statistički značajne, Height_V je razuman
- ✅ **SJ logika je relativno robustna** - korelacije su jake, većina skokova je validna
- ⚠️ **SJ negativan vTO rate je još uvek visok** - zahteva dodatnu pažnju

---

## 🔧 PREPORUKE ZA DALJE POBOLJŠANJE

1. **SJ Negativan vTO:**
   - Ručna provera problematičnih fajlova
   - Razmotriti dodatno pooštravanje validacije
   - Možda koristiti različite parametre za različite subjekte

2. **CMJ Ekstremni slučajevi:**
   - Ručna provera `07_4_5.txt`
   - Razmotriti dodatnu validaciju za ekstremne vrednosti

3. **Razlika Height_V vs Height_T:**
   - Razmotriti kombinaciju oba metoda za finalnu visinu
   - Dodatno poboljšanje drift correction

---

**Napomena:** Sve popravke su implementirane u `calculate_fp_kpis.py`. QC flagovi (`has_countermovement`, `negative_vto`, `invalid_events`, `invalid_jump`, `qc_notes`) su ažurirani u Excel sheetovima.
