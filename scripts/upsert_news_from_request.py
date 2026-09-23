#!/usr/bin/env python3
import argparse,json,os,sys
ap=argparse.ArgumentParser(); ap.add_argument('--request-json',required=True); ap.add_argument('--file',default='data/news.json'); a=ap.parse_args()
with open(a.request_json,encoding='utf-8') as f: req=json.load(f)
news=req.get('news')
if not news: sys.exit(0)
if not news.get('id') or not news.get('title'): sys.exit('news.id e news.title são obrigatórios')
with open(a.file,encoding='utf-8') as f: data=json.load(f)
if not isinstance(data,list): sys.exit('data/news.json não é lista')
idx=next((i for i,x in enumerate(data) if str(x.get('id'))==str(news['id'])),None)
if idx is None: data.insert(0,news)
else:
    merged=dict(data[idx]); merged.update(news); data[idx]=merged
with open(a.file,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
print(('inserida' if idx is None else 'atualizada')+': '+str(news['id']))
