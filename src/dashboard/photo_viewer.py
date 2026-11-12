"""Full photo viewer with zoom in / zoom out / pan / rotate, used for shift-closing photos.

Streamlit's own full-screen button kept the thumbnail CSS of the page (cropped to 140-190 px, low resolution), so a
photo could not be read up close. This popup shows a sharp copy of the original and lets the user zoom with buttons,
the mouse wheel or two fingers, and drag (or scroll) to move around.
"""
from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

MAX_SIDE = 2200


@lru_cache(maxsize=24)
def _jpeg(path: str, mtime: float) -> str:
    from PIL import Image, ImageOps
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:  # pragma: no cover - optional
        pass
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def photo_data_uri(path: str | Path) -> str:
    p = Path(path)
    return 'data:image/jpeg;base64,' + _jpeg(str(p), p.stat().st_mtime)


VIEWER = """<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box} body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#fff}
.bar{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:6px 2px 8px}
.bar button{border:1px solid #e5e7eb;background:#fff;border-radius:10px;padding:7px 12px;font-size:15px;cursor:pointer;min-width:42px}
.bar button:active{background:#fee2e2}
.bar .pct{font-size:13px;color:#6b7280;margin-left:4px;min-width:48px}
.box{height:__H__px;overflow:auto;border:1px solid #e5e7eb;border-radius:12px;background:#f8fafc;touch-action:pan-x pan-y;
     cursor:grab;-webkit-overflow-scrolling:touch}
.box.drag{cursor:grabbing}
.stage{display:flex;align-items:flex-start;justify-content:center;min-width:100%;min-height:100%}
img{display:block;max-width:none;user-select:none;-webkit-user-drag:none;transform-origin:center center}
.hint{font-size:12px;color:#9ca3af;padding-top:6px}
</style></head><body>
<div class="bar">
  <button id="out" title="Thu nhỏ">−</button><button id="in" title="Phóng to">+</button>
  <button id="fit" title="Vừa khung">Vừa khung</button><button id="one" title="Kích thước thật">1:1</button>
  <button id="rot" title="Xoay 90°">⟳</button><span class="pct" id="pct"></span>
</div>
<div class="box" id="box"><div class="stage" id="stage"><img id="img" alt="Ảnh chứng từ" src="__SRC__"></div></div>
<div class="hint">Lăn chuột hoặc chụm/mở 2 ngón để phóng to – thu nhỏ; kéo để di chuyển.</div>
<script>
const box=document.getElementById('box'), img=document.getElementById('img'), stage=document.getElementById('stage'),
      pct=document.getElementById('pct');
let scale=1, fitScale=1, rot=0, nw=0, nh=0;
const MIN=0.1, MAX=8;
function dims(){ const r=rot%180!==0; return r?[nh,nw]:[nw,nh]; }
function apply(cx, cy){
  const [w,h]=dims();
  const oldW=stage.scrollWidth, oldH=stage.scrollHeight;
  const fx=cx===undefined?0.5:(box.scrollLeft+cx)/Math.max(oldW,1), fy=cy===undefined?0.5:(box.scrollTop+cy)/Math.max(oldH,1);
  img.style.width=(nw*scale)+'px'; img.style.height=(nh*scale)+'px';
  img.style.transform='rotate('+rot+'deg)';
  const W=w*scale, H=h*scale;
  stage.style.width=Math.max(W,box.clientWidth)+'px'; stage.style.height=Math.max(H,box.clientHeight)+'px';
  stage.style.alignItems='center';
  const offX=(nw*scale-W)/2, offY=(nh*scale-H)/2;  // rotation keeps the box size of the unrotated image
  img.style.margin=(-offY)+'px '+(-offX)+'px';
  box.scrollLeft=fx*stage.scrollWidth-(cx===undefined?box.clientWidth/2:cx);
  box.scrollTop=fy*stage.scrollHeight-(cy===undefined?box.clientHeight/2:cy);
  pct.textContent=Math.round(scale*100)+'%';
}
function zoomTo(s, cx, cy){ scale=Math.min(MAX,Math.max(MIN,s)); apply(cx,cy); }
function fit(){ const [w,h]=dims(); fitScale=Math.min((box.clientWidth-4)/w,(box.clientHeight-4)/h,1); zoomTo(fitScale); }
img.onload=()=>{ nw=img.naturalWidth; nh=img.naturalHeight; fit(); };
if(img.complete&&img.naturalWidth){ img.onload(); }
document.getElementById('in').onclick=()=>zoomTo(scale*1.4);
document.getElementById('out').onclick=()=>zoomTo(scale/1.4);
document.getElementById('fit').onclick=fit;
document.getElementById('one').onclick=()=>zoomTo(1);
document.getElementById('rot').onclick=()=>{ rot=(rot+90)%360; fit(); };
box.addEventListener('wheel',e=>{ e.preventDefault(); const r=box.getBoundingClientRect();
  zoomTo(scale*(e.deltaY<0?1.15:1/1.15), e.clientX-r.left, e.clientY-r.top); },{passive:false});
img.addEventListener('dblclick',e=>{ const r=box.getBoundingClientRect(); zoomTo(scale<fitScale*1.5?fitScale*2.5:fitScale, e.clientX-r.left, e.clientY-r.top); });
// drag to pan (mouse); touch uses native scrolling
let drag=null;
box.addEventListener('mousedown',e=>{ drag={x:e.clientX,y:e.clientY,l:box.scrollLeft,t:box.scrollTop}; box.classList.add('drag'); e.preventDefault(); });
window.addEventListener('mousemove',e=>{ if(!drag) return; box.scrollLeft=drag.l-(e.clientX-drag.x); box.scrollTop=drag.t-(e.clientY-drag.y); });
window.addEventListener('mouseup',()=>{ drag=null; box.classList.remove('drag'); });
// pinch with two fingers
let pinch=null;
function dist(t){ return Math.hypot(t[0].clientX-t[1].clientX, t[0].clientY-t[1].clientY); }
box.addEventListener('touchstart',e=>{ if(e.touches.length===2){ const r=box.getBoundingClientRect();
  pinch={d:dist(e.touches),s:scale,cx:(e.touches[0].clientX+e.touches[1].clientX)/2-r.left,cy:(e.touches[0].clientY+e.touches[1].clientY)/2-r.top}; e.preventDefault(); } },{passive:false});
box.addEventListener('touchmove',e=>{ if(pinch&&e.touches.length===2){ e.preventDefault(); zoomTo(pinch.s*dist(e.touches)/pinch.d, pinch.cx, pinch.cy); } },{passive:false});
box.addEventListener('touchend',e=>{ if(e.touches.length<2) pinch=null; });
window.addEventListener('resize',()=>apply());
</script></body></html>"""


def viewer_html(src: str, height: int = 560) -> str:
    return VIEWER.replace('__SRC__', src).replace('__H__', str(height))


@st.dialog('Xem ảnh', width='large')
def show_photo(path: str, caption: str = '') -> None:
    if caption:
        st.caption(caption)
    try:
        src = photo_data_uri(path)
    except (OSError, ValueError) as exc:
        st.error(f'Không mở được ảnh: {exc}')
        return
    components.html(viewer_html(src), height=640, scrolling=False)
