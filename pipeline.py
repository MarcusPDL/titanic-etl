"""ETL didático do Titanic: extrair, transformar e carregar."""

import argparse
import json
import os
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from dotenv import load_dotenv
from pandas.api.types import is_integer_dtype
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL as DatabaseURL

RAIZ = Path(__file__).resolve().parent
URL = "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv"
URL_CSV_LAB = "http://localhost:8001/passageiros.csv"
CHAVE = "PassengerId"
COLUNAS_API = {"Survived", "Pclass", "Fare"}
COLUNAS = {
    "PassengerId": "id_passageiro", "Survived": "sobreviveu",
    "Pclass": "classe", "Name": "nome", "Sex": "sexo", "Age": "idade",
    "SibSp": "irmaos_conjuges", "Parch": "pais_filhos", "Ticket": "bilhete",
    "Fare": "tarifa", "Embarked": "porto",
}
SEXO = {"male": "masculino", "female": "feminino"}
PORTOS = {"S": "Southampton", "C": "Cherbourg", "Q": "Queenstown"}


def extrair(origem=URL):
    """Aceita uma URL ou um caminho de CSV."""
    dados = pd.read_csv(origem)
    print(f"Chegaram {len(dados)} passageiros.")
    return dados


def extrair_api(url):
    """Consulta a coleção de passageiros e lê a lista de objetos JSON."""
    with urlopen(url, timeout=10) as resposta:
        registros = json.load(resposta)
    if not isinstance(registros, list) or any(not isinstance(item, dict) for item in registros):
        raise ValueError("A API deve retornar uma lista JSON de passageiros.")
    dados = pd.DataFrame(registros)
    print(f"API: chegaram {len(dados)} passageiros.")
    return dados


def integrar_fontes(dados_csv, dados_api):
    """Faz o INNER JOIN com cobertura integral e uma linha por passageiro."""
    fontes = []
    for fonte, dados in (("CSV", dados_csv), ("API", dados_api)):
        if CHAVE not in dados:
            raise ValueError(f"{fonte}: coluna {CHAVE} ausente.")
        ids = pd.to_numeric(dados[CHAVE], errors="coerce")
        if ids.empty or ids.isna().any() or not is_integer_dtype(ids):
            raise ValueError(f"{fonte}: {CHAVE} deve conter identificadores inteiros preenchidos.")
        if not ids.is_unique:
            raise ValueError(f"{fonte}: identificadores duplicados em {CHAVE}.")
        fontes.append(dados.assign(**{CHAVE: ids}))

    csv, api = fontes
    faltantes = COLUNAS_API - set(api.columns)
    if faltantes:
        raise ValueError(f"API: colunas obrigatórias ausentes: {sorted(faltantes)}.")
    sobrepostas = (set(csv.columns) & set(api.columns)) - {CHAVE}
    if sobrepostas:
        raise ValueError(f"CSV e API têm colunas em comum além da chave: {sorted(sobrepostas)}.")

    ids_csv, ids_api = set(csv[CHAVE]), set(api[CHAVE])
    if ids_csv != ids_api:
        raise ValueError(
            f"Identificadores sem correspondência: {len(ids_csv - ids_api)} só no CSV "
            f"e {len(ids_api - ids_csv)} só na API."
        )
    return csv.merge(api, how="inner", on=CHAVE, validate="one_to_one")


def extrair_titanic(origem=None, url_api=None):
    dados = extrair(origem or (URL_CSV_LAB if url_api else URL))
    return integrar_fontes(dados, extrair_api(url_api)) if url_api else dados


def transformar(dados):
    """Traduz sem modificar o DataFrame bruto nem inventar dados ausentes."""
    faltantes = (set(COLUNAS) | {"Cabin"}) - set(dados.columns)
    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(faltantes)}")
    # rename e drop operam na estrutura da tabela.
    dados = dados.rename(columns=COLUNAS).drop(columns=["Cabin"])
    # map opera nos valores de uma coluna. Chaves desconhecidas virariam NaN;
    # por isso validamos os valores antes de traduzir.
    for coluna, mapa in (("sexo", SEXO), ("porto", PORTOS)):
        desconhecidos = set(dados[coluna].dropna().unique()) - set(mapa)
        if desconhecidos:
            raise ValueError(f"Valores desconhecidos em {coluna}: {sorted(desconhecidos)}")
        dados[coluna] = dados[coluna].map(mapa)
    if dados["id_passageiro"].isna().any() or dados["id_passageiro"].duplicated().any():
        raise ValueError("Cada passageiro deve ter um ID preenchido e único.")
    if dados["sobreviveu"].isna().any() or not dados["sobreviveu"].isin([0, 1]).all():
        raise ValueError("sobreviveu deve conter apenas 0 ou 1.")
    return dados


def qualidade(dados):
    return {
        "linhas": len(dados),
        "colunas": len(dados.columns),
        "ausentes_por_coluna": {c: int(n) for c, n in dados.isna().sum().items()},
        "ids_duplicados": int(dados["id_passageiro"].duplicated().sum()),
    }


def criar_engine():
    load_dotenv(RAIZ / ".env", override=False)
    obrigatorias = ["PGDATABASE", "PGUSER", "PGPASSWORD"]
    faltantes = [nome for nome in obrigatorias if not os.getenv(nome)]
    if faltantes:
        raise ValueError("Configure o .env: " + ", ".join(faltantes))
    url = DatabaseURL.create(
        "postgresql+psycopg2", username=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"], host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5433")), database=os.environ["PGDATABASE"],
    )
    return create_engine(url, connect_args={"connect_timeout": 10})


def carregar(dados, engine, substituir=False):
    """Cria passageiros. Uma tabela existente só é substituída explicitamente."""
    with engine.begin() as conexao:
        dados.to_sql(
            "passageiros", conexao, index=False,
            if_exists="replace" if substituir else "fail",
        )
        total = conexao.execute(text("SELECT COUNT(*) FROM passageiros")).scalar_one()
        if total != len(dados):
            raise ValueError("Contagem no banco diferente do DataFrame.")
    print(f"Carregados {total} passageiros no PostgreSQL.")
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", help="URL ou caminho de CSV")
    parser.add_argument("--api", metavar="URL", help="URL da coleção de passageiros (opcional)")
    parser.add_argument("--carregar", action="store_true", help="Gravar no PostgreSQL")
    parser.add_argument("--substituir", action="store_true", help="Substituir a tabela passageiros")
    args = parser.parse_args()
    if args.substituir and not args.carregar:
        parser.error("--substituir exige --carregar")
    try:
        brutos = extrair_titanic(args.origem, args.api)
        limpos = transformar(brutos)
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
    destino = RAIZ / "data"
    destino.mkdir(exist_ok=True)
    brutos.to_csv(destino / "titanic_bruto.csv", index=False)
    limpos.to_csv(destino / "titanic_limpo.csv", index=False)
    relatorio = qualidade(limpos)
    (destino / "qualidade.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    if args.carregar:
        engine = criar_engine()
        try:
            carregar(limpos, engine, substituir=args.substituir)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
