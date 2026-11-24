"""Candidati foto per gli articoli ancora senza immagine.

Per ogni articolo in tools/mancanti.json cerca per nome (e codice) su Bing e
DuckDuckGo, scarica fino a 4 foto diverse, le impagina come le altre e le salva
come out/cand/<codice>_<n>.webp. La scelta finale si fa a mano.

Uso: python tools/candidati.py SHARD TOTALE
"""
import io, json, os, re, sys, time, random, html
import requests
from PIL import Image, ImageFilter, ImageOps, ImageDraw

SHARD, TOT = int(sys.argv[1]), int(sys.argv[2])
OUT = 'out/cand'
os.makedirs(OUT, exist_ok=True)
H = requests.Session()
H.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                  'Accept-Language': 'it-IT,it;q=0.9'})

manc = json.load(open('tools/mancanti.json'))
mio = [r for i, r in enumerate(manc) if i % TOT == SHARD]
print(f'shard {SHARD}: {len(mio)} articoli', flush=True)

from rembg import remove, new_session
SESS = new_session('isnet-general-use')

ESPANDI = {'DET.': 'detersivo ', 'AMM.': 'ammorbidente ', 'SAP.': 'sapone ', 'PAV.': 'pavimenti ', 'CONF.': 'confettura ',
           'SPAZZ.': 'spazzolino ', 'D.G.': 'dolce gusto ', 'DG ': 'dolce gusto ', 'VAP ': 'vetro ', 'LAV.': 'lavaggi ',
           'AST.': 'astuccio ', 'TOV ': 'tovaglioli ', 'S/GLUTINE': 'senza glutine', 'S/C': 'senza coperchio',
           'S/E': '', 'PZ': ' pezzi', 'LIQU.': 'liquido ', 'CONC.': 'concentrato ', 'PROF.': 'profumatore '}


def query_da(nome):
    n = ' ' + nome.upper() + ' '
    for k, v in ESPANDI.items():
        n = n.replace(k, ' ' + v.upper() + ' ')
    n = re.sub(r'\b\d+X\d+\b', ' ', n)          # 33X24, 18X30: confezioni multiple
    n = re.sub(r'[^A-Z0-9À-Ù\' ]', ' ', n)
    return re.sub(r'\s+', ' ', n).strip().lower()


def bing(q):
    try:
        r = H.get('https://www.bing.com/images/search', params={'q': q, 'form': 'HDRSC2', 'first': 1, 'cc': 'it', 'setlang': 'it'}, timeout=20)
        out = []
        for m in re.findall(r'\sm="([^"]+)"', r.text):
            try:
                d = json.loads(html.unescape(m))
                if d.get('murl'):
                    out.append((d['murl'], d.get('turl'), d.get('t', '') + ' ' + d.get('purl', '')))
            except Exception:
                pass
        return out
    except Exception as e:
        print('bing', e, flush=True)
        return []


def ddg(q):
    try:
        from ddgs import DDGS
        res = DDGS().images(q, region='it-it', safesearch='moderate', max_results=15)
        return [(r.get('image'), r.get('thumbnail'), (r.get('title') or '') + ' ' + (r.get('url') or '')) for r in res]
    except Exception as e:
        print('ddg', e, flush=True)
        return []


def scarica(url, timeout=15):
    r = H.get(url, timeout=timeout)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)); im.load()
    if min(im.size) < 160:
        raise ValueError('piccola')
    return im


def impagina(im):
    im = ImageOps.exif_transpose(im).convert('RGBA')
    if max(im.size) > 1400:
        im.thumbnail((1400, 1400))
    sc = False
    try:
        cut = remove(im, session=SESS)
        a = cut.getchannel('A')
        bbox = a.point(lambda v: 255 if v > 24 else 0).getbbox()
        if bbox:
            area = (bbox[2]-bbox[0])*(bbox[3]-bbox[1]) / (im.size[0]*im.size[1])
            ac = a.crop(bbox)
            pieno = sum(1 for v in ac.getdata() if v > 128) / (ac.size[0]*ac.size[1])
            if area > 0.15 and pieno > 0.62:
                im = cut.crop(bbox); sc = True
    except Exception:
        pass
    if not sc:
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
        g = im.convert('L').point(lambda v: 0 if v > 236 else 255)
        b2 = g.getbbox()
        if b2 and (b2[2]-b2[0])*(b2[3]-b2[1]) > 0.2*im.size[0]*im.size[1]:
            im = im.crop(b2)
    S, M = 600, 0.80
    k = min(S*M/im.width, S*M/im.height)
    im = im.resize((max(1, round(im.width*k)), max(1, round(im.height*k))), Image.LANCZOS)
    tela = Image.new('RGBA', (S, S), (255, 255, 255, 255))
    x, y = (S-im.width)//2, (S-im.height)//2 - 8
    if sc:
        ombra = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        w = im.width*0.42
        ImageDraw.Draw(ombra).ellipse((S/2-w, y+im.height-10, S/2+w, y+im.height+14), fill=(28, 23, 20, 70))
        tela.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(10)))
    tela.alpha_composite(im, (x, y))
    return tela.convert('RGB')


rep = {}
for n, (cod, nome) in enumerate(mio):
    q = query_da(nome)
    risultati = []
    vero_ean = cod.isdigit() and len(cod) >= 8 and not cod.startswith('8000000')
    for qq in ([q, f'{q} {cod}'] if vero_ean else [q]):
        risultati += bing(qq); time.sleep(1 + random.random())
    if len(risultati) < 6:
        risultati += ddg(q); time.sleep(2)
    visti, presi, fonti = set(), 0, []
    for full, thumb, info in risultati:
        if presi >= 4:
            break
        if not full or full in visti:
            continue
        visti.add(full)
        im = None
        for u in (full, thumb):
            if not u:
                continue
            try:
                im = scarica(u); break
            except Exception:
                pass
        if im is None:
            continue
        try:
            impagina(im).save(f'{OUT}/{cod}_{presi}.webp', 'WEBP', quality=84, method=6)
            fonti.append(info[:160]); presi += 1
        except Exception:
            pass
    rep[cod] = {'nome': nome, 'query': q, 'candidati': presi, 'fonti': fonti}
    print(f'{n+1}/{len(mio)} {cod} {presi} candidati', flush=True)
json.dump(rep, open(f'{OUT}/cand_{SHARD}.json', 'w'), ensure_ascii=False)
print('fine', flush=True)
