# Analyse du Bug fill_null dans transform.py

## 🔍 Hypothèse du Bug

Vous avez signalé que des données en entrée bien renseignées deviennent manquantes en sortie.

Vous pensez que le problème vient du fait qu'on fait une update d'une ligne qui n'avait **pas de valeur montant** et qu'on choisit la valeur **null** au lieu de choisir la **nouvelle valeur de montant**.

## 📍 Localisation du Code Suspect

**Fichier:** `src/tasks/transform.py`
**Fonction:** `replace_with_modification_data()`
**Lignes:** 199-204

```python
# Étape 4: Remplir les valeurs nulles en utilisant les dernières valeurs non-nulles pour chaque id
lf_concat = lf_concat.with_columns(
    pl.col("montant", "dureeMois", "titulaires")
    .fill_null(strategy="backward")  # ← CODE SUSPECT
    .over("uid")
)
```

## 📊 Contexte: Comment les Données Sont Triées

**Ligne 193-196:**
```python
.sort(
    ["uid", "dateNotification", "modification_id"],
    descending=[False, True, True]
)
```

Cela signifie:
- `uid`: ordre **croissant** (A → Z)
- `dateNotification`: ordre **décroissant** (2023-12-01 → 2023-01-01)
- `modification_id`: ordre **décroissant** (2 → 1 → 0)

**Résultat:** Les modifications les plus **RÉCENTES** sont en **HAUT** du DataFrame.

## 🧪 Scénario de Test

Imaginons un marché avec ces données:

### Données d'entrée (ordre chronologique):
```
uid="M123", modification_id=0, date=2023-01-01, montant=null     (version initiale)
uid="M123", modification_id=1, date=2023-06-01, montant=5000     (modification)
```

### Après tri (dateNotification DESC):
```
Index 0: uid="M123", modification_id=1, date=2023-06-01, montant=5000  ← Plus RÉCENT
Index 1: uid="M123", modification_id=0, date=2023-01-01, montant=null  ← Plus ANCIEN
```

## ❓ Questions Clés

### Question 1: Que fait `fill_null(strategy="backward")`?

D'après la [documentation Polars](https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.fill_null.html):

- **`strategy="backward"`** (ou `bfill`): "Propage les valeurs vers l'arrière" = remplit avec la **prochaine** valeur non-null
- **`strategy="forward"`** (ou `ffill`): "Propage les valeurs vers l'avant" = remplit avec la **précédente** valeur non-null

**MAIS ATTENTION:** "arrière" et "avant" dépendent de l'**ordre des lignes** dans le DataFrame, pas de l'ordre chronologique!

### Question 2: Dans notre cas, que se passe-t-il?

Avec les données triées DESC (plus récent en haut):

```
Index 0: montant=5000  ← Plus RÉCENT en HAUT
Index 1: montant=null  ← Plus ANCIEN en BAS
```

#### Avec `fill_null(strategy="backward")`:
- Index 1 (null) cherche la **prochaine** valeur non-null **en remontant** dans le DataFrame
- Mais Index 1 est déjà **en bas**, il n'y a rien "après"
- **Résultat:** `montant` reste `null` ❌

#### Avec `fill_null(strategy="forward")`:
- Index 0 (5000) propage sa valeur **vers le bas**
- Index 1 (null) reçoit la valeur de Index 0
- **Résultat:** `montant` devient `5000` ✅

## 🎯 Diagnostic

**LE BUG EST CONFIRMÉ!**

Avec les données triées par `dateNotification DESC`:
- Les modifications **récentes** sont en **haut**
- `fill_null(strategy="backward")` essaie de remplir vers le **haut** (= vers le futur)
- Mais les valeurs nulles sont en **bas** (dans le passé)
- Elles ne peuvent donc **pas** être remplies

## ✅ Solution

**Remplacer:**
```python
.fill_null(strategy="backward")
```

**Par:**
```python
.fill_null(strategy="forward")
```

## 📝 Explication de la Solution

Avec `strategy="forward"`:
1. Les modifications **récentes** (en haut) ont leurs valeurs
2. Ces valeurs sont **propagées vers le bas** (vers le passé)
3. Les versions **anciennes** (en bas) qui ont des `null` reçoivent les valeurs des modifications récentes
4. **C'est exactement le comportement voulu!**

## 🔬 Test de Validation

Pour valider cette correction, vous devriez:

1. **Installer l'environnement:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install polars
   ```

2. **Exécuter le test:**
   ```bash
   python3 test_fill_null_simple.py
   ```

3. **Vérifier le résultat:**
   - `strategy="backward"` devrait laisser des `null` ❌
   - `strategy="forward"` devrait propager les valeurs ✅

## ⚠️ Attention

Avant d'appliquer la correction, **il faut absolument tester** avec les vraies données pour s'assurer que:

1. Le comportement de Polars est bien celui attendu
2. Il n'y a pas d'autres effets de bord
3. Les tests existants passent toujours

## 🧩 Code de Test Minimal

Si vous avez polars installé, testez ceci:

```python
import polars as pl

# Données test
df = pl.DataFrame({
    "uid": ["M1", "M1"],
    "modification_id": [0, 1],
    "date": ["2023-01-01", "2023-06-01"],
    "montant": [None, 5000.0]
})

# Tri DESC
df_sorted = df.sort("date", descending=True)
print("Après tri DESC:")
print(df_sorted)
# Index 0: date=2023-06-01, montant=5000
# Index 1: date=2023-01-01, montant=null

# Test backward
df_back = df_sorted.with_columns(
    pl.col("montant").fill_null(strategy="backward")
)
print("\nAvec backward:")
print(df_back)

# Test forward
df_fwd = df_sorted.with_columns(
    pl.col("montant").fill_null(strategy="forward")
)
print("\nAvec forward:")
print(df_fwd)
```

## 📌 Conclusion

Le bug est **probablement confirmé** mais **nécessite un test** avec Polars pour être 100% sûr.

La correction à appliquer est dans `src/tasks/transform.py` ligne 202:
- ❌ `strategy="backward"` (actuel)
- ✅ `strategy="forward"` (corrigé)

---

**Auteur:** Diagnostic automatique
**Date:** 2025-10-10
**Status:** ⚠️ **NÉCESSITE VALIDATION PAR TEST**
