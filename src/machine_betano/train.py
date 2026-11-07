"""Evaluación temporal exploratoria de resultado 1X2, sin apostar dinero."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from machine_betano.features import FEATURE_COLUMNS, build_features

CLASSES = ["A", "D", "H"]


def evaluate(matches: pd.DataFrame, output_dir: Path, min_rows: int = 80, min_history: int = 3) -> dict:
    """Orden temporal estricto; el test incluye fechas posteriores al train."""
    df = build_features(matches)
    df = df[
        (df["home_matches_prev"] >= min_history)
        & (df["away_matches_prev"] >= min_history)
    ].sort_values(["date", "match_id"]).reset_index(drop=True)
    if len(df) < min_rows:
        raise ValueError(
            f"Solo {len(df)} partidos con historial suficiente (mínimo {min_rows}). "
            "StatsBomb Open Data puede contener una muestra incompleta de la liga; "
            "no entrenar como si fuera una temporada completa."
        )

    # Dividir por fecha para impedir que partidos del mismo día estén en ambos lados.
    unique_days = sorted(df["date"].unique())
    if len(unique_days) < 5:
        raise ValueError("No hay suficientes fechas distintas")
    split_day = unique_days[int(len(unique_days) * 0.8)]
    train = df[df["date"] < split_day]
    test = df[df["date"] >= split_day]
    if len(train) < 30 or len(test) < 10:
        raise ValueError("Separación temporal insuficiente para evaluar")
    if set(train["outcome"]) != set(CLASSES):
        raise ValueError("Entrenamiento sin las tres clases H/D/A")

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=2000, random_state=42)),
    ])
    x_train, x_test = train[FEATURE_COLUMNS], test[FEATURE_COLUMNS]
    y_train, y_test = train["outcome"], test["outcome"]
    model.fit(x_train, y_train)
    p = model.predict_proba(x_test)
    pred = model.predict(x_test)
    classes = list(model.named_steps["classifier"].classes_)
    priors = y_train.value_counts().reindex(CLASSES, fill_value=0).to_numpy(dtype=float)
    priors = (priors + 1) / (priors.sum() + len(CLASSES))
    prior_map = dict(zip(CLASSES, priors.tolist()))
    baseline_probs = np.array([[prior_map[c] for c in classes]] * len(test))
    baseline_pred = max(CLASSES, key=lambda c: prior_map[c])

    metrics = {
        "status": "EXPLORATORY_ONLY",
        "source": "StatsBomb Open Data",
        "warning": "Cobertura abierta no necesariamente completa. Esto no demuestra capacidad de vencer cuotas.",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_last_date": str(train["date"].max()),
        "test_first_date": str(test["date"].min()),
        "accuracy": float(accuracy_score(y_test, pred)),
        "log_loss": float(log_loss(y_test, p, labels=classes)),
        "baseline_accuracy": float(accuracy_score(y_test, [baseline_pred] * len(test))),
        "baseline_log_loss": float(log_loss(y_test, baseline_probs, labels=classes)),
        "classification_report": classification_report(
            y_test, pred, labels=CLASSES, output_dict=True, zero_division=0
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    predictions = test[["date", "match_id"]].copy()
    for optional in ("home_team", "away_team"):
        if optional in test:
            predictions[optional] = test[optional]
    predictions["actual"] = y_test.to_numpy()
    predictions["predicted"] = pred
    for c, label in (("H", "p_home"), ("D", "p_draw"), ("A", "p_away")):
        predictions[label] = p[:, classes.index(c)]
    predictions.to_csv(output_dir / "predictions_test.csv", index=False)
    joblib.dump(model, output_dir / "model.joblib")
    return metrics
