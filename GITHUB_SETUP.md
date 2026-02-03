# Kako povezati projekat sa GitHub-om

## 1. Kreiraj GitHub nalog (ako ga nemaš)

Idi na [github.com](https://github.com) i registruj se.

## 2. Kreiraj novi repozitorijum na GitHub-u

1. Klikni **"+"** → **"New repository"**
2. Unesi ime (npr. `SJ_CMJ_Biomechanics`)
3. Opciono: dodaj opis, odaberi Public/Private
4. **Ne** čekiraj "Initialize with README"
5. Klikni **"Create repository"**

## 3. Lokalno: Inicijalizuj Git i poveži

Otvori terminal (PowerShell) u folderu projekta:

```powershell
cd "c:\Users\dmirk\SJ_CMJ_Original_files"

# Inicijalizuj Git
git init

# Dodaj sve fajlove (poštuje .gitignore)
git add .

# Prvi commit
git commit -m "Initial commit: SJ/CMJ analysis scripts and results"

# Poveži sa GitHub repozitorijumom (zameni USER i REPO svojim)
git remote add origin https://github.com/USER/REPO.git

# Pošalji na GitHub
git branch -M main
git push -u origin main
```

## 4. Zameni USER i REPO

Ako je tvoj repo npr. `https://github.com/dmirkovic/SJ_CMJ_Biomechanics`:

```powershell
git remote add origin https://github.com/dmirkovic/SJ_CMJ_Biomechanics.git
```

## 5. Autentifikacija

Pri prvom `git push` Git će tražiti prijavu:

- **HTTPS:** username + Personal Access Token (ne lozinka)
- **SSH:** ako imaš SSH ključ podešen

Token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token.

## 6. Kasnije – ažuriranje repozitorijuma

```powershell
git add .
git status                    # proveri šta je dodato
git commit -m "Opis promena"
git push
```

## Napomena o veličini

Ako `Backup_Fajlovi`, `*_ForcePlates`, `*_Qualisys*` i `Output` zajedno budu preko ~100 MB, razmisli o uključivanju samo skripti i manjih fajlova. U `.gitignore` možeš odkomentarisati te foldere da se ne snime.
