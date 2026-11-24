"""Prepara treino e teste do Titanic e grava as duas versões em SQLite."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from pipeline import RAIZ, extrair_titanic, transformar

ID = "id_passageiro"
ALVO = "sobreviveu"
COLUNAS_X = ["classe", "sexo", "idade", "irmaos_conjuges", "pais_filhos", "tarifa"]
TABELAS = ("x_treino", "x_teste", "y_treino", "y_teste")


def preparar(dados):
    """Recebe a saída de transformar e retorna os conjuntos nas duas escalas."""
    dados = dados.set_index(ID)
    if dados.index.hasnans or not dados.index.is_unique:
        raise ValueError("Cada passageiro deve ter um ID preenchido e único.")
    x = dados[COLUNAS_X].copy()
    x["sexo"] = x["sexo"].map({"masculino": 0, "feminino": 1})
    x_treino, x_teste, y_treino, y_teste = train_test_split(
        x, dados[ALVO], test_size=0.2, random_state=42
    )

    mediana = x_treino["idade"].median()
    if pd.isna(mediana):
        raise ValueError("Não há idades válidas no treino para calcular a mediana.")
    x_treino = x_treino.fillna({"idade": mediana})
    x_teste = x_teste.fillna({"idade": mediana})
    if x_treino.isna().any().any() or x_teste.isna().any().any():
        raise ValueError("Ainda há valores ausentes nas características após imputar a idade.")

    sem_escala = dict(zip(TABELAS, (x_treino, x_teste, y_treino, y_teste)))
    padronizador = StandardScaler().fit(x_treino)
    padronizados = {
        nome: pd.DataFrame(
            padronizador.transform(conjunto), index=conjunto.index, columns=conjunto.columns
        )
        for nome, conjunto in (("x_treino", x_treino), ("x_teste", x_teste))
    }
    return sem_escala, sem_escala | padronizados


def verificar_indices(conjuntos):
    for particao in ("treino", "teste"):
        x = conjuntos[f"x_{particao}"].index
        y = conjuntos[f"y_{particao}"].index
        if x.empty or x.hasnans or not x.is_unique or not x.equals(y):
            raise ValueError(f"IDs inválidos ou X e y desalinhados em {particao}.")
    if not conjuntos["x_treino"].index.intersection(conjuntos["x_teste"].index).empty:
        raise ValueError("Há passageiros presentes no treino e no teste.")


def carregar_sqlite(arquivo, conjuntos):
    verificar_indices(conjuntos)
    engine = create_engine(URL.create("sqlite", database=str(arquivo)))
    try:
        with engine.begin() as conexao:
            # O BEGIN explícito inclui as operações de criação de tabela na transação.
            conexao.exec_driver_sql("BEGIN IMMEDIATE")
            for tabela in TABELAS:
                conjuntos[tabela].to_sql(
                    tabela, conexao, if_exists="replace", index_label=ID
                )
    finally:
        engine.dispose()


def ler_sqlite(arquivo):
    """Recupera os conjuntos ordenados pelo mesmo ID e verifica o alinhamento."""
    uri = Path(arquivo).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conexao, conexao:
        conexao.execute("BEGIN")
        conjuntos = {
            tabela: pd.read_sql_query(
                f"SELECT * FROM {tabela} ORDER BY {ID}", conexao, index_col=ID
            )
            for tabela in TABELAS
        }
    verificar_indices(conjuntos)
    conjuntos["y_treino"] = conjuntos["y_treino"][ALVO]
    conjuntos["y_teste"] = conjuntos["y_teste"][ALVO]
    return conjuntos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", help="URL ou caminho de CSV")
    parser.add_argument("--api", metavar="URL", help="URL da coleção de passageiros")
    parser.add_argument("--destino", type=Path, default=RAIZ / "data", help="Pasta dos bancos")
    args = parser.parse_args()
    try:
        dados = transformar(extrair_titanic(args.origem, args.api))
        sem_escala, com_escala = preparar(dados)
        args.destino.mkdir(parents=True, exist_ok=True)
        for nome, conjuntos in (("titanic.db", sem_escala), ("titanic_esc.db", com_escala)):
            arquivo = args.destino / nome
            carregar_sqlite(arquivo, conjuntos)
            print(f"{arquivo}: {len(conjuntos['x_treino'])} no treino e "
                  f"{len(conjuntos['x_teste'])} no teste.")
    except (OSError, ValueError, SQLAlchemyError) as erro:
        parser.error(str(erro))


if __name__ == "__main__":
    main()
