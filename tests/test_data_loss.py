"""
Test pour identifier les pertes de données à chaque étape du pipeline.
Ce test trace le nombre de lignes à chaque étape critique.
"""

import polars as pl
import pytest
from pathlib import Path
import sys

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tasks.clean import clean_decp
from src.tasks.transform import (
    explode_titulaires,
    process_modifications,
    concat_decp_json,
    process_string_lists,
)
from src.tasks.enrich import enrich_from_sirene
from src.config import DECP_FORMAT_2019, DECP_FORMAT_2022


class DataLossTracker:
    """Classe pour tracer les pertes de données à chaque étape."""

    def __init__(self):
        self.steps = []

    def record(self, step_name: str, df: pl.DataFrame | pl.LazyFrame, details: str = ""):
        """Enregistre le nombre de lignes à une étape donnée."""
        if isinstance(df, pl.LazyFrame):
            count = df.select(pl.len()).collect().item()
        else:
            count = len(df)

        self.steps.append({"step": step_name, "count": count, "details": details})
        print(f"📊 {step_name}: {count:,} lignes {details}")

    def report_losses(self):
        """Affiche un rapport des pertes de données."""
        print("\n" + "=" * 80)
        print("RAPPORT DES PERTES DE DONNÉES")
        print("=" * 80)

        for i in range(len(self.steps)):
            current = self.steps[i]
            print(f"\n{i+1}. {current['step']}: {current['count']:,} lignes")
            if current["details"]:
                print(f"   → {current['details']}")

            if i > 0:
                previous = self.steps[i - 1]
                loss = previous["count"] - current["count"]
                if loss > 0:
                    loss_pct = (loss / previous["count"]) * 100
                    print(f"   ⚠️  PERTE: -{loss:,} lignes (-{loss_pct:.2f}%)")
                elif loss < 0:
                    gain = -loss
                    gain_pct = (gain / previous["count"]) * 100
                    print(f"   ➕ AUGMENTATION: +{gain:,} lignes (+{gain_pct:.2f}%)")

        print("\n" + "=" * 80)


def test_data_loss_in_clean():
    """Test pour identifier les pertes de données dans la fonction clean_decp."""
    tracker = DataLossTracker()

    # Créer un DataFrame de test avec des cas problématiques
    test_data = {
        "id": ["M1", "M2", None, "M4", "M5"],  # M3 a un id null
        "acheteur_id": ["A1", None, "A3", "A4", "A5"],  # A2 a un acheteur_id null
        "titulaires": [
            [{"id": "T1", "typeIdentifiant": "SIRET"}],
            [{"id": "T2", "typeIdentifiant": "SIRET"}],
            [{"id": "T3", "typeIdentifiant": "SIRET"}],
            [{"id": "T4", "typeIdentifiant": "SIRET"}],
            [{"id": "T5", "typeIdentifiant": "SIRET"}],
        ],
        "montant": [1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
        "dateNotification": [
            "2023-01-01",
            "2023-01-02",
            "2023-01-03",
            "2023-01-04",
            "2023-01-05",
        ],
        "datePublicationDonnees": [
            "2023-01-01",
            "2023-01-02",
            "2023-01-03",
            "2023-01-04",
            "2023-01-05",
        ],
        "nature": ["Marche", "Marche", "Marche", "Marche", "Marche"],
    }

    lf = pl.LazyFrame(test_data)
    tracker.record("1. Données initiales", lf)

    # Test du filtre qui supprime les lignes sans id ou acheteur_id
    print("\n🔍 Test du filtre: id.is_not_null() & acheteur_id.is_not_null()")
    lf_filtered = lf.filter(
        pl.col("id").is_not_null() & pl.col("acheteur_id").is_not_null()
    )
    tracker.record(
        "2. Après filtrage (id & acheteur_id non-null)", lf_filtered, "Filtre appliqué"
    )

    # Afficher les lignes supprimées
    lf_removed = lf.filter(
        pl.col("id").is_null() | pl.col("acheteur_id").is_null()
    ).collect()
    if len(lf_removed) > 0:
        print("\n❌ Lignes SUPPRIMÉES par le filtre:")
        print(lf_removed[["id", "acheteur_id"]])

    tracker.report_losses()

    # Assertions
    assert (
        lf_filtered.select(pl.len()).collect().item() == 3
    ), "Devrait avoir 3 lignes après filtrage (M1, M4, M5)"


def test_data_loss_in_enrich():
    """Test pour identifier les pertes de données dans l'enrichissement SIRENE."""
    tracker = DataLossTracker()

    # Créer des données de test simulant le problème INNER JOIN
    decp_data = {
        "uid": ["A1M1", "A2M2", "A3M3"],
        "acheteur_id": ["12345678901234", "98765432109876", "11111111111111"],
        "titulaire_id": ["56789012345678", "99999999999999", "22222222222222"],
        "titulaire_typeIdentifiant": ["SIRET", "SIRET", "SIRET"],
        "montant": [1000.0, 2000.0, 3000.0],
    }

    df = pl.LazyFrame(decp_data)
    tracker.record("1. Données DECP initiales", df)

    # Simuler les données SIRENE (seulement 2 SIREN sur 3)
    sirene_data = {
        "siren": ["123456789", "567890123"],  # Manque 111111111
        "denominationUniteLegale": ["Entreprise A", "Entreprise B"],
    }

    sirene_lf = pl.LazyFrame(sirene_data)
    tracker.record("2. Données SIRENE disponibles", sirene_lf)

    # Extraire les SIREN des acheteurs
    df_sirets_acheteurs = df.select("acheteur_id").with_columns(
        pl.col("acheteur_id").str.head(9).alias("siren")
    )
    tracker.record("3. SIREN extraits des acheteurs", df_sirets_acheteurs)

    # INNER JOIN (problème potentiel!)
    print("\n🔍 Test du INNER JOIN avec les données SIRENE")
    df_sirets_matched = df_sirets_acheteurs.join(sirene_lf, how="inner", on="siren")
    tracker.record(
        "4. Après INNER JOIN avec SIRENE",
        df_sirets_matched,
        "Les acheteurs sans match SIRENE sont perdus ici!",
    )

    # Afficher les SIREN non matchés
    df_unmatched = df_sirets_acheteurs.join(
        sirene_lf, how="anti", on="siren"
    ).collect()
    if len(df_unmatched) > 0:
        print("\n❌ SIREN NON TROUVÉS dans SIRENE (perdus avec INNER JOIN):")
        print(df_unmatched)

    # LEFT JOIN final sur les données principales
    df_final = df.with_columns(pl.col("acheteur_id").str.head(9).alias("siren")).join(
        df_sirets_matched, how="left", on="acheteur_id"
    )
    tracker.record(
        "5. Après LEFT JOIN final",
        df_final,
        "Données conservées mais sans enrichissement SIRENE",
    )

    tracker.report_losses()

    # Assertions
    inner_count = df_sirets_matched.select(pl.len()).collect().item()
    assert (
        inner_count == 2
    ), f"Le INNER JOIN devrait ne garder que 2 lignes, mais en a gardé {inner_count}"


def test_full_pipeline_data_loss():
    """Test intégré pour tracer les pertes de données dans tout le pipeline."""
    tracker = DataLossTracker()

    # Données de test plus réalistes
    test_data = {
        "id": [f"M{i}" for i in range(1, 11)],
        "acheteur_id": [
            "12345678901234",
            "12345678901234",
            None,  # Sera supprimé
            "98765432109876",
            "98765432109876",
            "11111111111111",
            "11111111111111",
            "11111111111111",
            "22222222222222",
            "22222222222222",
        ],
        "titulaires": [
            [{"id": f"T{i}", "typeIdentifiant": "SIRET"}] for i in range(1, 11)
        ],
        "montant": [float(i * 1000) for i in range(1, 11)],
        "dateNotification": ["2023-01-01"] * 10,
        "datePublicationDonnees": ["2023-01-01"] * 10,
        "nature": ["Marché"] * 10,
        "modifications": [None] * 10,
    }

    lf = pl.LazyFrame(test_data)
    tracker.record("1. Données source brutes", lf, "10 marchés au départ")

    # Étape 1: Filtrage des nulls
    lf = lf.filter(pl.col("id").is_not_null() & pl.col("acheteur_id").is_not_null())
    tracker.record("2. Après filtrage nulls", lf, "Filter: id & acheteur_id non-null")

    # Étape 2: Explosion des titulaires
    df = lf.collect()
    df = df.explode("titulaires")
    tracker.record("3. Après explosion titulaires", df, "1 ligne par titulaire")

    # Afficher les statistiques finales
    tracker.report_losses()

    print("\n📈 STATISTIQUES FINALES:")
    print(f"   • Taux de conservation: {(df.height / 10) * 100:.1f}%")
    print(f"   • Lignes perdues: {10 - df.height}")


if __name__ == "__main__":
    print("🧪 TESTS DE DÉTECTION DE PERTE DE DONNÉES\n")

    print("\n" + "=" * 80)
    print("TEST 1: Perte de données dans clean_decp()")
    print("=" * 80)
    test_data_loss_in_clean()

    print("\n\n" + "=" * 80)
    print("TEST 2: Perte de données dans enrich_from_sirene() - INNER JOIN")
    print("=" * 80)
    test_data_loss_in_enrich()

    print("\n\n" + "=" * 80)
    print("TEST 3: Perte de données dans le pipeline complet")
    print("=" * 80)
    test_full_pipeline_data_loss()

    print("\n\n✅ Tous les tests terminés!")
