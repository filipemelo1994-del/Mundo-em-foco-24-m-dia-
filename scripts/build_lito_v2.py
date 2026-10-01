import json,os,subprocess,sys
photos=[
"https://cdn.jornalmassa.com.br/img/Chamada-Home/1330000/piloto-lito-relata-luta-contra-doenca-rara-entenda0133673200202608261828.jpg?xid=6386449",
"https://img.band.com.br/image/2026/08/21/quem-e-lito-sousa-conheca-especialista-em-aviacao-que-conquistou-milhoes-na-internet-111642.png",
"https://cloudfront-us-east-1.images.arcpublishing.com/estadao/23WC4XUBA5BFHBNVWA4PRY42HQ.jpg",
"https://static.poder360.com.br/uploads/2026/08/Lito-Sousa-29.ago_.2026.png",
"https://assets.clubefm.com.br/uploads/post/image/59633/open_graph_c822ff5f-fa3d-47fb-a1a1-a4ff15a88810.jpg"
]
cards=[
("HOMENAGEM","Quem foi Lito Sousa?","Especialista em aviação e criador do Aviões e Músicas, Lito transformou décadas de experiência em conhecimento acessível para milhões de pessoas."),
("TRAJETÓRIA","Mais de três décadas na aviação","Mecânico de aeronaves, piloto privado e especialista em segurança aérea, construiu uma longa carreira antes de se tornar referência na internet."),
("AVIÕES E MÚSICAS","Aviação explicada para todos","No Aviões e Músicas, Lito tornou assuntos técnicos mais fáceis de entender e ajudou muita gente a conhecer melhor a segurança e o funcionamento dos aviões."),
("SAÚDE","A doença de Creutzfeldt-Jakob","A DCJ é uma doença priônica humana rara, neurodegenerativa, progressiva e fatal. Ela pode provocar rápida deterioração das funções neurológicas."),
("HOMENAGEM","Seu legado segue voando","Obrigado, Lito, por compartilhar conhecimento, histórias e sua paixão pela aviação. Seu trabalho continuará vivo na memória de quem aprendeu e voou com você.")
]
out="public/carousel/lito-sousa-v2";os.makedirs(out,exist_ok=True)
for i,((cat,title,summary),photo) in enumerate(zip(cards,photos),1):
 req={"id":f"lito-v2-{i}","category":cat,"date":"01 OUT 2026","title":title,"summary":summary,"credit":"Foto: Reprodução / imprensa","imageCandidates":[photo]}
 p=f"/tmp/lito-{i}.json"
 with open(p,"w",encoding="utf-8") as fh: json.dump(req,fh,ensure_ascii=False)
 rc=subprocess.call([sys.executable,"scripts/build_news_art_v2.py","--request-json",p,"--out-dir",out])
 if rc: raise SystemExit(rc)
 os.replace(f"{out}/lito-v2-{i}.jpg",f"{out}/{i:02d}.jpg")
