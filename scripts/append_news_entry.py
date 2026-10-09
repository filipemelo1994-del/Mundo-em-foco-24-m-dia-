#!/usr/bin/env python3
import argparse,json,os,sys,re
p=argparse.ArgumentParser(); p.add_argument('--file',default='data/news.json'); p.add_argument('--entry',required=True); a=p.parse_args()
with open(a.file,encoding='utf-8') as f: data=json.load(f)
with open(a.entry,encoding='utf-8') as f: entry=json.load(f)
if not isinstance(data,list): sys.exit('news.json must be a list')
nid=str(entry.get('id','')).strip()
if not nid: sys.exit('entry id required')
if any(str(x.get('id'))==nid for x in data):
 print('already exists:',nid); sys.exit(0)

# Gate editorial: não publicar pauta curta como reportagem completa.
body=entry.get('body')
if isinstance(body,str):
 paragraphs=[part.strip() for part in re.split(r'\n\s*\n',body) if part.strip()]
elif isinstance(body,list):
 paragraphs=[str(part).strip() for part in body if str(part).strip()]
else:
 paragraphs=[]
word_count=len(re.findall(r'\b[\wÀ-ÿ]+\b',' '.join(paragraphs)))
if len(paragraphs)<5 or word_count<350:
 sys.exit(f'EDITORIAL_REPROVADO: {nid}: {word_count} palavras em {len(paragraphs)} parágrafos; mínimo exigido: 350 palavras e 5 parágrafos. Complemente a apuração antes de publicar.')

data.insert(0,entry)
with open(a.file,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
print(f'added: {nid} ({word_count} palavras; {len(paragraphs)} parágrafos)')
