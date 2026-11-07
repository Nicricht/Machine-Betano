"""CLI para extracción y evaluación local; no ejecuta apuestas."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from machine_betano.statsbomb import catalog_table, download_json, fetch_season
from machine_betano.train import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Machine-Betano: exploración de estadísticas de fútbol")
    sub = parser.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("catalog", help="Descargar catálogo StatsBomb Open Data")
    catalog.add_argument("--data", type=Path, default=Path("data"))
    fetch = sub.add_parser("fetch", help="Descargar temporada de partidos y muestra de jugadores")
    fetch.add_argument("--competition", type=int, default=37)
    fetch.add_argument("--season", type=int, default=90)
    fetch.add_argument("--events", type=int, default=10, help="Partidos con eventos individuales; 0 para omitir")
    fetch.add_argument("--data", type=Path, default=Path("data"))
    train = sub.add_parser("train", help="Evaluación cronológica exploratoria 1X2")
    train.add_argument("--competition", type=int, default=37)
    train.add_argument("--season", type=int, default=90)
    train.add_argument("--data", type=Path, default=Path("data"))
    train.add_argument("--output", type=Path, default=Path("outputs"))
    args = parser.parse_args()

    if args.command == "catalog":
        raw = download_json("competitions.json")
        target = args.data / "processed" / "competitions.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        catalog_table(raw).to_csv(target, index=False)
        print(f"Catálogo guardado en {target}; {len(raw)} competición/temporada")
    elif args.command == "fetch":
        matches, player = fetch_season(args.competition, args.season, args.data, args.events)
        print(f"Partidos: {matches}")
        if player:
            print(f"Muestra parcial de jugadores: {player}")
    elif args.command == "train":
        input_path = args.data / "processed" / f"matches_{args.competition}_{args.season}.csv"
        if not input_path.exists():
            parser.error(f"No existe {input_path}. Ejecuta fetch primero.")
        metrics = evaluate(pd.read_csv(input_path), args.output / f"{args.competition}_{args.season}")
        print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
