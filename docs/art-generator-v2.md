# Gerador v2 do feed e validador (fase 2)

**Estado:** V1 aprovada por Filipe em 2026-09-27 para uso operacional; revisão do ChatGPT pendente antes do merge em `main`. **Não está ligado a nenhum workflow do GitHub Actions e não publica no Instagram** — isso fica para depois da revisão. Nada aqui desenha o layout "parecido": a identidade fixa vem dos pixels da referência aprovada.

## V1 (operacional) x spec oficial definitiva (pendente)

Há duas specs no repositório, por design, e isso não muda em V1.1:

- `assets/templates/layout-spec.v1.json` — **V1, `status: APPROVED`**. É a spec padrão dos dois CLIs (`--spec` tem esse arquivo como default). Master RGBA (`assets/templates/master-feed-v1.png`) gerado a partir da referência JPEG preliminar 1536×1536 (`assets/templates/reference/referencia-preliminar-1536.jpg`), com fonte Work Sans (provisória — ver `assets/fonts/README.md`). O bloco `approval.v1_1_pending` na própria spec lista o que fica para depois: ajuste fino de título/transição/chip/posicionamento, a fonte definitiva e o PNG original íntegro.
- `assets/templates/layout-spec.json` — a spec **oficial definitiva**, continua `status: PENDING_REFERENCE` e **não foi tocada pela V1**. Enquanto não vier o PNG original íntegro e a medição humana for confirmada nela, os dois CLIs recusam rodar contra ela (código de saída 2) — é o mesmo gate de segurança de antes, para impedir "aproximação" da identidade visual. Use `--spec assets/templates/layout-spec.json` para exercitar esse bloqueio ou, no futuro, para trocá-la para `APPROVED` quando o PNG chegar.

V1.1 ajusta apenas medidas/posições dentro da mesma arquitetura de zonas e a fonte/PNG, nunca a separação entre template (identidade fixa) e conteúdo variável — por isso a V1 pode entrar em uso agora sem esperar essa "perfeição visual".

## Como o layout aprovado vira template

1. `scripts/measure_reference.py auto REF.png --out-dir DIR` mede o PNG e grava `report.json`, `overlay.png` (caixas sobre a referência) e `layout-spec.proposed.json`.
2. Uma pessoa confere o `overlay.png`, ajusta as caixas e a capacidade real das zonas, coloca a fonte aprovada em `assets/fonts/` e só então troca `status` para `APPROVED` em `assets/templates/layout-spec.json`.
3. O **mestre** (a arte sem a matéria de exemplo) vem de uma destas fontes (`master.source` na spec):
   - `generate`: o script limpa as zonas variáveis do PNG de referência (`clear.mode`: `solid`, `interpolate_rows`, `interpolate_cols`). Se sobrar detalhe de exemplo dentro de alguma zona, o carregamento falha e diz qual.
   - `file`: um mestre já limpo, entregue pronto.
   - `file` com **transparência (RGBA)**: a janela da foto é transparente e a foto entra **por baixo**; chip, borda suave do painel e demais elementos que ficam sobre a foto continuam por cima. É o modo recomendado quando o layout tem elementos sobrepostos à foto, como o chip "TECNOLOGIA" e a transição suave do painel.
4. `build_news_art_v2.py --emit-master DIR` grava `master-feed.png`, uma prévia e `master-feed.meta.json` (sha256 do PNG e hash perceptual) para comparação visual.

## Zonas

Variáveis: foto, categoria, data, título, resumo, crédito. Fixas: cabeçalho, logo, rodapé e todo o resto da arte. Coordenadas ficam em pixels do PNG de referência (`[x, y, largura, altura]`); a saída é reduzida para `output.width × output.height`, que precisa ter a **mesma proporção** da referência (a spec recusa se não tiver).

## Checks (`scripts/validate_news_art.py`)

| Check | Reprova quando |
| --- | --- |
| `dimensions`, `size_limits` | Tamanho diferente do `output` ou fora de 20 KB a 8 MB. |
| `not_equal_to_master`, `not_near_master` | Arquivo igual a um de `assets/templates/` (sha256), ou quase igual ao mestre (diferença média e hash perceptual). |
| `no_sample_content` | A arte repete a foto ou o texto do exemplo da referência (o caso "Alibaba dentro de outra notícia"). |
| `photo_zone_changed` | Zona da foto igual ao mestre ou sem variação (foto ausente ou chapada). |
| `text_zones_changed` | Categoria, data ou título obrigatório sem texto visível. |
| `identity_preserved`, `outside_zones_intact` | Zonas fixas ou qualquer pixel fora das zonas variáveis diferente do mestre (logo deformado, retângulo, texto vazando). |
| `text_fit` | Texto cortado ou fora da zona (o resumo pode terminar em reticências; título não). |
| `photo_matches_source` | A foto usada não é a informada (`--source-photo`). |
| `published_equals_validated` | O arquivo público (`--public-url`) tem sha256 diferente do validado. |

O Story usa `assets/templates/layout-spec-story.json` (1080×1920) com validação estrutural: dimensões, tamanho, foto com variação no miolo, texto presente e cores fixas.

## Comandos

```bash
python3 scripts/measure_reference.py auto REF.png --out-dir /tmp/medida
python3 scripts/build_news_art_v2.py --emit-master /tmp/mestre
python3 scripts/build_news_art_v2.py --sample /tmp/amostra.jpg          # foto placeholder, para comparação visual
python3 scripts/build_news_art_v2.py --request-json req.json --photo-file foto.jpg --out-dir /tmp/saida --output-json /tmp/res.json
python3 scripts/validate_news_art.py --art /tmp/saida/x.jpg --source-photo foto.jpg --fit-report /tmp/res.json --output-json /tmp/val.json
```

Saída de `build_news_art_v2.py`: 0 ok e validada · 2 spec pendente/inválida · 3 erro de renderização ou mídia · 4 gerada mas reprovada (não publicar). `validate_news_art.py`: 0 aprovada · 1 reprovada · 2 spec pendente ou arquivos ausentes. O relatório de validação tem o formato de `context.validator_report` do pedido de revisão Claude e pode ir para a fila com `update_publish_queue.py --art-validation`.

## Limites conhecidos

- A medição automática foi calibrada na arte aprovada em JPEG (1536×1536) e em uma referência sintética. Ela mede caixas de **tinta do texto de exemplo**; a capacidade real de cada zona (linhas máximas, margens) precisa de confirmação humana.
- A transição foto→painel é suave: o `y` do painel tem margem de ±20 px. Sem as camadas originais, o modo RGBA (janela transparente) é o que preserva essa borda com fidelidade.
- O tamanho da fonte só fecha com o arquivo da fonte aprovada.
- A referência aprovada tem proporção 1:1; a saída do feed acompanha a referência (por exemplo 1080×1080). Usar 4:5 exige um layout aprovado nessa proporção.

## Testes

```bash
python3 -m unittest discover -s tests -p "test_news_art*.py"
python3 -m unittest tests.test_v1_integration   # confere a V1 real (não sintética) e o gate da spec oficial
```
