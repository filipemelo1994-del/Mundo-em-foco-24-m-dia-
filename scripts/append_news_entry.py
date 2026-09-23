#!/usr/bin/env python3
import argparse,json,os,sys
p=argparse.ArgumentParser(); p.add_argument('--file',default='data/news.json'); p.add_argument('--entry',required=True); a=p.parse_args()
with open(a.file,encoding='utf-8') as f: data=json.load(f)
with open(a.entry,encoding='utf-8') as f: entry=json.load(f)
if not isinstance(data,list): sys.exit('news.json must be a list')
nid=str(entry.get('id','')).strip()
if not nid: sys.exit('entry id required')
if any(str(x.get('id'))==nid for x in data):
 print('already exists:',nid); sys.exit(0)
data.insert(0,entry)
with open(a.file,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
print('added:',nid)
