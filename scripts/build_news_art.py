#!/usr/bin/env python3
import argparse,json,os,re,sys,time
from io import BytesIO
import requests
from PIL import Image,ImageDraw,ImageFont,ImageOps

W,H=1080,1350
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

def render(photo,title,category,date,credit):
    c=photo.convert("RGBA")
    # identidade do portal: cabeçalho branco + azul, foto dominante, degradê azul inferior
    top=Image.new("RGBA",(W,142),(255,255,255,248)); c.alpha_composite(top,(0,0))
    d=ImageDraw.Draw(c)
    f_logo=font(BOLD,42); f_24=font(BOLD,62); f_cat=font(BOLD,23); f_title=font(BOLD,66); f_meta=font(REG,25)
    d.ellipse((42,37,110,105),fill=BLUE)
    d.text((126,62),"MUNDO EM FOCO",font=f_logo,fill=(10,18,30),anchor="lm")
    x=126+d.textlength("MUNDO EM FOCO",font=f_logo)+16
    d.text((x,69),"24",font=f_24,fill=BLUE,anchor="lm")
    cat=(category or "NOTÍCIAS").upper()
    cw=d.textlength(cat,font=f_cat)+34
    d.rounded_rectangle((W-48-cw,49,W-48,95),radius=8,fill=BLUE)
    d.text((W-48-cw/2,72),cat,font=f_cat,fill=WHITE,anchor="mm")
    # separador azul da marca
    d.rectangle((0,136,W,142),fill=BLUE)

    gh=710
    grad=Image.new("RGBA",(1,gh))
    px=grad.load()
    for y in range(gh):
        t=y/(gh-1); a=int(8+(242-8)*(t*t))
        px[0,y]=(*DARK,a)
    c.alpha_composite(grad.resize((W,gh)),(0,H-gh))
    d=ImageDraw.Draw(c)
    title=(title or "").strip().upper()
    lines=wrap(d,title,f_title,W-112)
    if len(lines)>4:
        lines=lines[:4]
        if len(lines[-1])>3: lines[-1]=lines[-1].rstrip(" .") + "…"
    lh=78; meta=(34 if date else 0)+(34 if credit else 0)
    y=H-54-meta-lh*len(lines)
    d.rectangle((56,y-28,130,y-20),fill=BLUE)
    for line in lines:
        d.text((56,y),line,font=f_title,fill=WHITE,stroke_width=1,stroke_fill=(0,0,0,80)); y+=lh
    y+=8
    if date:
        d.text((56,y),date.upper(),font=f_meta,fill=GRAY); y+=34
    if credit:
        txt=credit if credit.lower().startswith("foto:") else "Foto: "+credit
        d.text((56,y),txt,font=f_meta,fill=GRAY)
    return c.convert("RGB")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--request-json"); ap.add_argument("--image",action="append",default=[])
    ap.add_argument("--title"); ap.add_argument("--category"); ap.add_argument("--date"); ap.add_argument("--credit"); ap.add_argument("--id")
    ap.add_argument("--out-dir",default="public/news-art"); ap.add_argument("--output-json")
    a=ap.parse_args(); p={}
    if a.request_json:
        with open(a.request_json,encoding="utf-8") as f: p=json.load(f)
    nid=a.id or p.get("id"); title=a.title or p.get("title")
    urls=a.image or p.get("imageCandidates") or [p.get("sourceImage") or p.get("image")]
    urls=[u for u in urls if u]
    if not nid or not title or not urls:
        print("ERRO: id, title e imagem são obrigatórios",file=sys.stderr); return 3
    sid=slug(nid)
    try: raw,used=download(urls)
    except Exception as e:
        result={"id":sid,"status":"media_error","error":str(e)}
        print("RESULT_JSON: "+json.dumps(result,ensure_ascii=False)); return 2
    try:
        final=render(cover(raw),title,a.category or p.get("category",""),a.date or p.get("date",""),a.credit or p.get("credit",""))
        os.makedirs(a.out_dir,exist_ok=True); path=os.path.join(a.out_dir,sid+".jpg")
        q=93
        while True:
            final.save(path,"JPEG",quality=q,optimize=True,progressive=True)
            if os.path.getsize(path)<=MAX or q<=65: break
            q-=4
        result={"id":sid,"status":"ok","path":path,"sourceImage":used,"width":W,"height":H,"bytes":os.path.getsize(path),"jpegQuality":q}
        if a.output_json:
            with open(a.output_json,"w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
        print("RESULT_JSON: "+json.dumps(result,ensure_ascii=False)); return 0
    except Exception as e:
        print("RENDER_ERROR:",e,file=sys.stderr); return 3
if __name__=="__main__": sys.exit(main())
