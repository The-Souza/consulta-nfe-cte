# Changelog

Todas as mudanças relevantes do projeto ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/). As versões anteriores à 2.0.0 estão descritas nas [releases do GitHub](https://github.com/The-Souza/consulta-nfe-cte/releases).

## [2.0.0-alpha.0] — em andamento

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
