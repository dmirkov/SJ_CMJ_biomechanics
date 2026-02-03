# ANALIZA TRENUTNE LOGIKE I PREDLOZI ZA POPRAVKU

## 1. TRENUTNA LOGIKA ZA POČETAK KRETANJA (ONSET)

### SJ (Squat Jump):
```
1. Traži prvu tačku gde je sila > BW + 2*SD (loading/trigger)
2. Ide unazad (look_back_window = 500 samples) 
3. Traži poslednju tačku gde je sila <= BW + 1.5*SD (quiet standing)
4. To je onset (A)
```

**Problem:** 
- BW se računa na početku fajla (prvih 3000 samples)
- Ako ima pomeranja na početku, BW je pogrešan
- Trigger može biti previše kasno

### CMJ (Countermovement Jump):
```
1. Traži prvu tačku gde je sila < BW - 2*SD (unloading)
2. To je onset (A)
```

**Problem:**
- Isti problem sa BW - ako ima pomeranja na početku, BW je pogrešan
- Može detektovati onset previše rano ili kasno

---

## 2. TRENUTNA LOGIKA ZA INTEGRACIJU

```
1. acc = (f_crop - bw) / bm
2. vel = cumulative_trapezoid(acc, t_crop, initial=0)
3. vel = vel - vel[idx['A']]  # Postavi brzinu na 0 na onset-u
4. disp = cumulative_trapezoid(vel, t_crop, initial=0)
5. disp = disp - disp[idx['A']]  # Postavi pomeraj na 0 na onset-u
```

**Problem:**
- ✅ Integracija počinje od onset-a (idx['A'])
- ❌ Ako je idx['A'] loš, dolazi do drifta
- ❌ Drift correction pokušava da popravi, ali ako je onset loš, drift correction ne može pomoći

---

## 3. TRENUTNA LOGIKA ZA TAKE-OFF DETEKCIJU

```
1. Nađe globalni minimum sile (idx['min'])
2. Nađe impact (prvi maksimum posle minimuma)
3. Traži prvu tačku PRE impact-a gde je sila < 15N
4. To je take-off (F)
5. Traži poslednju tačku gde je sila < 15N
6. To je landing (H)
```

**Problem:**
- ❌ Često nalazi take-off odmah kod landing-a
- ❌ Ne koristi strukturu signala (pikovi)
- ❌ Threshold od 15N može biti problematičan

---

## 4. PREDLOŽENA POPRAVKA - RAZUMEVANJE

### A. ROBUSTNIJI BW I ONSET:

**Korak 1: Nađi prvi minimum (unloading/unweighting)**
- Najniži minimum u signalu (to je verovatno countermovement ili početak skoka)

**Korak 2: Odredi BW iz stabilnog perioda**
- Od početka do tačke koja je 0.5s PRE minimuma
- Nađi sve tačke koje međusobno ne odstupaju značajno (npr. unutar 1-2 SD)
- Izračunaj BW i SD_BW iz tih tačaka

**Korak 3: Nađi onset**
- Idi LEVO od minimuma
- Nađi prvu tačku koja je > BW - 5*SD_BW
- To je onset (A)

**Prednosti:**
- ✅ BW se računa iz stabilnog perioda (pre bilo kakvog kretanja)
- ✅ Onset je precizniji (koristi 5*SD umesto 2*SD)
- ✅ Radi za oba tipa skokova (SJ i CMJ)

---

### B. POBOLJŠANA TAKE-OFF DETEKCIJA:

**Korak 1: Nađi apsolutni minimum sile**
- To je flight period (sila ≈ 0)

**Korak 2: Nađi pike oko minimuma**
- **Prvi pik LEVO od minimuma** = propulsion peak (take-off faza)
- **Prvi pik DESNO od minimuma** = landing peak

**Korak 3: Precizna detekcija take-off**
- Od propulsion peak-a, idi DESNO
- Nađi prvu tačku gde je sila < 50N
- Proveri: ako je blizu (npr. < 10 samples) veća od 10N, pomeri za još jednu tačku desno
- To je take-off (F)

**Korak 4: Precizna detekcija landing**
- Od landing peak-a, idi LEVO
- Nađi prvu tačku gde je sila < 50N
- Proveri: ako je blizu veća od 10N, pomeri za još jednu tačku levo
- To je landing (H)

**Prednosti:**
- ✅ Koristi strukturu signala (pike)
- ✅ Ne zavisi od fiksnog threshold-a
- ✅ Preciznija detekcija take-off i landing

---

## 5. PITANJA ZA POTVRDU

1. **Za SJ:** Da li je logika za onset ista kao za CMJ (traži prvu tačku > BW - 5*SD_BW levo od minimuma), ili treba drugačije?

2. **Za minimum:** Da li tražim globalni minimum u celom signalu, ili samo u crop-ovanom delu (oko globalnog maksimuma)?

3. **Za pike:** Kako definišem "pik"? 
   - Lokalni maksimum sa određenom visinom?
   - Prvi lokalni maksimum levo/desno od minimuma?
   - Neki drugi kriterijum?

4. **Za threshold 50N i 10N:** Da li su ovi brojevi fiksni ili treba da zavise od BW?

5. **Za "blizu veća od 10N":** Šta znači "blizu"? Npr. unutar 10-20 samples?

---

## 6. MOJI PREDLOZI ZA DODATNA POBOLJŠANJA

1. **Adaptivni threshold:** Umesto fiksnog 50N, možda koristiti nešto kao 0.1*BW ili slično

2. **Validacija take-off:** Proveriti da li je brzina na take-off pozitivna i razumna

3. **Validacija landing:** Proveriti da li je brzina na landing blizu 0 (posle drift correction)

4. **Fallback logika:** Ako nova metoda ne uspe, koristiti staru metodu kao fallback

---

**Molim potvrdu razumevanja i odgovore na pitanja!**
