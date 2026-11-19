"""Foto prodotti Dolce Caffè.

Per ogni articolo del catalogo cerca la foto dal codice a barre, la scontorna e la
mette su sfondo bianco 600x600 con ombra leggera, tutte nello stesso stile.

Uso: python tools/foto.py SHARD TOTALE CARTELLA_USCITA
"""
import io, json, os, re, sys, time, random
import requests
from PIL import Image, ImageFilter, ImageOps

SHARD, TOT, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
os.makedirs(OUT + '/img', exist_ok=True)
UA = {'User-Agent': 'DolceCaffeCatalogo/1.0'}
H = requests.Session(); H.headers.update(UA)

catalogo = json.load(open('catalogo.json'))
mio = [r for i, r in enumerate(catalogo) if i % TOT == SHARD]
print(f'shard {SHARD}: {len(mio)} articoli', flush=True)

from rembg import remove, new_session
SESS = new_session('isnet-general-use')

OFF = ['https://world.openfoodfacts.org', 'https://world.openbeautyfacts.org',
       'https://world.openproductsfacts.org', 'https://world.openpetfoodfacts.org']


def scarica(url, timeout=20):
    r = H.get(url, timeout=timeout)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content))
    im.load()
    if min(im.size) < 140:
        raise ValueError('troppo piccola')
    return im


def da_off(cod):
    for host in OFF:
        try:
            r = H.get(f'{host}/api/v2/product/{cod}.json?fields=image_front_url,image_url,selected_images', timeout=15)
            if r.status_code == 429:
                time.sleep(20); continue
            if r.status_code != 200:
                continue
            p = r.json().get('product') or {}
            sel = (p.get('selected_images') or {}).get('front', {}).get('display', {})
            urls = [sel.get('it'), p.get('image_front_url'), p.get('image_url')] + list(sel.values())
            for u in urls:
                if not u:
                    continue
                full = re.sub(r'\.(\d+)\.\d+\.jpg$', r'.\1.full.jpg', u).replace('.400.jpg', '.full.jpg')
                for cand in (full, u):
                    try:
                        return scarica(cand), host.split('//')[1].split('.')[1] + ':' + cod
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            time.sleep(0.7)
    return None, None


def parole(t):
    return [w for w in re.sub(r'[^a-z0-9 ]', ' ', t.lower()).split() if len(w) > 2 and not w.isdigit()]


def da_web(cod, nome):
    try:
        from ddgs import DDGS
    except Exception:
        return None, None
    pn = parole(nome)
    for q in (cod, f'{nome} {cod}', nome):
        for tent in range(3):
            try:
                res = DDGS().images(q, region='it-it', safesearch='moderate', max_results=12)
                break
            except Exception as e:
                time.sleep(4 + tent * 6); res = []
        time.sleep(1.5 + random.random())
        cand = []
        for r in res:
            titolo = (r.get('title') or '') + ' ' + (r.get('url') or '')
            tl = titolo.lower()
            pt = sum(1 for w in pn if w in tl)
            ok_cod = cod in titolo or cod in (r.get('image') or '')
            sc = pt / max(1, len(pn)) + (1 if ok_cod else 0)
            if q == nome and sc < 0.5:
                continue
            if q == cod and not (ok_cod or sc >= 0.4):
                continue
            cand.append((sc, r))
        cand.sort(key=lambda x: -x[0])
        for sc, r in cand[:5]:
            for u in (r.get('image'), r.get('thumbnail')):
                if not u:
                    continue
                try:
                    return scarica(u, 15), f'web:{q == cod and "ean" or "nome"}:{sc:.2f}:{r.get("url","")[:120]}'
                except Exception:
                    pass
    return None, None


def impagina(im):
    """Scontorna, centra su bianco 600x600 con ombra morbida."""
    im = ImageOps.exif_transpose(im).convert('RGBA')
    if max(im.size) > 1400:
        im.thumbnail((1400, 1400))
    try:
        cut = remove(im, session=SESS)
        a = cut.getchannel('A')
        bbox = a.point(lambda v: 255 if v > 24 else 0).getbbox()
        area = 0 if not bbox else (bbox[2]-bbox[0])*(bbox[3]-bbox[1]) / (im.size[0]*im.size[1])
        if bbox and area > 0.06:
            im = cut.crop(bbox); scontornata = True
        else:
            scontornata = False
    except Exception:
        scontornata = False
    if not scontornata:
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    S, M = 600, 0.80
    k = min(S*M/im.width, S*M/im.height)
    im = im.resize((max(1, round(im.width*k)), max(1, round(im.height*k))), Image.LANCZOS)
    tela = Image.new('RGBA', (S, S), (255, 255, 255, 255))
    x, y = (S-im.width)//2, (S-im.height)//2 - 8
    if scontornata:
        ombra = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        from PIL import ImageDraw
        d = ImageDraw.Draw(ombra)
        w = im.width*0.42
        d.ellipse((S/2-w, y+im.height-10, S/2+w, y+im.height+14), fill=(28, 23, 20, 70))
        ombra = ombra.filter(ImageFilter.GaussianBlur(10))
        tela.alpha_composite(ombra)
    tela.alpha_composite(im, (x, y))
    return tela.convert('RGB'), scontornata


rep = {}
t0 = time.time()
for n, r in enumerate(mio):
    cod, nome = r[1], r[2]
    fonte = None; im = None
    if re.fullmatch(r'\d{8,14}', cod) and not cod.startswith('8000000'):
        im, fonte = da_off(cod)
        if im is None:
            im, fonte = da_web(cod, nome)
    else:
        fonte = 'codice-interno'
    if im is not None:
        try:
            out, sc = impagina(im)
            out.save(f'{OUT}/img/{cod}.webp', 'WEBP', quality=84, method=6)
            rep[cod] = {'fonte': fonte, 'scontornata': sc}
        except Exception as e:
            rep[cod] = {'fonte': None, 'errore': str(e)[:100]}
    else:
        rep[cod] = {'fonte': fonte}
    if n % 25 == 0:
        print(f'{n}/{len(mio)} {time.time()-t0:.0f}s trovate {sum(1 for v in rep.values() if v.get("scontornata") is not None)}', flush=True)
json.dump(rep, open(f'{OUT}/report_{SHARD}.json', 'w'), ensure_ascii=False)
print('fine', len(rep), flush=True)
