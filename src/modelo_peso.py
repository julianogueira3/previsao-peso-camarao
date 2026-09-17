"""
modelo_peso.py
--------------
Avaliacao e comparacao de modelos para previsao do peso do camarao, com
validacao GroupKFold por viveiro (mesma estrategia do modelo de sobrevivencia).

Uso:
    python -m src.modelo_peso
"""
import warnings; warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, cross_validate, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.svm import SVR
from sklearn.ensemble import (RandomForestRegressor, ExtraTreesRegressor,
                              GradientBoostingRegressor, HistGradientBoostingRegressor)

from src.config import SEED, N_FOLDS
from src.peso import construir_dataset_peso, FEATURES_PESO, ALVO_PESO

try:
    from xgboost import XGBRegressor
    TEM_XGB = True
except ImportError:
    TEM_XGB = False
try:
    from lightgbm import LGBMRegressor
    TEM_LGBM = True
except ImportError:
    TEM_LGBM = False


def catalogo():
    m = {
        "Ridge (linear)": (Ridge(alpha=1.0), True),
        "SVR": (SVR(C=10, epsilon=0.1), True),
        "Random Forest": (RandomForestRegressor(
            n_estimators=300, max_depth=8, min_samples_leaf=3, random_state=SEED), False),
        "Extra Trees": (ExtraTreesRegressor(
            n_estimators=400, max_depth=10, min_samples_leaf=3, random_state=SEED), False),
        "Gradient Boosting": (GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=SEED), False),
        "HistGradientBoosting": (HistGradientBoostingRegressor(
            max_depth=4, learning_rate=0.05, random_state=SEED), False),
    }
    if TEM_XGB:
        m["XGBoost"] = (XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, random_state=SEED, verbosity=0), False)
    if TEM_LGBM:
        m["LightGBM"] = (LGBMRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                         subsample=0.8, random_state=SEED, verbose=-1), False)
    return m


def _pipeline(modelo, escalar):
    et = [("imp", SimpleImputer(strategy="median"))]
    if escalar:
        et.append(("sc", StandardScaler()))
    et.append(("m", modelo))
    return Pipeline(et)


def carregar():
    df = construir_dataset_peso()
    feats = [f for f in FEATURES_PESO if f in df.columns]
    return df, feats


def avaliar_um(df, feats, modelo, escalar):
    X, y, g = df[feats], df[ALVO_PESO], df["VIVEIRO"]
    cv = cross_validate(_pipeline(modelo, escalar), X, y, groups=g,
                        cv=GroupKFold(N_FOLDS),
                        scoring=["neg_mean_absolute_error", "r2",
                                 "neg_root_mean_squared_error"])
    return (-cv["test_neg_mean_absolute_error"].mean(),
            -cv["test_neg_root_mean_squared_error"].mean(),
            cv["test_r2"].mean())


def comparar():
    df, feats = carregar()
    linhas = []
    for nome, (mod, esc) in catalogo().items():
        mae, rmse, r2 = avaliar_um(df, feats, mod, esc)
        linhas.append({"Modelo": nome, "MAE": mae, "RMSE": rmse, "R2": r2})
    base_mae, base_rmse, base_r2 = avaliar_um(df, feats, DummyRegressor(strategy="mean"), False)
    linhas.append({"Modelo": "Baseline (média)", "MAE": base_mae, "RMSE": base_rmse, "R2": base_r2})
    return pd.DataFrame(linhas).sort_values("RMSE").reset_index(drop=True), len(df), df["VIVEIRO"].nunique()


if __name__ == "__main__":
    tab, n, nv = comparar()
    print(f"PREVISAO DE PESO — {n} biometrias, {nv} viveiros, GroupKFold por viveiro\n")
    for _, r in tab.iterrows():
        marca = "  <-- escolhido" if r.Modelo == "Random Forest" else ""
        print(f"  {r.Modelo:22} MAE {r.MAE:.3f}g  RMSE {r.RMSE:.3f}g  R2 {r.R2:+.3f}{marca}")
