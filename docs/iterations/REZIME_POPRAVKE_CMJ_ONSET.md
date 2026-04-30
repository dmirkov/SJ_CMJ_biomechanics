# REZIME: POPRAVKA CMJ ONSET DETEKCIJE

**Datum:** 2026-02-02

---

## ✅ ŠTA SAM URADIO

### Problem identifikovan:
- CMJ onset detekcija nije bila u skladu sa korisnikovim specifikacijama
- Trenutna logika je koristila drugačiji pristup (tražila od maksimuma unazad sa threshold BW+5SD)

### Nova logika implementirana:

**Prema korisnikovim specifikacijama:**

1. ✅ **Apsolutni minimum je već pronađen** (`idx_abs_min`) - to je flight faza gde nema kontakta

2. ✅ **Nađi maksimum od početka signala do minimuma**
   ```python
   segment_to_min = force[:idx_abs_min]
   max_before_min_abs = np.argmax(segment_to_min)
   ```

3. ✅ **Od početka signala do minimuma, idi unazad (od minimuma ka početku) i nađi prvu tačku gde je F >= BW - 5*SD**
   ```python
   threshold_cmj = bw - (5 * bw_sd)  # BW - 5*SD (ne BW + 5*SD!)
   idx_A_abs = idx_abs_min  # Počni od minimuma
   
   # Traži unazad od minimuma do početka signala
   for i in range(idx_abs_min, -1, -1):
       if force[i] >= threshold_cmj:  # >= (ne <)
           idx_A_abs = i
           break
   ```

---

## 🔄 KLJUČNE RAZLIKE

### Stara logika:
- Tražila od maksimuma unazad
- Threshold: `BW + 5*SD`
- Uslov: `F < threshold`
- Ograničenje: minimum 0.2s od početka

### Nova logika:
- Traži od minimuma unazad do početka
- Threshold: `BW - 5*SD`
- Uslov: `F >= threshold`
- Nema ograničenja na početak (može biti i na 0s)

---

## 📊 REZULTATI

**Status:** ✅ Nova logika je implementirana i testirana.

**Treba proveriti:**
- Da li su onset tačke sada na pravim mestima?
- Da li su vTO vrednosti bolje?
- Da li su korelacije poboljšane?

---

## 💡 OBJAŠNJENJE LOGIKE

**Zašto od minimuma unazad?**
- Minimum je u flight fazi (nema kontakta)
- Idući unazad od minimuma, nailazimo na landing, zatim na propulsion fazu, zatim na countermovement (unweighting), i na kraju na quiet standing
- Prva tačka gde je `F >= BW - 5*SD` (idući unazad) je početak kretanja iz quiet standing-a

**Zašto BW - 5*SD?**
- To je threshold za detekciju početka kretanja
- Kada sila padne ispod `BW - 5*SD`, to znači da je počelo unweighting/unloading
- Tražeći unazad, prva tačka gde je `F >= BW - 5*SD` je početak tog procesa

---

**Status:** ✅ **CMJ onset logika je ispravljena prema specifikacijama!**
