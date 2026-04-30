# REZIME: POPRAVKA BW DETEKCIJE

**Datum:** 2026-02-02

## ✅ POBOLJŠANJE: BW DETEKCIJA

### Promena:
- **Pre:** BW se računao iz segmenta 0.5s PRE minimuma
- **Sada:** BW se računao iz početka signala (0.1-1.0s) - quiet standing period

### Rezultati:

#### SJ_FP:
- ✅ **Mean BW:** 720.3 N (razumno!)
- ✅ **Std:** 154.3 N (normalno)
- ✅ **Range:** 401.4 - 988.6 N (sve razumno)
- ✅ **Sve vrednosti su razumne** (200-2000N)

#### CMJ_FP:
- ✅ **Mean BW:** 734.6 N (razumno!)
- ✅ **Std:** 155.8 N (normalno)
- ✅ **Range:** 7.6 - 944.8 N
- ⚠️ **1 nerealan:** 07_4_5.txt (7.6N) - zahteva proveru

---

## 📊 POBOLJŠANJE vTO

### SJ (Squat Jump):
- ✅ **Mean vTO:** 2.47 m/s (razumno!)
- ✅ **Std:** 0.32 m/s (normalno)
- ✅ **Range:** 1.69 - 3.38 m/s (sve razumno)
- ✅ **Nema negativnih vTO**
- ✅ **Korelacija:** r = 0.72 (p < 0.001) - **JAKA!** ✅

### CMJ (Countermovement Jump):
- ⚠️ **Mean vTO:** 0.018 m/s (previše mali!)
- ⚠️ **Std:** 0.022 m/s
- ⚠️ **23 negativna vTO** (31%)
- ⚠️ **Korelacija:** r = 0.22-0.25 (nije značajno)

---

## 🔍 ANALIZA PROBLEMA

### SJ: ✅ REŠENO
- BW je sada razuman
- vTO je razuman
- Korelacija je jaka (r = 0.72)

### CMJ: ⚠️ JOŠ UVEK IMA PROBLEMA

**Problem:** vTO je previše mali (0.018 m/s umesto ~2-3 m/s)

**Mogući uzroci:**
1. **Onset detekcija previše kasno** - integracija počinje previše kasno
2. **TO detekcija previše rano** - TO se detektuje pre stvarnog odskoka
3. **Drift correction previše agresivan** - koriguje previše brzinu

**Preporuka:** 
- Proveriti plotove za CMJ da vidimo gde se onset i TO nalaze
- Možda treba drugačija logika za CMJ onset (možda koristiti početak signala umesto minimuma)

---

## 💡 SLEDEĆI KORAK

1. ✅ **BW detekcija** - REŠENO (koristi početak signala)
2. ⏳ **Onset detekcija** - Proveriti za CMJ (možda koristiti početak signala umesto minimuma)
3. ⏳ **TO detekcija** - Proveriti plotove da vidimo gde se TO nalazi
4. ⏳ **Drift correction** - Proveriti da li je ispravan

---

**Status:** 
- ✅ SJ je sada dobar (BW i vTO razumni, jaka korelacija)
- ⚠️ CMJ zahteva dodatnu proveru (vTO previše mali)
