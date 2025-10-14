#!/usr/bin/env python3
"""
Script de diagnostic pour identifier les marchés avec des titulaires mal formés.
"""

import json
import sys
from pathlib import Path

def check_titulaires(marche, fichier, index_marche):
    """Vérifie la structure des titulaires d'un marché."""
    problems = []
    uid = marche.get("uid", "UNKNOWN")

    # Vérifier titulaires
    titulaires = marche.get("titulaires")
    if titulaires is not None:
        if not isinstance(titulaires, list):
            problems.append(f"  - titulaires n'est pas une liste: {type(titulaires)}")
        else:
            for i, tit in enumerate(titulaires):
                if not isinstance(tit, dict):
                    problems.append(f"  - titulaires[{i}] n'est pas un dict: {type(tit)} = {tit}")
                else:
                    # Vérifier la structure interne
                    if "titulaire" in tit:
                        # Format 2022
                        inner = tit.get("titulaire")
                        if not isinstance(inner, dict):
                            problems.append(f"  - titulaires[{i}]['titulaire'] n'est pas un dict: {type(inner)}")
                    elif "typeIdentifiant" not in tit and "id" not in tit:
                        problems.append(f"  - titulaires[{i}] n'a ni 'typeIdentifiant' ni 'id': {tit}")

    # Vérifier modifications
    modifications = marche.get("modifications", [])
    if isinstance(modifications, dict):
        modifications = modifications.get("modification", [])
    if isinstance(modifications, dict):
        modifications = [modifications]

    for mod_idx, mod in enumerate(modifications or []):
        if isinstance(mod, dict) and "modification" in mod:
            mod = mod["modification"]

        mod_titulaires = mod.get("titulaires") if isinstance(mod, dict) else None
        if mod_titulaires is not None:
            if not isinstance(mod_titulaires, list):
                problems.append(f"  - modifications[{mod_idx}].titulaires n'est pas une liste: {type(mod_titulaires)}")
            else:
                for i, tit in enumerate(mod_titulaires):
                    if not isinstance(tit, dict):
                        problems.append(f"  - modifications[{mod_idx}].titulaires[{i}] n'est pas un dict: {type(tit)} = {tit}")

    if problems:
        print(f"\n❌ MARCHE #{index_marche} - UID: {uid}")
        print(f"   Fichier: {fichier}")
        for problem in problems:
            print(problem)
        return True

    return False

def scan_json_file(filepath):
    """Scanne un fichier JSON pour trouver les problèmes."""
    print(f"\n📂 Scan de {filepath.name}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Erreur JSON: {e}")
            return

    # Essayer différentes structures
    marches = None
    if isinstance(data, dict):
        if "marches" in data:
            marches = data["marches"]
            if isinstance(marches, dict) and "marche" in marches:
                marches = marches["marche"]
        elif "marche" in data:
            marches = data["marche"]
    elif isinstance(data, list):
        marches = data

    if not marches:
        print("⚠️  Aucun marché trouvé dans ce fichier")
        return

    if not isinstance(marches, list):
        marches = [marches]

    problems_found = 0
    for idx, marche in enumerate(marches):
        if check_titulaires(marche, filepath.name, idx):
            problems_found += 1
            if problems_found >= 10:  # Limiter à 10 problèmes par fichier
                print(f"\n⚠️  ... et potentiellement plus de problèmes (limité à 10)")
                break

    if problems_found == 0:
        print("✅ Aucun problème détecté")
    else:
        print(f"\n⚠️  Total: {problems_found} marché(s) avec des problèmes")

if __name__ == "__main__":
    data_dir = Path("data")

    print("="*80)
    print("🔍 DIAGNOSTIC DES TITULAIRES DANS LES FICHIERS JSON")
    print("="*80)

    json_files = sorted(data_dir.glob("decp-*.json"))

    if not json_files:
        print("❌ Aucun fichier decp-*.json trouvé dans data/")
        sys.exit(1)

    print(f"\n📋 {len(json_files)} fichier(s) à scanner")

    for json_file in json_files:
        try:
            scan_json_file(json_file)
        except Exception as e:
            print(f"❌ Erreur lors du scan de {json_file.name}: {e}")

    print("\n" + "="*80)
    print("✅ Diagnostic terminé")
    print("="*80)
