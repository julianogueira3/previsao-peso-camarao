"""
features.py
-----------
Transforma o dataset diario (uma linha por dia) no dataset de modelagem
(uma linha por cultivo de engorda), com:

  - classificacao da fase do ciclo (bercario / engorda / incompleto / ...)
  - agregacao ambiental por cultivo (media, desvio, minimo, maximo)
  - features de manejo alimentar (racao)
  - features derivadas (amplitude termica, taxa de hipoxia, sazonalidade)
  - os alvos: SOBREVIVENCIA, GP_SEMANAL (g/semana), PESO_FINAL

Expoe funcoes reutilizaveis (classificar_fase, construir_features) que os
notebooks e os modulos de modelagem importam, e um main() que gera o
dataset_cultivos.csv e a lista de features parcimoniosas.

Uso:
    python -m src.features
"""

import numpy as np
import pandas as pd

from src.config import (
    CSV_COMPLETO, CSV_TRATADO, CSV_CULTIVOS, CSV_SOBREVIVENCIA, CSV_CALENDARIO,
    DIR_PROCESSED, LIMITES, LIMIAR_HIPOXIA,
    PESO_MINIMO_VENDA, PESO_MAXIMO_BERCARIO, DIAS_MAXIMO_BERCARIO,
)

COLUNAS_AMBIENTAIS = [
    "SUP_05", "SOLO_05", "TEMP_05", "PH_05",
    "SUP_14", "SOLO_14", "TEMP_14", "PH_14", "SAL_14",
    "NIVEL", "DELTA_OXI_SUP", "DELTA_OXI_SOLO",
]

# Features derivadas do proprio evento de despesca: NAO usar para prever
# sobrevivencia (vazamento direto). Ficam no dataset so para analise.
VAZAMENTO_DESPESCA = [
    "KG_DESPESCADO", "PRODUTIVIDADE_KG_HA", "PESO_MEDIO_DESPESCA", "N_DESBASTES",
]

FEATURES_PARCIMONIOSO = [
    "N_DIAS", "DENSIDADE_PL_M2", "TAMANHO_AREA", "PESO_INICIAL",
    "RACAO_POR_PL", "RACAO_POR_DIA",
    "SUP_05_MEDIA", "SUP_05_STD", "SUP_05_MIN",
    "TEMP_05_MEDIA", "AMPLITUDE_TERMICA",
    "PH_05_MEDIA", "SAL_14_MEDIA",
    "TAXA_O2_BAIXO", "SEN_MES", "COS_MES",
]

# Alvos modelados no TCC. O ganho de peso semanal (GP_SEMANAL) ainda e
# calculado em adicionar_alvos() e fica disponivel no dataset como extensao
# opcional, mas nao e modelado: sai das mesmas biometrias que o peso final e
# cairia na mesma limitacao (o ambiente agregado nao acrescenta sinal).
ALVOS = ["SOBREVIVENCIA", "PESO_FINAL"]


def aplicar_filtros_fisicos(df: pd.DataFrame) -> pd.DataFrame:
    """Anula (celula, nao linha) valores fora dos limites fisico-biologicos."""
    df = df.copy()
    for col in ["DIAS", "SEMANA", "PESO", "GANHO_PESO", "NIVEL", "TDIA",
                "QUANTIDADE_PL", "TAMANHO_AREA", "DENSIDADE_PL_HA"] + COLUNAS_AMBIENTAIS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col, (lo, hi) in LIMITES.items():
        if col in df.columns:
            df.loc[(df[col] < lo) | (df[col] > hi), col] = np.nan

    # Ganho de peso: so positivo e fisicamente plausivel.
    # O parceiro de campo indica crescimento de ~1 g/semana; ganhos acima de
    # 10 g/semana sao erro de biometria (tipicamente a linha do peso de 970 g,
    # cujo PESO ja foi anulado mas cujo GANHO_PESO permanecia). Sem este teto,
    # a MEDIA do ganho por cultivo era contaminada por esses valores.
    df.loc[df["GANHO_PESO"] <= 0, "GANHO_PESO"] = np.nan
    df.loc[df["GANHO_PESO"] > 10, "GANHO_PESO"] = np.nan

    if {"SUP_05", "SUP_14"}.issubset(df.columns):
        df["DELTA_OXI_SUP"] = df["SUP_14"] - df["SUP_05"]
    if {"SOLO_05", "SOLO_14"}.issubset(df.columns):
        df["DELTA_OXI_SOLO"] = df["SOLO_14"] - df["SOLO_05"]

    if "ORDEM" not in df.columns:
        df["ORDEM"] = df.groupby("ID_CULTIVO").cumcount()
    if "DIAS" in df.columns:
        df.loc[df["DIAS"] == 0, "DIAS"] = np.nan

    return df


def marcar_biometrias(df: pd.DataFrame) -> pd.DataFrame:
    """Garante a flag EH_BIOMETRIA (1 na linha da pesagem real)."""
    df = df.copy()
    if "EH_BIOMETRIA" not in df.columns:
        mudou = df["PESO"] != df.groupby("ID_CULTIVO")["PESO"].shift()
        df["EH_BIOMETRIA"] = (df["PESO"].notna() & mudou).astype(int)
    return df


def classificar_fase(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna um DataFrame indexado por ID_CULTIVO com o perfil de cada cultivo
    e a coluna FASE. Regras em cascata (ver docs/ESTRUTURA_MONOGRAFIA.md 3.5).
    """
    bio = df.sort_values(["ID_CULTIVO", "ORDEM"]).groupby("ID_CULTIVO")

    perfil = pd.DataFrame({
        "VIVEIRO":      bio["VIVEIRO"].first(),
        "PESO_FINAL":   bio["PESO"].max(),
        "PESO_INICIAL": bio["PESO"].first(),
        "N_BIOMETRIAS": bio["EH_BIOMETRIA"].sum(),
        "N_DIAS":       bio["DIAS"].max(),
        "PL_M2":        bio["DENSIDADE_PL_HA"].first() / 10_000,
    })
    perfil["N_CULT"] = perfil.index.str.extract(r"_C(\d+)$")[0].astype(int).values
    perfil["ULTIMO"] = perfil.groupby("VIVEIRO")["N_CULT"].transform("max") == perfil["N_CULT"]

    def regra(r):
        if pd.isna(r.PESO_FINAL) or r.N_BIOMETRIAS < 2:
            return "sem_biometria"
        if r.PESO_FINAL <= PESO_MAXIMO_BERCARIO and r.N_DIAS <= DIAS_MAXIMO_BERCARIO:
            return "bercario"
        if r.PESO_FINAL < PESO_MINIMO_VENDA:
            return "incompleto"
        if r.ULTIMO and r.N_DIAS <= DIAS_MAXIMO_BERCARIO:
            return "em_andamento"
        return "engorda"

    perfil["FASE"] = perfil.apply(regra, axis=1)

    # Erro de digitacao explicito: densidade fisicamente impossivel
    perfil.loc[perfil["PL_M2"] > 100, "FASE"] = "erro_digitacao"
    return perfil


def agregar_por_cultivo(df_eng: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por cultivo: agregados ambientais + racao + derivadas."""
    agg = {}
    for col in COLUNAS_AMBIENTAIS:
        agg[f"{col}_MEDIA"] = (col, "mean")
        agg[f"{col}_STD"] = (col, "std")
        agg[f"{col}_MIN"] = (col, "min")
        agg[f"{col}_MAX"] = (col, "max")

    cult = df_eng.groupby("ID_CULTIVO").agg(
        VIVEIRO         = ("VIVEIRO", "first"),
        QUANTIDADE_PL   = ("QUANTIDADE_PL", "first"),
        TAMANHO_AREA    = ("TAMANHO_AREA", "first"),
        DENSIDADE_PL_HA = ("DENSIDADE_PL_HA", "first"),
        N_DIAS          = ("DIAS", "max"),
        **agg,
    )
    cult["DENSIDADE_PL_M2"] = cult["DENSIDADE_PL_HA"] / 10_000

    # Racao
    racao = df_eng.groupby("ID_CULTIVO").agg(
        RACAO_TOTAL = ("TDIA", "sum"),
        RACAO_MEDIA = ("TDIA", "mean"),
        RACAO_STD   = ("TDIA", "std"),
    )
    racao["RACAO_POR_PL"] = racao["RACAO_TOTAL"] / cult["QUANTIDADE_PL"]
    racao["RACAO_POR_DIA"] = racao["RACAO_TOTAL"] / cult["N_DIAS"]
    cult = cult.join(racao)

    # Derivadas
    cult["AMPLITUDE_TERMICA"] = cult["TEMP_14_MEDIA"] - cult["TEMP_05_MEDIA"]
    # Fracao de dias do cultivo com oxigenio das 05h abaixo do limiar critico.
    # E uma FEATURE (preditor da sobrevivencia), nao um alvo de previsao.
    o2_baixo = (df_eng[df_eng["SUP_05"].notna()]
                .groupby("ID_CULTIVO")["SUP_05"]
                .apply(lambda x: (x < LIMIAR_HIPOXIA).mean()))
    cult["TAXA_O2_BAIXO"] = o2_baixo

    # Tendencias temporais (slope da reta ajustada ao longo do cultivo).
    # Capturam se o parametro PIOROU ou MELHOROU com o tempo — a "pitada" de
    # serie temporal comprimida em um numero por cultivo. O notebook 04 mostra
    # que, para este N, elas nao acrescentam sinal (o MIN e o STD ja capturam a
    # dinamica), mas ficam disponiveis como feature opcional e como experimento.
    cult = cult.join(_tendencias_temporais(df_eng))

    return cult


def _slope(serie_ordem, serie_valor, minimo=5):
    """Coeficiente angular (g/observacao) da reta y=ax+b. NaN se dados de menos."""
    mask = serie_valor.notna()
    if mask.sum() < minimo:
        return np.nan
    return np.polyfit(serie_ordem[mask], serie_valor[mask], 1)[0]


def _tendencias_temporais(df_eng: pd.DataFrame) -> pd.DataFrame:
    """Uma coluna TEND_<param> por cultivo: como o parametro evoluiu no tempo."""
    linhas = {}
    for id_cult, g in df_eng.groupby("ID_CULTIVO"):
        g = g.sort_values("ORDEM")
        linhas[id_cult] = {
            "TEND_SUP_05":  _slope(g["ORDEM"], g["SUP_05"]),
            "TEND_TEMP_05": _slope(g["ORDEM"], g["TEMP_05"]),
            "TEND_PH_05":   _slope(g["ORDEM"], g["PH_05"]),
        }
    return pd.DataFrame.from_dict(linhas, orient="index")


def adicionar_alvos(cult, df_eng, perfil):
    """Anexa PESO_FINAL, PESO_INICIAL, GP_SEMANAL, SOBREVIVENCIA e sazonalidade."""
    bio = df_eng[df_eng["EH_BIOMETRIA"] == 1].sort_values(["ID_CULTIVO", "ORDEM"])
    alvos = pd.DataFrame({
        "PESO_FINAL":   bio.groupby("ID_CULTIVO")["PESO"].max(),
        "PESO_INICIAL": bio.groupby("ID_CULTIVO")["PESO"].first(),
        "GP_SEMANAL":   (bio[bio["GANHO_PESO"] > 0]
                         .groupby("ID_CULTIVO")["GANHO_PESO"].mean()),
    })
    cult = cult.join(alvos)

    # Sobrevivencia (gerada por despesca.py)
    if CSV_SOBREVIVENCIA.exists():
        sob = pd.read_csv(CSV_SOBREVIVENCIA)
        sob = sob[sob["SOBREVIVENCIA_VALIDA"]].set_index("ID_CULTIVO")
        cols = ["SOBREVIVENCIA", "KG_DESPESCADO", "PRODUTIVIDADE_KG_HA",
                "N_DESBASTES", "PESO_MEDIO_DESPESCA"]
        cult = cult.join(sob[[c for c in cols if c in sob.columns]])

    # Sazonalidade (gerada por despesca.py)
    if CSV_CALENDARIO.exists():
        cal = pd.read_csv(CSV_CALENDARIO).set_index("ID_CULTIVO")
        if "MES_POVOAMENTO" in cal.columns:
            cult = cult.join(cal[["MES_POVOAMENTO"]])
            cult["SEN_MES"] = np.sin(2 * np.pi * cult["MES_POVOAMENTO"] / 12)
            cult["COS_MES"] = np.cos(2 * np.pi * cult["MES_POVOAMENTO"] / 12)

    return cult


def construir_features(df: pd.DataFrame):
    """
    Pipeline completo de features. Recebe o dataset diario bruto (com FASE ja
    calculada ou nao) e devolve (df_diario_tratado, df_cultivos_engorda).
    """
    df = aplicar_filtros_fisicos(df)
    df = marcar_biometrias(df)
    perfil = classificar_fase(df)
    df = df.merge(perfil[["FASE"]], left_on="ID_CULTIVO", right_index=True, how="left")

    df_eng = df[df["FASE"] == "engorda"].copy()
    cult = agregar_por_cultivo(df_eng)
    cult = adicionar_alvos(cult, df_eng, perfil)

    return df, cult.reset_index()


def lista_features(cult: pd.DataFrame, incluir_vazamento=False):
    """Conjunto completo de features (sem ids, alvos e, opcionalmente, vazamento)."""
    # GP_SEMANAL nao esta em ALVOS (nao e modelado), mas continua sendo uma
    # coluna calculada — precisa ser excluido explicitamente para nao virar
    # feature (seria vazamento: prever peso final usando ganho de peso).
    excluir = ["ID_CULTIVO", "VIVEIRO", "FAIXA_SAL", "N_BIOMETRIAS",
               "MES_POVOAMENTO", "GP_SEMANAL"] + ALVOS
    if not incluir_vazamento:
        excluir += VAZAMENTO_DESPESCA
    return [c for c in cult.columns if c not in excluir]


def main():
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    if not CSV_COMPLETO.exists():
        print(f"{CSV_COMPLETO} nao encontrado. Rode antes: python -m src.limpeza")
        return

    df = pd.read_csv(CSV_COMPLETO)
    df_tratado, cult = construir_features(df)

    df_tratado.to_csv(CSV_TRATADO, index=False, encoding="utf-8-sig")
    cult.to_csv(CSV_CULTIVOS, index=False, encoding="utf-8-sig")
    (DIR_PROCESSED / "features_parcimonioso.txt").write_text(
        "\n".join([f for f in FEATURES_PARCIMONIOSO if f in cult.columns]))

    print(f"Salvo: {CSV_TRATADO}  ({len(df_tratado):,} linhas)")
    print(f"Salvo: {CSV_CULTIVOS}  ({len(cult)} cultivos de engorda)")
    print()
    print("Distribuicao das fases:")
    perfil = classificar_fase(marcar_biometrias(aplicar_filtros_fisicos(df)))
    print(perfil["FASE"].value_counts().to_string())
    print()
    for alvo in ALVOS:
        print(f"  {alvo:<16} disponivel em {cult[alvo].notna().sum()} cultivos")


if __name__ == "__main__":
    main()
