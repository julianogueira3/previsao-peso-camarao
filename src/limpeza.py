"""
limpeza.py
----------
Le os arquivos por viveiro, consolida num unico DataFrame e aplica limpeza.

Correcoes:
  - DIAS e SEMANA convertidos para numerico
  - UM, DOIS, TDIA (racao) mantidos: variavel economica central
  - coluna ORDEM preserva a cronologia (DIAS==0 vem em branco na planilha e
    nao serve para ordenar)

Uso:
    python -m src.limpeza
"""

from pathlib import Path
import numpy as np
import pandas as pd

from src.config import DIR_PROCESSED, CSV_COMPLETO

COLUNAS_ZERO_EH_NAN = [
    "SUP_05", "SOLO_05", "TEMP_05", "PH_05",
    "SUP_14", "SOLO_14", "TEMP_14", "PH_14", "SAL_14",
    "PESO", "GANHO_PESO", "UM", "DOIS", "TDIA",
]
COLUNAS_DROPAR = ["SEMANA.1", "A", "D", "CM"]
COLUNAS_NUMERICAS = ["DIAS", "SEMANA", "NIVEL", "CULTIVO", "QUANTIDADE_PL", "TAMANHO_AREA"]
MAPA_COR = {"VE": "verde", "T": "turva", "M": "marrom", 0: np.nan, "0": np.nan}
MAPA_LUA = {"MIN": "minguante", "NOV": "nova", "CRE": "crescente", "CHE": "cheia", 0: np.nan, "0": np.nan}


def extrair_numero_viveiro(nome_arquivo: str) -> str:
    return nome_arquivo.replace("VIVEIRO_N_", "").replace(".xlsx", "")


def ler_viveiro(caminho: Path) -> pd.DataFrame:
    numero_viveiro = extrair_numero_viveiro(caminho.name)
    abas = pd.ExcelFile(caminho).sheet_names
    frames = []

    for aba in abas:
        df = pd.read_excel(caminho, sheet_name=aba)
        df["VIVEIRO"] = numero_viveiro
        df["CULTIVO_ABA"] = aba
        df["ID_CULTIVO"] = f"V{numero_viveiro}_{aba}"
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    cols_dropar = [c for c in COLUNAS_DROPAR if c in df.columns]
    df = df.drop(columns=cols_dropar)

    cols_nan = [c for c in COLUNAS_ZERO_EH_NAN if c in df.columns]
    df[cols_nan] = df[cols_nan].apply(pd.to_numeric, errors="coerce")
    df[cols_nan] = df[cols_nan].replace(0, np.nan)

    for col in COLUNAS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # A ordem das linhas dentro de cada cultivo E a ordem cronologica
    # (SEMANA e monotonica em 184 dos 185 cultivos). DIAS NAO serve para
    # ordenar: 14% das celulas vem em branco na planilha e viram 0.
    df["ORDEM"] = df.groupby("ID_CULTIVO").cumcount()

    if "DIAS" in df.columns:
        df["DIAS_BRUTO"] = df["DIAS"]
        df.loc[df["DIAS"] == 0, "DIAS"] = np.nan

    if "CULTIVO" in df.columns:
        df["CULTIVO"] = df["CULTIVO"].astype("Int64")

    if "EH_BIOMETRIA" in df.columns:
        df["EH_BIOMETRIA"] = pd.to_numeric(df["EH_BIOMETRIA"], errors="coerce").fillna(0).astype(int)
        df.loc[df["PESO"].isna(), "EH_BIOMETRIA"] = 0

    if "COR" in df.columns:
        df["COR"] = df["COR"].map(lambda x: MAPA_COR.get(x, x))
    if "LUA" in df.columns:
        df["LUA"] = df["LUA"].map(lambda x: MAPA_LUA.get(x, x))

    if "QUANTIDADE_PL" in df.columns and "TAMANHO_AREA" in df.columns:
        df["DENSIDADE_PL_HA"] = (
            df["QUANTIDADE_PL"] / df["TAMANHO_AREA"].replace(0, np.nan)
        ).round(0)
        df["DENSIDADE_PL_M2"] = (df["DENSIDADE_PL_HA"] / 10_000).round(2)

    if "SUP_05" in df.columns and "SUP_14" in df.columns:
        df["DELTA_OXI_SUP"] = df["SUP_14"] - df["SUP_05"]
    if "SOLO_05" in df.columns and "SOLO_14" in df.columns:
        df["DELTA_OXI_SOLO"] = df["SOLO_14"] - df["SOLO_05"]

    id_cols = ["ID_CULTIVO", "VIVEIRO", "CULTIVO_ABA", "CULTIVO", "ORDEM", "SEMANA", "DIAS",
               "QUANTIDADE_PL", "TAMANHO_AREA", "DENSIDADE_PL_HA", "DENSIDADE_PL_M2"]
    id_cols = [c for c in id_cols if c in df.columns]
    outras = [c for c in df.columns if c not in id_cols]
    df = df[id_cols + outras]

    return df


def relatorio_qualidade(df: pd.DataFrame):
    print(f"\n{'-'*50}")
    print("DATASET FINAL")
    print(f"{'-'*50}")
    print(f"  Linhas:          {len(df):>8,}")
    print(f"  Colunas:         {len(df.columns):>8}")
    print(f"  Viveiros:        {df['VIVEIRO'].nunique():>8}")
    print(f"  Cultivos unicos: {df['ID_CULTIVO'].nunique():>8}")
    if "EH_BIOMETRIA" in df.columns:
        print(f"  Biometrias:      {int(df['EH_BIOMETRIA'].sum()):>8,}")
    print("\n  % de NaN por coluna de medicao:")
    for col in [c for c in COLUNAS_ZERO_EH_NAN if c in df.columns]:
        pct = df[col].isna().mean() * 100
        print(f"    {col:<15} {pct:5.1f}%  {'#' * int(pct / 5)}")


def main():
    arquivos = sorted(DIR_PROCESSED.glob("VIVEIRO_N_*.xlsx"))

    if not arquivos:
        print("Nenhum arquivo encontrado em data/processed/")
        print("   Rode primeiro: python src/extracao.py")
        return

    print(f"Lendo {len(arquivos)} arquivos de viveiro...\n")

    frames = []
    for arq in arquivos:
        df_v = ler_viveiro(arq)
        frames.append(df_v)
        print(f"  {arq.name:<30} -> {len(df_v):>5} linhas")

    print("\nConsolidando e limpando...")
    df_total = pd.concat(frames, ignore_index=True)
    df_limpo = limpar(df_total)

    df_limpo.to_csv(CSV_COMPLETO, index=False, encoding="utf-8-sig")
    print(f"\nSalvo: {CSV_COMPLETO}")

    relatorio_qualidade(df_limpo)
    print("\nPronto! Dataset disponivel em data/processed/")


if __name__ == "__main__":
    main()
