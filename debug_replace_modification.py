#!/usr/bin/env python3
"""
Script de débogage pour comprendre ce qui se passe dans replace_with_modification_data()
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import polars as pl

# Simuler exactement ce qui se passe pour le marché problématique
print("="*80)
print("SIMULATION DE replace_with_modification_data()")
print("="*80)

# Données APRÈS write_marche_rows() et AVANT replace_with_modification_data()
# C'est ce qu'on a dans le DataFrame à l'entrée de la fonction
data_input = {
    "uid": ["UID123", "UID123", "UID123"],
    "montant": [75000.0, None, None],  # Seule la première ligne a le montant
    "dureeMois": [48, None, None],     # Seule la première ligne a la durée
    "dateNotification": ["2022-12-15", "2022-12-14", "2022-12-14"],
    "modification_montant": [None, None, None],      # Les modifs n'ont pas de montant
    "modification_dureeMois": [None, None, None],    # Les modifs n'ont pas de durée
    "modification_dateNotificationModification": [None, "2022-12-14", "2022-12-14"],
}

df = pl.DataFrame(data_input)

print("\n1️⃣  DONNÉES EN ENTRÉE (après write_marche_rows):")
print(df)

# ÉTAPE 1: Extraire les modifications
import polars.selectors as cs

df_mods = df.select(cs.by_name("uid") | cs.starts_with("modification_"))

print("\n2️⃣  df_mods AVANT rename:")
print(df_mods)

df_mods = df_mods.rename({
    "modification_montant": "montant",
    "modification_dureeMois": "dureeMois",
    "modification_dateNotificationModification": "dateNotification",
}).filter(~pl.all_horizontal(pl.all().exclude("uid").is_null()))

print("\n2️⃣bis  df_mods APRÈS rename et filter:")
print(df_mods)

# ÉTAPE 2: Créer df_base avec unique("uid")
df_unique = df.unique("uid")
print("\n3️⃣  Après df.unique('uid') - QUELLE LIGNE EST GARDÉE ?")
print(df_unique)

df_base = df_unique.select(
    "uid",
    "dateNotification",
    "montant",
    "dureeMois",
)

print("\n4️⃣  df_base (données de base):")
print(df_base)
print(f"   Colonnes: {df_base.columns}")
print(f"   df_mods colonnes: {df_mods.columns}")

# ÉTAPE 3: Concat
# S'assurer que les colonnes sont dans le même ordre
df_mods_reordered = df_mods.select(df_base.columns)
df_concat = pl.concat([df_base, df_mods_reordered], how="vertical_relaxed")

print("\n5️⃣  Après concat (df_base + df_mods):")
print(df_concat)

# ÉTAPE 4: Ajouter modification_id
df_concat = df_concat.with_columns(
    pl.col("dateNotification")
    .rank(method="ordinal")
    .over("uid")
    .cast(pl.Int64)
    .sub(1)
    .alias("modification_id")
)

print("\n6️⃣  Après ajout de modification_id:")
print(df_concat)

# ÉTAPE 5: Tri DESC
df_concat = df_concat.sort(
    ["uid", "dateNotification", "modification_id"],
    descending=[False, True, True]
)

print("\n7️⃣  Après tri (dateNotification DESC):")
print(df_concat)

# ÉTAPE 6: fill_null backward
df_filled = df_concat.with_columns(
    pl.col("montant", "dureeMois")
    .fill_null(strategy="backward")
    .over("uid")
)

print("\n8️⃣  Après fill_null(strategy='backward'):")
print(df_filled)

# Test avec forward
df_filled_fwd = df_concat.with_columns(
    pl.col("montant", "dureeMois")
    .fill_null(strategy="forward")
    .over("uid")
)

print("\n9️⃣  Si on utilisait fill_null(strategy='forward'):")
print(df_filled_fwd)

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)
print("Le problème vient de unique('uid') à l'étape 3 !")
print("Polars prend une ligne ARBITRAIRE, qui peut être n'importe laquelle des 3.")
print("Si c'est une ligne de modification (sans montant), on perd le montant initial!")
