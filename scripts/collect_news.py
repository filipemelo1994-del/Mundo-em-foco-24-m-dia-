#!/usr/bin/env python3
import json, os, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

NEWS="data/news.json"; OUT="requests/news"
FEEDS=[
 ("G1","https://g1.globo.com/rss/g1/tecnologia/"),
 ("G1","https://g1.globo.com/rss/g1/ciencia-e-saude/"),
 ("Agência Brasil","https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"),
]
POLITICAL=("eleição","eleicoes","eleições","candidato","presidente","governo","ministro","deputado","senador","lula","bolsonaro","partido","congresso","stf","tse")
def slug(s):
 s=s.lower(); s=re.sub(r"[^a-z0-9]+","-",s.encode("ascii","ignore").decode()); return s.strip("-")[:90]
def txt(e,name):
 x=e.find(name); return (x.text or "").strip() if x is not None else ""
def image_url(item):
 for e in item.iter():
  tag=e.tag.lower()
  if tag.endswith("content") or tag.endswith("thumbnail") or tag.endswith("enclosure"):
   u=e.attrib.get("url","")
   typ=e.attrib.get("type","")
   if u and (typ.startswith("image/") or re.search(r"\.(jpe?g|png|webp)(\?|$)",u,re.I)): return u
 desc=txt(item,"description")
 m=re.search(r'<img[^>]+src=["\']([^"\']+)',desc,re.I)
 return m.group(1) if m else ""
def main():
 with open(NEWS,encoding="utf-8") as f: existing=json.load(f)
 seen_urls={s.get("url") for n in existing for s in (n.get("sources") or [])}
 seen_titles={re.sub(r"\W+"," ",str(n.get("title","")).lower()).strip() for n in existing}
 cand=[]
 for source,url in FEEDS:
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 MundoEmFoco24/1.0"})
   with urllib.request.urlopen(req,timeout=25) as r: root=ET.fromstring(r.read())
  except Exception as e:
   print("feed falhou",source,url,e); continue
  for item in root.findall(".//item"):
   title=txt(item,"title"); link=txt(item,"link"); desc=re.sub(r"<[^>]+>"," ",txt(item,"description"))
   desc=re.sub(r"\s+"," ",desc).strip()
   low=(title+" "+desc).lower()
   if not title or not link or link in seen_urls: continue
   if any(k in low for k in POLITICAL): continue
   norm=re.sub(r"\W+"," ",title.lower()).strip()
   if norm in seen_titles: continue
   img=image_url(item)
   if not img: continue
   try: dt=parsedate_to_datetime(txt(item,"pubDate"))
   except: dt=datetime.now(timezone.utc)
   cand.append((dt,title,desc,link,img,source))
 if not cand:
  print("Nenhuma pauta nova segura com imagem."); return 0
 cand.sort(key=lambda x:x[0],reverse=True)
 dt,title,desc,link,img,source=cand[0]
 now=datetime.now()
 nid=slug(title)+"-"+now.strftime("%d-%m-%Y")
 summary=(desc[:320].rsplit(" ",1)[0]+"…") if len(desc)>320 else desc
 req={"id":nid,"published":now.isoformat(),"category":"BRASIL / MUNDO","title":title,"summary":summary,
      "location":"","date":now.strftime("%d %b %Y").upper(),"image":img,"sourceImage":img,
      "credit":source,"body":[summary],"sources":[{"name":source,"url":link}],
      "imageCandidates":[img]}
 os.makedirs(OUT,exist_ok=True)
 path=os.path.join(OUT,nid+".json")
 with open(path,"w",encoding="utf-8") as f: json.dump(req,f,ensure_ascii=False,indent=2); f.write("\n")
 print("PAUTA_CRIADA="+path)
if __name__=="__main__": main()
