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

def render(photo,title,category,date,credit,summary="",story=False):
    c=photo.convert("RGBA")\n    # Story usa a mesma identidade; o quadro 1080x1350 será centralizado em 1080x1920.
    # Padrão oficial: azul/branco, foto dominante e fumaça/degradê lateral.
    fog=Image.new("RGBA",(W,H),(0,0,0,0)); fp=fog.load()
    for x in range(W):
        edge=min(x,W-1-x); strength=max(0.0,1.0-edge/(W*0.18)); a=int(150*(strength**1.7))
        for y in range(142,930): fp[x,y]=(5,74,150,a)
    c.alpha_composite(fog)
    head=Image.new("RGBA",(W,176),(255,255,255,248)); c.alpha_composite(head,(0,0))
    d=ImageDraw.Draw(c)
    f_logo=font(BOLD,43); f_24=font(BOLD,64); f_tag=font(REG,15); f_cat=font(BOLD,25)
    f_title=font(BOLD,58); f_sum=font(REG,28); f_meta=font(REG,20)
    d.polygon([(0,0),(650,0),(590,176),(0,176)],fill=DARK)
    # Logo fixo Mundo em Foco 24: globo com meridianos/paralelos (sem texto improvisado).
    d.ellipse((32,25,142,135),fill=(8,96,190),outline=(55,205,255),width=4)
    d.ellipse((50,28,124,132),outline=WHITE,width=2)
    d.ellipse((72,28,102,132),outline=WHITE,width=2)
    d.arc((34,49,140,111),0,360,fill=WHITE,width=2)
    d.line((39,80,135,80),fill=WHITE,width=2)
    d.text((160,61),"MUNDO",font=f_logo,fill=WHITE,anchor="lm")
    d.text((160,108),"EM FOCO",font=f_logo,fill=WHITE,anchor="lm")
    d.text((382,83),"24",font=f_24,fill=(24,184,245),anchor="lm")
    d.text((160,145),"NOTÍCIAS DE VERDADE, SEM FRONTEIRAS",font=f_tag,fill=(220,235,250))
    if date: d.text((W-42,47),date.upper(),font=font(BOLD,22),fill=DARK,anchor="ra")
    region=(category or "NOTÍCIAS").upper()
    d.polygon([(W-310,82),(W,82),(W,150),(W-350,150)],fill=(4,48,105))
    d.text((W-155,116),region,font=f_cat,fill=WHITE,anchor="mm")
    panel_y=840
    panel=Image.new("RGBA",(W,H-panel_y),(4,30,67,246)); c.alpha_composite(panel,(0,panel_y))
    d=ImageDraw.Draw(c); cat=(category or "NOTÍCIAS").upper()
    cw=min(360,int(d.textlength(cat,font=f_cat)+70))
    d.polygon([(38,panel_y-42),(38+cw,panel_y-42),(38+cw-28,panel_y+18),(18,panel_y+18)],fill=(8,117,226))
    d.text((55,panel_y-12),cat,font=f_cat,fill=WHITE,anchor="lm")
    title=(title or "").strip().upper(); tf=f_title; lines=wrap(d,title,tf,W-100)
    while len(lines)>3 and tf.size>40:
        tf=font(BOLD,tf.size-3); lines=wrap(d,title,tf,W-100)
    y=panel_y+48; lh=tf.size+9
    for line in lines[:3]:
        d.text((48,y),line,font=tf,fill=WHITE,stroke_width=1,stroke_fill=(0,0,0,90)); y+=lh
    if summary:
        sf=f_sum; sl=wrap(d,summary.strip(),sf,W-120)[:2]; y+=8
        d.rectangle((48,y,54,y+min(72,len(sl)*36)),fill=(28,194,246))
        for line in sl:
            d.text((72,y),line,font=sf,fill=(235,243,252)); y+=36
    footer_y=H-112
    d.rectangle((0,footer_y,W,H),fill=(3,43,91))
    # Globo oficial estilizado no rodapé (mesma linguagem do cabeçalho).
    gx1,gy1,gx2,gy2=38,footer_y+25,92,footer_y+79
    d.ellipse((gx1,gy1,gx2,gy2),outline=WHITE,width=3)
    d.ellipse((gx1+12,gy1+2,gx2-12,gy2-2),outline=WHITE,width=2)
    d.arc((gx1+2,gy1+13,gx2-2,gy2-13),0,360,fill=WHITE,width=2)
    d.line((gx1+3,(gy1+gy2)//2,gx2-3,(gy1+gy2)//2),fill=WHITE,width=2)
    d.text((112,footer_y+25),"ACOMPANHE MAIS NOTÍCIAS EM NOSSO PORTAL",font=font(BOLD,15),fill=WHITE)
    d.text((112,footer_y+51),"www.mundoemfoco24.com.br",font=font(BOLD,21),fill=WHITE)
    # Assinatura oficial fixa — nunca substituir pelo nome da pauta.
    d.text((112,footer_y+79),"MUNDO EM FOCO 24",font=font(BOLD,18),fill=(27,197,247))
    # Elementos fixos da identidade aprovada.
    d.text((W-40,footer_y+37),"INFORMAÇÃO",font=font(BOLD,19),fill=WHITE,anchor="ra")
    d.text((W-40,footer_y+65),"EM TODO LUGAR",font=font(BOLD,19),fill=(27,197,247),anchor="ra")
    d.text((W-330,footer_y+82),"◎  f  ▶  ♪",font=font(BOLD,18),fill=WHITE,anchor="ra")
    if credit:
        txt=credit if credit.lower().startswith("foto:") else "Foto: "+credit
        d.text((48,footer_y-28),txt,font=f_meta,fill=(220,230,240))
    return c.convert("RGB")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--request-json"); ap.add_argument("--image",action="append",default=[])
    ap.add_argument("--title"); ap.add_argument("--category"); ap.add_argument("--date"); ap.add_argument("--credit"); ap.add_argument("--summary"); ap.add_argument("--id")
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
        final=render(cover(raw),title,a.category or p.get("category",""),a.date or p.get("date",""),a.credit or p.get("credit",""),a.summary or p.get("summary",""))
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
