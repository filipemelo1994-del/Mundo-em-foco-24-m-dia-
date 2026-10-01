import json,os,subprocess,sys
photo="https://cloudfront-us-east-1.images.arcpublishing.com/estadao/23WC4XUBA5BFHBNVWA4PRY42HQ.jpg"
cards=[
("HOMENAGEM","Quem foi Lito Sousa?","Especialista em aviação e criador do Aviões e Músicas, Lito aproximou o público do universo dos aviões."),
("TRAJETÓRIA","Uma vida ligada à aviação","Com décadas de experiência no setor aéreo, transformou conhecimento técnico em conteúdo acessível para milhões de pessoas."),
("AVIÕES E MÚSICAS","Informação com leveza","Segurança, manutenção e histórias da aviação ganharam explicações didáticas e bem-humoradas em seu trabalho."),
("SAÚDE","A doença de Creutzfeldt-Jakob","A DCJ é uma doença priônica humana rara, neurodegenerativa, progressiva e fatal, que causa rápida deterioração neurológica."),
("NOSSA HOMENAGEM","Seu legado seguirá voando","O Mundo em Foco 24 presta sua homenagem a Lito Sousa. Ficam o conhecimento compartilhado, a paixão pela aviação e o carinho de quem acompanhou sua trajetória.")
]
out="public/carousel/lito-sousa-v2";os.makedirs(out,exist_ok=True)
for i,(cat,title,summary) in enumerate(cards,1):
 req={"id":f"lito-v2-{i}","category":cat,"date":"01 OUT 2026","title":title,"summary":summary,"credit":"Foto: Reprodução / Estadão","imageCandidates":[photo]}
 p=f"/tmp/lito-{i}.json"
 with open(p,"w",encoding="utf-8") as f: json.dump(req,f,ensure_ascii=False)
 rc=subprocess.call([sys.executable,"scripts/build_news_art_v2.py","--request-json",p,"--out-dir",out])
 if rc: raise SystemExit(rc)
 os.replace(f"{out}/lito-v2-{i}.jpg",f"{out}/{i:02d}.jpg")
