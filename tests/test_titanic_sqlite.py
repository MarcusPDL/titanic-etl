from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from titanic_sqlite import carregar_sqlite, ler_sqlite, preparar


class TitanicSQLiteTest(unittest.TestCase):
    def setUp(self):
        self.dados = pd.DataFrame({
            "id_passageiro": range(1, 11),
            "classe": [1, 2, 3, 1, 2, 3, 1, 2, 3, 1],
            "sexo": ["masculino", "feminino"] * 5,
            "idade": [20, 900, None, 30, 40, 50, 60, 70, None, 80],
            "irmaos_conjuges": [0, 1] * 5,
            "pais_filhos": [0] * 10,
            "tarifa": range(10, 20),
            "sobreviveu": [0, 1] * 5,
        })

    def test_imputacao_e_escala_usam_so_o_treino(self):
        original = self.dados.copy(deep=True)
        sem_escala, com_escala = preparar(self.dados)
        treino, teste = sem_escala["x_treino"], sem_escala["x_teste"]
        self.assertEqual(set(teste.index), {2, 9})
        self.assertTrue(treino.index.intersection(teste.index).empty)
        self.assertEqual(treino.loc[3, "idade"], 50)
        self.assertEqual(teste.loc[9, "idade"], 50)
        esperado = (teste["idade"] - treino["idade"].mean()) / treino["idade"].std(ddof=0)
        assert_series_equal(com_escala["x_teste"]["idade"], esperado)
        self.assertTrue(com_escala["x_teste"]["pais_filhos"].eq(0).all())
        assert_series_equal(com_escala["y_teste"], sem_escala["y_teste"])
        assert_frame_equal(self.dados, original)

    def test_recupera_por_id_e_reverte_uma_recarga_incompleta(self):
        sem_escala, com_escala = preparar(self.dados)
        with TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "titanic.db"
            carregar_sqlite(arquivo, sem_escala)
            obtidos = ler_sqlite(arquivo)
            for particao in ("treino", "teste"):
                x, y = f"x_{particao}", f"y_{particao}"
                assert_frame_equal(obtidos[x], sem_escala[x].sort_index())
                assert_series_equal(obtidos[y], sem_escala[y].sort_index())

            to_sql = pd.DataFrame.to_sql

            def falhar_no_teste(dataframe, name, *args, **kwargs):
                if name == "x_teste":
                    raise RuntimeError("falha de escrita")
                return to_sql(dataframe, name, *args, **kwargs)

            with patch.object(pd.DataFrame, "to_sql", falhar_no_teste):
                with self.assertRaisesRegex(RuntimeError, "falha de escrita"):
                    carregar_sqlite(arquivo, com_escala)
            assert_frame_equal(ler_sqlite(arquivo)["x_treino"], obtidos["x_treino"])
