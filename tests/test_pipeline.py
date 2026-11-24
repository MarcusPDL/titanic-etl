import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from pipeline import COLUNAS, integrar_fontes, qualidade, transformar


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

    def test_integra_por_id_com_api_fora_de_ordem(self):
        campos_api = ["PassengerId", "Survived", "Pclass", "Fare"]
        csv = self.brutos.drop(columns=campos_api[1:])
        api = self.brutos[campos_api].iloc[::-1].assign(PassengerId=["2", "1"])

        integrados = integrar_fontes(csv, api)
        assert_frame_equal(integrados[self.brutos.columns], self.brutos)
        self.assertEqual(api["PassengerId"].tolist(), ["2", "1"])
        self.assertEqual(transformar(integrados)["sobreviveu"].tolist(), [0, 1])

    def test_rejeita_fontes_com_chaves_invalidas_ou_sem_correspondencia(self):
        campos_api = ["PassengerId", "Survived", "Pclass", "Fare"]
        csv = self.brutos.drop(columns=campos_api[1:])
        api = self.brutos[campos_api]
        for ids, mensagem in (
            ([1, None], "inteiros preenchidos"),
            ([1, 2.5], "inteiros preenchidos"),
            ([1, "01"], "duplicados"),
            ([1, 3], "sem correspondência"),
        ):
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, mensagem):
                integrar_fontes(csv, api.assign(PassengerId=ids))
        with self.assertRaisesRegex(ValueError, "PassengerId ausente"):
            integrar_fontes(csv.drop(columns="PassengerId"), api)
        with self.assertRaisesRegex(ValueError, "Survived"):
            integrar_fontes(csv, api.drop(columns="Survived"))


if __name__ == "__main__":
    unittest.main()
