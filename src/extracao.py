"""
extracao.py
-----------
Extrai os dados de campo de TODOS os viveiros do formulario e salva um arquivo
Excel por viveiro em data/processed/.

Correcoes em relacao a versao inicial:
  - peso_value / gp_value reinicializados a cada CULTIVO (antes vazavam de um
    cultivo para o seguinte dentro do mesmo viveiro)
  - coluna EH_BIOMETRIA: 1 apenas na linha da pesagem real

Uso:
    python -m src.extracao
"""

from pathlib import Path
import numpy as np
import pandas as pd
import xlsxwriter

from src.config import ARQ_FORMULARIO, DIR_PROCESSED, VIVEIROS

COLUNAS_CULTIVO = [
    "dias", "sup_05", "solo_05", "temp_05", "ph_05",
    "sup_14", "solo_14", "temp_14", "ph_14", "sal_14",
    "cor", "nivel", "a", "d", "lua",
    "um", "dois", "tdia", "cm",
    "semana", "cultivo", "quantidade_pl", "tamanho_area",
    "peso", "ganho_peso", "eh_biometria",
]


def novo_cultivo(viveiro_nome: str) -> dict:
    d = {col: [] for col in COLUNAS_CULTIVO}
    d["viveiro"] = viveiro_nome
    return d


def extrair_viveiro(aba: str, viveiro_nome: str, df: pd.DataFrame) -> list[dict]:
    cultivos = []
    i = -1
    inicio = False
    racao = False
    semana = 0
    cultivo_num = qtd_pl = qtd_area = None
    peso_value = gp_value = 0

    for _, row in df.iterrows():
        valores = row.values

        if viveiro_nome in valores:
            cultivos.append(novo_cultivo(viveiro_nome))
            semana = 0
            i += 1
            peso_value = gp_value = 0
            cultivo_num = qtd_pl = qtd_area = None

        if "CULTIVO Nº" in valores:
            cultivo_label = pl_label = area_label = False
            for idx, val in enumerate(valores):
                if val == "CULTIVO Nº":
                    cultivo_label = True
                    continue
                if cultivo_label:
                    try:
                        if not np.isnan(val):
                            cultivo_num = val
                            cultivo_label = False
                    except TypeError:
                        cultivo_num = val
                        cultivo_label = False

                if val == "QTD DE PL´S":
                    pl_label = True
                    continue
                if pl_label:
                    try:
                        if not np.isnan(val):
                            qtd_pl = val
                            pl_label = False
                    except TypeError:
                        qtd_pl = val
                        pl_label = False

                if val == "ÁREA":
                    area_label = True
                    continue
                if area_label:
                    try:
                        if not np.isnan(val):
                            qtd_area = val
                            area_label = False
                    except TypeError:
                        qtd_area = val
                        area_label = False

        if racao:
            racao = False

        if "CULT." in valores:
            racao = True
            semana += 1

        if "DIAS" in valores:
            inicio = True
            continue

        if "PESO" in valores:
            inicio = False
            peso_found = gp_found = False
            for val in valores:
                v = np.nan_to_num(val)
                if v == "PESO":
                    peso_found = True
                    continue
                if peso_found:
                    peso_value = v
                    peso_found = False
                if v == "GP":
                    gp_found = True
                    continue
                if gp_found:
                    gp_value = v
                    gp_found = False
                    break

            if i >= 0:
                cultivos[i]["peso"].extend([peso_value] * 7)
                cultivos[i]["ganho_peso"].extend([gp_value] * 7)
                cultivos[i]["eh_biometria"].extend([1] + [0] * 6)

        if inicio and i >= 0:
            for idx, val in enumerate(valores):
                if idx <= 18:
                    cultivos[i][COLUNAS_CULTIVO[idx]].append(np.nan_to_num(val))
                elif idx == 19:
                    cultivos[i]["semana"].append(semana)
                elif idx == 20:
                    cultivos[i]["cultivo"].append(cultivo_num)
                elif idx == 21:
                    cultivos[i]["quantidade_pl"].append(qtd_pl)
                elif idx == 22:
                    cultivos[i]["tamanho_area"].append(qtd_area)

    return cultivos


def salvar_cultivos(cultivos: list[dict], viveiro_nome: str, pasta: Path):
    nome_arquivo = viveiro_nome.replace(" ", "_").replace("Nº", "N") + ".xlsx"
    caminho = pasta / nome_arquivo

    workbook = xlsxwriter.Workbook(str(caminho))
    for i, cultivo in enumerate(cultivos):
        ws = workbook.add_worksheet(f"C{i + 1}")

        colunas_saida = ["SEMANA"] + [c.upper() for c in COLUNAS_CULTIVO]
        for j, col in enumerate(colunas_saida):
            ws.write(0, j, col)

        for linha, semana in enumerate(cultivo["semana"]):
            ws.write(linha + 1, 0, semana)

        for j, col in enumerate(COLUNAS_CULTIVO):
            for linha, dado in enumerate(cultivo[col]):
                ws.write(linha + 1, j + 1, dado)

    workbook.close()
    return caminho


def main():
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)

    total_cultivos = 0
    erros = []

    print(f"Lendo: {ARQ_FORMULARIO}\n")

    for aba, viveiro_nome in VIVEIROS.items():
        try:
            df = pd.read_excel(ARQ_FORMULARIO, sheet_name=aba)
            cultivos = extrair_viveiro(aba, viveiro_nome, df)
            caminho = salvar_cultivos(cultivos, viveiro_nome, DIR_PROCESSED)
            total_cultivos += len(cultivos)
            print(f"  {viveiro_nome:<20} -> {len(cultivos):>2} cultivos -> {caminho.name}")
        except Exception as e:
            erros.append((viveiro_nome, str(e)))
            print(f"  {viveiro_nome:<20} -> ERRO: {e}")

    print(f"\n{'-'*50}")
    print(f"Extracao concluida: {len(VIVEIROS) - len(erros)}/{len(VIVEIROS)} viveiros")
    print(f"Total de cultivos extraidos: {total_cultivos}")
    if erros:
        print(f"Erros em {len(erros)} viveiros:")
        for nome, err in erros:
            print(f"   {nome}: {err}")


if __name__ == "__main__":
    main()
