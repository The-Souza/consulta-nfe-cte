# Changelog

Todas as mudanças relevantes do projeto ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/). As versões anteriores à 2.0.0 estão descritas nas [releases do GitHub](https://github.com/The-Souza/consulta-nfe-cte/releases).

## [2.0.0-alpha.2] — em andamento

### Alterado
- Consulta: um campo único "NF-es" no lugar de "NF-e inicial" e "NF-e final". Aceita uma NF-e (`4516661`), uma faixa (`4516661-4516680`) ou uma lista separada por vírgula, espaço, `;` ou quebra de linha, como uma coluna colada do Excel. Repetidas são consultadas uma vez só.
- Consulta: acima do campo aparece como o app entendeu o texto ("1 NF-e", "Faixa · 20 NF-es", "Lista · 3 NF-es" ou "Formato não reconhecido"). Enter busca.
- Consulta: acima de 500 NF-es, o app pede confirmação antes de buscar; o limite é de 5.000 NF-es por consulta.
- Histórico da consulta: guarda o texto do campo e o devolve ao restaurar.
- Consulta com o novo visual: a tabela fica leve mesmo com centenas de NF-es e ganha as colunas Motorista e Entrega (com "—" até a próxima etapa). O CT-e mostra "×N" quando se repete na consulta, e a linha inteira fica na cor do status quando não é OK.
- Consulta: os chips viram filtros (Todos, Com CT-e, Sem CT-e, Não cadastrada, Sem imagem, Falha de conexão), cada um com a contagem; o menu "Filtrar" saiu.
- Consulta: as falhas de conexão aparecem numa faixa no topo da tabela com o botão "Tentar de novo só essas N".
- Consulta: no fim, o status mostra o total, as falhas e o tempo ("Consulta concluída · 20 NF-es · 2 com falha · 00:41"). A janela abre maior.

### Corrigido
- Voltar da Consulta ou do Upload para o Início deixava a janela larga.

## [2.0.0-alpha.1] — 2026-11-18

### Adicionado
- Consulta: botão "Tentar de novo só essas (N)", que reconsulta só as NF-es com falha de conexão e atualiza as linhas, os contadores e o histórico no lugar.
- Consulta: chip e filtro "Falha de conexão".
- Se a sessão expirar no meio de uma busca ou de um upload, o app entra de novo sozinho e continua. Se não conseguir, para e pede para entrar de novo. A senha usada para isso fica só na memória enquanto o app está aberto.

### Alterado
- Consulta: no fim da busca, as NF-es com falha de conexão são consultadas de novo automaticamente, uma vez.
- Consulta: depois de 3 falhas de conexão seguidas, a busca pausa 10 segundos ("Servidor instável, aguardando…") antes de continuar.
- O botão "Cancelar" também interrompe as esperas entre tentativas.
- Upload: um arquivo com falha de conexão fica na pasta, com o status "Falha de conexão". Basta iniciar o upload de novo para enviar só esses.
- Upload: a tentativa extra só no primeiro arquivo deixou de existir; agora todo arquivo tem as mesmas retentativas.
- Upload: os arquivos são enviados em ordem alfabética.
- Consulta e upload repetem a chamada sozinhos quando o servidor oscila (tempo esgotado, queda de conexão, servidor sobrecarregado ou sessão devolvendo página em vez de dados): até 3 novas tentativas, com espera crescente.
- O que continuar falhando aparece como "Falha de conexão", com cor própria, diferente de "Não cadastrada". O Excel também mostra esse status.
- O envio da imagem só é repetido quando a conexão nem chegou a ser feita, porque o portal não aceita uma segunda imagem para o mesmo canhoto.

## [2.0.0-alpha.0] — 2026-11-18

### Adicionado
- Versão do app definida em `config.py` (`APP_VERSION`).
- Ferramentas de desenvolvimento: `ruff` para lint e `pytest` para testes (`requirements-dev.txt`).
- CI no GitHub Actions: lint e testes em todo push e PR para `develop` e `master`.
- Tema escuro com cores, fontes e espaçamentos centralizados (`ui/theme.py`).
- Ícones Lucide no lugar de símbolos de texto, incluídos no executável.
- Login: opção "Lembrar senha neste computador". O e-mail é sempre lembrado; desmarcada, o app apaga a senha salva. A opção abre como foi deixada no último login.
- Login: botão para mostrar/ocultar a senha e a versão do app abaixo do card.
- Login: usa o arquivo de ícone do `.env` (`ICON_FILE`) como logo; sem ele, mostra um ícone padrão.

### Alterado
- Tags com hífen (ex.: `v2.0.0-alpha.0`) geram o executável como pré-lançamento. O link de download do README continua apontando para a última versão estável.
- O release só gera o executável se o lint e os testes passarem e se a versão do app for igual à da tag.
- Novo visual do Login e do Início: no Início, os dois botões viraram cards com ícone, título e descrição.
- Barra de título escura no Windows 11 e nova barra superior, com ícones nos botões "Voltar" e "Sair".
- Consulta e Upload sem emojis: os status aparecem como badges coloridos na tabela e nos contadores, e os avisos ficam em amarelo.
- Botão "Cancelar" com ícone e cor de erro; o filtro, o histórico e a tabela seguem o tema escuro.
- O Excel exportado traz o status sem emoji (`OK`, `Sem CT-e`, `Não cadastrada`).

### Corrigido
- Consulta: uma mensagem de erro com "OK" no texto era contada e filtrada como "Com CT-e".
