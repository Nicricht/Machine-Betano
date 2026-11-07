#!/usr/bin/env python3
"""Modelo 1X2 exploratorio con evaluacion cronologica usando OpenLigaDB.

Nunca usa ratings FC27 sin un vinculo de identidad revisado. Tampoco usa
cuotas ni estadisticas del propio encuentro para predecirlo.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from scripts.build_live_features import FEATURES

LABELS = ("H", "D", "A")
X_COLS = [f"{side}_{field}" for side in ("home", "away") for field in FEATURES]
SCORE_COLS = [
    "league", "season_start_year", "match_id", "kickoff_utc",
    "home_team", "away_team", "as_of_utc",
    "p_home", "p_draw", "p_away",
    "history_sufficient", "model_status",
]


def utc(timestamp: str) -> datetime:
    value = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Fecha sin zona horaria")
    return value.astimezone(timezone.utc)


def read_rows(directory: Path, manifest: dict) -> list[dict]:
    rows = []
    seen = set()
    expected_time = utc(manifest["checked_at_utc"])
    for record in manifest["leagues"]:
        name = f"{record['league']}_{record['season']}_features_prepartido.csv"
        path = directory / name
        with path.open(encoding="utf-8", newline="") as file:
            values = list(csv.DictReader(file))
        if len(values) != int(record["matches"]):
            raise ValueError(f"{name}: cantidad distinta del manifiesto")
        for row in values:
            key = (row["league"], row["season_start_year"], row["match_id"])
            if key in seen:
                raise ValueError("Partido duplicado")
            seen.add(key)
            if utc(row["as_of_utc"]) != expected_time:
                raise ValueError(f"Features desactualizadas respecto de la fuente: {name}")
            row["_kickoff"] = utc(row["kickoff_utc"])
            # Un resultado conocido del futuro respecto de la consulta es inadmisible.
            if row["target_1x2"] and row["_kickoff"] > expected_time:
                raise ValueError("Fuga temporal: marcador futuro en resultados")
            rows.append(row)
    return rows


def sufficient(row: dict) -> bool:
    return str(row.get("both_teams_min3_prior", "")).lower() == "true"


def matrix(rows: list[dict]) -> np.ndarray:
    values = []
    for row in rows:
        one = []
        for col in X_COLS:
            item = str(row.get(col, "")).strip()
            one.append(float(item) if item else np.nan)
        values.append(one)
    return np.asarray(values, dtype=float).reshape(-1, len(X_COLS))


def baseline(train_targets: list[str], n: int) -> np.ndarray:
    # Suavizado de Laplace; no inferir distribucion del conjunto test.
    counts = Counter(train_targets)
    distribution = np.asarray([counts.get(label, 0) + 1 for label in LABELS], dtype=float)
    distribution /= distribution.sum()
    return np.tile(distribution, (n, 1))


def multiclass_brier(targets: list[str], probabilities: np.ndarray) -> float:
    observed = np.asarray([[float(label == x) for label in LABELS] for x in targets])
    return float(np.mean(np.sum((probabilities - observed) ** 2, axis=1)))


def evaluate(targets: list[str], probs: np.ndarray) -> dict:
    if not len(targets):
        raise ValueError("No hay partidos para evaluar")
    if probs.shape != (len(targets), 3):
        raise ValueError("Matriz de probabilidades mal dimensionada")
    if np.any(~np.isfinite(probs)) or np.any(probs < 0) or not np.allclose(probs.sum(axis=1), 1):
        raise ValueError("Probabilidades invalidas")
    pred = [LABELS[int(i)] for i in np.argmax(probs, axis=1)]
    return {
        "matches": len(targets),
        "accuracy": round(float(accuracy_score(targets, pred)), 4),
        "log_loss": round(float(log_loss(targets, probs, labels=list(LABELS))), 4),
        "brier_multiclass": round(multiclass_brier(targets, probs), 4),
        "distribution": {label: targets.count(label) for label in LABELS},
    }


def new_model():
    return make_pipeline(
        SimpleImputer(strategy="median", add_indicator=False),
        StandardScaler(),
        LogisticRegression(max_iter=1000, C=0.5, random_state=42),
    )


def ordered_probabilities(model, x: np.ndarray) -> np.ndarray:
    values = model.predict_proba(x)
    return np.column_stack([values[:, list(model.classes_).index(label)] for label in LABELS])


def split_temporally(finished: list[dict], train_ratio: float = 0.75):
    finished = sorted(finished, key=lambda r: (r["_kickoff"], r["league"], r["match_id"]))
    days = sorted({r["_kickoff"].date() for r in finished})
    if len(days) < 8:
        raise ValueError("Demasiadas pocas fechas para prueba cronologica")
    cutoff = days[max(1, min(len(days) - 1, int(len(days) * train_ratio)))]
    train = [row for row in finished if row["_kickoff"].date() < cutoff]
    test = [row for row in finished if row["_kickoff"].date() >= cutoff]
    if len(train) < 35 or len(test) < 10:
        raise ValueError("Muestra insuficiente para un holdout real")
    if len({row["target_1x2"] for row in train}) != 3:
        raise ValueError("El entrenamiento requiere las tres clases H/D/A")
    if max(row["_kickoff"] for row in train).date() >= min(row["_kickoff"] for row in test).date():
        raise ValueError("Corte temporal invalido")
    return train, test


def fit_report(rows: list[dict], as_of: str, horizon_days: int = 7) -> tuple[dict, list[dict]]:
    checked = utc(as_of)
    finished = [
        row for row in rows if row.get("target_1x2") in LABELS
        and row["_kickoff"] < checked and sufficient(row)
    ]
    train, test = split_temporally(finished)
    x_train, x_test = matrix(train), matrix(test)
    train_y = [r["target_1x2"] for r in train]
    test_y = [r["target_1x2"] for r in test]
    model = new_model().fit(x_train, train_y)
    predicted = ordered_probabilities(model, x_test)
    raw = baseline(train_y, len(test))
    validation = evaluate(test_y, predicted)
    reference = evaluate(test_y, raw)
    improved = validation["log_loss"] < reference["log_loss"]
    # Tras validar sin usar el futuro del holdout, reentrenar con el
    # pasado completo para la fotografia actual.
    full_model = new_model().fit(matrix(finished), [r["target_1x2"] for r in finished])
    next_rows = [
        row for row in rows if not row.get("target_1x2")
        and checked < row["_kickoff"] <= checked + timedelta(days=horizon_days)
        and sufficient(row) and str(row.get("future_fixture", "")).lower() == "true"
    ]
    next_rows.sort(key=lambda r: (r["_kickoff"], r["league"], r["match_id"]))
    scored = []
    # No publicar probabilidades cuando el modelo pierde contra el baseline.
    if next_rows and improved:
        next_probs = ordered_probabilities(full_model, matrix(next_rows))
        for row, probs in zip(next_rows, next_probs):
            scored.append({
                "league": row["league"],
                "season_start_year": row["season_start_year"],
                "match_id": row["match_id"],
                "kickoff_utc": row["kickoff_utc"],
                "home_team": row["home_team"], "away_team": row["away_team"],
                "as_of_utc": as_of,
                "p_home": round(float(probs[0]), 5),
                "p_draw": round(float(probs[1]), 5),
                "p_away": round(float(probs[2]), 5),
                "history_sufficient": True,
                "model_status": "EXPLORATORY_NOT_CALIBRATED",
            })
    report = {
        "evaluated_at_utc": as_of,
        "train_matches": len(train),
        "test_matches": len(test),
        "train_end_utc": max(r["_kickoff"] for r in train).isoformat(),
        "test_start_utc": min(r["_kickoff"] for r in test).isoformat(),
        "warm_matches_with_result": len(finished),
        "warmup_min_previous_matches_each_team": 3,
        "features": X_COLS,
        "labels": LABELS,
        "training_leagues": sorted({r["league"] for r in finished}),
        "test_model": validation,
        "baseline_only_train_distribution": reference,
        "test_model_better_log_loss_than_baseline": improved,
        "upcoming_next_7_days_with_enough_history": len(next_rows),
        "published_probability_rows": len(scored),
        "publication_guard": (
            "MODEL_BETTER_THAN_BASELINE_BUT_UNCALIBRATED" if improved
            else "BLOCKED_MODEL_WORSE_THAN_BASELINE"
        ),
        "model_status": (
            "EXPLORATORY_NOT_CALIBRATED" if improved
            else "RESEARCH_UNDERPERFORMS_BASELINE"
        ),
        "player_ratings_in_training": False,
        "source": "OpenLigaDB ODbL; datos de resultados ya publicados",
        "limitations": [
            "Aun no hay prediccion de tiros individuales, tarjetas ni goles por jugador",
            "Sin ratings EA FC27 en entrenamiento porque falta vinculo de identidad verificado",
            "Datos de una sola temporada y muestra pequena; la mejora no garantiza rentabilidad",
            "No hay validacion cruzada walk-forward extendida ni calibracion fuera de muestra",
            "No usar el conjunto de prueba para elegir hiperparametros sin una nueva validacion",
        ],
    }
    return report, scored


def run(directory: Path, output: Path, horizon_days: int = 7) -> dict:
    manifest = json.loads((directory / "ultima_actualizacion.json").read_text(encoding="utf-8"))
    rows = read_rows(directory, manifest)
    report, scored = fit_report(rows, manifest["checked_at_utc"], horizon_days=horizon_days)
    output.mkdir(parents=True, exist_ok=True)
    (output / "modelo_1x2_validacion.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "partidos_proximos_1x2_exploratorio.csv").open(
            "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SCORE_COLS)
        writer.writeheader()
        writer.writerows(scored)
    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluar 1X2 con corte temporal y baseline")
    parser.add_argument("--data", type=Path, default=Path("datasets/actualizados"))
    parser.add_argument("--out", type=Path, default=Path("outputs/modelo_actual"))
    parser.add_argument("--horizon-days", type=int, default=7)
    args = parser.parse_args()
    if args.horizon_days < 1 or args.horizon_days > 30:
        parser.error("horizon-days debe estar entre 1 y 30")
    report = run(args.data, args.out, horizon_days=args.horizon_days)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
