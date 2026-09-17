const news=[
{cat:"Mobilidade",title:"Linha Sul do Metrô é paralisada",text:"Falha elétrica interrompeu a circulação e fechou estações da Linha Sul no Recife.",meta:"RECIFE • 16 SET 2026"},
{cat:"Mundo",title:"Helicóptero de imprensa cai em Los Angeles",text:"Aeronave usada em cobertura jornalística caiu em Chatsworth. Autoridades investigam as causas.",meta:"LOS ANGELES • 16 SET 2026"},
{cat:"Tecnologia & Educação",title:"Embarque Digital forma 185 estudantes",text:"Nova turma amplia a formação de profissionais para o setor de tecnologia no Recife.",meta:"RECIFE • 16 SET 2026"}
];
document.getElementById("newsGrid").innerHTML=news.map(n=>`<article class="card"><div class="thumb">M24</div><div class="body"><span class="cat">${n.cat}</span><h3>${n.title}</h3><p>${n.text}</p><span class="meta">${n.meta}</span></div></article>`).join("");
document.getElementById("menuBtn").onclick=()=>document.getElementById("nav").classList.toggle("open");