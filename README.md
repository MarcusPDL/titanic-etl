# Pipelines ETL com Python: Titanic e Brasileirão

Repositório das aulas de Banco de Dados. Os dois exercícios compartilham o ambiente virtual e a conexão PostgreSQL:

| Aula | Notebook | Código | Tabela |
| --- | --- | --- | --- |
| 1 — Titanic | [bdia_titanic.ipynb](bdia_titanic.ipynb) | [pipeline.py](pipeline.py) | `passageiros` |
| 2 — Brasileirão | [brasileirao.ipynb](brasileirao.ipynb) | [brasileirao.py](brasileirao.py) | `jogos_brasileirao` |

## Aula 1 — Titanic

Este projeto transforma as anotações da aula em um exercício executável. O foco é entender a preparação dos dados: nomes em inglês, valores categóricos e informações ausentes. Não treinamos um modelo de machine learning nesta etapa.

ETL significa **Extrair → Transformar → Carregar**. Como numa cozinha, cada etapa prepara o que a próxima precisa: buscar os ingredientes, prepará-los e guardá-los para uso.

## Começar no Windows (PowerShell)

Na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name titanic-etl --display-name "Python (Titanic ETL)"
```

Abra `bdia_titanic.ipynb` no VS Code ou Jupyter, selecione **Python (Titanic ETL)** e execute as células em ordem. O notebook usa `%pip`, que instala no ambiente do kernel selecionado. Confira `sys.executable` antes de instalar. O notebook também mostra a transformação passo a passo; `pipeline.py` reúne as funções reutilizáveis.

Para executar sem notebook:

```powershell
.\.venv\Scripts\python.exe pipeline.py
```

A primeira execução precisa de internet. Gera `data/titanic_bruto.csv`, `data/titanic_limpo.csv` e `data/qualidade.json`, ignorados pelo Git. Para repetir offline:

```powershell
.\.venv\Scripts\python.exe pipeline.py --origem data/titanic_bruto.csv
```

O notebook prefere a cópia local quando ela existe. Nesta máquina, o acesso HTTPS pelo Python apresentou um certificado incompatível com o domínio de origem. O CSV foi baixado pelo PowerShell e usado localmente; a verificação de certificados não foi desativada. Se precisar baixar novamente em uma rede com esse problema:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv' -OutFile 'data/titanic_bruto.csv' -UseBasicParsing
```

## Decisões da transformação

- `rename(columns=COLUNAS)` muda os nomes das colunas usando um dicionário: chave antiga → nome novo.
- `drop(columns=["Cabin"])` remove a cabine, conforme o exercício. É uma escolha didática, não uma regra universal de análise.
- `map(SEXO)` traduz `male` e `female`; `map(PORTOS)` expande os códigos dos portos. Os nomes das cidades permanecem como no material.
- As linhas e os IDs são preservados. Idades e portos ausentes continuam ausentes; preencher com mediana ou moda exigiria uma decisão explícita e alteraria os dados.
- `sobreviveu` mantém `0` (não) e `1` (sim); `classe` é a classe da passagem. `irmaos_conjuges` e `pais_filhos` representam familiares a bordo. `tarifa` é o valor da passagem.
- Valores categóricos desconhecidos e IDs duplicados geram erro, evitando que problemas desapareçam silenciosamente.

Na verificação de 20/10/2026, o CSV contém **891 passageiros e 12 colunas**, com **177 idades**, **687 cabines** e **2 portos** ausentes. Após excluir `Cabin`, ficam 11 colunas. A contagem de passageiros e as lacunas são verificadas na execução, sem fixar o número das anotações. `isna().sum()` conta ausências por coluna: primeiro cria indicadores booleanos, depois os soma.

## PostgreSQL

É necessário um servidor PostgreSQL disponível. Para usar o Docker Desktop, inicie-o e execute:

```powershell
Copy-Item .env.example .env
# Edite PGPASSWORD no .env antes de iniciar.
docker compose up -d --wait
.\.venv\Scripts\python.exe pipeline.py --carregar
```

O banco do exercício é `bdia_titanic`, na porta local `5433`; a tabela é `passageiros`. Para um servidor existente, ajuste as variáveis `PG*` no `.env`. A senha nunca deve ser adicionada ao Git. A URL de conexão é construída com SQLAlchemy, aceitando caracteres especiais na senha.

Por padrão, uma tabela existente causa erro. Para refazer a carga, **apagando e recriando apenas a tabela `passageiros`**, use explicitamente:

```powershell
.\.venv\Scripts\python.exe pipeline.py --carregar --substituir
```

A escrita e a conferência da contagem ficam na mesma transação. A opção `index=False` impede gravar o índice do pandas como uma coluna adicional. Valores ausentes são gravados como `NULL`.

Consulta para conferir no seu cliente SQL:

```sql
SELECT COUNT(*) AS passageiros,
       COUNT(*) - COUNT(idade) AS idades_ausentes,
       COUNT(*) - COUNT(porto) AS portos_ausentes
FROM passageiros;
```

## Verificar o projeto

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes verificam preservação dos dados brutos e das lacunas, traduções e rejeição de entradas inválidas. Eles não substituem um teste de integração com PostgreSQL.

Validação local em 20/10/2026: os cinco testes passaram e o pipeline executou sobre o CSV baixado, gerando 891 linhas e 11 colunas, sem IDs duplicados. Todas as células do notebook também executaram sem erros, usando o CSV local e com a carga desativada. Ambiente: Python 3.10.6, pandas 2.3.3 e SQLAlchemy 2.0.55; `pip check` não encontrou dependências incompatíveis. A carga no PostgreSQL ainda não foi validada: o Docker não estava em execução e nenhum servidor foi configurado.

## Aula 2 — Brasileirão: filtrar por time e ano

A continuação baixa todas as partidas da fonte, corrige os nomes das colunas, remove técnicos e formações e seleciona jogos de um time em um ano. Abra `brasileirao.ipynb` para acompanhar cada etapa.

O CSV verificado em **28/10/2026** tem **8.785 jogos, 16 colunas e datas de 2003 a 2024**. O recorte **Palmeiras, 2022** contém **38 jogos e 13 colunas**. Não esperamos 17 colunas na fonte: ao criar `ano` antes de remover outras colunas, uma tabela intermediária pode chegar a 17.

```powershell
# Baixar a fonte e executar o exemplo da aula:
.\.venv\Scripts\python.exe brasileirao.py --time Palmeiras --ano 2022

# Descobrir a grafia das equipes (mandantes e visitantes):
.\.venv\Scripts\python.exe brasileirao.py --origem data/brasileirao_bruto.csv --listar-times

# Repetir offline com outros parâmetros:
.\.venv\Scripts\python.exe brasileirao.py --origem data/brasileirao_bruto.csv --time "Sao Paulo" --ano 2023
```

O nome do time deve corresponder à fonte, incluindo maiúsculas e acentos. `--listar-times` mostra as opções; por exemplo, a fonte usa `Sao Paulo`, `Gremio` e `Palmeiras`. Um nome desconhecido ou ano indisponível gera erro explicativo. Um time existente sem partidas no ano escolhido retorna um recorte vazio, que não é carregado no banco.

Se a rede apresentar o mesmo problema de certificado descrito na aula 1, faça o download pelo PowerShell e use `--origem`:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/adaoduque/Brasileirao_Dataset/master/campeonato-brasileiro-full.csv' -OutFile 'data/brasileirao_bruto.csv'
.\.venv\Scripts\python.exe brasileirao.py --origem data/brasileirao_bruto.csv --time Palmeiras --ano 2022
```

### Transformações

| Nome na fonte | Nome padronizado |
| --- | --- |
| `ID` | `id_jogo` |
| `rodata` | `rodada` |
| `arena` | `estadio` |
| `mandante_Placar` | `gols_mandante` |
| `visitante_Placar` | `gols_visitante` |
| `mandante_Estado` | `estado_mandante` |
| `visitante_Estado` | `estado_visitante` |

Removemos `formacao_mandante`, `formacao_visitante`, `tecnico_mandante` e `tecnico_visitante`. A data é validada no formato `DD/MM/AAAA`, e `ano` é extraído com `.dt.year`. O notebook também demonstra `.str[-4:].astype(int)`, como nas anotações. Os dados brutos ficam preservados, os IDs são conferidos e o resultado é ordenado por data e ID.

O filtro central combina **OU** entre mandante e visitante e **E** com o ano, sempre usando parênteses:

```python
filtro_do_time = (dados["mandante"] == TIME) | (dados["visitante"] == TIME)
filtro_do_ano = dados["ano"] == ANO
recorte = dados.loc[filtro_do_time & filtro_do_ano, COLUNAS_DESEJADAS]
```

**Ano civil não é temporada:** o filtro usa a data em que a partida foi disputada. A fonte tem jogos da temporada 2020 realizados em 2021. Não imponha 38 como limite: isso varia com o calendário e o formato do campeonato; em 2003 e 2004, por exemplo, uma equipe podia disputar 46 jogos. A fonte não possui uma coluna explícita de temporada, e o pipeline não tenta adivinhá-la.

### Arquivos gerados e carga

O script salva `data/brasileirao_bruto.csv`, `data/brasileirao_filtrado.csv` e `data/brasileirao_qualidade.json`. O CSV filtrado e o relatório representam o último filtro executado; os arquivos do Titanic têm nomes separados. Datas exportadas usam `AAAA-MM-DD`.

Após configurar `.env` e iniciar o PostgreSQL:

```powershell
.\.venv\Scripts\python.exe brasileirao.py --origem data/brasileirao_bruto.csv --time Palmeiras --ano 2022 --carregar
```

A carga grava as partidas do **recorte selecionado** em `jogos_brasileirao`. A tabela acumula as partidas de recortes sucessivos. `id_jogo` é a chave primária, `data` usa o tipo SQL `DATE` e `hora` mantém o texto do CSV. Campos opcionais ausentes são gravados como `NULL`. Na primeira carga sobre uma tabela criada pela versão anterior, o PostgreSQL acrescenta a chave primária e preserva as partidas existentes.

O PostgreSQL usa `INSERT ... ON CONFLICT (id_jogo) DO UPDATE` para atualizar uma partida já gravada. Assim, carregar o mesmo recorte de novo ou carregar um adversário que jogou as mesmas partidas mantém uma linha por jogo. A mensagem do script conta os jogos processados no recorte. Para deixar na tabela apenas o novo recorte, acrescente `--substituir`. A exclusão e a carga ficam na mesma transação.

```sql
SELECT COUNT(*) AS jogos, MIN(data) AS primeira_partida,
       MAX(data) AS ultima_partida
FROM jogos_brasileirao
WHERE ano = 2022 AND (mandante = 'Palmeiras' OR visitante = 'Palmeiras');

SELECT mandante, visitante, gols_mandante, gols_visitante
FROM jogos_brasileirao
WHERE ano = 2022 AND (mandante = 'Palmeiras' OR visitante = 'Palmeiras')
ORDER BY data, id_jogo;
```

Com a base da aula, a primeira consulta retorna 38 partidas. Os testes locais usam SQLite em memória e verificam o filtro, a chave primária, a recarga, a sobreposição entre recortes, a compatibilidade com a tabela anterior e a reversão da substituição em caso de falha.

Na validação da transformação em 28/10/2026, o notebook executou com o CSV local e a carga desativada. São Paulo em 2023 retornou 38 partidas e Palmeiras no ano civil 2021 retornou 50.

## Aula 3 — Titanic com CSV e API

Na aula de 24/11/2026, duas fontes complementares descrevem os mesmos passageiros. O CSV fornece nome, sexo, idade, parentes a bordo, bilhete, cabine e porto. A API fornece sobrevivência (`Survived`), classe (`Pclass`) e tarifa (`Fare`). Ambas trazem `PassengerId`, a chave usada para associar cada passageiro independentemente da ordem das linhas.

### Iniciar as fontes locais

Os comandos abaixo pressupõem a pasta `../../fontes_titanic/` com os arquivos e Dockerfiles fornecidos na aula. Ajuste os caminhos dos contextos de build conforme a localização dessa pasta no seu computador. Com o Docker Desktop em execução, rode os comandos na pasta deste exercício. Cada contêiner escuta internamente na porta 8000. As portas 8001 e 8002 do computador permitem acessar os dois serviços em paralelo.

```powershell
docker build -t titanic-csv ../../fontes_titanic/csv
docker build -t titanic-api ../../fontes_titanic/api
docker run -d --rm --name titanic-csv -p 127.0.0.1:8001:8000 titanic-csv
docker run -d --rm --name titanic-api -p 127.0.0.1:8002:8000 titanic-api
```

### Integrar e carregar

```powershell
.\.venv\Scripts\python.exe pipeline.py --api http://localhost:8002/passageiros
```

Com `--api`, o CSV padrão é `http://localhost:8001/passageiros.csv`. Use `--origem ../../fontes_titanic/csv/passageiros.csv` para ler o arquivo diretamente e manter a consulta à API. O endereço `http://localhost:8002/passageiros/1` consulta um único passageiro. O pipeline usa a rota da coleção e lê a resposta JSON com a biblioteca padrão do Python.

Antes do `merge`, o código verifica se os IDs são inteiros, preenchidos, únicos e correspondem entre as duas fontes. Mesmo com o mesmo número de linhas, duas fontes podem trazer passageiros diferentes. `validate="one_to_one"` reforça a unicidade dos dois lados da junção. O CSV e a API da aula têm 891 passageiros cada. O resultado integrado tem 12 colunas e, após a transformação, 11.

O script grava o CSV integrado em `data/titanic_bruto.csv`, o tratado em `data/titanic_limpo.csv` e o relatório em `data/qualidade.json`. Para gravar também na tabela `passageiros`, prepare o [PostgreSQL](#postgresql) e acrescente `--carregar`. A consulta SQL da Aula 1 também serve para conferir essa carga.

### Revisão da aula

| Conceito | Aplicação no laboratório |
| --- | --- |
| Extração | Ler o CSV e pedir à API a lista de passageiros com HTTP GET. |
| Transformação | Validar chaves, aplicar o INNER JOIN e limpar os dados integrados. |
| Carregamento | Gravar o resultado em arquivo ou, com `--carregar`, no PostgreSQL. |
| Status HTTP | 200 indica sucesso, 404 indica recurso ausente e 500 indica erro interno do servidor. |
| Tipos de JOIN | INNER preserva as correspondências. LEFT preserva as chaves da esquerda, RIGHT as da direita e OUTER as de ambos os lados. |
| Variável-alvo | `Survived` é o rótulo `y`. Características como classe, sexo e tarifa podem compor `X`. |

## Aula 4 — Treino e teste em SQLite

[O script](titanic_sqlite.py) reaproveita a extração e a integração da Aula 3. Execute na pasta deste exercício. O comando usa o CSV e a API locais e grava os bancos em `data/`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe titanic_sqlite.py --api http://localhost:8002/passageiros
```

Para repetir sem Docker, use o CSV completo já salvo pela Aula 1 ou integrado pela Aula 3.

```powershell
.\.venv\Scripts\python.exe titanic_sqlite.py --origem data/titanic_bruto.csv
```

O script seleciona classe, sexo, idade, irmãos e cônjuges, pais e filhos e tarifa como características. Codifica sexo como 0 ou 1 e separa `sobreviveu` como alvo. A divisão é de 80% para treino e 20% para teste, com semente 42. Imputação por mediana e padronização aprendem seus parâmetros só no treino para evitar vazamento de dados.

| Banco | Tabelas | Conteúdo |
| --- | --- | --- |
| `titanic.db` | `x_treino`, `x_teste`, `y_treino`, `y_teste` | Características tratadas na escala original e seus rótulos. |
| `titanic_esc.db` | As mesmas quatro tabelas | Características padronizadas com `StandardScaler`, com os mesmos passageiros e rótulos. |

Cada carga substitui as quatro tabelas de um arquivo em uma transação SQLite. Para escolher outra pasta, use `--destino`. Na base da aula, cada arquivo contém **712 passageiros no treino e 179 no teste**. O SQLite grava em arquivo local. A função de leitura ordena as tabelas por `id_passageiro` e confere a correspondência entre as características e os rótulos.

```python
from titanic_sqlite import ler_sqlite

conjuntos = ler_sqlite("data/titanic_esc.db")
x_treino, y_treino = conjuntos["x_treino"], conjuntos["y_treino"]
```

O exercício termina na preparação dos conjuntos. Segundo as anotações, a prova é conceitual e o trabalho final pode ser apresentado pelo notebook, com células Markdown explicando as etapas. O enunciado, os critérios e o prazo exato do trabalho ficaram em aberto no material.

## Referências

- [CSV fornecido na aula](https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv)
- [Repositório de origem e atribuição](https://github.com/datasciencedojo/datasets)
- [pandas.read_csv](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html)
- [DataFrame.rename](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rename.html)
- [DataFrame.drop](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop.html)
- [Series.map](https://pandas.pydata.org/docs/reference/api/pandas.Series.map.html): valores fora do dicionário viram ausentes.
- [DataFrame.to_sql](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html)

- [Brasileirão: repositório da fonte](https://github.com/adaoduque/Brasileirao_Dataset)
- [Brasileirão: CSV usado na aula](https://raw.githubusercontent.com/adaoduque/Brasileirao_Dataset/master/campeonato-brasileiro-full.csv)
- [pandas.to_datetime](https://pandas.pydata.org/pandas-docs/version/2.3/reference/api/pandas.to_datetime.html)
- [Filtros booleanos no pandas](https://pandas.pydata.org/pandas-docs/version/2.3/user_guide/indexing.html#boolean-indexing)

Os CSVs são baixados das fontes durante a execução, sem redistribuí-los no histórico Git. Credenciais, ambientes virtuais e relatórios gerados também ficam fora do Git.
