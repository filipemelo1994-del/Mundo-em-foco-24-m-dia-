#!/usr/bin/env python3
import argparse, html, json, os, urllib.parse
p=argparse.ArgumentParser()
p.add_argument('--file',default='data/news.json')
p.add_argument('--out',default='share')
p.add_argument('--base',default='https://filipemelo1994-del.github.io/Mundo-em-foco-24-m-dia-/')
a=p.parse_args()
with open(a.file,encoding='utf-8') as f: news=json.load(f)
os.makedirs(a.out,exist_ok=True)
def e(v): return html.escape(str(v or ''),quote=True)
for n in news:
    if n.get('published') is False or not n.get('id'): continue
    nid=str(n['id'])
    target=a.base+'noticia.html?id='+urllib.parse.quote(nid,safe='')
    share=a.base+'share/'+urllib.parse.quote(nid,safe='')+'.html'
    image=n.get('instagramImage') or n.get('image') or a.base+'assets/logo-site.png'
    title=e(n.get('title','Mundo em Foco 24')); desc=e(n.get('summary','Informação que importa.'))
    doc=f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | Mundo em Foco 24</title><meta name="description" content="{desc}"><link rel="canonical" href="{e(target)}"><meta property="og:type" content="article"><meta property="og:site_name" content="Mundo em Foco 24"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:image" content="{e(image)}"><meta property="og:image:alt" content="{title}"><meta property="og:url" content="{e(share)}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{desc}"><meta name="twitter:image" content="{e(image)}"><meta http-equiv="refresh" content="0;url={e(target)}"><script>location.replace({json.dumps(target)})</script></head><body><p>Abrindo matéria no Mundo em Foco 24…</p><a href="{e(target)}">Continuar</a></body></html>'''
    with open(os.path.join(a.out,nid+'.html'),'w',encoding='utf-8') as f:f.write(doc)
print('share pages:',sum(1 for n in news if n.get('published') is not False and n.get('id')))
