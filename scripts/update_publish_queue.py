#!/usr/bin/env python3
import argparse,json,os
from datetime import datetime,timezone

p=argparse.ArgumentParser()
p.add_argument("--queue",default="data/publish-queue.json")
p.add_argument("--news",default="data/news.json")
p.add_argument("--id")
p.add_argument("--state")
p.add_argument("--feed-media-id")
p.add_argument("--story-media-id")
p.add_argument("--error")
p.add_argument("--increment",choices=["feed","story"])
p.add_argument("--sync-news",action="store_true")
a=p.parse_args()

try:
    with open(a.queue,encoding="utf-8") as f:q=json.load(f)
except FileNotFoundError:
    q={"version":1,"updated_at":None,"items":{}}
q.setdefault("items",{})

if a.sync_news:
    with open(a.news,encoding="utf-8") as f: news=json.load(f)
    for n in news:
        nid=n.get("id")
        if not nid: continue
        item=q["items"].setdefault(nid,{"state":"ARTE_PENDENTE","portal":True,"feed_art":False,"story_art":False,"feed_media_id":None,"story_media_id":None,"attempts":{"feed":0,"story":0},"last_error":None})
        item["portal"]=True
        item["feed_art"]=bool(n.get("instagramImage"))
        if item["state"] in ("ARTE_PENDENTE","PORTAL_OK") and item["feed_art"]:
            item["state"]="FEED_PENDENTE"

if a.id:
    item=q["items"].setdefault(a.id,{"state":"PORTAL_PENDENTE","portal":False,"feed_art":False,"story_art":False,"feed_media_id":None,"story_media_id":None,"attempts":{"feed":0,"story":0},"last_error":None})
    if a.state:item["state"]=a.state
    if a.feed_media_id:item["feed_media_id"]=a.feed_media_id
    if a.story_media_id:item["story_media_id"]=a.story_media_id
    if a.error is not None:item["last_error"]=a.error or None
    if a.increment:
        item.setdefault("attempts",{}).setdefault(a.increment,0)
        item["attempts"][a.increment]+=1

q["updated_at"]=datetime.now(timezone.utc).isoformat()
os.makedirs(os.path.dirname(a.queue) or ".",exist_ok=True)
with open(a.queue,"w",encoding="utf-8") as f:
    json.dump(q,f,ensure_ascii=False,indent=2);f.write("\n")
