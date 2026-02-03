# REZIME: KORELACIJE I PLOTOVI

**Datum:** 2026-02-02

## 📊 KORELACIJE vTO (FP vs Qualisys)

### SJ (Squat Jump)
- **Pearson r:** -0.13 (nije značajno)
- **Spearman r:** 0.33-0.34 (p < 0.01) ✅
- **MAE:** 322.88 m/s ❌
- **Bias:** -29.90 m/s (FP niže)
- **vTO_FP:** -27.84 ± 1251.13 m/s ❌ (ekstremno!)
- **vTO_Q:** 2.07 ± 0.18 m/s ✅

### CMJ (Countermovement Jump)
- **Pearson r:** 0.02 (nije značajno)
- **Spearman r:** -0.57 (p < 0.001) ⚠️ (negativna!)
- **MAE:** 3.98 m/s
- **Bias:** -3.07 m/s (FP niže)
- **vTO_FP:** -0.84 ± 14.79 m/s ❌
- **vTO_Q:** 2.23 ± 0.28 m/s ✅

---

## ⚠️ KRITIČNI PROBLEMI

### 1. Ekstremno visoke vTO vrednosti (SJ)
- **Mean pozitivnih:** 155.42 m/s (nerealno!)
- **Max:** 754.85 m/s (ekstremno!)
- **Uzrok:** Verovatno TO detekcija previše rano ili problem sa integracijom

### 2. Negativan vTO
- **SJ:** 7 slučajeva (9%)
- **CMJ:** 14 slučajeva (19%)
- **Uzrok:** TO detekcija previše kasno ili problem sa drift correction

### 3. Veoma velika varijansa
- **SJ:** Std = 1152.70 m/s (ekstremno!)
- **CMJ:** Std = 13.51 m/s (velika)
- **Uzrok:** Neispravna TO detekcija ili problem sa integracijom

---

## 📈 PLOTOVI

### Status:
- ✅ **SJ:** 79 plotova kreirano
- ⏳ **CMJ:** Plotovi se kreiraju...

### Lokacija:
- `Output/Plots/SJ_FP/` - 79 PNG fajlova
- `Output/Plots/CMJ_FP/` - u toku...

### Format:
- **Leva Y osa:** Vertikalno ubrzanje az(t) [m/s²] - plava linija
- **Desna Y osa:** Vertikalna brzina vz(t) [m/s] - crvena linija
- **X osa:** Vreme [s]

### Obeležene tačke:
- START (A), vmin, vmax, hmin, TO (F), LAND (H)
- C, D (samo CMJ)
- Sve sa anotacijama i vrednostima

---

## 🔍 ANALIZA PROBLEMA

### Mogući uzroci ekstremnih vTO vrednosti:

1. **TO detekcija previše rano**
   - Ako se TO detektuje pre stvarnog odskoka, brzina može biti veoma visoka
   - Proveriti plotove da vidimo gde se TO nalazi

2. **Problem sa integracijom**
   - Ako je onset loš, integracija može dati ekstremne vrednosti
   - Proveriti da li je brzina na onset-u stvarno 0

3. **Problem sa drift correction**
   - Možda je previše agresivan ili koristi pogrešan period
   - Proveriti landing period

4. **Problem sa crop-ovanjem**
   - Možda crop-ovanje uklanja važne delove signala
   - Proveriti da li su svi događaji unutar crop-ovanog signala

---

## 💡 PREPORUKE

### Prioritet 1 (HITNO):

1. **Proveriti plotove**
   - Otvoriti nekoliko plotova i videti gde se TO nalazi
   - Proveriti da li je TO na pravom mestu (pre flight faze)

2. **Proveriti TO detekciju**
   - Možda threshold od 50N nije dovoljno dobar
   - Možda treba dodatna validacija (npr. proveriti da li je brzina pozitivna)

3. **Proveriti integraciju**
   - Proveriti da li je brzina na onset-u stvarno 0
   - Proveriti da li je drift correction ispravan

### Prioritet 2:

4. **Validacija podataka**
   - Proveriti problematične fajlove ručno
   - Videti plotove za različite slučajeve

5. **Poboljšanje logike**
   - Možda treba dodatna validacija za TO detekciju
   - Možda treba različiti parametri za različite tipove skokova

---

**Status:** ⚠️ Zahteva hitnu proveru plotova i popravku TO detekcije!
