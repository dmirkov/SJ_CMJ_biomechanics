# OBJAŠNJENJE: KAKO RAČUNAM BW I PROBLEM

**Datum:** 2026-02-02

---

## 📋 KAKO TRENUTNO RAČUNAM BW

### Strategija:
**Koristim početak signala (quiet standing period) umesto segmenta pre minimuma.**

### Detaljni koraci:

1. **Izbor segmenta:**
   - Preskočim prvih **100ms** (možda artefakti)
   - Uzmem period od **0.1s do 1.0s** (quiet standing)
   - Ovo je period gde osoba mirno stoji pre bilo kakvog kretanja

2. **Prva aproksimacija:**
   - Izračunam **median** i **standardnu devijaciju** tog segmenta
   - Median je robusniji od mean-a (manje osetljiv na ekstremne vrednosti)

3. **Filtriranje:**
   - Uklonim tačke koje su van **±2*SD** od median-a
   - Ovo uklanja artefakte i ekstremne vrednosti

4. **Finalni BW:**
   - Izračunam **mean** i **SD** od filtriranih tačaka
   - Ako nema dovoljno čistih tačaka (>100), koristim ceo segment

5. **Validacija:**
   - Proverim da li je BW razuman: **200-2000N**
   - Ako nije, koristim fallback metodu (stara logika)

### Fallback metoda:
- Ako validacija ne prođe ili ima problema, koristim staru metodu:
  - Uzmem prvih 3s signala (ili kraće ako je signal kratak)
  - Izračunam mean i SD

---

## ⚠️ PROBLEM: EKSTREMNI SLUČAJ 07_4_5.txt

### Rezultati:
- **BW = 7.58 N** ❌ (potpuno nerealan! Trebalo bi ~600-1000N)
- **Onset = 1.000s** (fiksna vrednost - znači fallback)
- **vTO = 373.47 m/s** ❌ (ekstremno! Trebalo bi ~2-3 m/s)

### Analiza problema (DEBUG):

**Iz debug analize:**
```
quiet_segment mean = 7.11 N
quiet_segment min = -4.55 N
quiet_segment max = 28.52 N
```

**Problem:** 
- **Na početku signala (0.1-1.0s) NEMA KONTAKTA sa Force Plate-om!**
- Sila je ~7N umesto ~700N
- Osoba verovatno nije stajala na Force Plate-u na početku merenja
- Možda je osoba stala na Force Plate tek kasnije u signalu

**Zašto validacija nije pomogla:**
- Validacija je prošla (6.40N < 200N), pa je koristio fallback metodu
- Ali fallback metoda (`calculate_body_weight`) takođe uzima početak signala (prvih 3s)
- Ako na početku nema kontakta, i fallback daje nerealan rezultat

---

## 🔍 UZROK PROBLEMA

### Problem 1: Fiksni period možda nema kontakt
- Koristim fiksni period **0.1-1.0s** za BW
- Ali ako osoba nije stajala na Force Plate-u na početku, taj period nema kontakt
- Treba **prvo naći period gde je kontakt** (sila > threshold, npr. 100N)

### Problem 2: Fallback metoda takođe koristi početak
- Fallback metoda uzima prvih 3s signala
- Ako na početku nema kontakta, i ona daje nerealan rezultat

### Problem 3: Nema provere da li postoji kontakt
- Treba proveriti da li je sila u quiet period-u razumna (> 100N)
- Ako nije, tražiti drugi period gde je kontakt

---

## 💡 REŠENJE

### Poboljšana strategija za BW:

1. **Pronađi period sa kontaktom:**
   - Traži period gde je sila > 100N (ili neki drugi threshold)
   - Ako nema takvog perioda, označi fajl kao invalid

2. **Koristi taj period za BW:**
   - Uzmi stabilan period (npr. 0.5-1.5s) gde je kontakt
   - Izračunaj BW iz tog perioda

3. **Dodatna validacija:**
   - Proveri da li je BW razuman (300-1500N)
   - Ako nije, označi fajl kao invalid

4. **QC flag:**
   - Dodaj flag `invalid_bw` ako je BW nerealan
   - Ne računaj KPIs za takve skokove

---

## 📊 STATISTIKE

Iz analize ekstremnih slučajeva:
- **07_4_5.txt**: BW=7.58N, vTO=373.47 m/s ❌ (nema kontakt na početku)
- **11_4_7.txt**: BW=863.62N, vTO=4.36 m/s ⚠️ (malo visok)
- **11_4_4.txt**: BW=862.28N, vTO=4.02 m/s ⚠️ (malo visok)
- **11_4_3.txt**: BW=856.70N, vTO=3.94 m/s ⚠️ (malo visok)
- **03_4_3.txt**: BW=943.17N, vTO=3.77 m/s ⚠️ (malo visok)

**Zaključak:** 
- Većina ekstremnih slučajeva ima razuman BW, ali vTO je malo visok
- Samo **07_4_5.txt** ima potpuno nerealan BW zbog nedostatka kontakta na početku

---

**Status:** ⚠️ Zahteva hitnu popravku - prvo naći period sa kontaktom pre računanja BW!
