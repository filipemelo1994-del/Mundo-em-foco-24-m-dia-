# Ponte de revisão ChatGPT ↔ Claude (fase 1)

Claude é **segunda opinião consultiva**. Ele não publica no Instagram e não altera produção; devolve diagnóstico e correção proposta, e o orquestrador decide. A decisão final de publicar continua sendo do validador determinístico.

```
Workflow / ChatGPT ──▶ scripts/review_gate.py (lê data/review-ledger.json)
        │                    bloqueado? ──▶ HUMAN_REVIEW_REQUIRED, sem chamar ninguém
        ▼
POST /.netlify/functions/claude-review   (chave + HMAC-SHA256 + timestamp)
        │  valida schema · reserva a rodada no ledger · chama a Anthropic
        ▼
resposta JSON (schemas/claude-review-response.v1.json) ──▶ validador ──▶ orquestrador
```

## Arquivos

| Arquivo | Função |
| --- | --- |
| `schemas/claude-review-request.v1.json` / `...response.v1.json` | Contrato de entrada e saída. |
| `netlify/functions/claude-review.mjs` + `lib/review-core.mjs` | Endpoint. Sem dependências externas. |
| `data/review-ledger.json` | Rodadas por `task_id`, `request_id` já vistos, falhas de transporte. Escrito só pelo endpoint. |
| `data/reviews/<task_id>-r<rodada>.json` | Pedido (com segredos redigidos) e resposta de cada rodada. |
| `scripts/review_gate.py` | Gate local somente leitura; `reset` exige `--by` e `--reason`. |
| `scripts/request_claude_review.py` | Cliente: gate, assinatura, chamada, grava resposta e (opcional) o item da fila. |
| `.github/workflows/claude-review.yml` | Recebe `repository_dispatch: claude_review_request`. |
| `scripts/update_publish_queue.py` | Novas flags opcionais `--review-json`, `--art-validation`, `--art-sha256`. |

Os pareceres ficam em `data/reviews/` e **não** em `requests/`, porque `import-news-image.yml` dispara em qualquer push em `requests/**/*.json`.

## Regras aplicadas pelo endpoint (nesta ordem)

1. `request_id` já respondido devolve o parecer guardado (`CACHED`) sem chamar Claude nem consumir rodada; em andamento devolve 409.
2. `max_review_rounds = 2` por `task_id`, `HUMAN_REVIEW_REQUIRED` já registrado, ou 3 falhas de transporte: devolve `HUMAN_REVIEW_REQUIRED` com `claude_called: false`.
3. Mesmo `error_fingerprint` depois de uma `applied_fix`: escala direto, mesmo com rodada sobrando.
4. Teto global `hourly_cap` (20 por hora): HTTP 429.
5. A rodada é **reservada no ledger antes** de chamar a Anthropic. Se a função cair, a rodada continua contada.
6. Timeout, 429 e 5xx da Anthropic: até 2 novas tentativas (2 s e 6 s, respeitando `retry-after`) dentro do prazo. Se falhar, a rodada é devolvida, soma em `transport_failures` e a resposta é `UNAVAILABLE`. Erro 4xx da Anthropic (chave ou modelo inválido) não é repetido e conta como falha.
7. Resposta de Claude fora do schema: 1 reparo; depois, parecer `INSUFICIENTE` (consome rodada, nunca `SIM`).
8. Regras do servidor sobre o parecer: validador reprovado força `publish: NAO`; `SIM` só com `status: OK`; correção que toque `.github/workflows/`, segredos ou este endpoint vira `manual` e perde o patch.
9. Segredos são redigidos do texto antes de ir para Claude e antes de gravar o parecer. Texto de terceiros vai dentro de `<untrusted_data>`. Imagens só são enviadas de hosts permitidos (`CLAUDE_REVIEW_IMAGE_HOSTS`, padrão `raw.githubusercontent.com,mundoemfoco24.netlify.app`).

## Configuração (nada disso está no código)

Netlify (variáveis de ambiente do site):

- `ANTHROPIC_API_KEY`
- `CLAUDE_REVIEW_MODEL`: obrigatória, sem valor padrão. Use um modelo Anthropic atual com visão. Sem ela o endpoint responde 500 `not_configured`, listando só os nomes ausentes.
- `CLAUDE_REVIEW_KEY` e `CLAUDE_REVIEW_HMAC_SECRET`
- `GITHUB_REVIEW_TOKEN`: token fine-grained só deste repositório, permissão *Contents: read and write*. Opcionais: `GITHUB_REVIEW_REPO`, `GITHUB_REVIEW_BRANCH`, `CLAUDE_REVIEW_IMAGE_HOSTS`.

GitHub Actions (secrets): `CLAUDE_REVIEW_URL`, `CLAUDE_REVIEW_KEY`, `CLAUDE_REVIEW_HMAC_SECRET`.

## Como pedir uma revisão

```bash
curl -X POST https://api.github.com/repos/filipemelo1994-del/Mundo-em-foco-24-m-dia-/dispatches \
  -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" \
  -d '{"event_type":"claude_review_request","client_payload":{ ...pedido conforme o schema... }}'
```

O gate local consulta o ledger antes; o resultado vai para `data/reviews/`, para o item da fila (`review`, e `state: HUMAN_REVIEW_REQUIRED` quando escalado) e para o resumo da execução.

Sair de `HUMAN_REVIEW_REQUIRED` é ação humana registrada:

```bash
python3 scripts/review_gate.py reset --task-id <task_id> --by <nome> --reason "<motivo>"
```

(o `reset` altera o ledger no checkout local; commite o arquivo depois).

## Pontos para verificar antes de ligar

- **Prazo da função na Netlify.** Funções síncronas têm limite de tempo (padrão de 10 s no plano comum). Revisão com imagem pode passar disso. Confirme o limite do seu plano; `deadline_s` (padrão 25) só é respeitado até esse teto. Se o limite for menor, uma revisão longa termina como `UNAVAILABLE` sem consumir rodada.
- **Gravação concorrente.** O endpoint grava o ledger pela API de conteúdo do GitHub com controle de versão (sha) e repete em caso de conflito.
- **Commits no `main`.** Cada rodada gera até 3 commits do token de revisão (`data/review-ledger.json` e `data/reviews/`). Nenhum workflow existente dispara nesses caminhos.

## Testes

```bash
node --test tests/claude-review.test.mjs
python3 -m unittest discover -s tests -p "test_*.py"
```
