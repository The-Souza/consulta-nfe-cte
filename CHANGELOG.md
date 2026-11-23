# Changelog

Todas as mudanças relevantes do projeto ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/). As versões anteriores à 2.0.0 estão descritas nas [releases do GitHub](https://github.com/The-Souza/consulta-nfe-cte/releases).

## [2.0.0-alpha.4] — 2026-11-23

### Adicionado
- Utilitário **Enviar planilha** (`enviar-planilha.exe`), separado do app e usado só no PC de quem mantém a planilha de entregas. Ele lê a planilha `.xlsx` e atualiza a tabela de motoristas e datas que a Consulta usa, gravando só as NF-es novas e as que mudaram. Nada é apagado.
- Enviar planilha: as colunas de NF-e, motorista, data de entrega e CT-e (opcional) são sugeridas pelo título do cabeçalho e ficam salvas. Linhas só com CT-e entram como carregamento com XML único, e "S/D" conta como célula vazia.
- Enviar planilha: "Conferir sem enviar" mostra quantas linhas seriam novas, atualizadas e ignoradas, sem gravar nada. O resultado do envio traz as linhas ignoradas com o número e o motivo, como "sem motorista (linhas 10.488 e 10.491)".
- Enviar planilha: "Enviar sozinho quando eu salvar a planilha" confere a planilha a cada 30 segundos e envia uns 35 segundos depois de ela ser salva. Se o envio falhar, como sem internet, tenta de novo nas conferências seguintes.
- Enviar planilha: as colunas escolhidas são conferidas pelo título do cabeçalho antes de cada envio. Se uma coluna foi inserida ou renomeada, ou se o título está repetido ou vazio, nada é enviado e a tela pede para conferir as colunas. Assim, uma coluna fora do lugar não grava dados errados na tabela.
- Enviar planilha: a configuração fica em `enviar_planilha.env`, com a chave secreta do Supabase, separada do `.env` do app. O build é feito pelo `build_enviar.ps1`.

### Alterado
- O código-fonte passa a exigir Python 3.13 (o 3.10 saiu de suporte). O executável já usava o 3.13.

### Corrigido
- A barra de título perdia a cor do app ao trocar de tela e ficava com a cor de destaque do Windows.
- Consulta: os chips não se deslocam mais quando uma contagem sai do zero durante a busca.

## [2.0.0-alpha.3] — 2026-11-22

### Adicionado
- Consulta: motorista e data de entrega de cada NF-e, lidos de uma tabela no Supabase (só leitura) e mostrados nas colunas Motorista e Entrega. Quando o carregamento foi lançado com um XML único e a NF-e não está na tabela, o motorista vem pelo CT-e.
- Consulta: ao lado dos chips, de quando é a planilha de motoristas ("Motoristas e datas: planilha de hoje, 14:20"), ou "Motoristas e datas indisponíveis" quando a leitura falha.
- Consulta: o painel lateral ganha as abas CT-es | Motoristas. A aba Motoristas mostra as NF-es de cada motorista, com as datas de entrega e as sem motorista por último; clicar num motorista filtra a tabela ("Mostrando N NF-es de X · Limpar filtro"), junto com o chip ativo.
- Consulta: com o chip Sem imagem, o painel mostra "Sem imagem por motorista", para saber de quem cobrar as fotos e de quais dias, e o botão vira "Exportar por motorista": um Excel com uma aba por motorista, cada uma com Motorista, NF-e, Entrega e CT-e. Ao sair do chip, o painel volta para a aba de antes.
- Excel: colunas Motorista e Entrega na aba "Consulta".
- Configuração opcional `SUPABASE_URL` e `SUPABASE_ANON_KEY` no `.env`, e o SQL da tabela em `supabase/001_entregas.sql`. Sem elas, ou com o Supabase fora do ar, a consulta funciona normalmente.

### Alterado
- Consulta: o limite passa de 5.000 para 200 NF-es por consulta, contando só as diferentes. Uma lista colada com repetidas não é mais recusada por causa delas.
- Consulta: o CT-e repetido aparece como "25540 · ×3", e clicar numa linha da tabela não a deixa mais selecionada.

### Removido
- Consulta: a confirmação acima de 500 NF-es.

### Corrigido
- A barra de rolagem da tabela da Consulta, do painel lateral, do histórico e da lista do Upload só aparece quando há o que rolar.

## [2.0.0-alpha.2] — 2026-11-19

### Adicionado
- Consulta: painel "CT-es nesta consulta", com cada CT-e, a quantidade de NF-es e uma barra proporcional. Clicar num CT-e filtra a tabela ("Mostrando as N NF-es do CT-e X · Limpar filtro"); embaixo ficam as NF-es com e sem CT-e, e "sem CT-e" pode ser clicado.
- Excel: aba "Resumo CT-e", com cada CT-e e a quantidade de NF-es.

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
- A Consulta e o Upload abrem dentro da área útil do monitor em que a janela está, sem passar da barra de tarefas em telas menores ou com zoom.
- Consulta: os chips não piscam mais a cada NF-e nem se deslocam ao trocar o filtro.

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
