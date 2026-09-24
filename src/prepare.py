"""Audita un ZIP y divide por prefijo CxPy (agrupación provisional conservadora)."""
import argparse, csv, hashlib, io, json, re, zipfile
from pathlib import Path, PurePosixPath
from collections import Counter, defaultdict
from PIL import Image
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', required=True, type=Path)
    args = parser.parse_args()
    rows, seen = [], {}
    with zipfile.ZipFile(args.zip) as archive:
        by_hash = defaultdict(list)
        parent = {}
        def find(g):
            parent.setdefault(g, g)
            if parent[g] != g:
                parent[g] = find(parent[g])
            return parent[g]
        for name in sorted(archive.namelist()):
            p = PurePosixPath(name)
            if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
                by_hash[hashlib.sha256(archive.read(name)).hexdigest()].append(name)
        conflicts = {h: ns for h, ns in by_hash.items() if len({PurePosixPath(n).parent.name for n in ns}) > 1}
        for ns in by_hash.values():
            gs = [re.match(r'^(C\d+P\d+)', PurePosixPath(n).stem) for n in ns]
            if any(g is None for g in gs):
                raise ValueError('Nombre sin grupo CxPy; revisar dataset')
            gs = [g.group(1) for g in gs]
            for g in gs[1:]:
                parent[find(g)] = find(gs[0])
        for info in sorted(archive.infolist(), key=lambda i: i.filename):
            p = PurePosixPath(info.filename)
            if p.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                continue
            if p.is_absolute() or '..' in p.parts or len(p.parts) != 2:
                raise ValueError(f'Ruta inesperada: {p}')
            blob = archive.read(info)
            with Image.open(io.BytesIO(blob)) as im:
                im.verify()
            digest = hashlib.sha256(blob).hexdigest()
            label = p.parts[0]
            if digest in conflicts:
                continue
            if digest in seen:
                if seen[digest] != label:
                    raise ValueError('Duplicado con etiquetas contradictorias')
                continue
            seen[digest] = label
            match = re.match(r'^(C\d+P\d+)', p.stem)
            if not match:
                raise ValueError(f'Revisar agrupación del nombre: {p.name}')
            dest = ROOT / 'data/raw' / str(p)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            rows.append(dict(path=dest.relative_to(ROOT).as_posix(), label=label,
                             group=find(match.group(1)), sha256=digest))
    if not rows:
        raise ValueError('El ZIP no contiene imágenes')
    # Cinco folds: 60% entrenamiento, 20% validación, 20% prueba aproximadamente.
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    y, groups = [r['label'] for r in rows], [r['group'] for r in rows]
    for fold, (_, ids) in enumerate(splitter.split(rows, y, groups)):
        for i in ids:
            rows[i]['split'] = 'test' if fold == 0 else 'val' if fold == 1 else 'train'
    classes = sorted(set(y))
    for split in ['train', 'val', 'test']:
        if {r['label'] for r in rows if r['split'] == split} != set(classes):
            raise ValueError(f'Faltan clases en {split}; revisar división')
    out = ROOT / 'data/processed'
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'manifest.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    report = {'conflicting_files_excluded': sum(map(len, conflicts.values())), 'conflicts': list(conflicts.values()), 'same_label_duplicate_copies_removed': sum(len(ns)-1 for h,ns in by_hash.items() if h not in conflicts), 'images': len(rows), 'classes': dict(Counter(y)),
              'groups': len(set(groups)), 'grouping': 'Prefijo CxPy provisional: confirmar significado en fuente original',
              'splits': {s: dict(Counter(r['label'] for r in rows if r['split'] == s)) for s in ['train','val','test']}}
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports/dataset_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
