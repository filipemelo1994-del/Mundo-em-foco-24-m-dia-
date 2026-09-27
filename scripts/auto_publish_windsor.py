#!/usr/bin/env python3
import hashlib,json,os,re,sys,urllib.parse,urllib.request
from datetime import datetime,timezone

QUEUE="data/publish-queue.json"; NEWS="data/news.json"; VALID="data/public-validation/latest.json"
ACCOUNT=os.environ["INSTAGRAM_ACCOUNT_ID"]; KEY=os.environ.get("WINDSOR_API_KEY","")
POLITICAL_TERMS=(
 "política","politica","eleição","eleicao","eleições","eleicoes","eleitoral","candidato","candidata",
 "presidente","governador","governadora","prefeito","prefeita","senador","senadora","deputado","deputada",
 "vereador","vereadora","ministro","ministra","partido","congresso","câmara","camara","senado","stf",
 "supremo tribunal federal","tse","tribunal superior eleitoral","governo federal","planalto",
 "lula","bolsonaro"
)
def is_political(n):
 text=" ".join(str(n.get(k,"")) for k in ("category","title","summary","body")).lower()
 return any(term in text for term in POLITICAL_TERMS)
def eligible_item(nid,item,n,pv):
 if not n or is_political(n): return False
 if item.get("state")!="FEED_PENDENTE" or item.get("feed_media_id"): return False
 image=(n.get("instagramImage") or "").strip()
 return bool(item.get("portal") and item.get("feed_art") and image.startswith("https://raw.githubusercontent.com/"))
def save(q):
 q["updated_at"]=datetime.now(timezone.utc).isoformat()
 with open(QUEUE,"w",encoding="utf-8") as f: json.dump(q,f,ensure_ascii=False,indent=2); f.write("\n")
def main():
 if not KEY: raise SystemExit("WINDSOR_API_KEY ausente")
 with open(QUEUE,encoding="utf-8") as f:q=json.load(f)
 with open(NEWS,encoding="utf-8") as f:news=json.load(f)
 with open(VALID,encoding="utf-8") as f:pvall=json.load(f)
 byid={n.get("id"):n for n in news}; eligible=[]
 target=(os.environ.get("PUBLISH_NEWS_ID") or "").strip()
 for nid,item in q.get("items",{}).items():
  if target and nid != target: continue
  n=byid.get(nid); pv=pvall.get(nid) or {}
  if eligible_item(nid,item,n,pv): eligible.append((n.get("published",""),nid,item,n,pv))
 eligible.sort(key=lambda x: str(x[0]))
 if not eligible:
  print("Nenhuma matéria elegível"+((" para "+target) if target else "")+"."); return 0
 _,nid,item,n,pv=eligible[0]; image_url=(n.get("instagramImage") or "").strip()
 try:
  # Confirma que a arte RAW existe e é realmente uma imagem antes de publicar.
  req_img=urllib.request.Request(image_url,headers={"User-Agent":"MundoEmFoco24/1.0"})
  with urllib.request.urlopen(req_img,timeout=30) as r:
   ctype=(r.headers.get("Content-Type") or "").lower(); data=r.read()
  if not data or not ctype.startswith("image/"): raise RuntimeError("Arte RAW inválida: "+ctype)
  caption=(n.get("title","").strip()+"\n\n"+n.get("summary","").strip()).strip()
  source=((n.get("sources") or [{}])[0].get("name") or "").strip()
  if source: caption+="\n\nFonte: "+source
  caption=(caption+"\n\n#MundoEmFoco24")[:2200]
  payload=json.dumps({"account":ACCOUNT,"action":"create_image_post","params":{"image_url":image_url,"caption":caption}},ensure_ascii=False).encode()
  url="https://connectors.windsor.ai/instagram/actions?api_key="+urllib.parse.quote(KEY,safe="")
  req=urllib.request.Request(url,data=payload,headers={"Content-Type":"application/json"},method="POST")
  with urllib.request.urlopen(req,timeout=90) as r: response=json.loads(r.read().decode())
  result=str(response.get("result","")); m=re.search(r"[Mm]edia id:\s*(\d+)",result)
  if not m: raise RuntimeError("Windsor respondeu sem media_id; bloqueado contra duplicação: "+result[:250])
 except Exception as e:
  item.setdefault("attempts",{}); item["attempts"]["feed"]=item["attempts"].get("feed",0)+1
  item["last_error"]=str(e)[:300]; save(q); raise
 item["feed_media_id"]=m.group(1); item.setdefault("attempts",{}); item["attempts"]["feed"]=item["attempts"].get("feed",0)+1
 item["last_error"]=None; item["state"]="FEED_OK"; save(q)
 print("Publicado "+nid+"; media_id="+m.group(1)); return 0
if __name__=="__main__": sys.exit(main())
