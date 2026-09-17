# Predição do Peso do Camarão com Machine Learning

Projeto de aprendizado de máquina para prever o **peso** do camarão-branco
(*Litopenaeus vannamei*) ao longo do cultivo, a partir de dados reais de campo de uma
fazenda de carcinicultura.

> Os notebooks já vêm executados, com os gráficos e resultados visíveis — é só abrir
> na ordem 01 → 07.

## A ideia

Depois de estudar o trabalho de Mujahid et al. (2025), que previu o crescimento de
camarão na Indonésia usando dados operacionais reais, decidi seguir a mesma lógica: tratar
cada biometria (pesagem) como um exemplo e usar o **dia de cultivo** e a **ração
acumulada** como preditores principais. A intuição é simples — o que mais determina o
tamanho do camarão é há quanto tempo ele cresce e quanto ele comeu no total.

## Principais resultados

- Modelo **Random Forest** com erro médio de ~2,4g e **R² ≈ 0,68** (validação GroupKFold
  por viveiro).
- As variáveis mais importantes são o **dia de cultivo** e a **ração acumulada por
  animal**, batendo com a literatura.
- Foram comparados 8 algoritmos; os modelos de árvore tiveram o melhor desempenho.

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# pipeline de dados
python -m src.extracao
python -m src.limpeza
python -m src.despesca
python -m src.features
python -m src.peso            # gera o dataset de biometrias

# modelagem
python -m src.modelo_peso     # compara os modelos
```

Depois é só abrir os notebooks (`jupyter notebook`) na ordem 01 → 07.

## Estrutura

```
├── data/raw/          formulário de campo original (.xlsx)
├── notebooks/         a análise passo a passo
│   ├── 01_extracao_limpeza.ipynb
│   ├── 02_exploracao.ipynb
│   ├── 03_features.ipynb
│   ├── 04_modelagem.ipynb
│   ├── 05_comparacao_modelos.ipynb
│   ├── 06_interpretabilidade.ipynb
│   └── 07_conclusao.ipynb
├── src/
│   ├── extracao.py / limpeza.py / despesca.py / features.py   pipeline de dados
│   ├── peso.py           monta o dataset de biometrias (uma linha por pesagem)
│   └── modelo_peso.py    treino, comparação e validação por viveiro
├── requirements.txt
└── README.md
```

## Referência principal

MUJAHID, M. A. A. A. et al. Prediction of Shrimp Growth by Machine Learning: The Use of
Actual Data of Industrial-Scale Outdoor White Shrimp (*Litopenaeus vannamei*) Aquaculture
in Indonesia. *Aquaculture Journal*, v. 5, n. 4, art. 27, 2025.
# previsao-peso-camarao
