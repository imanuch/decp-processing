"""Script pour tester le traitement de fichiers JSON locaux."""
import json
from pathlib import Path

from src.flows import decp_processing
from src.config import DATA_DIR

# Charger le fichier de configuration pour les fichiers locaux
with open(DATA_DIR / "source_datasets_local.json", "r") as f:
    local_datasets = json.load(f)

# Pour tester, on peut temporairement utiliser seulement les fichiers locaux
# En remplaçant TRACKED_DATASETS dans config.py
from src import config
config.TRACKED_DATASETS = local_datasets

print("🚀 Lancement du traitement avec les fichiers JSON locaux...")
print(f"Fichiers à traiter :")
for dataset in local_datasets:
    for resource in dataset.get("resources", []):
        print(f"  - {resource['title']}")

# Lancer le flow
decp_processing(enable_cache_removal=False)
