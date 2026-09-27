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
                from urllib.parse import urlsplit
                p=urlsplit(url)
                referer=f"{p.scheme}://{p.netloc}/"
                r=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36","Accept":"image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8","Referer":referer})
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
OFFICIAL_LAYOUT_FILE=os.path.join(ROOT,"assets","templates","layout-oficial-mundo-em-foco24.webp")

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
    return Image.open(OFFICIAL_LAYOUT_FILE).convert("RGB")

def render_story(photo,title,category,date,credit,summary=""):
    """Arte Story 1080x1920: foto sempre contida, sem crop, zoom ou distorção."""
    src=ImageOps.exif_transpose(photo).convert("RGB")
    c=Image.new("RGBA",(SW,SH),DARK+(255,))
    d=ImageDraw.Draw(c)

    # Fundo azul oficial em camadas.
    d.rectangle((0,0,SW,SH),fill=(4,31,66,255))
    d.rectangle((0,0,SW,190),fill=(255,255,255,250))
    d.polygon([(0,0),(650,0),(585,190),(0,190)],fill=DARK+(255,))

    f_logo=font(BOLD,43); f_24=font(BOLD,64); f_tag=font(REG,15)
    f_cat=font(BOLD,25); f_title=font(BOLD,56); f_sum=font(REG,27); f_meta=font(REG,20)

    # Cabeçalho com a mesma logo oficial usada no Feed.
    logo=brand_logo(500,150)
    if logo:
        c.alpha_composite(logo,(28,18))
        d=ImageDraw.Draw(c)
    if date: d.text((SW-42,50),date.upper(),font=font(BOLD,22),fill=DARK,anchor="ra")
    region=(category or "NOTÍCIAS").upper()
    d.polygon([(SW-310,88),(SW,88),(SW,156),(SW-350,156)],fill=(4,48,105))
    d.text((SW-155,122),region,font=f_cat,fill=WHITE,anchor="mm")

    # Janela da fotografia: contain preserva 100% do enquadramento e proporção.
    box=(48,238,SW-48,1125)
    bw,bh=box[2]-box[0],box[3]-box[1]
    fitted=ImageOps.contain(src,(bw,bh),Image.Resampling.LANCZOS)
    px=box[0]+(bw-fitted.width)//2; py=box[1]+(bh-fitted.height)//2
    d.rounded_rectangle(box,radius=22,fill=(7,72,145),outline=(38,181,241),width=4)
    c.alpha_composite(fitted.convert("RGBA"),(px,py))

    # Faixa editorial e texto abaixo da foto, sem cobrir elementos importantes.
    chip_y=1168
    cat=(category or "NOTÍCIAS").upper()
    cw=min(500,int(d.textlength(cat,font=f_cat)+80))
    d.rounded_rectangle((48,chip_y,48+cw,chip_y+62),radius=15,fill=(8,117,226))
    d.text((72,chip_y+31),cat,font=f_cat,fill=WHITE,anchor="lm")

    title=(title or "").strip().upper(); tf=f_title; lines=wrap(d,title,tf,SW-96)
    while len(lines)>4 and tf.size>38:
        tf=font(BOLD,tf.size-3); lines=wrap(d,title,tf,SW-96)
    y=chip_y+90; lh=tf.size+10
    for line in lines[:4]:
        d.text((48,y),line,font=tf,fill=WHITE); y+=lh

    if summary:
        sl=wrap(d,summary.strip(),f_sum,SW-130)[:3]
        y+=10
        d.rectangle((48,y,55,y+min(116,len(sl)*38)),fill=(28,194,246))
        for line in sl:
            d.text((76,y),line,font=f_sum,fill=(225,237,249)); y+=38

    footer_y=SH-170
    d.rectangle((0,footer_y,SW,SH),fill=(3,43,91))
    if credit:
        txt=credit if credit.lower().startswith("foto:") else "Foto: "+credit
        credit_lines=wrap(d,txt,f_meta,SW-96)[:2]
        cy=footer_y-58-(len(credit_lines)-1)*25
        for line in credit_lines:
            d.text((48,cy),line,font=f_meta,fill=(220,230,240)); cy+=25
    d.text((48,footer_y+35),"MUNDO EM FOCO 24",font=font(BOLD,28),fill=WHITE)
    d.text((48,footer_y+75),"INFORMAÇÃO EM TODO LUGAR",font=font(BOLD,21),fill=(27,197,247))
    d.text((48,footer_y+112),"www.mundoemfoco24.com.br",font=font(BOLD,20),fill=WHITE)
    d.text((SW-48,footer_y+74),"CONFIRA A MATÉRIA",font=font(BOLD,22),fill=WHITE,anchor="ra")
    d.text((SW-48,footer_y+108),"NO NOSSO FEED",font=font(BOLD,26),fill=(27,197,247),anchor="ra")
    return c.convert("RGB")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--request-json"); ap.add_argument("--image",action="append",default=[])
    ap.add_argument("--title"); ap.add_argument("--category"); ap.add_argument("--date"); ap.add_argument("--credit"); ap.add_argument("--summary"); ap.add_argument("--id")
    ap.add_argument("--out-dir",default="public/news-art"); ap.add_argument("--output-json"); ap.add_argument("--story",action="store_true")
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
        final=(render_story(raw,title,a.category or p.get("category",""),a.date or p.get("date",""),a.credit or p.get("credit",""),a.summary or p.get("summary","")) if a.story else render(cover(raw),title,a.category or p.get("category",""),a.date or p.get("date",""),a.credit or p.get("credit",""),a.summary or p.get("summary","")))
        os.makedirs(a.out_dir,exist_ok=True); path=os.path.join(a.out_dir,sid+".jpg")
        q=93
        while True:
            final.save(path,"JPEG",quality=q,optimize=True,progressive=True)
            if os.path.getsize(path)<=MAX or q<=65: break
            q-=4
        result={"id":sid,"status":"ok","path":path,"sourceImage":used,"width":SW if a.story else W,"height":SH if a.story else H,"bytes":os.path.getsize(path),"jpegQuality":q}
        if a.output_json:
            with open(a.output_json,"w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
        print("RESULT_JSON: "+json.dumps(result,ensure_ascii=False)); return 0
    except Exception as e:
        print("RENDER_ERROR:",e,file=sys.stderr); return 3
if __name__=="__main__": sys.exit(main())
