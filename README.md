# Consulta NF-e / CT-e

Aplicativo desktop para consultar associações NF-e → CT-e via API interna. Desenvolvido com Python e CustomTkinter — sem necessidade de browser ou cópia manual de tokens.

> **Origem:** este projeto foi desenvolvido originalmente para uso interno em uma transportadora. O código foi estruturado de forma genérica (via `.env`) para que qualquer empresa com uma API compatível possa adaptá-lo ao seu ambiente.

## Funcionalidades

- Login automático com e-mail e senha
- Busca por intervalo de NF-e
- Tabela de resultados com status: ✅ Com CT-e / ⚠ Sem CT-e / ❌ Não cadastrada
- Histórico de consultas com restauração em um clique
- Exportação para Excel
- Salvamento seguro de credenciais (Windows Credential Manager)

## Requisitos

- Python 3.10+
- Dependências listadas em `requirements.txt`

## Instalação e execução

```powershell
# 1. Clone o repositório
git clone https://github.com/The-Souza/consulta-nfe-cte.git
cd consulta-nfe-cte

# 2. Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
copy .env.example .env
# Edite o .env com os valores do seu sistema

# 5. Execute
python script.py
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha os valores:

| Variável        | Descrição                                     |
|-----------------|-----------------------------------------------|
| `LOGIN_URL`     | URL do endpoint de login                      |
| `CANHOTOS_URL`  | URL do endpoint de consulta de NF-e           |
| `SIGLA_SISTEMA` | Identificador do sistema (header da requisição) |
| `PROGRAMA`      | Nome do módulo (header da requisição)         |
| `APP_NAME`      | Identificador do app para a barra de tarefas  |
| `APP_SUBTITULO` | Subtítulo exibido na tela de login            |
| `ICON_FILE`     | Nome do arquivo de ícone (ex: `icon.ico`)     |

## Gerando o executável

```powershell
# Instale o PyInstaller
pip install pyinstaller

# Execute o script de build
.\build.ps1
```

O executável será gerado em `dist\consulta-nfe-cte\`. Antes de distribuir, copie seu `.env` e o arquivo de ícone para essa pasta.

> O arquivo `.env` nunca é embutido no executável — ele deve estar na mesma pasta que `consulta-nfe-cte.exe` na máquina de destino.

## Licença

Distribuído sob a licença [MIT](LICENSE). Sinta-se livre para usar, modificar e distribuir.

## Estrutura do projeto

```
consulta-nfe-cte/
├── script.py          # Ponto de entrada
├── api.py             # Chamadas HTTP (login + consulta NF-e)
├── config.py          # Carrega .env e exporta constantes
├── credentials.py     # Armazenamento seguro de credenciais (keyring)
├── build.ps1          # Script de build para gerar o .exe
├── ui/
│   ├── app.py         # Janela principal
│   ├── login_frame.py # Tela de login
│   └── busca_frame.py # Tela de busca
├── .env.example       # Modelo de variáveis de ambiente
└── requirements.txt
```
