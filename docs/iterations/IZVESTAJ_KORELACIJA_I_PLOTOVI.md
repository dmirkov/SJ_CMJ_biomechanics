# IZVEŠTAJ O KORELACIJAMA I PLOTOVIMA

**Datum:** 2026-02-02

## 📊 KORELACIJE vTO IZMEĐU FP I QUALISYS

### SJ (Squat Jump)

| Model | N   | Pearson r | p-value | MAE (m/s) | Bias (m/s) | vTO_FP (m/s) | vTO_Q (m/s) |
|-------|-----|-----------|---------|-----------|------------|--------------|-------------|
| 3D    | 66  | -0.1257   | 0.3144   | 322.88    | -29.90     | -27.84 ± 1251.13 | 2.07 ± 0.18 |
| 2DL   | 66  | -0.1257   | 0.3146   | 322.88    | -29.91     | -27.84 ± 1251.13 | 2.07 ± 0.18 |
| 2DR   | 66  | -0.1435   | 0.2503   | 322.88    | -29.91     | -27.84 ± 1251.13 | 2.07 ± 0.18 |

**⚠️ PROBLEM:** 
- Negativan vTO_FP (mean = -27.84 m/s) - nerealno!
- Veoma velika standardna devijacija (1251 m/s) - ukazuje na probleme
- Niska/nulta Pearson korelacija
- Spearman korelacija je umerena (r ~ 0.33-0.34, p < 0.01)

### CMJ (Countermovement Jump)

| Model | N   | Pearson r | p-value | MAE (m/s) | Bias (m/s) | vTO_FP (m/s) | vTO_Q (m/s) |
|-------|-----|-----------|---------|-----------|------------|--------------|-------------|
| 3D    | 60  | 0.0216    | 0.8698   | 3.98      | -3.07      | -0.84 ± 14.79 | 2.23 ± 0.27 |
| 2DL   | 60  | 0.0246    | 0.8517   | 3.98      | -3.08      | -0.84 ± 14.79 | 2.23 ± 0.27 |
| 2DR   | 60  | 0.0141    | 0.9149   | 3.98      | -3.07      | -0.84 ± 14.79 | 2.23 ± 0.28 |

**⚠️ PROBLEM:**
- Negativan vTO_FP (mean = -0.84 m/s) - neispravno!
- Velika standardna devijacija (14.79 m/s)
- Niska/nulta Pearson korelacija
- Negativna Spearman korelacija (r ~ -0.57, p < 0.001) - ukazuje na inverznu vezu!

---

## 🔍 ANALIZA PROBLEMA

### Glavni problemi:

1. **Negativan vTO u FP podacima**
   - SJ: Mean = -27.84 m/s (nerealno!)
   - CMJ: Mean = -0.84 m/s
   - **Uzrok:** Verovatno problem sa novom logikom za TO detekciju ili drift correction

2. **Veoma velika varijansa**
   - SJ: Std = 1251 m/s (ekstremno!)
   - CMJ: Std = 14.79 m/s (velika)
   - **Uzrok:** Neispravna detekcija TO tačke ili problem sa integracijom

3. **Niska/nulta Pearson korelacija**
   - Objašnjava se velikom varijansom i negativnim vrednostima

---

## 📈 PLOTOVI

### Status:
- ✅ Nova skripta kreirana: `plot_fp_jumps_fixed.py`
- ✅ Koristi istu novu logiku kao `calculate_fp_kpis.py`
- ⏳ Plotovi se kreiraju...

### Format plotova:
- **Leva Y osa:** Vertikalno ubrzanje az(t) [m/s²] - plava linija
- **Desna Y osa:** Vertikalna brzina vz(t) [m/s] - crvena linija
- **X osa:** Vreme [s]

### Obeležene karakteristične tačke:
- START (A) - Početak skoka
- vmin - Minimalna brzina
- vmax - Maksimalna brzina
- hmin - Minimalna visina (displacement)
- C, D - Countermovement faze (samo CMJ)
- TO (F) - Takeoff (odskok) - sa vTO vrednošću
- LAND (H) - Landing (doskok)

---

## ⚠️ PREPORUKE ZA POPRAVKU

### Prioritet 1 (KRITIČNO):

1. **Proveriti TO detekciju**
   - Zašto je vTO negativan?
   - Da li je TO tačka ispravno detektovana?
   - Proveriti plotove da vidimo gde se TO nalazi

2. **Proveriti drift correction**
   - Možda je previše agresivan
   - Proveriti da li je landing period validan

3. **Proveriti integraciju**
   - Da li je onset ispravno detektovan?
   - Da li je brzina na onset-u stvarno 0?

### Prioritet 2:

4. **Validacija podataka**
   - Proveriti problematične fajlove ručno
   - Videti plotove za različite slučajeve

5. **Poboljšanje logike**
   - Možda treba dodatna validacija za TO detekciju
   - Možda treba različiti parametri za različite tipove skokova

---

**Status:** ⚠️ Zahteva hitnu proveru i popravku - negativan vTO je kritičan problem!
