import json,os,subprocess,sys
photos=[
"https://static.clubs.nfl.com/image/upload/f_auto,q_auto,w_1600/cowboys/zgsiwziqoogj7zquqlcq.jpg",
"https://static.clubs.nfl.com/image/upload/f_auto,q_auto,w_1600/cowboys/quayc2v1g4yj1x3hqdzk.jpg",
"https://static.clubs.nfl.com/image/upload/f_auto,q_auto,w_1600/cowboys/yxha2mr3cughk9bb7rbr.jpg",
"https://static.clubs.nfl.com/image/upload/f_auto,q_auto,w_1600/cowboys/diktoxvzznsvsgopu0tw.jpg",
"https://static.clubs.nfl.com/image/upload/f_auto,q_auto,w_1600/cowboys/biibyiuvaycnkxjhefid.jpg"]
cards=[
("NFL • RIO DE JANEIRO","Brasil e EUA se encontram em noite histórica da NFL no Maracanã","O Rio recebeu Ravens e Cowboys no primeiro jogo de temporada regular da NFL realizado na cidade."),
("NFL • MARACANÃ","Maracanã vira palco do futebol americano","Torcedores brasileiros acompanharam de perto o duelo entre Baltimore Ravens e Dallas Cowboys."),
("NFL • RESULTADO","Ravens vencem Cowboys por 34 a 31 no Rio","Baltimore levou a melhor em uma partida equilibrada e decidida apenas nos segundos finais."),
("NFL • DECISÃO","Field goal no fim decide duelo no Maracanã","Tyler Loop acertou a tentativa decisiva e garantiu a vitória dos Ravens por três pontos."),
("NFL • BRASIL","Noite reforça expansão da NFL no Brasil","A liga amplia sua presença no país e transforma o Rio de Janeiro em novo palco de jogos internacionais.")
]
out="public/carousel/nfl-rio-v2-fotos-28-09-2026";os.makedirs(out,exist_ok=True)
for i,(photo,(cat,title,summary)) in enumerate(zip(photos,cards),1):
 req={"id":f"nfl-rio-v2-{i:02d}","category":cat,"date":"27 SET 2026","title":title,"summary":summary,"credit":"James D. Smith / Dallas Cowboys","imageCandidates":[photo]}
 p=f"/tmp/nfl-{i}.json";json.dump(req,open(p,"w"),ensure_ascii=False)
 rc=subprocess.call([sys.executable,"scripts/build_news_art_v2.py","--request-json",p,"--out-dir",out,"--no-validate"])
 if rc: raise SystemExit(f"card {i} falhou: {rc}")
 os.rename(f"{out}/nfl-rio-v2-{i:02d}.jpg",f"{out}/{i:02d}.jpg")
