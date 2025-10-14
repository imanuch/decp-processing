#!/usr/bin/env python3
"""
Script pour identifier et corriger les problèmes dans les fichiers JSON DECP.
"""

import json
import sys
from pathlib import Path

def fix_titulaires(value):
    """Corrige la structure des titulaires."""
    if value is None:
        return None

    # Si c'est un float ou un nombre, retourner None
    if isinstance(value, (int, float)):
        return None

    # Si ce n'est pas une liste, essayer de la convertir
    if not isinstance(value, list):
        return None

    fixed_list = []
    for item in value:
        if isinstance(item, dict):
            # Structure correcte
            fixed_list.append(item)
        elif isinstance(item, list):
            # Liste imbriquée, aplatir
            for sub_item in item:
                if isinstance(sub_item, dict):
                    fixed_list.append(sub_item)

    return fixed_list if fixed_list else None

def fix_marche(marche, marche_index):
    """Corrige un marché."""
    uid = marche.get("uid", f"INDEX_{marche_index}")
    changes = []

    try:
        # Corriger titulaires
        if "titulaires" in marche:
            original = marche["titulaires"]
            fixed = fix_titulaires(original)
            if original != fixed:
                marche["titulaires"] = fixed
                changes.append(f"titulaires: {type(original).__name__} -> {type(fixed).__name__ if fixed else 'None'}")

        # Corriger modifications
        modifications = marche.get("modifications", [])

        # DIAGNOSTIC: Afficher le type si ce n'est pas le type attendu
        if not isinstance(modifications, (dict, list, type(None))):
            print(f"❌ MARCHÉ {uid} (index {marche_index}): modifications est de type {type(modifications).__name__} = {modifications}")
            changes.append(f"modifications invalide: {type(modifications).__name__}")
            # Marquer pour recherche de ligne
            marche['_problematic_uid'] = uid
            return changes

        # Si c'est un nombre ou None, pas de modifications
        if not isinstance(modifications, (dict, list)):
            modifications = []
        elif isinstance(modifications, dict):
            modifications = modifications.get("modification", [])
            if not isinstance(modifications, (dict, list)):
                modifications = []

        if isinstance(modifications, dict):
            modifications = [modifications]

        for mod_idx, mod in enumerate(modifications):
            if isinstance(mod, dict) and "modification" in mod:
                mod = mod["modification"]

            if isinstance(mod, dict) and "titulaires" in mod:
                original = mod["titulaires"]
                fixed = fix_titulaires(original)
                if original != fixed:
                    mod["titulaires"] = fixed
                    changes.append(f"modifications[{mod_idx}].titulaires: {type(original).__name__} -> {type(fixed).__name__ if fixed else 'None'}")

    except Exception as e:
        print(f"❌ ERREUR sur marché {uid}: {e}")
        print(f"   Type de modifications: {type(marche.get('modifications'))}")
        print(f"   Valeur: {marche.get('modifications')}")
        raise

    return changes

def find_line_number(file_path, uid):
    """Trouve le numéro de ligne contenant un UID dans le fichier JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if f'"uid": "{uid}"' in line or f'"uid":"{uid}"' in line:
                    return line_num
    except Exception:
        pass
    return None

def fix_json_file(input_path, output_path=None):
    """Corrige un fichier JSON."""
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_fixed.json"

    print(f"\n{'='*80}")
    print(f"🔧 CORRECTION DE {input_path.name}")
    print(f"{'='*80}\n")

    # Lire le fichier
    with open(input_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Erreur JSON: {e}")
            return False

    # Trouver les marchés
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
        print("⚠️  Aucun marché trouvé")
        return False

    if not isinstance(marches, list):
        marches = [marches]

    # Corriger les marchés
    total_changes = 0
    problematic_uids = []

    for idx, marche in enumerate(marches):
        uid = marche.get("uid", f"INDEX_{idx}")
        changes = fix_marche(marche, idx)

        if changes:
            total_changes += 1
            problematic_uids.append(uid)
            if total_changes <= 10:  # Afficher les 10 premiers
                print(f"✏️  Marché {idx} (UID: {uid}):")

                # Trouver le numéro de ligne dans le fichier
                line_num = find_line_number(input_path, uid)
                if line_num:
                    print(f"   📍 Ligne approximative: {line_num}")

                for change in changes:
                    print(f"   - {change}")

    if total_changes > 10:
        print(f"\n... et {total_changes - 10} autres marchés corrigés")

    # Sauvegarder
    if total_changes > 0:
        print(f"\n💾 Sauvegarde dans {output_path.name}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ {total_changes} marché(s) corrigé(s)")
        print(f"📄 Fichier original: {input_path}")
        print(f"📄 Fichier corrigé: {output_path}")

        # Sauvegarder la liste des UIDs problématiques
        uids_file = output_path.parent / f"{output_path.stem}_uids.txt"
        with open(uids_file, 'w') as f:
            f.write('\n'.join(problematic_uids))
        print(f"📄 Liste des UIDs: {uids_file}")

        return True
    else:
        print("✅ Aucune correction nécessaire")
        return False

if __name__ == "__main__":
    file_path = Path("data/decp-2025-07.json")

    if not file_path.exists():
        print(f"❌ Fichier introuvable: {file_path}")
        sys.exit(1)

    success = fix_json_file(file_path)

    print(f"\n{'='*80}")
    if success:
        print("✅ Correction terminée avec succès")
        print("\nPour utiliser le fichier corrigé, remplacez l'original par:")
        print(f"  mv {file_path.parent / f'{file_path.stem}_fixed.json'} {file_path}")
    else:
        print("ℹ️  Aucune correction appliquée")
    print(f"{'='*80}\n")
