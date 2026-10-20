import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from pipeline import COLUNAS, qualidade, transformar


class TransformacaoTest(unittest.TestCase):
    def setUp(self):
        self.brutos = pd.DataFrame({
            "PassengerId": [1, 2], "Survived": [0, 1], "Pclass": [3, 1],
            "Name": ["Pessoa A", "Pessoa B"], "Sex": ["male", "female"],
            "Age": [None, 38.0], "SibSp": [1, 0], "Parch": [0, 0],
            "Ticket": ["A", "B"], "Fare": [7.25, 71.28],
            "Cabin": [None, "C85"], "Embarked": ["S", None],
        })

    def test_traducao_preserva_brutos_linhas_e_ausencias(self):
        copia = self.brutos.copy(deep=True)
        limpos = transformar(self.brutos)
        assert_frame_equal(self.brutos, copia)
        self.assertEqual(list(limpos.columns), list(COLUNAS.values()))
        self.assertEqual(limpos["sexo"].tolist(), ["masculino", "feminino"])
        self.assertEqual(limpos["porto"].iloc[0], "Southampton")
        self.assertEqual(limpos["id_passageiro"].tolist(), [1, 2])
        self.assertEqual(qualidade(limpos)["ausentes_por_coluna"]["idade"], 1)
        self.assertTrue(pd.isna(limpos["porto"].iloc[1]))

    def test_rejeita_categoria_desconhecida(self):
        self.brutos.loc[0, "Sex"] = "valor inesperado"
        with self.assertRaisesRegex(ValueError, "Valores desconhecidos"):
            transformar(self.brutos)

    def test_rejeita_coluna_ausente(self):
        with self.assertRaisesRegex(ValueError, "Colunas obrigatórias"):
            transformar(self.brutos.drop(columns=["Age"]))

    def test_rejeita_id_duplicado(self):
        self.brutos["PassengerId"] = [1, 1]
        with self.assertRaisesRegex(ValueError, "único"):
            transformar(self.brutos)

    def test_rejeita_sobrevivencia_invalida(self):
        self.brutos.loc[0, "Survived"] = 2
        with self.assertRaisesRegex(ValueError, "0 ou 1"):
            transformar(self.brutos)


if __name__ == "__main__":
    unittest.main()
