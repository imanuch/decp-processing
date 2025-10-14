#!/usr/bin/env python3
"""
Script pour exécuter le flow DECP avec les données JSON locales.
Génère un fichier Excel avec toutes les données consolidées.
"""

import os
import sys

# Configurer la variable d'environnement pour pointer vers la config locale
os.environ["DATASETS_REFERENCE_FILEPATH"] = "data/source_datasets_all_local.json"

# Désactiver la publication sur data.gouv.fr
os.environ["DECP_PROCESSING_PUBLISH"] = "false"

# Ajouter le dossier src au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from flows import decp_processing

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 Lancement du traitement DECP avec les données locales")
    print("=" * 80)
    print("\nConfiguration:")
    print(f"  - Fichier de config: {os.environ['DATASETS_REFERENCE_FILEPATH']}")
    print(f"  - Publication: {os.environ.get('DECP_PROCESSING_PUBLISH', 'false')}")
    print(f"  - Format de sortie: CSV, Parquet")
    print("\n" + "=" * 80 + "\n")

    # Lancer le flow
    decp_processing()

    print("\n" + "=" * 80)
    print("✅ Traitement terminé!")
    print("=" * 80)
    print("\nFichiers générés dans le dossier dist/:")
    print("  - dist/decp.csv")
    print("  - dist/decp.parquet")
    print("=" * 80)
