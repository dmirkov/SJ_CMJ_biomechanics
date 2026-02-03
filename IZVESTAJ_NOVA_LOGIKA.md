# IZVEŠTAJ O IMPLEMENTIRANOJ NOVOJ LOGICI

**Datum:** 2026-02-02

## ✅ IMPLEMENTIRANE PROMENE

### 1. Robustniji Body Weight (BW) Izračun

**Pre:** BW se računao na početku fajla (prvih 3000 samples)

**Sada:**
- Nađe se prvi apsolutni minimum u celom signalu (flight faza)
- BW se računa iz stabilnog perioda 0.5s PRE minimuma
- Filtriranje tačaka koje međusobno ne odstupaju značajno (unutar 2*SD)
- Fallback na staru metodu ako nema dovoljno podataka

**Funkcija:** `calculate_body_weight_robust()`

---

### 2. Poboljšana Take-Off (TO) i Landing (LAND) Detekcija

**Pre:** Tražila se prva tačka gde je sila < 15N pre/posle impact-a

**Sada:**
- Nađe se apsolutni minimum sile u celom signalu (flight faza, sila ≈ 0)
- Pronađe se maksimum LEVO od minimuma = propulsion peak (take-off faza)
- Pronađe se maksimum DESNO od minimuma = landing peak
- Od propulsion peak-a, ide DESNO i traži prvu tačku gde je sila < 50N
  - Ako je blizu (unutar 1 sample) veća od 10N, pomeri za još jednu tačku desno
- Od landing peak-a, ide LEVO i traži prvu tačku gde je sila < 50N
  - Ako je blizu veća od 10N, pomeri za još jednu tačku levo

**Threshold:** 50N i 10N su fiksni (ne zavise od BW) jer se odnose na kontakt sa Force Plate

---

### 3. Poboljšana Onset (START) Detekcija

#### SJ (Squat Jump):
- Nađe se maksimum od početka signala do minimuma
- Od maksimuma ide UNAZAD (levo) i traži prvu tačku gde je sila < BW + 5*SD
- Detekcija countermovement-a:
  - Proverava da li postoji negativna faza (sila < BW - 2*SD) pre onset-a
  - Ako postoji, skok je označen kao neispravan (nije pravi SJ)

#### CMJ (Countermovement Jump):
- Od minimuma ide LEVO i traži prvu tačku gde je sila > BW - 5*SD

**Threshold:** 5*SD (umesto 2*SD) za precizniju detekciju

---

### 4. Integracija Brzine i Pomeraja

**Pre:** Integracija počinje od onset-a (idx['A']), ali ako je onset loš, dolazi do drifta

**Sada:**
- ✅ Integracija i dalje počinje od onset-a (idx['A'])
- ✅ Onset je sada precizniji (koristi robustniji BW i 5*SD threshold)
- ✅ Drift correction koristi landing period umesto kraja signala
- ✅ Validacija: proverava da li je brzina na landing-u blizu 0

---

### 5. QC Flagovi

Dodati flagovi za identifikaciju neispravnih skokova:
- `has_countermovement`: Detektovan countermovement u SJ skoku
- `negative_vto`: Negativan vTO (greška u detekciji)
- `invalid_events`: Neispravna detekcija događaja (pike, minimum, itd.)
- `invalid_jump`: Kombinacija svih flagova
- `qc_notes`: Detaljne napomene o problemima

---

## 📊 REZULTATI

### Status izvršavanja:
- ✅ SJ_FP: 79 fajlova obrađeno
- ✅ CMJ_FP: 74 fajlova obrađeno
- ✅ Excel fajl ažuriran sa novim KPIs

### Edge Case Handling:
- ✅ Dodate provere za prazne nizove
- ✅ Validacija pika i minimuma
- ✅ Fallback logika za problematične slučajeve

---

## 🔧 TEHNIČKI DETALJI

### Ključne funkcije:
1. `calculate_body_weight_robust()` - Robustniji BW izračun
2. `analyze_jump()` - Glavna funkcija za analizu skoka
   - Detekcija pika oko minimuma
   - Precizna TO i LAND detekcija
   - Poboljšana onset detekcija
   - Integracija i drift correction

### Validacije:
- Provera da li su pike validni (unutar granica signala)
- Provera da li je minimum između pika
- Provera da li su segmenti dovoljno veliki za analizu
- Provera NaN vrednosti u BW izračunu

---

## 📝 NAPOMENE

1. **SJ Countermovement Detekcija:** 
   - Sada se detektuje negativna faza pre onset-a
   - Skokovi sa countermovement-om su označeni kao neispravni

2. **TO i LAND Threshold:**
   - Fiksni threshold (50N, 10N) jer se odnosi na kontakt sa Force Plate
   - Ne zavisi od BW jer je to fizička karakteristika Force Plate-a

3. **Onset Threshold:**
   - 5*SD umesto 2*SD za precizniju detekciju
   - Različita logika za SJ i CMJ

---

**Status:** ✅ Implementacija završena i testirana
