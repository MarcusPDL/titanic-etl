import unittest

import pandas as pd
from pandas.testing import assert_frame_equal
from sqlalchemy import Date, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from brasileirao import APAGAR, COLUNAS_DESEJADAS, carregar, listar_times, transformar


class BrasileiraoTest(unittest.TestCase):
    def setUp(self):
        self.brutos = pd.DataFrame({
            "ID": [3, 1, 2, 4, 5], "rodata": [2, 1, 1, 3, 4],
            "data": ["15/04/2022", "10/04/2022", "11/04/2022", "01/01/2021", "20/05/2023"],
            "hora": ["16:00"] * 5,
            "mandante": ["Santos", "Palmeiras", "Santos", "Palmeiras", "Palmeiras"],
            "visitante": ["Palmeiras", "Santos", "Flamengo", "Santos", "Santos"],
            "formacao_mandante": [None] * 5, "formacao_visitante": [None] * 5,
            "tecnico_mandante": [None] * 5, "tecnico_visitante": [None] * 5,
            "vencedor": ["Palmeiras", "-", "Santos", "Palmeiras", "Santos"],
            "arena": ["Estádio de teste"] * 5,
            "mandante_Placar": [0, 1, 2, 1, 0], "visitante_Placar": [1, 1, 0, 0, 1],
            "mandante_Estado": ["SP"] * 5, "visitante_Estado": ["SP", "SP", "RJ", "SP", "SP"],
        })

    def test_filtra_mandante_ou_visitante_e_ano_sem_alterar_brutos(self):
        copia = self.brutos.copy(deep=True)
        dados = transformar(self.brutos, " Palmeiras ", 2022)
        assert_frame_equal(self.brutos, copia)
        self.assertEqual(dados["id_jogo"].tolist(), [1, 3])
        self.assertEqual(dados.columns.tolist(), COLUNAS_DESEJADAS)
        self.assertEqual(dados["ano"].tolist(), [2022, 2022])
        self.assertEqual(dados["gols_mandante"].tolist(), [1, 0])
        self.assertEqual(dados["vencedor"].tolist(), ["-", "Palmeiras"])
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(dados["data"]))
        self.assertTrue(all(c not in dados for c in APAGAR))

    def test_lista_time_presente_apenas_como_visitante(self):
        self.assertIn("Flamengo", listar_times(self.brutos))

    def test_converte_dia_mes_sem_inverter_e_usa_ano_civil(self):
        dados = transformar(self.brutos, "Palmeiras", 2021)
        self.assertEqual(dados["id_jogo"].tolist(), [4])
        self.assertEqual(dados["data"].iloc[0], pd.Timestamp("2021-01-01"))
        dados = transformar(self.brutos, "Palmeiras", 2022)
        self.assertEqual(dados["data"].iloc[0], pd.Timestamp("2022-04-10"))

    def test_time_sem_jogos_no_ano_retorna_tabela_vazia_com_esquema(self):
        dados = transformar(self.brutos, "Flamengo", 2023)
        self.assertTrue(dados.empty)
        self.assertEqual(dados.columns.tolist(), COLUNAS_DESEJADAS)

    def test_rejeita_time_ano_data_e_id_invalidos(self):
        for time, ano in (("Inexistente", 2022), ("Palmeiras", 1999), ("Palmeiras", 2022.5)):
            with self.subTest(time=time, ano=ano), self.assertRaises(ValueError):
                transformar(self.brutos, time, ano)
        for data in ("31/02/2022", None):
            dados = self.brutos.copy()
            dados.loc[0, "data"] = data
            with self.subTest(data=data), self.assertRaises(ValueError):
                transformar(dados, "Palmeiras", 2022)
        dados = self.brutos.copy()
        dados.loc[0, "ID"] = 1
        with self.assertRaisesRegex(ValueError, "duplicados"):
            transformar(dados, "Palmeiras", 2022)

    def test_rejeita_coluna_obrigatoria_ausente(self):
        with self.assertRaisesRegex(ValueError, "obrigatórias"):
            transformar(self.brutos.drop(columns=["arena"]), "Palmeiras", 2022)

    def test_carga_acumula_recortes_e_atualiza_partidas_sem_duplicar(self):
        # SQLite valida o contrato SQL local, não substitui integração PostgreSQL.
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        dados = transformar(self.brutos, "Palmeiras", 2022)
        self.assertEqual(carregar(dados, engine), 2)
        self.assertEqual(carregar(dados, engine), 2)
        self.assertEqual(
            [c["name"] for c in inspect(engine).get_columns("jogos_brasileirao")],
            COLUNAS_DESEJADAS,
        )
        self.assertEqual(
            inspect(engine).get_pk_constraint("jogos_brasileirao")["constrained_columns"],
            ["id_jogo"],
        )

        santos = transformar(self.brutos, "Santos", 2022)
        santos.loc[santos["id_jogo"] == 1, ["estadio", "gols_mandante"]] = [None, 2]
        self.assertEqual(carregar(santos, engine), 3)
        with engine.connect() as conexao:
            jogos = conexao.execute(text(
                "SELECT id_jogo, data, estadio, gols_mandante FROM jogos_brasileirao ORDER BY id_jogo"
            )).all()
            self.assertEqual([jogo.id_jogo for jogo in jogos], [1, 2, 3])
            self.assertEqual(jogos[0], (1, "2022-04-10", None, 2))

        # Uma falha na substituição deve reverter também a exclusão anterior.
        invalido = dados.assign(mandante=None)
        with self.assertRaises(IntegrityError):
            carregar(invalido, engine, substituir=True)
        with engine.connect() as conexao:
            self.assertEqual(conexao.scalar(text("SELECT COUNT(*) FROM jogos_brasileirao")), 3)

        self.assertEqual(carregar(dados.iloc[:1], engine, substituir=True), 1)
        with engine.connect() as conexao:
            self.assertEqual(conexao.scalar(text("SELECT COUNT(*) FROM jogos_brasileirao")), 1)
        with self.assertRaisesRegex(ValueError, "nenhuma carga"):
            carregar(dados.iloc[:0], engine)

    def test_carga_preserva_partidas_da_tabela_criada_com_pandas(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        dados = transformar(self.brutos, "Palmeiras", 2022)
        dados.to_sql("jogos_brasileirao", engine, index=False, dtype={"data": Date()})

        novo_recorte = transformar(self.brutos, "Palmeiras", 2021)
        self.assertEqual(carregar(novo_recorte, engine), 1)
        self.assertEqual(carregar(novo_recorte, engine), 1)
        with engine.connect() as conexao:
            ids = conexao.scalars(text("SELECT id_jogo FROM jogos_brasileirao ORDER BY id_jogo"))
            self.assertEqual(ids.all(), [1, 3, 4])
