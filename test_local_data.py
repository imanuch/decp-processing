#!/usr/bin/env python3
"""
Script pour tester le traitement avec un fichier JSON local.
Usage: python test_local_data.py /chemin/vers/votre/fichier.json
"""

import sys
from pathlib import Path

# Ajouter le répertoire src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import polars as pl
from config import DECP_FORMAT_2019, DECP_FORMAT_2022, DIST_DIR
from tasks.get import json_stream_to_parquet
from tasks.clean import clean_decp
from tasks.transform import process_modifications, explode_titulaires
from tasks.enrich import enrich_from_sirene


def print_stats(df, step_name):
    """Affiche les statistiques d'un DataFrame à une étape donnée."""
    if isinstance(df, pl.LazyFrame):
        count = df.select(pl.len()).collect().item()
    else:
        count = len(df)

    # Compter les nulls dans les colonnes importantes
    if isinstance(df, pl.LazyFrame):
        df_collected = df.collect()
    else:
        df_collected = df

    null_stats = {}
    for col in ["montant", "dureeMois", "titulaire_id", "acheteur_id"]:
        if col in df_collected.columns:
            null_count = df_collected[col].null_count()
            null_pct = (null_count / count * 100) if count > 0 else 0
            null_stats[col] = (null_count, null_pct)

    print(f"\n{'='*80}")
    print(f"📊 {step_name}")
    print(f"{'='*80}")
    print(f"   Nombre de lignes: {count:,}")

    if null_stats:
        print(f"   Valeurs NULL:")
        for col, (null_count, null_pct) in null_stats.items():
            print(f"      • {col}: {null_count:,} ({null_pct:.1f}%)")

    # Afficher un échantillon
    print(f"\n   Échantillon (5 premières lignes):")
    cols_to_show = [c for c in ["uid", "modification_id", "montant", "dureeMois",
                                  "dateNotification", "titulaire_id"]
                    if c in df_collected.columns]
    if cols_to_show:
        print(df_collected.select(cols_to_show).head(5))


def test_local_file(file_path: str):
    """Teste le traitement d'un fichier JSON local."""

    file_path = Path(file_path)

    if not file_path.exists():
        print(f"❌ Erreur: Le fichier {file_path} n'existe pas")
        return

    print(f"\n🚀 Début du test avec le fichier: {file_path}")
    print(f"   Taille du fichier: {file_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Créer le dossier de sortie
    output_path = DIST_DIR / "test_get"
    output_path.mkdir(parents=True, exist_ok=True)

    # ÉTAPE 1: Lecture du JSON et conversion en Parquet
    print("\n" + "="*80)
    print("ÉTAPE 1: Lecture du fichier JSON")
    print("="*80)

    try:
        # Essayer avec les deux formats DECP
        fields, decp_format = json_stream_to_parquet(
            str(file_path),
            output_path / "test.parquet",
            [DECP_FORMAT_2022, DECP_FORMAT_2019]
        )
        print(f"✅ Format détecté: {decp_format.label}")
        print(f"   Champs trouvés: {len(fields)}")
    except Exception as e:
        print(f"❌ Erreur lors de la lecture: {e}")
        return

    # Charger le parquet (le fichier est créé avec l'extension .parquet par sink_to_files)
    parquet_file = output_path / "test.parquet"
    if not parquet_file.exists():
        # Chercher le fichier créé
        import glob
        files = list((output_path).glob("*.parquet"))
        if files:
            parquet_file = files[0]
            print(f"   Fichier parquet trouvé: {parquet_file}")
        else:
            print(f"❌ Aucun fichier parquet trouvé dans {output_path}")
            return

    lf = pl.scan_parquet(parquet_file)
    print_stats(lf, "Après lecture JSON")

    # ÉTAPE 2: Nettoyage
    print("\n" + "="*80)
    print("ÉTAPE 2: Nettoyage des données")
    print("="*80)

    # NOTE: clean_decp() fait déjà process_modifications() et explode_titulaires()
    # donc on n'a pas besoin de les appeler séparément !
    lf_clean = clean_decp(lf, decp_format)
    print_stats(lf_clean, "Après clean_decp() - COMPLET")

    # DEBUG: Vérifier les titulaire_id vides AVANT le collect final
    print("\n[DEBUG] Vérification des titulaire_id vides AVANT collect():")
    empty_count = lf_clean.filter(
        (pl.col("titulaire_id").is_null()) | (pl.col("titulaire_id") == "")
    ).select(pl.len()).collect().item()
    print(f"   Nombre de lignes avec titulaire_id vide: {empty_count}")

    if empty_count > 0:
        print("   Exemples de lignes concernées:")
        empty_rows = lf_clean.filter(
            (pl.col("titulaire_id").is_null()) | (pl.col("titulaire_id") == "")
        ).select(["uid", "modification_id", "titulaire_id", "titulaire_typeIdentifiant", "dateNotification"]).limit(5).collect()
        print(empty_rows)

    # Collecter le résultat final
    df_final = lf_clean.collect()

    # DEBUG: Vérifier les titulaire_id vides APRÈS le collect final
    print("\n[DEBUG] Vérification des titulaire_id vides APRÈS collect():")
    empty_count_after = len(df_final.filter(
        (pl.col("titulaire_id").is_null()) | (pl.col("titulaire_id") == "")
    ))
    print(f"   Nombre de lignes avec titulaire_id vide: {empty_count_after}")

    if empty_count_after > 0:
        print("   Exemples de lignes concernées:")
        empty_rows_after = df_final.filter(
            (pl.col("titulaire_id").is_null()) | (pl.col("titulaire_id") == "")
        ).select(["uid", "modification_id", "titulaire_id", "titulaire_typeIdentifiant", "dateNotification"]).head(5)
        print(empty_rows_after)

    # RAPPORT FINAL
    print("\n" + "="*80)
    print("📋 RAPPORT FINAL")
    print("="*80)

    # Identifier les lignes avec des données manquantes
    for col in ["montant", "dureeMois"]:
        if col in df_final.columns:
            df_null = df_final.filter(pl.col(col).is_null())
            if len(df_null) > 0:
                print(f"\n⚠️  {len(df_null)} lignes avec {col}=null:")
                print(df_null.select(["uid", "modification_id", "dateNotification", col]).head(10))

    # Sauvegarder le résultat pour inspection
    output_csv = output_path / "test_result.csv"
    df_final.write_csv(output_csv)
    print(f"\n💾 Résultat sauvegardé dans: {output_csv}")

    print("\n✅ Test terminé!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_local_data.py /chemin/vers/votre/fichier.json")
        print("\nExemple:")
        print("  python test_local_data.py data/mon_fichier_decp.json")
        sys.exit(1)

    test_local_file(sys.argv[1])
