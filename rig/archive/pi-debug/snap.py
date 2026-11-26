import os
import numpy as np
from PIL import Image
from lep import Stream, grab
st = Stream(); st.hard()
f = grab(st); st.close()
if f is None: raise SystemExit("no frame")
t = f.astype(np.float32) * 0.01 - 273.15
print("temperature C: min %.1f  max %.1f  mean %.1f" % (t.min(), t.max(), t.mean()))
v = (f.astype(np.float32) - f.min()) / max(1.0, float(f.max() - f.min()))
rgb = np.stack([np.clip(v*3,0,1), np.clip(v*3-1,0,1), np.clip(v*3-2,0,1)], -1)
os.makedirs(os.path.expanduser("~/out"), exist_ok=True)
Image.fromarray((rgb*255).astype(np.uint8)).resize((640,480), Image.NEAREST).save(os.path.expanduser("~/out/heat.png"))
print("saved ~/out/heat.png")
