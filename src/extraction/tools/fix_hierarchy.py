"""Fix hierarchy levels in extracted chunks files.

This tool shifts hierarchy levels down (e.g., level_3 → level_2) without
requiring re-extraction. Useful when chunks were extracted with wrong
toc_hierarchy_level config.

Usage:
    python -m extraction.tools.fix_hierarchy chunks.json --shift-down 1
    python -m extraction.tools.fix_hierarchy chunks.json --shift-down 2 --backup
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List


def shift_hierarchy_down(hierarchy: Dict[str, str], shift_amount: int, preserve_level_1: bool = True) -> Dict[str, str]:
    """Shift hierarchy levels down by shift_amount.

    Args:
        hierarchy: Dict with level_1, level_2, etc.
        shift_amount: Number of levels to shift down (e.g., 1 means level_3 → level_2)
        preserve_level_1: If True, keep level_1 unchanged and only shift higher levels

    Returns:
        New hierarchy dict with shifted levels
    """
    new_hierarchy = {}

    for key, value in hierarchy.items():
        if not key.startswith('level_'):
            continue

        try:
            current_level = int(key.split('_')[1])

            if preserve_level_1 and current_level == 1:
                new_hierarchy[key] = value
            else:
                new_level = current_level - shift_amount
                if new_level >= 1:
                    new_hierarchy[f'level_{new_level}'] = value
        except (IndexError, ValueError):
            continue

    return new_hierarchy


def fix_chunks_file(
    chunks_file: Path,
    shift_amount: int,
    backup: bool = True,
    dry_run: bool = False,
    preserve_level_1: bool = True,
) -> Dict:
    """Fix hierarchy in chunks file.

    Args:
        chunks_file: Path to chunks JSON file
        shift_amount: Number of levels to shift down
        backup: Whether to create backup before modifying
        dry_run: If True, only show what would change

    Returns:
        Dict with statistics
    """
    with open(chunks_file) as f:
        data = json.load(f)

    stats = {
        'total_chunks': len(data.get('chunks', [])),
        'chunks_modified': 0,
        'hierarchy_changes': [],
    }

    for chunk in data.get('chunks', []):
        old_hierarchy = chunk.get('hierarchy', {})
        if not old_hierarchy:
            continue

        new_hierarchy = shift_hierarchy_down(old_hierarchy, shift_amount, preserve_level_1)

        if new_hierarchy != old_hierarchy:
            stats['chunks_modified'] += 1

            if len(stats['hierarchy_changes']) < 5:
                stats['hierarchy_changes'].append({
                    'chunk_id': chunk.get('stable_id', 'unknown'),
                    'old': old_hierarchy,
                    'new': new_hierarchy,
                })

            if not dry_run:
                chunk['hierarchy'] = new_hierarchy

                if 'hierarchy_depth' in chunk:
                    chunk['hierarchy_depth'] = len([v for v in new_hierarchy.values() if v])

                if 'heading_path' in chunk:
                    path_parts = [v for v in new_hierarchy.values() if v]
                    chunk['heading_path'] = ' / '.join(path_parts)

    if not dry_run:
        if backup:
            backup_path = chunks_file.with_suffix('.json.backup')
            shutil.copy2(chunks_file, backup_path)
            stats['backup_path'] = str(backup_path)

        with open(chunks_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Fix hierarchy levels in chunks files"
    )
    parser.add_argument(
        'chunks_file',
        type=Path,
        help='Path to chunks JSON file',
    )
    parser.add_argument(
        '--shift-down',
        type=int,
        default=1,
        help='Number of levels to shift down (default: 1, e.g., level_3 → level_2)',
    )
    parser.add_argument(
        '--no-backup',
        action='store_false',
        dest='backup',
        default=True,
        help='Do not create backup before modifying',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would change without modifying file',
    )

    args = parser.parse_args()

    if not args.chunks_file.exists():
        print(f"Error: File not found: {args.chunks_file}")
        return 1

    if args.shift_down < 1:
        print(f"Error: --shift-down must be >= 1")
        return 1

    print(f"Processing: {args.chunks_file}")
    print(f"Shift amount: {args.shift_down} level{'s' if args.shift_down > 1 else ''} down")
    if args.dry_run:
        print("DRY RUN - No changes will be made")
    print()

    stats = fix_chunks_file(
        args.chunks_file,
        shift_amount=args.shift_down,
        backup=args.backup,
        dry_run=args.dry_run,
    )

    print(f"Results:")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Chunks modified: {stats['chunks_modified']}")

    if stats['hierarchy_changes']:
        print(f"\nExample changes:")
        for i, change in enumerate(stats['hierarchy_changes'], 1):
            print(f"\n  {i}. Chunk ID: {change['chunk_id']}")
            print(f"     Old: {change['old']}")
            print(f"     New: {change['new']}")

    if not args.dry_run:
        if args.backup and 'backup_path' in stats:
            print(f"\nBackup saved to: {stats['backup_path']}")
        print(f"\n✓ File updated: {args.chunks_file}")
    else:
        print(f"\nTo apply changes, run without --dry-run")

    return 0


if __name__ == '__main__':
    exit(main())
