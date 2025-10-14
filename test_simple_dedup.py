"""Test simple de déduplication sans Prefect."""
import json
import sys
from pathlib import Path

import polars as pl

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import DATA_DIR, DIST_DIR, DECP_FORMAT_2022
from tasks.get import json_stream_to_parquet
from tasks.clean import clean_decp
from tasks.transform import concat_decp_json

print("=" * 80)
print("TEST DE DÉDUPLICATION DES UID (version simplifiée)")
print("=" * 80)

# Analyser les fichiers sources
print("\n🔍 Analyse des fichiers sources :")
print("\ntest1.json :")
with open(DATA_DIR / "test1.json", "r") as f:
    data1 = json.load(f)
    marche1 = data1["marches"]["marche"][0]
    print(f"  - ID marché: {marche1['id']}")
    print(f"  - Acheteur ID: {marche1['acheteur']['id']}")
    uid_attendu = f"{marche1['acheteur']['id']}{marche1['id']}"
    print(f"  - UID attendu: {uid_attendu}")
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

print("\n" + "=" * 80)
print("🚀 ÉTAPE 1 : Parsing des fichiers JSON")
print("=" * 80)

# Créer le dossier de sortie
output_dir = DIST_DIR / "test_get"
output_dir.mkdir(exist_ok=True, parents=True)

# Parser les deux fichiers
dfs = []
for filename in ["test1.json", "test2.json"]:
    print(f"\n📄 Traitement de {filename}...")
    url = str(DATA_DIR / filename)
    output_path = output_dir / filename.replace(".json", "")

    fields, decp_format = json_stream_to_parquet(url, output_path, [DECP_FORMAT_2022])

    # Charger le parquet
    lf = pl.scan_parquet(output_path.with_suffix(".parquet"))

    # Nettoyer
    lf = clean_decp(lf, decp_format)
    df = lf.collect(engine="streaming")

    print(f"  ✅ {df.height} lignes générées")
    print(f"  📊 UIDs uniques: {df.select('uid').n_unique()}")

    # Afficher les lignes pour ce fichier
    print(f"  Lignes avec UID={uid_attendu}:")
    result = df.filter(pl.col("uid") == uid_attendu)
    for row in result.iter_rows(named=True):
        print(f"    - modification_id={row.get('modification_id')}, "
              f"montant={row.get('montant')}, "
              f"dateNotification={row.get('dateNotification')}")

    dfs.append(df)

print("\n" + "=" * 80)
print("🚀 ÉTAPE 2 : Fusion et déduplication")
print("=" * 80)

print(f"\nAvant fusion:")
print(f"  - test1.json: {dfs[0].height} lignes")
print(f"  - test2.json: {dfs[1].height} lignes")
print(f"  - TOTAL: {dfs[0].height + dfs[1].height} lignes")

# Concaténer
df_final = concat_decp_json(dfs)

print(f"\nAprès concat_decp_json (déduplication par uid+titulaire_id+modification_id):")
print(f"  - Lignes restantes: {df_final.height}")
print(f"  - UIDs uniques: {df_final.select('uid').n_unique()}")

print("\n" + "=" * 80)
print("📊 RÉSULTATS FINAUX")
print("=" * 80)

result = df_final.filter(pl.col("uid") == uid_attendu)
print(f"\nNombre de lignes pour UID={uid_attendu}: {result.height}")

if result.height > 0:
    print(f"\nDétail des lignes :")
    for row in result.sort("modification_id").iter_rows(named=True):
        print(f"  - modification_id={row.get('modification_id')}, "
              f"montant={row.get('montant')}, "
              f"dateNotification={row.get('dateNotification')}, "
              f"donneesActuelles={row.get('donneesActuelles')}")

    print(f"\n🔍 Vérification :")
    print(f"  - test1.json avait 2 modifications → 3 lignes attendues (initial + 2 modifs)")
    print(f"  - test2.json avait 1 modification → 2 lignes attendues (initial + 1 modif)")
    print(f"  - Après déduplication: {result.height} ligne(s)")

    if result.height == 3:
        print(f"  ✅ SUCCÈS: La version la plus complète (test1.json) a été conservée !")
    elif result.height == 2:
        print(f"  ⚠️  Version avec moins de modifications conservée (test2.json)")
    else:
        print(f"  ❓ RÉSULTAT INATTENDU: {result.height} lignes")

print("\n" + "=" * 80)
