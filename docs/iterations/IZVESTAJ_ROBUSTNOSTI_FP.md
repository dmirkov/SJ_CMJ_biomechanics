# IZVEŠTAJ O ROBUSTNOSTI FORCE PLATE KPI IZRAČUNAVANJA

**Datum:** 2026-02-02

## 📊 REZULTATI KORELACIJA vTO IZMEĐU FP I QUALISYS

### SJ (Squat Jump)

| Model | N   | Pearson r | p-value | MAE (m/s) | Bias (m/s) |
|-------|-----|-----------|---------|-----------|------------|
| 3D    | 66  | 0.5233    | <0.001  | 0.3249    | 0.1248     |
| 2DL   | 66  | 0.5315    | <0.001  | 0.3224    | 0.1228     |
| 2DR   | 66  | 0.5269    | <0.001  | 0.3254    | 0.1229     |

**Zaključak:** Umereno jake korelacije (r ~ 0.52-0.53), statistički značajne.

### CMJ (Countermovement Jump)

| Model | N   | Pearson r | p-value | MAE (m/s) | Bias (m/s) |
|-------|-----|-----------|---------|-----------|------------|
| 3D    | 60  | 0.1282    | 0.329   | 4.6681    | 4.3202     |
| 2DL   | 60  | 0.1251    | 0.341   | 4.6679    | 4.3185     |
| 2DR   | 60  | 0.1260    | 0.337   | 4.6619    | 4.3257     |

**Zaključak:** Veoma niske korelacije (r ~ 0.13), nisu statistički značajne. Velika greška (MAE ~ 4.7 m/s).

---

## ⚠️ PROBLEMI I PREPORUKE

### 1. SJ Countermovement Detekcija

**Status:** ✅ Poboljšano
- **Countermovement rate:** 17.7% (smanjeno sa 100%)
- **Validni skokovi:** 64/79 (81.0%)

**Kriterijumi za detekciju:**
- Minimalna brzina < -0.15 m/s
- Minimalni displacement < -0.02 m (20mm)
- Minimalna sila < BW - 3*SD
- Trajanje > 50ms

**Preporuka:** 
- ✅ Kriterijumi su sada realniji
- ⚠️ 17.7% je i dalje visok procenat - proverite protokol merenja
- 💡 Razmotrite dodatno pooštravanje kriterijuma ako je potrebno

### 2. Negativan vTO Problem

**Status:** ⚠️ Problem postoji
- **SJ:** 19.0% skokova ima negativan vTO
- **CMJ:** 8.1% skokova ima negativan vTO

**Uzrok:**
- Problem sa drift correction
- Problem sa event detection (takeoff detection)
- Mogući problem sa integracijom (velocity calculation)

**Preporuka:**
- Proverite drift correction logiku
- Proverite flight detection threshold (trenutno 15N)
- Razmotrite poboljšanje velocity integration metode

### 3. CMJ Height_V Problem

**Status:** ❌ KRITIČAN PROBLEM
- **Mean Height_V:** 54.5 m (nerealno visoko!)
- **Std Height_V:** 447.3 m (veoma velika varijansa)
- **Mean Height_T:** 0.27 m (realno)

**Uzrok:**
- Problem sa vTO izračunavanjem za CMJ
- Verovatno problem sa drift correction ili event detection
- Velika standardna devijacija vTO (34.2 m/s) ukazuje na probleme

**Preporuka:**
- ⚠️ **HITNO:** Proverite logiku za CMJ event detection
- Proverite drift correction za CMJ skokove
- Razmotrite različite parametre za CMJ vs SJ

### 4. Konzistentnost Visina

**SJ:**
- Mean |Height_V - Height_T|: 0.036 m (3.6 cm)
- Max razlika: 0.157 m (15.7 cm)
- Skokovi sa razlikom > 5cm: 19/64 (29.7%)

**CMJ:**
- Mean |Height_V - Height_T|: 54.25 m (nerealno!)
- Max razlika: 3688 m (nerealno!)

**Preporuka:**
- SJ: Razlika je prihvatljiva za većinu skokova
- CMJ: **KRITIČAN PROBLEM** - Height_V nije pouzdan

---

## ✅ POZITIVNI ASPEKTI

1. **SJ korelacije:** Umereno jake (r ~ 0.52-0.53), statistički značajne
2. **SJ validni skokovi:** 81% validnih skokova
3. **CMJ validni skokovi:** 91.9% validnih skokova (bez Height_V problema)
4. **Detekcija countermovement:** Sada funkcioniše realnije (17.7% umesto 100%)

---

## 🔧 PREPORUKE ZA POBOLJŠANJE

### Prioritet 1 (KRITIČNO):
1. **Popraviti CMJ vTO izračunavanje**
   - Proveriti drift correction za CMJ
   - Proveriti event detection logiku
   - Razmotriti različite parametre za CMJ

2. **Popraviti negativan vTO problem**
   - Proveriti drift correction
   - Proveriti flight detection threshold
   - Razmotriti alternativne metode za velocity calculation

### Prioritet 2 (VAŽNO):
3. **Poboljšati SJ countermovement detekciju**
   - Razmotriti dodatno pooštravanje kriterijuma
   - Dodati proveru trajanja countermovement-a
   - Razmotriti kombinaciju kriterijuma (npr. sva tri moraju biti zadovoljena)

4. **Validacija Height_V vs Height_T**
   - Za SJ: Razlika je prihvatljiva
   - Za CMJ: Hitno popraviti Height_V izračunavanje

---

## 📈 FINALNI STATUS

| Metrika | SJ | CMJ |
|---------|----|----|
| Validni skokovi | 81.0% | 91.9% |
| Countermovement rate | 17.7% | N/A |
| Negativan vTO rate | 19.0% | 8.1% |
| Korelacija vTO (FP vs Q) | r=0.52-0.53*** | r=0.13 (NS) |
| Height_V pouzdanost | ✅ Prihvatljivo | ❌ Neispravno |

**Ukupan zaključak:**
- ✅ **SJ logika je relativno robustna** - korelacije su umereno jake, većina skokova je validna
- ❌ **CMJ logika zahteva hitne popravke** - Height_V je neispravan, korelacije su niske

---

**Napomena:** QC flagovi (`has_countermovement`, `negative_vto`, `invalid_jump`, `qc_notes`) su dodati u Excel sheetove za laku identifikaciju neispravnih skokova.
