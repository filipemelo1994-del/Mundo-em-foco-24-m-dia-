const NEWS_URL='https://raw.githubusercontent.com/filipemelo1994-del/Mundo-em-foco-24-m-dia-/main/data/news.json';
const AUTO_URL='https://raw.githubusercontent.com/filipemelo1994-del/Mundo-em-foco-24-m-dia-/main/data/news-auto.json';
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const href=n=>'noticia.html?id='+encodeURIComponent(n.id);
const safeImg=n=>n.image?'<img src="'+esc(n.image)+'" alt="'+esc(n.imageAlt||n.title)+'" onerror="if(!this.dataset.fallback){this.dataset.fallback=\'1\';this.src=\''+esc(n.instagramImage||'/Mundo-em-foco-24-m-dia-/assets/logo-site.png')+'\'}else{this.style.display=\'none\'}">':(n.instagramImage?'<img src="'+esc(n.instagramImage)+'" alt="'+esc(n.title)+'">':'');
const id=new URLSearchParams(location.search).get('id');
Promise.all([
 fetch(AUTO_URL,{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[]),
 fetch(NEWS_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw 0;return r.json()})
]).then(([auto,base])=>{
 const news=[...auto,...base].filter(x=>x.published!==false);
 const index=news.findIndex(x=>x.id===id),n=news[index]; if(!n)throw 0;
 document.title=n.title+' | Mundo em Foco 24';
 const shareUrl=new URL('share/'+encodeURIComponent(n.id)+'.html',location.origin+location.pathname.replace(/noticia\.html$/,'')).href;
 const body=n.body||[], paragraphs=body.map(p=>'<p>'+esc(p)+'</p>').join('');
 const sources=(n.sources||[]).map(s=>'<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.name)+'</a></li>').join('');
 const prev=news[index+1], next=index>0?news[index-1]:null;
 const navCard=(x,label)=>x?'<a class="storyNavCard" href="'+href(x)+'"><small>'+label+'</small>'+safeImg(x)+'<span><b>'+esc(x.category)+'</b><strong>'+esc(x.title)+'</strong></span></a>':'<div></div>';
 const related=news.filter(x=>x.id!==n.id).slice(0,4).map(x=>'<a class="relatedCard" href="'+href(x)+'">'+safeImg(x)+'<span class="label">'+esc(x.category)+'</span><strong>'+esc(x.title)+'</strong></a>').join('');
 const expandable=body.length>2;
 document.getElementById('article').innerHTML='<span class="label">'+esc(n.category)+'</span><h1>'+esc(n.title)+'</h1><p class="articleLead">'+esc(n.summary)+'</p><div class="articleMeta">'+esc(n.location)+' • '+esc(n.date)+'</div>'+(n.image||n.instagramImage?'<figure>'+safeImg(n)+'<figcaption>Crédito: '+esc(n.credit||'Mundo em Foco 24')+'</figcaption></figure>':'')+'<div class="shareBar"><button id="shareBtn" type="button">↗ <span>Compartilhar</span></button><button id="copyBtn" type="button">🔗 <span>Copiar link</span></button></div><div id="articleBody" class="articleBody '+(expandable?'isCollapsed':'')+'">'+paragraphs+(expandable?'<div class="readFade"></div>':'')+'</div>'+(expandable?'<div class="continueWrap"><button id="continueBtn">Continuar lendo ↓</button></div>':'')+(sources?'<section class="sources"><h2>Fontes</h2><ul>'+sources+'</ul></section>':'')+'<section class="storyNavigation"><h2>Continue acompanhando</h2><div class="storyNavGrid">'+navCard(prev,'← Matéria anterior')+navCard(next,'Próxima matéria →')+'</div></section><section class="related"><h2>Mais notícias</h2><div class="relatedGrid">'+related+'</div></section><a class="back" href="/">← Voltar para a capa</a>';
 const shareData={title:n.title,text:n.summary,url:shareUrl};
 document.getElementById('shareBtn').onclick=async()=>{try{if(navigator.share)await navigator.share(shareData);else{await navigator.clipboard.writeText(shareUrl);alert('Link copiado!')}}catch(e){if(e.name!=='AbortError')console.error(e)}};
 document.getElementById('copyBtn').onclick=async()=>{await navigator.clipboard.writeText(shareUrl);const b=document.getElementById('copyBtn');b.innerHTML='✓ <span>Link copiado</span>';setTimeout(()=>b.innerHTML='🔗 <span>Copiar link</span>',1800)};
 if(expandable)document.getElementById('continueBtn').onclick=()=>{document.getElementById('articleBody').classList.remove('isCollapsed');document.querySelector('.continueWrap').remove()};
}).catch(()=>document.getElementById('article').innerHTML='<h1>Matéria não encontrada</h1><p>Esta publicação pode ter sido removida ou atualizada.</p><a class="back" href="/">← Voltar para a capa</a>');
