#!/usr/bin/env python3
"""
Test minimal pour vérifier le comportement de fill_null avec backward vs forward.
Ce script peut être exécuté sans pytest, juste avec polars installé.
"""

try:
    import polars as pl
    print("✅ Polars importé avec succès\n")
except ImportError:
    print("❌ Erreur: polars n'est pas installé")
    print("   Installez-le avec: pip install polars")
    exit(1)

print("=" * 80)
print("TEST DU BUG fill_null(strategy='backward')")
print("=" * 80)

# CAS DE TEST: Un marché avec 2 versions
# - Version initiale (modif 0, date 2023-01-01): montant=null
# - Modification 1 (modif 1, date 2023-06-01): montant=5000
#
# COMPORTEMENT ATTENDU:
# Après fill_null, la version initiale devrait avoir montant=5000
# (elle hérite de la valeur de la modification)

data = {
    "uid": ["MARCHE1", "MARCHE1"],
    "modification_id": [0, 1],
    "dateNotification": ["2023-01-01", "2023-06-01"],
    "montant": [None, 5000.0],
}

df = pl.DataFrame(data)

print("\n📋 DONNÉES INITIALES (ordre chronologique):")
print(df)
print()

# TRI comme dans le code (ligne 193-196 de transform.py)
# descending=[False, True, True] signifie:
# - uid: ASC (False)
# - dateNotification: DESC (True) <- Les plus récentes en PREMIER
# - modification_id: DESC (True)
df_sorted = df.sort(
    ["uid", "dateNotification", "modification_id"],
    descending=[False, True, True]
)

print("📋 APRÈS TRI (dateNotification DESC = plus récent en premier):")
print(df_sorted)
print()

print("🔍 OBSERVATION: Après le tri DESC, l'ordre est:")
print("   Index 0: modification_id=1, montant=5000.0 (la plus RÉCENTE)")
print("   Index 1: modification_id=0, montant=null    (la plus ANCIENNE)")
print()

# TEST 1: AVEC backward (code actuel - BUGUÉ?)
print("-" * 80)
print("TEST 1: fill_null(strategy='backward') - CODE ACTUEL")
print("-" * 80)

df_backward = df_sorted.with_columns(
    pl.col("montant").fill_null(strategy="backward").over("uid")
)

print("\n📊 Résultat:")
print(df_backward)

montant_mod0_backward = df_backward.filter(pl.col("modification_id") == 0)["montant"][0]
montant_mod1_backward = df_backward.filter(pl.col("modification_id") == 1)["montant"][0]

print(f"\n   • modification_id=0 (initial): montant = {montant_mod0_backward}")
print(f"   • modification_id=1 (modif):   montant = {montant_mod1_backward}")

if montant_mod0_backward is None or pl.Series([montant_mod0_backward]).is_null()[0]:
    print("\n   ❌ PROBLÈME: modification_id=0 a toujours montant=null")
    print("      La valeur 5000 de la modification n'a PAS été propagée!")
    backward_is_buggy = True
else:
    print("\n   ✅ OK: modification_id=0 a bien hérité de la valeur")
    backward_is_buggy = False

# TEST 2: AVEC forward (correction proposée)
print("\n" + "-" * 80)
print("TEST 2: fill_null(strategy='forward') - CORRECTION PROPOSÉE")
print("-" * 80)

df_forward = df_sorted.with_columns(
    pl.col("montant").fill_null(strategy="forward").over("uid")
)

print("\n📊 Résultat:")
print(df_forward)

montant_mod0_forward = df_forward.filter(pl.col("modification_id") == 0)["montant"][0]
montant_mod1_forward = df_forward.filter(pl.col("modification_id") == 1)["montant"][0]

print(f"\n   • modification_id=0 (initial): montant = {montant_mod0_forward}")
print(f"   • modification_id=1 (modif):   montant = {montant_mod1_forward}")

if montant_mod0_forward is None or pl.Series([montant_mod0_forward]).is_null()[0]:
    print("\n   ❌ PROBLÈME: modification_id=0 a toujours montant=null")
    forward_is_buggy = True
else:
    print("\n   ✅ OK: modification_id=0 a bien hérité de la valeur 5000")
    forward_is_buggy = False

# CONCLUSION
print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

if backward_is_buggy and not forward_is_buggy:
    print("✅ BUG CONFIRMÉ!")
    print("   • strategy='backward' NE FONCTIONNE PAS (laisse des null)")
    print("   • strategy='forward' FONCTIONNE CORRECTEMENT")
    print("\n📝 CORRECTION NÉCESSAIRE dans transform.py ligne 202:")
    print("   Remplacer 'backward' par 'forward'")
elif not backward_is_buggy and forward_is_buggy:
    print("⚠️  ATTENTION: 'backward' fonctionne mais pas 'forward'")
    print("   Le code actuel est peut-être correct!")
elif not backward_is_buggy and not forward_is_buggy:
    print("✅ Les deux stratégies fonctionnent")
else:
    print("❌ Aucune stratégie ne fonctionne - problème plus profond")

print("\n" + "=" * 80)

# EXPLICATION DÉTAILLÉE
print("\n📚 EXPLICATION:")
print("""
Avec le tri DESC (plus récent en premier), le DataFrame ressemble à:
  Index 0: [date récente, montant=5000]  ← EN HAUT
  Index 1: [date ancienne, montant=null]  ← EN BAS

• fill_null(strategy='backward') remplit vers le HAUT du DataFrame
  → Index 1 essaie de prendre la valeur au-dessus (Index 0) = 5000 ✅
  → MAIS en Polars, 'backward' signifie "depuis la fin vers le début"
  → Avec .over("uid"), cela peut être confus!

• fill_null(strategy='forward') remplit vers le BAS du DataFrame
  → Index 0 essaie de prendre la valeur en dessous (Index 1) = null
  → Index 1 ne peut pas propager car il est à la fin

La vraie question: dans Polars, quelle direction prend fill_null quand
les données sont triées DESC?
""")
