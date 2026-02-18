# Konfiguracija putanja

## Objedinjeni projekat

Sve skripte koriste **paths_config** za putanje ka podacima. Podaci mogu biti na cloud-u (OneDrive, Google Drive, itd.) da ne opterećuju C disk ni repozitorijum.

## Postavljanje

1. **Kloniraj repo** na željenu lokaciju (npr. `C:\Cursor_Projekti\SJ_CMJ_biomechanics`)

2. **Kopiraj** `paths_config.example.py` kao `paths_config.py`:
   ```
   copy paths_config.example.py paths_config.py
   ```

3. **Uredi** `paths_config.py` i postavi `DATA_ROOT` na lokaciju gde su podaci:
   - `processed_data/`
   - `SJ_ForcePlates/`, `CMJ_ForcePlates/`
   - `SJ_Qualisys/`, `CMJ_Qualisys/`
   - `SJ_Qualisys_CoM/`, `CMJ_Qualisys_CoM/`

   Primer:
   ```python
   DATA_ROOT = Path(r"X:\OneDrive\SJ_CMJ_Data")  # ili tvoja cloud putanja
   ```

4. **Output** (Excel, plotovi) ostaje u projektu: `Output/`

## Struktura podataka na DATA_ROOT

```
DATA_ROOT/
├── processed_data/      # *_processed.tsv
├── SJ_ForcePlates/      # *.txt
├── CMJ_ForcePlates/     # *.txt
├── SJ_Qualisys/         # TSV bez CoM (input za add_com_columns)
├── CMJ_Qualisys/
├── SJ_Qualisys_CoM/     # TSV sa CoM (output od add_com_columns)
└── CMJ_Qualisys_CoM/
```

## Ako ne napraviš paths_config.py

Skripte rade i bez njega – koriste se podaci u korenu projekta (fallback u `lib/config.py`).
