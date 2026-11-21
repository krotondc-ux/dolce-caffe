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
SECONDO = len(sys.argv) > 4 and sys.argv[4] == 'nome'
SOLO_OFF = len(sys.argv) > 4 and sys.argv[4] == 'off'
if SOLO_OFF:
    # rifa solo le foto prese da Open Food Facts, con lo scontorno piu prudente
    vecchi = json.load(open('tools/report.json'))
    catalogo = [r for r in catalogo if (vecchi.get(r[1], {}).get('fonte') or '').startswith('open')]
if SECONDO:
    # secondo giro: solo articoli ancora senza foto, ricerca per nome con controllo piu severo
    manc = {c for c, _ in json.load(open('tools/mancanti.json'))}
    vecchi = json.load(open('tools/report.json')) if os.path.exists('tools/report.json') else {}
    catalogo = [r for r in catalogo if r[1] in manc]
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


ESPANDI = {'DET.': 'detersivo ', 'AMM.': 'ammorbidente ', 'SAP.': 'sapone ', 'PAV.': 'pavimenti ', 'CONF.': 'confezione ',
           'SPAZZ.': 'spazzolino ', 'DENT.': 'dentifricio ', 'BISC.': 'biscotti ', 'CIOCC.': 'cioccolato ', 'D.G.': 'dolce gusto '}


def nome_lungo(nome):
    n = nome.upper()
    for k, v in ESPANDI.items():
        n = n.replace(k, v.upper())
    return re.sub(r'\s+', ' ', n).strip()


def da_web_nome(cod, nome, evita=''):
    try:
        from ddgs import DDGS
    except Exception:
        return None, None
    nl = nome_lungo(nome)
    pn = parole(nl)
    if len(pn) < 2:
        return None, None
    for q in (nl, nl + ' prodotto supermercato'):
        res = []
        for tent in range(3):
            try:
                res = DDGS().images(q, region='it-it', safesearch='moderate', max_results=15, backend=os.environ.get('BACKEND', 'auto')); break
            except Exception:
                time.sleep(4 + tent * 6)
        time.sleep(1.5 + random.random())
        cand = []
        for r in res:
            if evita and evita in (r.get('url') or ''):
                continue
            tl = ((r.get('title') or '') + ' ' + (r.get('url') or '')).lower()
            sc = sum(1 for w in pn if w in tl) / len(pn)
            try:
                alto = int(r.get('height') or 600)
            except Exception:
                alto = 600
            if sc >= 0.6 and alto >= 250:
                cand.append((sc, r))
        cand.sort(key=lambda x: -x[0])
        for sc, r in cand[:5]:
            try:
                return scarica(r.get('image'), 15), f'web:nome2:{sc:.2f}:{r.get("url","")[:120]}'
            except Exception:
                pass
    return None, None


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
        pieno = 0
        if bbox:
            ac = a.crop(bbox)
            pieno = sum(1 for v in ac.getdata() if v > 128) / (ac.size[0]*ac.size[1])
        # si scontorna solo se il prodotto resta intero e compatto
        if bbox and area > 0.15 and pieno > 0.62:
            im = cut.crop(bbox); scontornata = True
        else:
            scontornata = False
    except Exception:
        scontornata = False
    if not scontornata:
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
        # toglie i bordi bianchi o quasi bianchi intorno alla foto
        g = im.convert('L').point(lambda v: 0 if v > 236 else 255)
        b2 = g.getbbox()
        if b2 and (b2[2]-b2[0])*(b2[3]-b2[1]) > 0.2*im.size[0]*im.size[1]:
            im = im.crop(b2)
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
    if SECONDO:
        ev = (vecchi.get(cod, {}).get('fonte') or '').split(':', 3)[-1] if (vecchi.get(cod, {}).get('fonte') or '').startswith('web') else ''
        im, fonte = da_web_nome(cod, nome, ev)
    elif SOLO_OFF:
        im, fonte = da_off(cod)
    elif re.fullmatch(r'\d{8,14}', cod) and not cod.startswith('8000000'):
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
