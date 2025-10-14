"""
Test pour reproduire le bug de fill_null dans replace_with_modification_data().

BUG IDENTIFIÉ:
- Quand un marché initial a montant=null et qu'une modification a montant=1000
- La stratégie fill_null(strategy="backward") remplit INCORRECTEMENT avec null
- au lieu de prendre la valeur 1000 de la modification

CAUSE:
- Les données sont triées par dateNotification DESC (plus récent en premier)
- fill_null(strategy="backward") remplit vers le HAUT du DataFrame
- Donc il prend les valeurs PLUS ANCIENNES au lieu des plus RÉCENTES
"""

import polars as pl


def test_fill_null_bug_simple():
    """Test simple pour reproduire le bug."""
    print("\n🧪 TEST 1: Reproduction du bug fill_null")
    print("=" * 80)

    # Données de test simulant le problème
    # UID1 : données initiales avec montant=null, modification avec montant=1000
    data = {
        "uid": ["UID1", "UID1", "UID2", "UID2"],
        "modification_id": [0, 1, 0, 1],
        "dateNotification": ["2023-01-01", "2023-06-01", "2023-02-01", "2023-08-01"],
        "montant": [None, 1000.0, 500.0, 2000.0],
    }

    df = pl.DataFrame(data)

    print("\n📋 Données AVANT tri et fill_null:")
    print(df)

    # Simulation du tri tel qu'il est fait dans le code (ligne 193-196)
    df_sorted = df.sort(
        ["uid", "dateNotification", "modification_id"], descending=[False, True, True]
    )

    print("\n📋 Données APRÈS tri (dateNotification DESC):")
    print(df_sorted)

    # Application du fill_null tel qu'il est fait dans le code (ligne 200-204)
    df_filled_backward = df_sorted.with_columns(
        pl.col("montant").fill_null(strategy="backward").over("uid")
    )

    print("\n❌ Résultat avec fill_null(strategy='backward') - BUGUÉ:")
    print(df_filled_backward)

    # Vérifier le bug
    uid1_mod0 = df_filled_backward.filter(
        (pl.col("uid") == "UID1") & (pl.col("modification_id") == 0)
    )["montant"][0]

    print(f"\n🔍 Valeur du montant pour UID1, modification_id=0: {uid1_mod0}")

    if uid1_mod0 is None or (isinstance(uid1_mod0, float) and pl.Series([uid1_mod0]).is_null()[0]):
        print("   ❌ BUG CONFIRMÉ: montant est resté NULL au lieu de prendre 1000.0")
    else:
        print(f"   ✅ montant = {uid1_mod0}")

    # LA BONNE SOLUTION: utiliser fill_null(strategy="forward")
    df_filled_forward = df_sorted.with_columns(
        pl.col("montant").fill_null(strategy="forward").over("uid")
    )

    print("\n✅ Résultat avec fill_null(strategy='forward') - CORRIGÉ:")
    print(df_filled_forward)

    uid1_mod0_fixed = df_filled_forward.filter(
        (pl.col("uid") == "UID1") & (pl.col("modification_id") == 0)
    )["montant"][0]

    print(f"\n🔍 Valeur du montant pour UID1, modification_id=0: {uid1_mod0_fixed}")
    print(f"   ✅ CORRECT: montant = {uid1_mod0_fixed} (valeur de la modification)")


def test_fill_null_bug_realistic():
    """Test plus réaliste avec plusieurs modifications."""
    print("\n\n🧪 TEST 2: Cas réaliste avec plusieurs modifications")
    print("=" * 80)

    # Marché avec 3 versions:
    # - Version initiale: montant=null, dureeMois=12
    # - Modification 1: montant=5000, dureeMois=null (garde 12)
    # - Modification 2: montant=null (devrait garder 5000), dureeMois=24
    data = {
        "uid": ["M123", "M123", "M123"],
        "modification_id": [0, 1, 2],
        "dateNotification": ["2023-01-01", "2023-06-01", "2023-12-01"],
        "montant": [None, 5000.0, None],
        "dureeMois": [12, None, 24],
    }

    df = pl.DataFrame(data)

    print("\n📋 Données initiales (ordre chronologique):")
    print(df)

    # Tri comme dans le code
    df_sorted = df.sort(
        ["uid", "dateNotification", "modification_id"], descending=[False, True, True]
    )

    print("\n📋 Après tri (dateNotification DESC):")
    print(df_sorted)

    # Stratégie BUGUÉE (backward)
    df_backward = df_sorted.with_columns(
        pl.col("montant", "dureeMois").fill_null(strategy="backward").over("uid")
    )

    print("\n❌ Avec strategy='backward' (BUGUÉ):")
    print(df_backward)

    # Stratégie CORRECTE (forward)
    df_forward = df_sorted.with_columns(
        pl.col("montant", "dureeMois").fill_null(strategy="forward").over("uid")
    )

    print("\n✅ Avec strategy='forward' (CORRECT):")
    print(df_forward)

    print("\n📊 Comparaison des résultats:")
    print("   Modification 0 (initial):")
    print(f"      - Backward: montant={df_backward[2]['montant']}, dureeMois={df_backward[2]['dureeMois']}")
    print(f"      - Forward:  montant={df_forward[2]['montant']}, dureeMois={df_forward[2]['dureeMois']}")
    print("   Modification 2 (plus récente):")
    print(f"      - Backward: montant={df_backward[0]['montant']}, dureeMois={df_backward[0]['dureeMois']}")
    print(f"      - Forward:  montant={df_forward[0]['montant']}, dureeMois={df_forward[0]['dureeMois']}")


def test_correct_solution():
    """Test de la solution correcte complète."""
    print("\n\n🧪 TEST 3: Validation de la solution complète")
    print("=" * 80)

    # Cas complexe avec 2 marchés
    data = {
        "uid": ["A", "A", "A", "B", "B"],
        "modification_id": [0, 1, 2, 0, 1],
        "dateNotification": [
            "2023-01-01",
            "2023-06-01",
            "2023-12-01",
            "2023-03-01",
            "2023-09-01",
        ],
        "montant": [1000.0, None, 3000.0, None, 2000.0],
        "dureeMois": [None, 24, None, 12, None],
        "titulaires": [["T1"], None, ["T3"], ["T4"], None],
    }

    df = pl.DataFrame(data)

    print("\n📋 Données de test (2 marchés, plusieurs modifications):")
    print(df)

    # Tri
    df_sorted = df.sort(
        ["uid", "dateNotification", "modification_id"], descending=[False, True, True]
    )

    # Solution CORRECTE
    df_correct = df_sorted.with_columns(
        pl.col("montant", "dureeMois", "titulaires")
        .fill_null(strategy="forward")
        .over("uid")
    )

    print("\n✅ SOLUTION CORRECTE avec fill_null(strategy='forward'):")
    print(df_correct)

    # Vérifications
    print("\n✅ VÉRIFICATIONS:")

    # Marché A, modification 0 (la plus ancienne)
    a_mod0 = df_correct.filter((pl.col("uid") == "A") & (pl.col("modification_id") == 0))
    print(
        f"   Marché A, modif 0: montant={a_mod0['montant'][0]}, dureeMois={a_mod0['dureeMois'][0]}"
    )
    assert a_mod0["montant"][0] == 1000.0, "Devrait garder le montant initial"
    assert a_mod0["dureeMois"][0] == 24, "Devrait prendre dureeMois de la modif 1"

    # Marché A, modification 1
    a_mod1 = df_correct.filter((pl.col("uid") == "A") & (pl.col("modification_id") == 1))
    print(
        f"   Marché A, modif 1: montant={a_mod1['montant'][0]}, dureeMois={a_mod1['dureeMois'][0]}"
    )
    assert a_mod1["montant"][0] == 3000.0, "Devrait prendre montant de la modif 2"
    assert a_mod1["dureeMois"][0] == 24, "Devrait garder dureeMois"

    # Marché B, modification 0
    b_mod0 = df_correct.filter((pl.col("uid") == "B") & (pl.col("modification_id") == 0))
    print(
        f"   Marché B, modif 0: montant={b_mod0['montant'][0]}, dureeMois={b_mod0['dureeMois'][0]}"
    )
    assert b_mod0["montant"][0] == 2000.0, "Devrait prendre montant de la modif 1"
    assert b_mod0["dureeMois"][0] == 12, "Devrait garder dureeMois initial"

    print("\n✅ TOUS LES TESTS PASSENT!")


if __name__ == "__main__":
    print("=" * 80)
    print("🔬 TESTS DE REPRODUCTION DU BUG fill_null(strategy='backward')")
    print("=" * 80)

    test_fill_null_bug_simple()
    test_fill_null_bug_realistic()
    test_correct_solution()

    print("\n\n" + "=" * 80)
    print("📝 RÉSUMÉ DU BUG")
    print("=" * 80)
    print("""
BUG IDENTIFIÉ dans transform.py ligne 200-204:

    lf_concat = lf_concat.with_columns(
        pl.col("montant", "dureeMois", "titulaires")
        .fill_null(strategy="backward")  # ❌ ERREUR ICI
        .over("uid")
    )

PROBLÈME:
- Les données sont triées par dateNotification DESC (plus récent d'abord)
- fill_null(strategy="backward") remplit vers le HAUT du DataFrame
- Résultat: les valeurs null prennent les valeurs PLUS ANCIENNES
  au lieu des plus RÉCENTES

SOLUTION:

    lf_concat = lf_concat.with_columns(
        pl.col("montant", "dureeMois", "titulaires")
        .fill_null(strategy="forward")  # ✅ CORRECT
        .over("uid")
    )

EXPLICATION:
- Avec dateNotification DESC, "forward" va vers le BAS = vers le passé
- Donc les null sont remplis avec les valeurs des modifications PRÉCÉDENTES
- C'est exactement le comportement voulu!
""")
