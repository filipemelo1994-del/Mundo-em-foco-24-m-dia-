#!/usr/bin/env python3
import hashlib,json,os,re,sys,urllib.parse,urllib.request
from datetime import datetime,timezone
QUEUE="data/publish-queue.json"; NEWS="data/news.json"; VALID="data/public-validation/latest.json"
ACCOUNT=os.environ["INSTAGRAM_ACCOUNT_ID"]; KEY=os.environ.get("WINDSOR_API_KEY",""); BASE=os.environ["PAGES_BASE"].rstrip("/")
if not KEY: raise SystemExit("WINDSOR_API_KEY ausente")
with open(QUEUE,encoding="utf-8") as f:q=json.load(f)
with open(NEWS,encoding="utf-8") as f:news=json.load(f)
with open(VALID,encoding="utf-8") as f:pvall=json.load(f)
byid={n.get("id"):n for n in news}
def political(n):
 s=" ".join(str(n.get(k,"")) for k in ("category","title","summary","body")).lower()
 return any(w in s for w in ("política","politica","eleição","eleicao","candidato","presidente","governador","prefeito","senador","deputado","lula","bolsonaro"))
eligible=[]
for nid,item in q.get("items",{}).items():
 n=byid.get(nid); pv=pvall.get(nid) or {}; av=item.get("art_validation") or {}; expected=item.get("art_sha256")
 if not n or political(n) or item.get("state")!="FEED_PENDENTE" or item.get("feed_media_id"): continue
 if not (item.get("portal") and item.get("feed_art") and av.get("passed") and pv.get("passed") and expected): continue
 if pv.get("expected_sha256")!=expected or pv.get("public_sha256")!=expected: continue
 eligible.append((n.get("published",""),nid,item,n,pv))
eligible.sort()
if not eligible:
 print("Nenhuma matéria validada elegível."); sys.exit(0)
_,nid,item,n,pv=eligible[0]; image_url=pv["url"]
with urllib.request.urlopen(image_url,timeout=30) as r:data=r.read()
if hashlib.sha256(data).hexdigest()!=item["art_sha256"]: raise SystemExit("SHA público divergente")
caption=(n.get("title","").strip()+"\n\n"+n.get("summary","").strip()).strip()
source=((n.get("sources") or [{}])[0].get("name") or "").strip()
if source: caption+="\n\nFonte: "+source
caption=(caption+"\n\n#MundoEmFoco24")[:2200]
payload=json.dumps({"account":ACCOUNT,"action":"create_image_post","params":{"image_url":image_url,"caption":caption}},ensure_ascii=False).encode()
url="https://connectors.windsor.ai/instagram/actions?api_key="+urllib.parse.quote(KEY,safe="")
req=urllib.request.Request(url,data=payload,headers={"Content-Type":"application/json"},method="POST")
try:
 with urllib.request.urlopen(req,timeout=90) as r: response=json.loads(r.read().decode())
except Exception as e:
 item["last_error"]="windsor publish failed: "+str(e)[:300]
 with open(QUEUE,"w",encoding="utf-8") as f:json.dump(q,f,ensure_ascii=False,indent=2);f.write("\n")
 raise
result=str(response.get("result","")); m=re.search(r"[Mm]edia id:\s*(\d+)",result)
if not m:
 item["last_error"]="Windsor respondeu sem media_id; bloqueado contra duplicação: "+result[:300]
 with open(QUEUE,"w",encoding="utf-8") as f:json.dump(q,f,ensure_ascii=False,indent=2);f.write("\n")
 raise SystemExit(item["last_error"])
item["feed_media_id"]=m.group(1); item.setdefault("attempts",{}); item["attempts"]["feed"]=item["attempts"].get("feed",0)+1
item["last_error"]=None; item["state"]="STORY_PENDENTE" if not item.get("story_media_id") else "STORY_OK"
q["updated_at"]=datetime.now(timezone.utc).isoformat()
with open(QUEUE,"w",encoding="utf-8") as f:json.dump(q,f,ensure_ascii=False,indent=2);f.write("\n")
print("Publicado "+nid+"; media_id="+m.group(1))
