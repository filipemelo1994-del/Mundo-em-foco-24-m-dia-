#!/usr/bin/env python3
import argparse,json,os,sys,tempfile
def main():
    p=argparse.ArgumentParser(); p.add_argument("--file",default="data/news.json"); p.add_argument("--id",required=True); p.add_argument("--source-image"); p.add_argument("--instagram-image"); p.add_argument("--story-image"); a=p.parse_args()
    with open(a.file,encoding="utf-8") as f: data=json.load(f)
    if not isinstance(data,list):
        print("ERRO: data/news.json precisa ser lista",file=sys.stderr); return 1
    entry=next((x for x in data if isinstance(x,dict) and str(x.get("id"))==str(a.id)),None)
    if entry is None:
        print("ERRO: pauta não encontrada; nenhuma alteração feita",file=sys.stderr); return 1
    if a.source_image:
        entry["sourceImage"]=a.source_image
        entry["image"]=a.source_image
    if a.instagram_image: entry["instagramImage"]=a.instagram_image
    if a.story_image: entry["storyImage"]=a.story_image
    if a.instagram_image and a.story_image: entry["mediaReady"]=True
    directory=os.path.dirname(os.path.abspath(a.file)); fd,tmp=tempfile.mkstemp(prefix=".news-",suffix=".json",dir=directory)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write("\n")
        os.replace(tmp,a.file)
    except Exception:
        if os.path.exists(tmp): os.remove(tmp)
        raise
    print(f"OK: {a.id} atualizado; {len(data)} pautas preservadas")
    return 0
if __name__=="__main__": sys.exit(main())
