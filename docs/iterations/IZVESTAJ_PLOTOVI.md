# IZVEŠTAJ O PLOTOVIMA FORCE PLATE SKOKOVA

**Datum:** 2026-02-02

## ✅ ZAVRŠENO

### 1. Popravka vTO
- **Promena:** vTO sada koristi direktno brzinu u trenutku odskoka (TO tački) - `vel[idx['F']]`
- **Status:** ✅ Implementirano u `calculate_fp_kpis.py`

### 2. Kreiranje Plotova
- **Skripta:** `plot_fp_jumps.py`
- **Output folderi:**
  - `Output/Plots/SJ_FP/` - 79 plotova
  - `Output/Plots/CMJ_FP/` - 74 plotova
- **Ukupno:** 153 plotova kreirano

## 📊 FORMAT PLOTOVA

Svaki plot sadrži:

### Osnovni podaci:
- **Leva Y osa:** Vertikalno ubrzanje az(t) [m/s²] - plava linija
- **Desna Y osa:** Vertikalna brzina vz(t) [m/s] - crvena linija
- **X osa:** Vreme [s]

### Obeležene karakteristične tačke:

| Tačka | Oznaka | Opis | Marker |
|-------|--------|------|--------|
| START | A | Početak skoka (onset) | Zeleni krug |
| vmin | vmin | Minimalna brzina | Ljubičasti kvadrat |
| vmax | vmax | Maksimalna brzina | Narandžasti trougao |
| hmin | hmin | Minimalna visina (displacement) | Tamnoplavi zvezda |
| C | C | Countermovement minimum (samo CMJ) | Cijan trougao |
| D | D | Braking phase start (samo CMJ) | Magenta pentagon |
| TO | F | Takeoff (odskok) | Crveni dijamant |
| LAND | H | Landing (doskok) | Braon X |

### Anotacije:
- Svaka karakteristična tačka ima anotaciju sa:
  - Nazivom tačke
  - Vrednošću brzine (vz) u toj tački
- Anotacije su u žutim okvirima sa strelicama

### Naslov:
- Tip skoka (SJ ili CMJ)
- Naziv fajla
- Ključne vrednosti: START, TO (sa vTO), LAND, vmax

## 📁 STRUKTURA FAJLOVA

```
Output/
└── Plots/
    ├── SJ_FP/
    │   ├── 01_3_1_plot.png
    │   ├── 01_3_2_plot.png
    │   └── ... (79 fajlova)
    └── CMJ_FP/
        ├── 02_4_1_plot.png
        ├── 02_4_2_plot.png
        └── ... (74 fajlova)
```

## 🔍 PRIMER UPOTREBE

Plotovi mogu biti korisni za:
1. **Vizuelnu validaciju** detektovanih karakterističnih tačaka
2. **Proveru kvaliteta** podataka i detekcije događaja
3. **Debugovanje** problema sa vTO ili drugim KPIs
4. **Edukaciju** o biomehanici skokova

## 📝 NAPOMENE

- Plotovi su kreirani sa rezolucijom 150 DPI
- Format: PNG
- Veličina: 14x8 inča
- Svi karakteristični događaji su automatski detektovani koristeći istu logiku kao u `calculate_fp_kpis.py`

---

**Status:** ✅ Kompletirano
