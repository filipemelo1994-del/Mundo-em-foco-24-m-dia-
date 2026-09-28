from PIL import Image,ImageDraw,ImageFont,ImageEnhance
import requests,io,os
OUT="public/carousel/nfl-rio-fotos-28-09-2026";os.makedirs(OUT,exist_ok=True)
photos=[
"https://static.clubs.nfl.com/image/upload/t_new_photo_album/t_lazy/f_auto/cowboys/zgsiwziqoogj7zquqlcq.jpg",
"https://static.clubs.nfl.com/image/upload/t_new_photo_album/t_lazy/f_auto/cowboys/quayc2v1g4yj1x3hqdzk.jpg",
"https://static.clubs.nfl.com/image/upload/t_new_photo_album/t_lazy/f_auto/cowboys/yxha2mr3cughk9bb7rbr.jpg",
"https://static.clubs.nfl.com/image/upload/t_new_photo_album/t_lazy/f_auto/cowboys/diktoxvzznsvsgopu0tw.jpg",
"https://static.clubs.nfl.com/image/upload/t_new_photo_album/t_lazy/f_auto/cowboys/biibyiuvaycnkxjhefid.jpg"]
texts=[("BRASIL 🇧🇷 × EUA 🇺🇸","NFL FAZ HISTÓRIA NO MARACANÃ"),("RIO VIROU PALCO DA NFL","RAVENS E COWBOYS DIANTE DO MARACANÃ"),("RAVENS 34 × 31 COWBOYS","UM JOGO DECIDIDO NO FIM"),("EMOÇÃO ATÉ O ÚLTIMO SEGUNDO","BALTIMORE GARANTIU A VITÓRIA POR TRÊS PONTOS"),("NFL NO BRASIL","UMA NOITE HISTÓRICA NO RIO DE JANEIRO")]
def ft(n,b=True):
 p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if b else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf";return ImageFont.truetype(p,n)
def wrap(d,s,f,x,y,w):
 cur=""; lines=[]
 for z in s.split():
  t=(cur+" "+z).strip()
  if d.textbbox((0,0),t,font=f)[2]<=w:cur=t
  else:lines.append(cur);cur=z
 if cur:lines.append(cur)
 for l in lines:d.text((x,y),l,font=f,fill="white",stroke_width=2,stroke_fill="black");y+=f.size+10
for i,(url,tx) in enumerate(zip(photos,texts),1):
 r=requests.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"});r.raise_for_status()
 src=Image.open(io.BytesIO(r.content)).convert("RGB")
 sw,sh=src.size; target=1080/1350
 if sw/sh>target:nw=int(sh*target);src=src.crop(((sw-nw)//2,0,(sw+nw)//2,sh))
 else:nh=int(sw/target);src=src.crop((0,(sh-nh)//2,sw,(sh+nh)//2))
 im=src.resize((1080,1350),Image.Resampling.LANCZOS);d=ImageDraw.Draw(im,"RGBA")
 d.rectangle((0,0,1080,210),fill=(4,12,25,205));d.rectangle((0,930,1080,1350),fill=(4,12,25,205))
 d.rectangle((0,0,1080,15),fill=(220,30,45,255));d.rectangle((0,15,540,26),fill=(0,150,70,255));d.rectangle((540,15,1080,26),fill=(45,80,180,255))
 d.text((55,55),"MUNDO EM FOCO 24",font=ft(40),fill="white");d.text((55,120),"NFL • RIO DE JANEIRO",font=ft(25),fill=(245,205,60))
 wrap(d,tx[0],ft(54),55,965,970);wrap(d,tx[1],ft(34),55,1100,970)
 d.text((55,1300),f"27 SET 2026  •  {i}/5  •  Foto: James D. Smith/Dallas Cowboys",font=ft(18),fill=(225,225,225))
 im.save(f"{OUT}/{i:02d}.jpg",quality=92)
