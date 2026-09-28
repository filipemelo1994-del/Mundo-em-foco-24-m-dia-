from PIL import Image,ImageDraw,ImageFont
import os,requests,io
OUT="public/carousel/nfl-rio-brasil-eua-28-09-2026"; os.makedirs(OUT,exist_ok=True)
def font(sz,b=False):
 p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if b else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
 return ImageFont.truetype(p,sz)
def wrap(d,text,f,x,y,w,spacing=14):
 words=text.split(); lines=[]; cur=""
 for z in words:
  t=(cur+" "+z).strip()
  if d.textbbox((0,0),t,font=f)[2]<=w: cur=t
  else: lines.append(cur); cur=z
 if cur: lines.append(cur)
 for line in lines: d.text((x,y),line,font=f,fill="white"); y+=f.size+spacing
 return y
cards=[
("BRASIL × EUA","NFL FAZ HISTÓRIA NO MARACANÃ","O futebol americano ganhou o palco mais famoso do Brasil."),
("DUAS BANDEIRAS","DOIS HINOS, UM MARACANÃ","Péricles cantou o Hino Nacional Brasileiro. Kandace Lindsey interpretou o hino dos Estados Unidos."),
("JOGO HISTÓRICO","RAVENS 34 × 31 COWBOYS","Baltimore e Dallas fizeram o primeiro jogo de temporada regular da NFL no Rio de Janeiro."),
("DECISÃO NO FIM","EMOÇÃO ATÉ O ÚLTIMO SEGUNDO","O duelo terminou com vitória dos Ravens por três pontos, diante do público no Maracanã."),
("NFL NO BRASIL","UMA RELAÇÃO QUE CRESCE","O Brasil já reúne mais de 36 milhões de fãs da NFL. O Rio tem compromisso de receber ao menos três jogos em cinco anos.")
]
for i,(k,t,b) in enumerate(cards,1):
 im=Image.new("RGB",(1080,1350),(10,19,35)); d=ImageDraw.Draw(im)
 d.rectangle((0,0,1080,18),fill=(230,35,45)); d.rectangle((0,18,540,30),fill=(0,150,70)); d.rectangle((540,18,1080,30),fill=(45,85,180))
 d.text((70,70),"MUNDO EM FOCO",font=font(44,1),fill="white"); d.text((70,120),"24",font=font(32,1),fill=(230,35,45))
 d.text((70,235),k,font=font(45,1),fill=(245,200,55))
 y=wrap(d,t,font(76,1),70,330,940,18)
 y+=55; wrap(d,b,font(42),70,y,930,18)
 if i==1:
  d.rectangle((70,930,500,1160),fill=(0,145,70)); d.ellipse((205,965,365,1125),fill=(245,210,30))
  d.rectangle((580,930,1010,1160),fill="white")
  for yy in range(930,1160,46): d.rectangle((580,yy,1010,yy+23),fill=(190,30,45))
  d.rectangle((580,930,760,1040),fill=(40,70,150))
 if i==3:
  try:
   for x,url in [(120,"https://a.espncdn.com/i/teamlogos/nfl/500/bal.png"),(650,"https://a.espncdn.com/i/teamlogos/nfl/500/dal.png")]:
    r=requests.get(url,timeout=15); logo=Image.open(io.BytesIO(r.content)).convert("RGBA"); logo.thumbnail((300,300)); im.paste(logo,(x,930),logo)
  except: pass
 d.text((70,1280),f"28 SET 2026  •  {i}/5",font=font(28,1),fill=(180,190,205))
 im.save(f"{OUT}/{i:02d}.jpg",quality=94)
