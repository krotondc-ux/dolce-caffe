"""Trova le foto prodotto in cui si vede una mano (MediaPipe) e scrive tools/mani.json."""
import json, os, glob, urllib.request
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task', '/tmp/hand.task')
det = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
    base_options=mpt.BaseOptions(model_asset_path='/tmp/hand.task'), num_hands=2,
    min_hand_detection_confidence=0.35, min_hand_presence_confidence=0.35))
from PIL import Image
import numpy as np
nomi = {r[1]: r[2] for r in json.load(open('catalogo.json'))}
out = []
fs = sorted(glob.glob('img/*.webp'))
for i, f in enumerate(fs):
    c = os.path.basename(f)[:-5]
    arr = np.asarray(Image.open(f).convert('RGB'))
    r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=arr))
    if r.hand_landmarks:
        sc = max(h[0].score for h in r.handedness)
        out.append([c, nomi.get(c, ''), round(sc, 2)])
    if i % 300 == 0: print(i, len(out), flush=True)
json.dump(out, open('tools/mani.json', 'w'), ensure_ascii=False, indent=0)
print('foto con mani', len(out))
