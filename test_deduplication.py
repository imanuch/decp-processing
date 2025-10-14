"""Test de déduplication des UID entre test1.json et test2.json."""
import json
import sys
from pathlib import Path

import polars as pl

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import DATA_DIR, DIST_DIR, BASE_DIR
from flows import decp_processing

print("=" * 80)
print("TEST DE DÉDUPLICATION DES UID")
print("=" * 80)

# Charger le fichier de configuration de test
with open(DATA_DIR / "source_datasets_test.json", "r") as f:
    test_datasets = json.load(f)

print("\n📁 Fichiers à traiter :")
for dataset in test_datasets:
    for resource in dataset.get("resources", []):
        print(f"  - {resource['title']} ({resource['latest']})")

print("\n🔍 Analyse des fichiers sources :")
print("\ntest1.json :")
with open(DATA_DIR / "test1.json", "r") as f:
    data1 = json.load(f)
    marche1 = data1["marches"]["marche"][0]
    print(f"  - ID marché: {marche1['id']}")
    print(f"  - Acheteur ID: {marche1['acheteur']['id']}")
    print(f"  - UID attendu: {marche1['acheteur']['id']}{marche1['id']}")
    print(f"  - Montant initial: {marche1['montant']}")
    print(f"  - Nombre de modifications: {len(marche1.get('modifications', []))}")
    if 'modifications' in marche1:
        for i, mod in enumerate(marche1['modifications']):
            m = mod['modification']
            print(f"    Modif {i+1}: dateNotif={m['dateNotificationModification']}, montant={m['montant']}")

print("\ntest2.json :")
with open(DATA_DIR / "test2.json", "r") as f:
    data2 = json.load(f)
    marche2 = data2["marches"]["marche"][0]
    print(f"  - ID marché: {marche2['id']}")
    print(f"  - Acheteur ID: {marche2['acheteur']['id']}")
    print(f"  - UID attendu: {marche2['acheteur']['id']}{marche2['id']}")
    print(f"  - Montant initial: {marche2['montant']}")
    print(f"  - Nombre de modifications: {len(marche2.get('modifications', []))}")
    if 'modifications' in marche2:
        for i, mod in enumerate(marche2['modifications']):
            m = mod['modification']
            print(f"    Modif {i+1}: dateNotif={m['dateNotificationModification']}, montant={m['montant']}")

# Remplacer temporairement TRACKED_DATASETS
import config
original_datasets = config.TRACKED_DATASETS
config.TRACKED_DATASETS = test_datasets

print("\n" + "=" * 80)
print("🚀 LANCEMENT DU PIPELINE DE TRAITEMENT")
print("=" * 80)

try:
    # Lancer le flow principal
    decp_processing(enable_cache_removal=False)

    print("\n" + "=" * 80)
    print("✅ TRAITEMENT TERMINÉ - ANALYSE DES RÉSULTATS")
    print("=" * 80)

    # Analyser le résultat
    output_file = DIST_DIR / "decp.parquet"
    if output_file.exists():
        df = pl.read_parquet(output_file)

        uid_attendu = f"{marche1['acheteur']['id']}{marche1['id']}"

        print(f"\n📊 Résultats pour UID = {uid_attendu} :")
        result = df.filter(pl.col("uid") == uid_attendu)

        if result.height > 0:
            print(f"  ✅ Nombre de lignes trouvées: {result.height}")
            print(f"\n  Détail des lignes :")
            for row in result.iter_rows(named=True):
                print(f"    - modification_id={row.get('modification_id')}, "
                      f"montant={row.get('montant')}, "
                      f"dateNotification={row.get('dateNotification')}, "
                      f"donneesActuelles={row.get('donneesActuelles')}")

            print(f"\n  Colonnes disponibles: {result.columns[:10]}...")

            # Vérification
            nb_modifs = result.height
            print(f"\n🔍 Vérification :")
            print(f"  - test1.json avait 2 modifications → 3 lignes attendues (initial + 2 modifs)")
            print(f"  - test2.json avait 1 modification → 2 lignes attendues (initial + 1 modif)")
            print(f"  - Résultat: {nb_modifs} ligne(s) dans le fichier final")

            if nb_modifs == 3:
                print(f"  ✅ SUCCÈS: La version la plus complète (test1.json) a été conservée !")
            elif nb_modifs == 2:
                print(f"  ⚠️  ATTENTION: La version avec moins de modifications (test2.json) a été conservée")
                print(f"     ou les modifications ont été fusionnées incorrectement")
            else:
                print(f"  ❓ RÉSULTAT INATTENDU: {nb_modifs} lignes trouvées")

        else:
            print(f"  ❌ Aucune ligne trouvée avec cet UID !")
            print(f"\n  UIDs présents dans le fichier:")
            print(df.select("uid").unique().head(10))
    else:
        print(f"❌ Fichier de sortie non trouvé: {output_file}")

except Exception as e:
    print(f"\n❌ ERREUR lors du traitement: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Restaurer les datasets originaux
    config.TRACKED_DATASETS = original_datasets

print("\n" + "=" * 80)
