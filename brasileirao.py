"""ETL do Brasileirão: extrair partidas, filtrar por time e ano e carregar."""

import argparse
import json
from numbers import Integral

import pandas as pd
from sqlalchemy import Date, text

from pipeline import RAIZ, criar_engine

URL = (
    "https://raw.githubusercontent.com/adaoduque/Brasileirao_Dataset/"
    "master/campeonato-brasileiro-full.csv"
)
COLUNAS = {
    "ID": "id_jogo",
    "rodata": "rodada",
    "arena": "estadio",
    "mandante_Placar": "gols_mandante",
    "visitante_Placar": "gols_visitante",
    "mandante_Estado": "estado_mandante",
    "visitante_Estado": "estado_visitante",
}
APAGAR = [
    "formacao_mandante", "formacao_visitante",
    "tecnico_mandante", "tecnico_visitante",
]
COLUNAS_DESEJADAS = [
    "id_jogo", "rodada", "data", "hora", "ano", "mandante", "visitante",
    "gols_mandante", "gols_visitante", "vencedor", "estadio",
    "estado_mandante", "estado_visitante",
]


def extrair(origem=URL):
    """Lê a URL pública ou uma cópia local do CSV, sem filtrar as linhas."""
    dados = pd.read_csv(origem)
    print(f"Chegaram {len(dados)} jogos.")
    return dados


def listar_times(dados):
    """Inclui equipes presentes como mandantes ou visitantes."""
    return sorted(set(dados["mandante"].dropna()) | set(dados["visitante"].dropna()))


def transformar(dados, time_desejado, ano_desejado):
    """Filtra pelo ano civil da partida; não confundir com a temporada."""
    obrigatorias = set(COLUNAS) | set(APAGAR) | {
        "data", "hora", "mandante", "visitante", "vencedor",
    }
    faltantes = obrigatorias - set(dados.columns)
    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(faltantes)}")
    if not isinstance(time_desejado, str) or not time_desejado.strip():
        raise ValueError("Informe o nome do time; use --listar-times para consultar.")
    time_desejado = time_desejado.strip()
    if time_desejado not in listar_times(dados):
        raise ValueError(f"Time desconhecido: {time_desejado!r}. Use --listar-times.")
    if isinstance(ano_desejado, bool) or not isinstance(ano_desejado, Integral):
        raise ValueError("O ano deve ser um número inteiro, por exemplo 2022.")

    # Trabalhamos em uma cópia: os dados brutos permanecem disponíveis.
    dados = dados.rename(columns=COLUNAS).drop(columns=APAGAR).copy()
    # O CSV usa dia/mês/ano. errors='raise' impede descartar datas ruins.
    dados["data"] = pd.to_datetime(dados["data"], format="%d/%m/%Y", errors="raise")
    if dados["data"].isna().any():
        raise ValueError("Existem partidas sem data.")
    dados["ano"] = dados["data"].dt.year
    anos = sorted(dados["ano"].unique().tolist())
    if ano_desejado not in anos:
        raise ValueError(f"Ano indisponível: {ano_desejado}. Anos disponíveis: {anos}")

    for coluna in ("id_jogo", "rodada", "gols_mandante", "gols_visitante"):
        valores = pd.to_numeric(dados[coluna], errors="raise")
        if valores.isna().any() or (valores < 0).any() or (valores % 1 != 0).any():
            raise ValueError(f"{coluna} deve conter inteiros não negativos preenchidos.")
        dados[coluna] = valores.astype("int64")
    if dados["id_jogo"].duplicated().any():
        raise ValueError("IDs de jogos duplicados na fonte.")

    filtro_do_time = (
        (dados["mandante"] == time_desejado)
        | (dados["visitante"] == time_desejado)
    )
    filtro_do_ano = dados["ano"] == ano_desejado
    return (
        dados.loc[filtro_do_time & filtro_do_ano, COLUNAS_DESEJADAS]
        .sort_values(["data", "id_jogo"])
        .reset_index(drop=True)
    )


def qualidade(dados):
    return {
        "linhas": len(dados),
        "colunas": len(dados.columns),
        "ids_duplicados": int(dados["id_jogo"].duplicated().sum()),
        "ausentes_por_coluna": {c: int(n) for c, n in dados.isna().sum().items()},
    }


def carregar(dados, engine, substituir=False):
    """Grava o recorte em tabela própria, sem afetar a tabela do Titanic."""
    if dados.empty:
        raise ValueError("O filtro não retornou jogos; nenhuma carga foi feita.")
    with engine.begin() as conexao:
        dados.to_sql(
            "jogos_brasileirao", conexao, index=False, dtype={"data": Date()},
            if_exists="replace" if substituir else "fail",
        )
        total = conexao.execute(text("SELECT COUNT(*) FROM jogos_brasileirao")).scalar_one()
        if total != len(dados):
            raise ValueError("Contagem no banco diferente do DataFrame.")
    print(f"Carregados {total} jogos na tabela jogos_brasileirao.")
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", default=URL, help="URL ou caminho do CSV")
    parser.add_argument("--time", default="Palmeiras", help="Nome exato na fonte")
    parser.add_argument("--ano", type=int, default=2022, help="Ano civil da partida")
    parser.add_argument("--listar-times", action="store_true")
    parser.add_argument("--carregar", action="store_true", help="Gravar no PostgreSQL")
    parser.add_argument("--substituir", action="store_true", help="Recriar jogos_brasileirao")
    args = parser.parse_args()
    if args.substituir and not args.carregar:
        parser.error("--substituir exige --carregar")
    if args.listar_times and (args.carregar or args.substituir):
        parser.error("--listar-times não pode ser combinado com carga")
    try:
        brutos = extrair(args.origem)
        if args.listar_times:
            print("\n".join(listar_times(brutos)))
            return
        limpos = transformar(brutos, args.time, args.ano)
    except (ValueError, KeyError) as erro:
        parser.error(str(erro))

    destino = RAIZ / "data"
    destino.mkdir(exist_ok=True)
    brutos.to_csv(destino / "brasileirao_bruto.csv", index=False)
    # Estes arquivos representam o último filtro executado.
    limpos.to_csv(destino / "brasileirao_filtrado.csv", index=False, date_format="%Y-%m-%d")
    relatorio = {"time": args.time.strip(), "ano": args.ano, **qualidade(limpos)}
    (destino / "brasileirao_qualidade.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    if limpos.empty:
        print("Nenhuma partida encontrada para este time neste ano civil.")
    if args.carregar:
        engine = criar_engine()
        try:
            carregar(limpos, engine, substituir=args.substituir)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
