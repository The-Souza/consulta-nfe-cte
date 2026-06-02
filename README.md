# Consulta NF-e / CT-e — Canhotos

Aplicativo desktop para consultar associações NF-e → CT-e e fazer upload de canhotos via API interna. Desenvolvido com Python e CustomTkinter — sem necessidade de browser ou cópia manual de tokens.

> **Origem:** este projeto foi desenvolvido originalmente para uso interno em uma transportadora. O código foi estruturado de forma genérica (via `.env`) para que qualquer empresa com uma API compatível possa adaptá-lo ao seu ambiente.

## Funcionalidades

### Consulta NF-e / CT-e

- Login automático com e-mail e senha
- Busca por intervalo de NF-e
- Tabela de resultados com status: ✅ Com CT-e / ⚠ Sem CT-e / ❌ Não cadastrada e indicador de imagem cadastrada
- Histórico de consultas com restauração em um clique
- Exportação para Excel
- Salvamento seguro de credenciais (Windows Credential Manager)

### Upload Canhotos

- **Etapa 1 — Renomear:** lê imagens (`.jpg`, `.jpeg` e `.png`) de uma pasta, detecta o número de NF-e via OCR (Tesseract) e renomeia os arquivos para `<nfe>.jpg` em `<pasta>/renomeadas/`
- **Etapa 2 — Upload:** envia os canhotos renomeados para o sistema; NF-es não `PENDENTE` vão para `nao-pendentes/`, enviadas para `pendentes/`
- Input de data com máscara automática (DD/MM/AAAA)
- Histórico de renomeações e uploads com restauração em um clique

## Requisitos

- Python 3.10+
- Dependências listadas em `requirements.txt`
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) instalado (necessário para a etapa de renomear)

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

| Variável         | Descrição                                                                                       |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| `LOGIN_URL`      | URL do endpoint de login                                                                        |
| `CANHOTOS_URL`   | URL do endpoint de consulta/upload de canhotos                                                  |
| `SIGLA_SISTEMA`  | Identificador do sistema (header da requisição)                                                 |
| `PROGRAMA`       | Nome do módulo (header da requisição)                                                           |
| `APP_NAME`       | Identificador do app para a barra de tarefas                                                    |
| `APP_SUBTITLE`   | Subtítulo exibido na tela de login                                                              |
| `ICON_FILE`      | Nome do arquivo de ícone (ex: `icon.ico`)                                                       |
| `TESSERACT_PATH` | Caminho para o executável do Tesseract (padrão: `C:\Program Files\Tesseract-OCR\tesseract.exe`) |

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
├── script.py           # Ponto de entrada
├── api.py              # Chamadas HTTP (login, consulta, upload)
├── ocr.py              # Lógica de OCR para detecção de NF-e em imagens
├── config.py           # Carrega .env e exporta constantes
├── credentials.py      # Armazenamento seguro de credenciais (keyring)
├── build.ps1           # Script de build para gerar o .exe
├── ui/
│   ├── app.py          # Janela principal e navegação entre telas
│   ├── frames/
│   │   ├── login.py    # Tela de login
│   │   ├── home.py     # Tela inicial (escolha de modo)
│   │   ├── search.py   # Tela de consulta NF-e / CT-e
│   │   └── upload.py   # Tela de renomear + upload de canhotos
│   ├── widgets/
│   │   ├── chip.py     # Indicador colorido de contagem
│   │   ├── history.py  # Painel de histórico recolhível
│   │   ├── progress.py # Barra de progresso + label
│   │   ├── table.py    # Cabeçalho e linhas da tabela
│   │   └── topbar.py   # Barra superior com título e botões de navegação
│   └── workers/
│       ├── search.py   # Thread de consulta NF-e
│       ├── rename.py   # Thread de OCR e renomeação
│       └── upload.py   # Thread de upload de canhotos
├── utils/
│   └── excel.py        # Exportação para Excel
├── .env.example        # Modelo de variáveis de ambiente
└── requirements.txt
```
