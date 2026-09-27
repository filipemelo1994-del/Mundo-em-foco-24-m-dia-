# Revisão Claude — arquitetura sem Netlify

Claude é uma segunda opinião consultiva. Ele não publica, não altera produção e não faz parte do caminho obrigatório de publicação.

## Fluxo operacional

GitHub / GitHub Actions → gerador V1 → validador determinístico → Windsor.ai → Instagram.

O Windsor.ai é o conector de publicação. O revisor Claude fica fora desse caminho crítico e só é acionado quando houver erro, inconsistência, repetição de falha ou pedido explícito de segunda opinião.

## Regras preservadas

- máximo de 2 rodadas por task_id;
- 3 falhas de transporte levam a HUMAN_REVIEW_REQUIRED;
- validador reprovado nunca pode virar autorização de publicação;
- segredos não ficam no frontend nem no repositório;
- pareceres ficam em data/reviews/;
- data/review-ledger.json mantém o histórico;
- correções do revisor são propostas, nunca publicação automática.

## Windsor.ai

A publicação no Instagram continua externa ao gerador. A arte só pode ser entregue ao Windsor.ai depois de passar pelo validador e depois de a URL pública apontar exatamente para o arquivo validado.

## Netlify

Netlify não faz parte da arquitetura atual. Os endpoints antigos em netlify/functions/ foram removidos da V1. Qualquer futura ponte HTTP para Claude deve ser implementada no backend/orquestrador escolhido para o projeto, sem reintroduzir Netlify implicitamente.
