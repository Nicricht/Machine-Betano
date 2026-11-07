#!/usr/bin/env python3
"""Backfill educativo y con atribucion OpenLigaDB (ODbL-1.0).

Solo temporadas terminadas; se ejecuta una vez si existe el manifiesto.
Las fuentes de otras webs pueden prohibir el uso para entrenar IA, por eso
aqui solo utilizamos las ligas que ya provee OpenLigaDB.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.refresh_openligadb import fetch_matches, normalize, write_csv, MATCH_COLUMNS
from scripts.build_live_features import build_features, COLUMNS as FEATURE_COLUMNS

LEAGUES = ("la1", "bl1")
YEARS = (2024, 2025)
MIN_COMPLETED = 150


def backfill(output_dir: Path, now: datetime | None = None,
             fetcher=fetch_matches, force: bool = False):
    checked = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    marker = output_dir / "manifest.json"
    if marker.exists() and not force:
        report = json.loads(marker.read_text(encoding="utf-8"))
        if (report.get("leagues") and all(
            (output_dir / f"{r['league']}_{r['season']}_features_prepartido.csv").exists()
            for r in report["leagues"]
        )):
            return report

    # Descargas del historico: si una temporada no existe, se informa y
    # se usan solamente temporadas con evidencia suficiente.
    prepared = []
    failures = []
    for league in LEAGUES:
        for year in YEARS:
            try:
                source = fetcher(league, year)
                matches, _ = normalize(source, league, year)
                finished = sum(row["outcome"] in {"H", "D", "A"} for row in matches)
                if finished < MIN_COMPLETED:
                    raise ValueError(f"Insuficiente cobertura ({finished} terminados)")
                features = build_features(matches, checked.isoformat(timespec="seconds"))
                prepared.append((league, year, matches, features, finished))
            except (ValueError, RuntimeError, KeyError, TypeError) as exc:
                failures.append({"league": league, "season": year, "reason": str(exc)[:250]})
    if not prepared:
        # No reemplazar un histórico anterior válido.
        raise RuntimeError("Sin temporadas anteriores con cobertura suficiente")

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "checked_at_utc": checked.isoformat(timespec="seconds"),
        "provider": "OpenLigaDB",
        "license": "ODbL-1.0",
        "leagues": [],
        "skipped_sources": failures,
        "historical_source_policy": "Solo resultados publicados, no se usan productos con restricciones para ML",
    }
    for league, year, matches, features, finished in prepared:
        prefix = f"{league}_{year}"
        write_csv(output_dir / (prefix + "_partidos.csv"), MATCH_COLUMNS, matches)
        write_csv(output_dir / (prefix + "_features_prepartido.csv"), FEATURE_COLUMNS, features)
        report["leagues"].append({
            "league": league, "season": year,
            "matches": len(matches), "finished_with_final_score": finished,
            "source_url": f"https://api.openligadb.de/getmatchdata/{league}/{year}",
        })
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Extraer temporadas históricas de OpenLigaDB")
    parser.add_argument("--output", type=Path, default=Path("datasets/historicos"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    report = backfill(args.output, force=args.force)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
