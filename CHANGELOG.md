# Changelog

Todas as mudanças relevantes do projeto ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/). As versões anteriores à 2.0.0 estão descritas nas [releases do GitHub](https://github.com/The-Souza/consulta-nfe-cte/releases).

## [2.0.0-alpha.0] — em andamento

### Adicionado
- Versão do app definida em `config.py` (`APP_VERSION`).
- Ferramentas de desenvolvimento: `ruff` para lint e `pytest` para testes (`requirements-dev.txt`).
- CI no GitHub Actions: lint e testes em todo push e PR para `develop` e `master`.

### Alterado
- Tags com hífen (ex.: `v2.0.0-alpha.0`) geram o executável como pré-lançamento. O link de download do README continua apontando para a última versão estável.
