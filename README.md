# Titanic: aprendendo ETL com Python

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

## Referências

- [CSV fornecido na aula](https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv)
- [Repositório de origem e atribuição](https://github.com/datasciencedojo/datasets)
- [pandas.read_csv](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html)
- [DataFrame.rename](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rename.html)
- [DataFrame.drop](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop.html)
- [Series.map](https://pandas.pydata.org/docs/reference/api/pandas.Series.map.html): valores fora do dicionário viram ausentes.
- [DataFrame.to_sql](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html)

O repositório é local; não foi publicado no GitHub. O CSV é baixado da fonte durante a execução, sem redistribuí-lo no histórico Git.
