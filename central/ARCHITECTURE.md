# Central de Controle — contrato de integração

A Central em `central/` é uma interface pública e somente de leitura. Ela busca `../data/news.json` sem cache, a cada 60 segundos. Nenhum fluxo de publicação existente foi alterado.

## Dados atuais

`news.json` contém notícias, mas não confirma publicação nas redes sociais nem saúde do GitHub Actions. A interface marca esses estados como “não verificado”. `published === true` sinaliza portal; uma string de data ou a existência de imagem não comprova publicação.

## Próximo contrato de status

Um backend autenticado deve produzir `central/status.json` ou um endpoint privado que retorne observações com `checkedAt`, `source`, `status` e `error` para Portal, Feed, Story, Reel e automações. Cada resultado deve carregar ID da matéria, ID da execução ou postagem e URL quando houver. Não derivar êxito de uma fila vazia.

As ações de publicar, repetir, pausar ou gerar conteúdo exigem autenticação do operador, autorização explícita por ação, proteção contra repetição e trilha de auditoria. Não colocar tokens do GitHub, Instagram, OneSignal, OpenAI ou Anthropic em arquivos publicados por GitHub Pages ou no JavaScript.

## ChatGPT e Claude

Criar um serviço no servidor com adaptadores `openai` e `anthropic`, configuração por segredo de ambiente, acesso restrito e validação do pedido. O frontend envia a intenção ao backend autenticado; o backend chama o provedor e devolve a resposta com referência da execução. Chaves permanecem no servidor. Até existir esse serviço e testes reais, o terminal local oferece apenas `ajuda`, `status`, `fila`, `erros`, `atualizar` e `limpar`.

## Diagnóstico

Verificar a execução mais recente em GitHub Actions, abrir `central/` e `data/news.json` no domínio do Pages, testar imagens separadamente e conferir o console do navegador. A Central não lê logs privados do Actions diretamente porque uma página pública não pode guardar credenciais.
