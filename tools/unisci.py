"""Unisce le foto dei vari gruppi e aggiorna il catalogo."""
import json, glob, os, shutil, sys
ver = int(sys.argv[1]) if len(sys.argv) > 1 else 2
rep = {}
for f in glob.glob('out/**/report_*.json', recursive=True):
    rep.update(json.load(open(f)))
n = 0
for f in glob.glob('out/**/img/*.webp', recursive=True):
    shutil.copy(f, 'img/' + os.path.basename(f)); n += 1
cat = json.load(open('catalogo.json'))
for r in cat:
    if r[1] in rep and rep[r[1]].get('scontornata') is not None:
        r[6] = ver
    elif not os.path.exists('img/' + r[1] + '.webp'):
        r[6] = 0
json.dump(cat, open('catalogo.json', 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(rep, open('tools/report.json', 'w'), ensure_ascii=False, indent=0)
mancanti = [[r[1], r[2]] for r in cat if not r[6]]
json.dump(mancanti, open('tools/mancanti.json', 'w'), ensure_ascii=False, indent=0)
print('foto nuove', n, 'con foto', sum(1 for r in cat if r[6]), 'mancanti', len(mancanti))
