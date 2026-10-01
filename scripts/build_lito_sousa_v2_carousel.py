import json,os,subprocess,sys
photo="https://cloudfront-us-east-1.images.arcpublishing.com/estadao/23WC4XUBA5BFHBNVWA4PRY42HQ.jpg"
cards=[
("HOMENAGEM","Quem foi Lito Sousa?","Especialista em aviação, comunicador e criador do Aviões e Músicas. Lito morreu aos 59 anos em 1º de outubro."),
("TRAJETÓRIA","Uma vida dedicada à aviação","Lito trabalhou por décadas no setor aéreo e levou sua experiência técnica para milhões de pessoas na internet."),
("AVIÕES E MÚSICAS","Conhecimento com linguagem simples","Em seu canal, explicava segurança, manutenção, operações e histórias da aviação de forma didática e acessível."),
("SAÚDE","O que é a doença de Creutzfeldt-Jakob?","A DCJ é uma doença priônica humana rara, neurodegenerativa, progressiva e fatal, que causa rápida deterioração neurológica."),
("LEGADO","Seu legado seguirá voando","Lito aproximou milhões de pessoas da aviação. O Mundo em Foco 24 presta solidariedade à família, aos amigos e a todos que acompanhavam seu trabalho.")
]
out="public/carousel/lito-sousa-v2-01-10-2026";os.makedirs(out,exist_ok=True)
for i,(cat,title,summary) in enumerate(cards,1):
 req={"id":f"lito-sousa-v2-{i:02d}","category":cat,"date":"01 OUT 2026","title":title,"summary":summary,"credit":"Foto: Reprodução / Estadão","imageCandidates":[photo]}
 p=f"/tmp/lito-{i}.json"
 with open(p,"w",encoding="utf-8") as f: json.dump(req,f,ensure_ascii=False)
 rc=subprocess.call([sys.executable,"scripts/build_news_art_v2.py","--request-json",p,"--out-dir",out,"--no-validate"])
 if rc: raise SystemExit(rc)
 os.rename(f"{out}/lito-sousa-v2-{i:02d}.jpg",f"{out}/{i:02d}.jpg")
