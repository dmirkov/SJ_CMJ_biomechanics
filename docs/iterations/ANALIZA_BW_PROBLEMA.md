# ANALIZA PROBLEMA SA BW DETEKCIJOM

**Datum:** 2026-02-02

## ⚠️ KRITIČAN PROBLEM: NEREALNE BW VREDNOSTI

### Rezultati za prvih 5 fajlova:

#### SJ:
- 01_3_1: BW = 19.0 N ❌ (trebalo bi ~600-1000N)
- 01_3_2: BW = 915.2 N ✅ (razumno, ali možda slučajno)
- 01_3_3: BW = 15.6 N ❌
- 01_3_4: BW = -14.2 N ❌ (negativan!)
- 01_3_5: BW = 14.8 N ❌

#### CMJ:
- 02_4_1: BW = -1.4 N ❌ (negativan!)
- 02_4_2: BW = 3.2 N ❌
- 02_4_3: BW = 3.0 N ❌
- 02_4_4: BW = -8.2 N ❌ (negativan!)
- 02_4_5: BW = 3.6 N ❌

---

## 🔍 ANALIZA UZROKA

### Problem 1: Segment pre minimuma možda nije stabilan period

**Trenutna logika:**
- Uzima segment 0.5s PRE minimuma
- Minimum je flight faza (sila ≈ 0)

**Problem:**
- Ako je minimum na početku signala, segment pre minimuma je veoma kratak ili ne postoji
- Ako je minimum kasno u signalu, segment pre minimuma možda već sadrži kretanje (unloading/countermovement)
- Segment pre minimuma možda nije "quiet standing" period

### Problem 2: Minimum možda nije pravi flight period

- Minimum bi trebao biti u flight fazi (sila ≈ 0)
- Ali možda se detektuje neki drugi minimum (npr. artefakt, šum)

### Problem 3: Filtriranje možda uklanja previše podataka

- Filtriranje unutar 2*SD možda uklanja sve podatke ako je segment već nestabilan

---

## 💡 PREDLOZI ZA POPRAVKU

### Opcija 1: Koristiti početak signala za BW (fallback)

**Logika:**
- Prvo pokušaj sa segmentom pre minimuma
- Ako je BW nerealan (npr. < 200N ili > 2000N), koristi početak signala (prvih 0.5-1s)
- Početak signala je verovatnije "quiet standing" period

### Opcija 2: Validacija BW vrednosti

**Logika:**
- Proveri da li je BW razuman (npr. 300-1500N za odraslu osobu)
- Ako nije, koristi fallback metodu (početak signala)

### Opcija 3: Kombinovana metoda

**Logika:**
1. Izračunaj BW iz početka signala (prvih 0.5-1s)
2. Izračunaj BW iz segmenta pre minimuma
3. Uporedi i koristi onu koja je razumnija ili kombinuj

### Opcija 4: Poboljšanje segmenta pre minimuma

**Logika:**
- Umesto fiksnog 0.5s, traži stabilan period (npr. gde je varijansa minimalna)
- Ili traži period gde je sila najbliža očekivanoj BW vrednosti

---

## 📊 PREPORUKE

**Hajde da prvo proverimo plotove** da vidimo:
1. Gde se minimum nalazi u signalu
2. Kako izgleda segment pre minimuma
3. Da li je segment stabilan ili već sadrži kretanje

**Zatim možemo da:**
1. Poboljšamo logiku za izbor segmenta
2. Dodamo validaciju BW vrednosti
3. Implementiramo fallback metodu

---

**Status:** ⚠️ BW detekcija je kritično neispravna - zahteva hitnu popravku!
