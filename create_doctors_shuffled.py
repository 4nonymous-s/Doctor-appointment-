#!/usr/bin/env python3
"""Create `doctors_shuffled.csv` from backup `doctors.csv.bak` (preferred) or `doctors.csv`.

This writes a new file `doctors_shuffled.csv` and does not overwrite `doctors.csv`.
It replaces numeric/placeholder names and deterministically shuffles names per hospital (stable across runs).
"""
import csv
from pathlib import Path
import random
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
DOCTORS = ROOT / 'doctors.csv'
BACKUP = ROOT / 'doctors.csv.bak'
OUT = ROOT / 'doctors_shuffled.csv'

FIRST_NAMES = [
    'Priya','Amit','Suman','Neha','Karan','Pooja','Vikram','Anita','Ritu','Siddharth','Isha','Rahul','Meera','Kavita','Ramesh'
]
LAST_NAMES = [
    'Sharma','Singh','Patel','Iyer','Nair','Bose','Kumar','Verma','Reddy','Desai','Kapoor','Das','Menon','Chopra','Gupta'
]

NUMERIC_PATTERN = re.compile(r'^dr[\.\s]*\d+[-_]?\d*$', re.IGNORECASE)


def is_numeric_name(name: str) -> bool:
    if not name:
        return True
    n = name.strip()
    if NUMERIC_PATTERN.match(n.replace(' ', '').lower()):
        return True
    if n.lower().startswith('guest') or n.isdigit():
        return True
    return False


def make_name(seed: int) -> str:
    rnd = random.Random(seed)
    return f"Dr. {rnd.choice(FIRST_NAMES)} {rnd.choice(LAST_NAMES)}"


def main():
    src = BACKUP if BACKUP.exists() else DOCTORS
    if not src.exists():
        print('No source doctors CSV found (neither doctors.csv.bak nor doctors.csv)')
        return

    with src.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    groups = {}
    for r in rows:
        hid = r.get('hospital_id') or r.get('hospital') or ''
        try:
            hid_key = int(hid) if str(hid).isdigit() else str(hid)
        except Exception:
            hid_key = str(hid)
        groups.setdefault(hid_key, []).append(r)

    for hid, items in groups.items():
        names = [it.get('name') or '' for it in items]
        new_names = []
        for idx, nm in enumerate(names):
            if is_numeric_name(nm):
                seed = (hash(str(hid)) & 0xffffffff) + idx
                new_names.append(make_name(seed))
            else:
                new_names.append(nm)

        # deterministic shuffle
        rnd = random.Random((hash(str(hid)) & 0xffffffff))
        rnd.shuffle(new_names)

        for it, nm in zip(items, new_names):
            it['name'] = nm

    # write to new file
    with OUT.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'Wrote {len(rows)} rows to {OUT} (source: {src})')


if __name__ == '__main__':
    main()
