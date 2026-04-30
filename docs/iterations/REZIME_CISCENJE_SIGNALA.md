# REZIME: ČIŠĆENJE SIGNALA ZA 14_4_2 I 14_4_5

**Datum:** 2026-02-02

---

## 🔍 ANALIZA PROBLEMA

### Problematični fajlovi:
- **14_4_2.txt**
- **14_4_5.txt**

### Greška:
```
index -1 is out of bounds for axis 0 with size 0
```

### Analiza:

**Iz debug analize:**
- Oba fajla **IMAJU kontakt** sa Force Plate-om
- Svi samples u prvih 3s imaju kontakt (> 100N)
- BW period je validan (1400 samples)
- BW vrednosti su razumne (~424N)

**Problem nije u BW detekciji!**

---

## 🔧 POPRAVKE IMPLEMENTIRANE

### 1. **Dodatna provera za kontakt**
```python
# Proveri da li ima dovoljno kontakta
if len(contact_indices) < 100:
    return calculate_body_weight(force, fs)
```

### 2. **Popravka impulse calculation**
```python
# Dodatna provera za prazne segmente
if idx['F'] > idx['A'] and idx['F'] < len(f_crop) and idx['A'] >= 0:
    segment_tot = f_crop[idx['A']:idx['F']] - bw
    if len(segment_tot) > 0:
        m['J_tot'] = cumulative_trapezoid(segment_tot, t_crop[idx['A']:idx['F']])[-1]
    else:
        m['J_tot'] = 0
```

### 3. **Validacija indeksa**
- Dodate provere da li su indeksi u validnom opsegu
- Provere da li segmenti nisu prazni pre pristupa `[-1]`

---

## ✅ REZULTAT

**Status:** Popravke su implementirane. Treba testirati da li su greške rešene.

---

## 📝 NAPOMENA

Ako greške i dalje postoje, možda je problem u:
- Detekciji pika (propulsion/landing peaks)
- Detekciji TO/LAND tačaka
- Nekom drugom delu koda gde se koristi `[-1]` na potencijalno praznom array-u

**Preporuka:** Ako greške i dalje postoje, treba dodati try-except blokove za bolje error handling.
