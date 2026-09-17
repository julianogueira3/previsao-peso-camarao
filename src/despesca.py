"""
despesca.py
-----------
Extrai das celulas de texto livre do formulario dois blocos que a extracao
tabular ignora:
  1. EVENTOS DE DESPESCA (coluna 21): data, kg, nota fiscal, peso medio, animais
  2. CALENDARIO SEMANAL (coluna 2): datas de inicio/fim de cada semana

A quantidade de animais despescados permite calcular a TAXA DE SOBREVIVENCIA.

Validacao interna: para os eventos com QTD ANIMAIS explicito, o valor confere
com kg*1000/PM (erro mediano 0,00%). Validacao externa: produtividade mediana
de ~832 kg/ha, dentro da faixa de carcinicultura semi-intensiva.

Uso:
    python -m src.despesca
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    ARQ_FORMULARIO, DIR_PROCESSED, VIVEIROS,
    CSV_COMPLETO, CSV_DESPESCA, CSV_SOBREVIVENCIA, CSV_CALENDARIO,
)

COL_OBSERVACAO = 21
COL_PERIODO = 2

RE_EVENTO  = re.compile(r"([\d.]+(?:,\d+)?)\s*Kg\s+de\s+Camar[aã]o", re.I)
RE_PM      = re.compile(r"PM\s*[:=]?\s*([\d.]+(?:,\d+)?)", re.I)
RE_QTD     = re.compile(r"QTD\s+Animais\s*[:=]?\s*([\d.]+(?:,\d+)?)", re.I)
RE_NF      = re.compile(r"NF\s*[:=]?\s*([\d.]+)", re.I)
RE_DATA    = re.compile(r"(\d{2}/\d{2}/\d{4})")
RE_PERIODO = re.compile(r"(\d{2}/\d{2}/\d{4})\s+A\s+(\d{2}/\d{2}/\d{4})", re.I)

# Doacoes e consumo interno: "Doacoes:2 Kg P/Elisson, 40 Kg P/Alvaro, 600g P/Luan"
# A secao vai de "Doacoes" ate "QTD Animais" (ou fim do texto).
RE_SECAO_DOACAO = re.compile(r"doa[çc][õo]es\s*:?(.*?)(?=QTD\s+Animais|$)", re.I | re.S)
RE_ITEM_DOACAO = re.compile(r"([\d.]+(?:,\d+)?)\s*(kg|g)\b", re.I)

JANELA = 120


def numero_br(texto: str) -> float:
    """Converte '1.536,5' -> 1536.5 e '26.578' -> 26578.0"""
    if texto is None:
        return np.nan
    t = texto.strip().rstrip(".")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") == 1 and len(t.split(".")[1]) == 3:
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return np.nan


def kg_doacoes(texto: str) -> float:
    """
    Soma os quilos doados / consumidos internamente registrados numa celula.
    Trata 'g' e 'Kg'. Retorna 0.0 quando nao ha secao de doacoes.

    Doacoes e consumo interno sao camaroes que foram RETIRADOS VIVOS do viveiro:
    contam como sobrevivencia, ainda que nao tenham nota fiscal.
    """
    secao = RE_SECAO_DOACAO.search(texto)
    if not secao:
        return 0.0
    total = 0.0
    for valor, unidade in RE_ITEM_DOACAO.findall(secao.group(1)):
        v = numero_br(valor)
        if not np.isnan(v):
            total += v / 1000 if unidade.lower() == "g" else v
    return total


def parse_observacao(texto: str) -> list[dict]:
    """
    Extrai os eventos de retirada de camarao de uma celula de observacao.

    Um evento pode ser:
      - uma venda ("X Kg de Camarao NF:... PM:... QTD Animais:...")
      - uma doacao/consumo interno sem venda ("Doacoes: 441,5 Kg ... PM:25 QTD Animais:17.660")

    Os quilos doados sao atribuidos ao PRIMEIRO evento de venda da celula (ou a um
    evento proprio, quando nao ha venda), para nao contar duas vezes.

    Nota importante: quando a planilha traz QTD Animais explicito, esse numero JA
    inclui as doacoes. Verificado em 81 eventos: usando kg_venda + kg_doacao o erro
    mediano contra o valor escrito e 0,00%; ignorando a doacao, sobe para 0,62%.
    """
    doado = kg_doacoes(texto)
    eventos = []

    for m in RE_EVENTO.finditer(texto):
        janela = texto[m.end(): m.end() + JANELA]
        antes = texto[max(0, m.start() - 30): m.start()]

        pm = RE_PM.search(janela)
        qtd = RE_QTD.search(janela)
        nf = RE_NF.search(janela)
        data = RE_DATA.search(antes)

        eventos.append({
            "DATA": data.group(1) if data else None,
            "KG_VENDA": numero_br(m.group(1)),
            "KG_DOACAO": doado if not eventos else 0.0,   # so no primeiro evento
            "NF": nf.group(1) if nf else None,
            "PESO_MEDIO": numero_br(pm.group(1)) if pm else np.nan,
            "QTD_ANIMAIS_TEXTO": numero_br(qtd.group(1)) if qtd else np.nan,
            "DESBASTE": "DESBASTE" in janela.upper(),
        })

    # Celula so com doacao (sem venda): tambem e uma retirada de animais vivos.
    if not eventos and doado > 0:
        pm = RE_PM.search(texto)
        qtd = RE_QTD.search(texto)
        data = RE_DATA.search(texto)
        if pm or qtd:
            eventos.append({
                "DATA": data.group(1) if data else None,
                "KG_VENDA": 0.0,
                "KG_DOACAO": doado,
                "NF": None,
                "PESO_MEDIO": numero_br(pm.group(1)) if pm else np.nan,
                "QTD_ANIMAIS_TEXTO": numero_br(qtd.group(1)) if qtd else np.nan,
                "DESBASTE": False,
            })

    for e in eventos:
        e["KG"] = e["KG_VENDA"] + e["KG_DOACAO"]

    return eventos


def extrair(arquivo):
    eventos, semanas = [], []

    for aba, viveiro_nome in VIVEIROS.items():
        planilha = pd.read_excel(arquivo, sheet_name=aba, header=None)
        indice_cultivo = -1
        semana = 0

        for linha in range(planilha.shape[0]):
            valores = planilha.iloc[linha].values

            if viveiro_nome in valores:
                indice_cultivo += 1
                semana = 0
            if indice_cultivo < 0:
                continue

            id_cultivo = f"V{aba[1:]}_C{indice_cultivo + 1}"

            if planilha.shape[1] > COL_PERIODO:
                cel = planilha.iat[linha, COL_PERIODO]
                if isinstance(cel, str):
                    p = RE_PERIODO.search(cel)
                    if p:
                        semana += 1
                        semanas.append({
                            "ID_CULTIVO": id_cultivo, "VIVEIRO": aba[1:], "SEMANA": semana,
                            "DATA_INICIO": p.group(1), "DATA_FIM": p.group(2),
                        })

            if planilha.shape[1] > COL_OBSERVACAO:
                cel = planilha.iat[linha, COL_OBSERVACAO]
                if isinstance(cel, str):
                    for ev in parse_observacao(cel):
                        ev["ID_CULTIVO"] = id_cultivo
                        ev["VIVEIRO"] = aba[1:]
                        eventos.append(ev)

    return pd.DataFrame(eventos), pd.DataFrame(semanas)


def deduplicar(eventos: pd.DataFrame) -> pd.DataFrame:
    """
    O mesmo evento e frequentemente transcrito em mais de uma celula: uma versao
    com "(DESBASTE)", outra sem; uma citando as doacoes, outra nao.

    A chave de deduplicacao usa KG_VENDA (nao KG total). Usar o total quebraria a
    deduplicacao, porque a copia que menciona a doacao teria kg diferente da copia
    que nao menciona — e a venda seria contada duas vezes.

    Entre copias, mantemos a que carrega MAIS informacao de doacao.
    """
    eventos = eventos.sort_values("KG_DOACAO", ascending=False)

    vendas = eventos[eventos["KG_VENDA"] > 0].drop_duplicates(
        subset=["VIVEIRO", "NF", "KG_VENDA", "DATA"], keep="first")
    doacoes = eventos[eventos["KG_VENDA"] == 0].drop_duplicates(
        subset=["VIVEIRO", "DATA", "KG_DOACAO"], keep="first")

    return pd.concat([vendas, doacoes], ignore_index=True)


def consolidar(eventos: pd.DataFrame) -> pd.DataFrame:
    antes = len(eventos)
    eventos = deduplicar(eventos)
    print(f"  Deduplicacao por (viveiro, NF, kg_venda, data): {antes} -> {len(eventos)} eventos")

    so_doacao = int((eventos["KG_VENDA"] == 0).sum())
    kg_doado = float(eventos["KG_DOACAO"].sum())
    kg_total = float(eventos["KG"].sum())
    print(f"  Eventos so de doacao/consumo interno (sem venda): {so_doacao}")
    print(f"  Quilos doados: {kg_doado:,.0f} de {kg_total:,.0f} kg colhidos "
          f"({kg_doado / kg_total:.1%})")

    # KG ja soma venda + doacao. Doacoes sao animais retirados vivos do viveiro.
    eventos["QTD_ANIMAIS_CALC"] = eventos["KG"] * 1000 / eventos["PESO_MEDIO"]

    ok = eventos.dropna(subset=["QTD_ANIMAIS_TEXTO", "QTD_ANIMAIS_CALC"])
    erro = (ok["QTD_ANIMAIS_CALC"] - ok["QTD_ANIMAIS_TEXTO"]).abs() / ok["QTD_ANIMAIS_TEXTO"]
    print(f"  Validacao (kg_venda + kg_doacao)*1000/PM vs QTD ANIMAIS (n={len(ok)}): "
          f"erro mediano {erro.median():.2%}, abaixo de 5% em {(erro < 0.05).mean():.1%}")

    eventos["QTD_ANIMAIS"] = eventos["QTD_ANIMAIS_TEXTO"].fillna(eventos["QTD_ANIMAIS_CALC"])
    return eventos


def calcular_sobrevivencia(eventos: pd.DataFrame, dataset: pd.DataFrame) -> pd.DataFrame:
    resumo = eventos.groupby("ID_CULTIVO").agg(
        N_EVENTOS_DESPESCA  = ("KG", "size"),
        KG_DESPESCADO       = ("KG", "sum"),          # venda + doacao
        KG_VENDIDO          = ("KG_VENDA", "sum"),
        KG_DOADO            = ("KG_DOACAO", "sum"),
        ANIMAIS_DESPESCADOS = ("QTD_ANIMAIS", "sum"),
        PESO_MEDIO_DESPESCA = ("PESO_MEDIO", "last"),
        N_DESBASTES         = ("DESBASTE", "sum"),
    )

    base = dataset.groupby("ID_CULTIVO").agg(
        VIVEIRO=("VIVEIRO", "first"),
        QUANTIDADE_PL=("QUANTIDADE_PL", "first"),
        TAMANHO_AREA=("TAMANHO_AREA", "first"),
    )

    r = resumo.join(base, how="left")
    r["SOBREVIVENCIA"] = r["ANIMAIS_DESPESCADOS"] / r["QUANTIDADE_PL"]
    r["PRODUTIVIDADE_KG_HA"] = r["KG_DESPESCADO"] / r["TAMANHO_AREA"]

    r["SOBREVIVENCIA_VALIDA"] = r["SOBREVIVENCIA"].between(0.01, 1.0)
    return r.reset_index()


def main():
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)

    print(f"Lendo: {ARQ_FORMULARIO}\n")
    eventos, semanas = extrair(ARQ_FORMULARIO)
    print(f"  Eventos de despesca encontrados: {len(eventos)}")
    print(f"  Semanas datadas:                 {len(semanas)}\n")

    eventos = consolidar(eventos)

    caminho_dataset = CSV_COMPLETO
    if not caminho_dataset.exists():
        print(f"\n{caminho_dataset} nao encontrado. Rode antes: python src/limpeza.py")
        return
    dataset = pd.read_csv(caminho_dataset)

    sobrevivencia = calcular_sobrevivencia(eventos, dataset)

    for col in ["DATA_INICIO", "DATA_FIM"]:
        semanas[col] = pd.to_datetime(semanas[col], format="%d/%m/%Y", errors="coerce")

    calendario = semanas.groupby("ID_CULTIVO").agg(
        DATA_POVOAMENTO=("DATA_INICIO", "min"),
        DATA_ULTIMA_SEMANA=("DATA_FIM", "max"),
        N_SEMANAS_DATADAS=("SEMANA", "max"),
    ).reset_index()
    calendario["MES_POVOAMENTO"] = calendario["DATA_POVOAMENTO"].dt.month
    calendario["ANO_POVOAMENTO"] = calendario["DATA_POVOAMENTO"].dt.year

    eventos.to_csv(CSV_DESPESCA, index=False, encoding="utf-8-sig")
    sobrevivencia.to_csv(CSV_SOBREVIVENCIA, index=False, encoding="utf-8-sig")
    calendario.to_csv(CSV_CALENDARIO, index=False, encoding="utf-8-sig")

    validos = sobrevivencia[sobrevivencia["SOBREVIVENCIA_VALIDA"]]

    print(f"\n{'-'*62}")
    print("SOBREVIVENCIA")
    print(f"{'-'*62}")
    print(f"  Cultivos com evento de despesca: {len(sobrevivencia)}")
    print(f"  Com sobrevivencia entre 1% e 100%: {len(validos)}")
    print(f"  Fora da faixa (QUANTIDADE_PL suspeito): "
          f"{len(sobrevivencia) - len(validos)}")
    print()
    print(f"  Sobrevivencia mediana:  {validos['SOBREVIVENCIA'].median():.1%}")
    print(f"  Quartis:                {validos['SOBREVIVENCIA'].quantile(.25):.1%} "
          f"- {validos['SOBREVIVENCIA'].quantile(.75):.1%}")
    print(f"  Produtividade mediana:  {validos['PRODUTIVIDADE_KG_HA'].median():.0f} kg/ha")
    print()
    kg_doado = float(validos["KG_DOADO"].sum())
    kg_total = float(validos["KG_DESPESCADO"].sum())
    print(f"  Dos quilos colhidos, {kg_doado / kg_total:.1%} foram doacao/consumo interno.")
    print()
    print("  DEFINICAO: sobrevivencia = animais retirados VIVOS do viveiro / PLs estocados.")
    print("  Doacoes e consumo interno contam: o animal nao morreu, so nao foi faturado.")
    print()
    print("  RESSALVA: ainda e um limite inferior, mas por outro motivo — despescas")
    print("  nunca anotadas na planilha nao podem ser recuperadas. Mortalidade nao e")
    print("  medida diretamente: e inferida como o complemento da retirada registrada.")
    print()
    print(f"  Cultivos datados: {len(calendario)}")
    print(f"  Periodo: {calendario['DATA_POVOAMENTO'].min():%d/%m/%Y} a "
          f"{calendario['DATA_ULTIMA_SEMANA'].max():%d/%m/%Y}")


if __name__ == "__main__":
    main()
