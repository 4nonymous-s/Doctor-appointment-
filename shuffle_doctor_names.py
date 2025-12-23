#!/usr/bin/env python3
"""Shuffle doctor names per hospital and replace numeric placeholder names.

Usage: run from repo root: python scripts/shuffle_doctor_names.py
This script creates a backup `doctors.csv.bak` before writing.
"""
import csv
from pathlib import Path
import random
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
DOCTORS = ROOT / 'doctors.csv'
BACKUP = ROOT / 'doctors.csv.bak'

FIRST_NAMES = [
    'Suman','Nitin','Amit','Priya','Anita','Rakesh','Sunita','Raj','Neha','Vikram',
    'Pooja','Manish','Karan','Divya','Ravi','Deepa','Kavita','Siddharth','Isha','Tanvi'
]
LAST_NAMES = [
    'Sharma','Singh','Patel','Gupta','Khan','Kapoor','Iyer','Reddy','Das','Mehta',
    'Joshi','Verma','Chopra','Nair','Bhat','Rao','Saxena','Mishra','Prasad','Kumar'
]

NUMERIC_PATTERN = re.compile(r'^dr[\.\s]*\d+[-_]?\d*$', re.IGNORECASE)


def is_numeric_name(name: str) -> bool:
    if not name:
        return True
    n = name.strip()
    # match patterns like "Dr. 1-1" or "Dr 12" or "doctor123"
    if NUMERIC_PATTERN.match(n.replace(' ', '').lower()):
        return True
    # also match guest-doctor or names that are exactly digits
    if n.lower().startswith('guest') or n.isdigit():
        return True
    # otherwise assume it's fine
    return False


def make_name(seed: int) -> str:
    random.seed(seed)
    fn = random.choice(FIRST_NAMES)
    ln = random.choice(LAST_NAMES)
    return f"Dr. {fn} {ln}"


def main():
    if not DOCTORS.exists():
        print('doctors.csv not found; nothing to do')
        return

    # backup
    shutil.copy2(DOCTORS, BACKUP)
    print(f'Backup written to {BACKUP}')

    with DOCTORS.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    # group rows by hospital_id
    groups = {}
    for r in rows:
        hid = r.get('hospital_id') or r.get('hospital') or r.get('hospitalId') or ''
        try:
            hid_key = int(hid) if str(hid).isdigit() else str(hid)
        except Exception:
            hid_key = str(hid)
        groups.setdefault(hid_key, []).append(r)

    # process each group: collect names, replace numeric placeholders, then shuffle
    for hid, items in groups.items():
        # collect current names
        names = [it.get('name') or '' for it in items]
        # replace names that are numeric/placeholder
        new_names = []
        for idx, nm in enumerate(names):
            if is_numeric_name(nm):
                # deterministic seed per hospital+index
                seed = (hash(str(hid)) & 0xffffffff) + idx
                new_names.append(make_name(seed))
            else:
                new_names.append(nm)

        # shuffle the names list deterministically per hospital so results are stable
        seed_shuffle = (hash(str(hid)) & 0xffffffff)
        rnd = random.Random(seed_shuffle)
        rnd.shuffle(new_names)

        # assign back shuffled names to items
        for it, nm in zip(items, new_names):
            it['name'] = nm

    # flatten rows in original order but with updated names
    out_rows = []
    for r in rows:
        hid = r.get('hospital_id') or r.get('hospital') or r.get('hospitalId') or ''
        try:
            hid_key = int(hid) if str(hid).isdigit() else str(hid)
        except Exception:
            hid_key = str(hid)
        # pop from groups[hid_key] sequentially
        updated = groups[hid_key].pop(0)
        out_rows.append(updated)

    # write back
    with DOCTORS.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f'Wrote {len(out_rows)} doctor rows with shuffled/replaced names to {DOCTORS}')


if __name__ == '__main__':
    main()
