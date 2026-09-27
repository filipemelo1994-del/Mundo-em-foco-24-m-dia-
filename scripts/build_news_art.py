#!/usr/bin/env python3
import argparse,json,os,re,sys,time
from io import BytesIO
import requests
from PIL import Image,ImageDraw,ImageFont,ImageOps

W,H=1080,1350
SW,SH=1080,1920
BLUE=(10,111,226); DARK=(5,31,63); WHITE=(255,255,255); GRAY=(215,225,238)
MAX=8*1024*1024
BOLD=["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
REG=["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]

def font(paths,size):
    for p in paths:
        if os.path.isfile(p): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def slug(s):
    return re.sub(r"-+","-",re.sub(r"[^A-Za-z0-9_-]","-",str(s).strip())).strip("-")

def download(urls):
    errors=[]
    for url in urls:
        if not url: continue
        for n in range(3):
            try:
                r=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0 MundoEmFoco24/1.0"})
                r.raise_for_status()
                im=Image.open(BytesIO(r.content)); im.load()
                return im,url
            except Exception as e:
                errors.append(f"{url} tentativa {n+1}: {e}")
                if n<2: time.sleep(2)
    raise RuntimeError(" | ".join(errors))

def cover(im):
    im=ImageOps.exif_transpose(im).convert("RGB")
    ratio=W/H; iw,ih=im.size
    if iw/ih>ratio:
        nw=int(ih*ratio); x=(iw-nw)//2; im=im.crop((x,0,x+nw,ih))
    else:
        nh=int(iw/ratio); y=max(0,int((ih-nh)*0.32)); im=im.crop((0,y,iw,y+nh))
    return im.resize((W,H),Image.Resampling.LANCZOS)

def wrap(draw,text,f,maxw):
    lines=[]; cur=""
    for word in text.split():
        test=(cur+" "+word).strip()
        if draw.textlength(test,font=f)<=maxw: cur=test
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    return lines


ROOT=os.path.dirname(os.path.dirname(__file__))
LOGO_FILE=os.path.join(ROOT,"assets","brand","logo-mundo-em-foco-24.webp")
TEMPLATE_FILE=os.path.join(ROOT,"assets","templates","mundo-em-foco24-publicacao.png")\nOFFICIAL_LAYOUT_FILE=os.path.join(ROOT,"assets","templates","layout-oficial-mundo-em-foco24.webp")

def brand_logo(max_w,max_h):
    """Carrega a logo oficial enviada pelo proprietário; nunca redesenha a marca."""
    try:
        im=Image.open(LOGO_FILE).convert("RGBA")
        im.thumbnail((max_w,max_h),Image.Resampling.LANCZOS)
        return im
    except Exception as e:
        print(f"AVISO: logo oficial indisponível: {e}",file=sys.stderr)
        return None

def render(photo,title,category,date,credit,summary="",story=False):
    # Teste fiel do layout mestre: nenhuma reconstrução da identidade.
    # O pipeline salva o retorno como JPEG compatível com Instagram.
    return Image.open(OFFICIAL_LAYOUT_FILE).convert("RGB")
