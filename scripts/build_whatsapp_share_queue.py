#!/usr/bin/env python3
"""Prepare WhatsApp channel share packs for recent articles confirmed on Instagram.
Never publishes to WhatsApp; a human must review and share the item in the app.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

NEWS = Path("data/news.json")
PUBLISH_QUEUE = Path("data/publish-queue.json")
OUT = Path("data/whatsapp-share-queue.json")
CHANNEL = "https://whatsapp.com/channel/0029Vb98zQ5AzNbvFs8pQm1x"
BASE = "https://filipemelo1994-del.github.io/Mundo-em-foco-24-m-dia-/"
CUTOFF = datetime.now(timezone.utc) - timedelta(hours=48)

def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None

news = json.loads(NEWS.read_text(encoding="utf-8"))
publish_queue = json.loads(PUBLISH_QUEUE.read_text(encoding="utf-8")).get("items", {})
try:
    share_queue = json.loads(OUT.read_text(encoding="utf-8"))
except FileNotFoundError:
    share_queue = {"version": 1, "channel_url": CHANNEL, "policy": {
        "auto_publish_to_channel": False,
        "require_manual_share_confirmation": True,
        "source_must_be_verified": True,
        "prevent_duplicates_by_news_id": True
    }, "items": {}}
share_queue.setdefault("items", {})
added = 0

for article in news:
    nid = str(article.get("id") or "")
    if not nid or nid in share_queue["items"] or article.get("published") is False:
        continue
    pub = parse_date(article.get("published"))
    status = publish_queue.get(nid, {})
    # Gate: article must be recent, on the portal, and have a confirmed Instagram media ID.
    if not pub or pub < CUTOFF or not status.get("portal") or status.get("state") != "FEED_OK" or not status.get("feed_media_id"):
        continue
    title = str(article.get("title") or "").strip()
    summary = str(article.get("summary") or "").strip()
    url = BASE + "noticia.html?id=" + nid
    source = str(article.get("credit") or "Mundo em Foco 24 — consulte as fontes na matéria").strip()
    share_text = f"📰 *{title}*\n\n{summary}\n\nLeia a matéria completa: {url}\n\n{source}\n\n📲 Siga o canal Mundo em Foco 24: {CHANNEL}"
    share_queue["items"][nid] = {
        "news_id": nid,
        "title": title,
        "summary": summary,
        "article_url": url,
        "image_url": article.get("image") or article.get("sourceImage") or "",
        "source_credit": source,
        "share_text": share_text,
        "state": "PRONTO_PARA_REVISAO_MANUAL",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "shared_at": None
    }
    added += 1

share_queue["updated_at"] = datetime.now(timezone.utc).isoformat()
OUT.write_text(json.dumps(share_queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"WhatsApp share queue: {added} new pack(s); {len(share_queue['items'])} total. No WhatsApp posts were sent.")
