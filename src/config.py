"""
config.py
---------
Ponto unico de verdade para caminhos, constantes e limites fisico-biologicos
do projeto. Todos os outros modulos importam daqui, para que uma mudanca de
limiar (ex.: o pH maximo aceitavel) seja feita em um lugar so.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_MODELS = RAIZ / "models"

ARQ_FORMULARIO = DIR_RAW / "formulario_de_dados_de_campo_2024.xlsx"

CSV_COMPLETO = DIR_PROCESSED / "dataset_completo.csv"
CSV_TRATADO = DIR_PROCESSED / "dataset_tratado.csv"
CSV_CULTIVOS = DIR_PROCESSED / "dataset_cultivos.csv"
CSV_DESPESCA = DIR_PROCESSED / "dataset_despesca.csv"
CSV_SOBREVIVENCIA = DIR_PROCESSED / "dataset_sobrevivencia.csv"
CSV_CALENDARIO = DIR_PROCESSED / "calendario_cultivos.csv"

PKL_SOBREVIVENCIA = DIR_MODELS / "modelo_sobrevivencia.pkl"

# Mapeamento dos viveiros (aba do Excel -> nome interno da planilha)

VIVEIROS = {
    "V1": "VIVEIRO Nº 1", "V3": "VIVEIRO Nº 3", "V4": "VIVEIRO Nº 4",
    "V5": "VIVEIRO Nº 5", "V6": "VIVEIRO Nº 6", "V7": "VIVEIRO Nº 7",
    "V8": "VIVEIRO Nº 8", "V9": "VIVEIRO Nº 9", "V10": "VIVEIRO Nº 10",
    "V11A": "VIVEIRO Nº 11A", "V11B": "VIVEIRO Nº 11B", "V11C": "VIVEIRO Nº 11C",
    "V12A": "VIVEIRO Nº 12A", "V12B1": "VIVEIRO Nº 12B1", "V12B2": "VIVEIRO Nº 12B2",
    "V12B3": "VIVEIRO Nº 12B3", "V12B4": "VIVEIRO Nº 12B4", "V12B5": "VIVEIRO Nº 12B5",
    "V13": "VIVEIRO Nº 13", "V14": "VIVEIRO Nº 14",
}

# Limites fisico-biologicos (validados com o parceiro de Engenharia de Pesca)
# Valores fora do intervalo sao anulados na celula, nao na linha.

LIMITES = {
    "SUP_05": (0, 15), "SOLO_05": (0, 15), "SUP_14": (0, 15), "SOLO_14": (0, 15),
    "TEMP_05": (20, 40), "TEMP_14": (20, 40),
    "PH_05": (5.0, 10.0), "PH_14": (5.0, 10.0),
    "SAL_14": (0, 60),
    "NIVEL": (1, 150),
    "PESO": (0, 60),
    "TDIA": (0.01, 500), "UM": (0.01, 500), "DOIS": (0.01, 500),
}

# Regras de classificacao da fase do ciclo produtivo

PESO_MINIMO_VENDA = 6.0        # g — abaixo disso o cultivo esta incompleto
PESO_MAXIMO_BERCARIO = 3.0     # g — bercario entrega animais pequenos
DIAS_MAXIMO_BERCARIO = 60      # dias — bercario e curto

# Limiar de hipoxia critica na madrugada
LIMIAR_HIPOXIA = 3.0           # mg/L de O2 dissolvido as 05h

# Validacao cruzada
N_FOLDS = 5
SEED = 42
