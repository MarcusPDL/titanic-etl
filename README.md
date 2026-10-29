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

A tabela `jogos_brasileirao` guarda **apenas o recorte selecionado**, com `data` do tipo SQL `DATE`, sem índice adicional do pandas. Uma tabela existente gera erro. Para trocar o recorte, acrescente `--substituir`: isso apaga e recria **somente `jogos_brasileirao`**, sem alterar `passageiros`.

```sql
SELECT COUNT(*) AS jogos, MIN(data) AS primeira_partida,
       MAX(data) AS ultima_partida
FROM jogos_brasileirao;

SELECT mandante, visitante, gols_mandante, gols_visitante
FROM jogos_brasileirao
ORDER BY data, id_jogo;
```

Os testes desta aula verificam o filtro em ambas as posições, datas, preservação dos dados brutos, entradas inválidas e a escrita SQL com SQLite em memória. Esse teste de SQL não substitui a integração PostgreSQL, que depende de um servidor ativo.

Validação em 28/10/2026: **12 testes passaram** (7 do Brasileirão e 5 do Titanic). Todas as células de código de `brasileirao.ipynb` executaram sem erros com o CSV local e a carga desativada. O resultado didático foi comparado ao da função reutilizável. Como verificação adicional, São Paulo em 2023 retornou 38 partidas e Palmeiras no ano civil 2021 retornou 50, reforçando a diferença entre ano e temporada. O Docker continua sem servidor ativo nesta máquina, portanto a carga PostgreSQL permanece não validada.

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
