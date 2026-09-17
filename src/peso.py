"""
peso.py
-------
Gera o dataset de modelagem para previsao do PESO do camarao, no formato do
estudo de Mujahid et al. (2025): uma linha por biometria (pesagem real), tendo
os dias de cultivo (DoC) como principal preditor temporal.

Diferente do modelo de sobrevivencia (uma linha por cultivo), aqui cada pesagem
e um exemplo, o que aproveita todas as 2000+ biometrias e permite ao modelo
aprender a curva de crescimento ao longo do tempo.

Feature-chave: a racao ACUMULADA ate cada pesagem (nao a diaria), que resume o
esforco alimentar total do cultivo ate aquele momento.

Uso:
    python -m src.peso
"""

import pandas as pd
import numpy as np

from src.config import CSV_TRATADO, DIR_PROCESSED

CSV_PESO = DIR_PROCESSED / "dataset_peso.csv"

# preditor temporal, manejo e ambiente
FEATURES_PESO = ["DIAS", "RACAO_ACUM", "RACAO_ACUM_POR_PL", "DENSIDADE_PL_M2",
                 "SUP_05", "TEMP_05", "PH_05", "SAL_14"]
ALVO_PESO = "PESO"


def construir_dataset_peso():
    df = pd.read_csv(CSV_TRATADO, low_memory=False)
    eng = df[df["FASE"] == "engorda"].copy()
    eng = eng.sort_values(["ID_CULTIVO", "ORDEM"])

    # racao acumulada ate cada linha (dentro de cada cultivo)
    eng["RACAO_ACUM"] = eng.groupby("ID_CULTIVO")["TDIA"].cumsum()
    qtd = eng.groupby("ID_CULTIVO")["QUANTIDADE_PL"].transform("first")
    eng["RACAO_ACUM_POR_PL"] = eng["RACAO_ACUM"] / qtd

    # densidade em PL/m2
    if "DENSIDADE_PL_M2" not in eng.columns and "DENSIDADE_PL_HA" in eng.columns:
        eng["DENSIDADE_PL_M2"] = eng["DENSIDADE_PL_HA"] / 10_000

    # uma linha por biometria real
    bio = eng[eng["EH_BIOMETRIA"] == 1].copy()
    bio = bio.dropna(subset=[ALVO_PESO, "DIAS"])

    cols = ["ID_CULTIVO", "VIVEIRO", "ORDEM"] + FEATURES_PESO + [ALVO_PESO]
    cols = [c for c in cols if c in bio.columns]
    return bio[cols].reset_index(drop=True)


def main():
    df = construir_dataset_peso()
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PESO, index=False)
    print(f"Salvo: {CSV_PESO.name}  ({len(df)} biometrias, "
          f"{df['ID_CULTIVO'].nunique()} cultivos, {df['VIVEIRO'].nunique()} viveiros)")
    print(f"Peso: min {df[ALVO_PESO].min():.1f}g | max {df[ALVO_PESO].max():.1f}g | "
          f"mediana {df[ALVO_PESO].median():.1f}g")


if __name__ == "__main__":
    main()
