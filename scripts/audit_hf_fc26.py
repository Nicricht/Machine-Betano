#!/usr/bin/env python3
"""Audita datasets comunitarios EA FC 26 alojados en Hugging Face.

Fuente de terceros (no EA): Kishohar/footballIQ.
Sin scraping del sitio de EA ni credenciales. La licencia de reutilización
no está identificada; por defecto solo genera metadatos de calidad.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "Kishohar/footballIQ"
REVISION = "b3338a3319b8fe33f40bcdc2c21e4da19adad07f"
FILENAMES = ("ea_fc26_outfield.csv", "ea_fc26_goalkeepers.csv")
SOURCE = "https://huggingface.co/datasets/" + REPO
FIELDS = ("id", "overallRating", "firstName", "lastName", "commonName", "team", "leagueName", "position",
          "pac", "sho", "pas", "dri", "def", "phy", "gkDiving", "gkHandling",
          "gkKicking", "gkPositioning", "gkReflexes")
MAX_BYTES = 10_000_000


def download(filename: str) -> bytes:
    if filename not in FILENAMES:
        raise ValueError("Archivo de origen no permitido")
    url = f"{SOURCE}/resolve/{REVISION}/{filename}"
    req = Request(url, headers={"User-Agent": "Machine-Betano-audit/0.1"})
    with urlopen(req, timeout=45) as response:
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("Archivo supera el límite de tamaño")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Archivo supera el límite de tamaño")
    return data


def rating(raw: str | None, field: str, row_number: int):
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip()
    if not value.isdecimal() or not 0 <= int(value) <= 99:
        raise ValueError(f"Fila {row_number}: {field} fuera de rango 0-99")
    return int(value)


def audit_csv(content: bytes, kind: str) -> dict:
    if kind not in ("outfield", "goalkeepers"):
        raise ValueError("Tipo de jugador no reconocido")
    decoded = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    required = {"id", "overallRating", "firstName", "lastName", "position", "team"}
    if kind == "outfield":
        required.update({"pac", "sho", "pas", "dri", "def", "phy"})
    else:
        required.update({"gkDiving", "gkHandling", "gkKicking", "gkPositioning", "gkReflexes"})
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Faltan columnas de {kind}: {sorted(missing)}")
    ids = set()
    total = 0
    min_rating, max_rating = 100, -1
    missing_club = 0
    nonempty = {field: 0 for field in FIELDS}
    for row_number, row in enumerate(reader, 2):
        raw_id = str(row.get("id") or "").strip()
        if not raw_id.isdecimal():
            raise ValueError(f"Fila {row_number}: id inválido")
        if raw_id in ids:
            raise ValueError(f"Fila {row_number}: id repetido")
        ids.add(raw_id)
        value = rating(row.get("overallRating"), "overallRating", row_number)
        if value is None:
            raise ValueError(f"Fila {row_number}: overallRating vacío")
        min_rating = min(min_rating, value)
        max_rating = max(max_rating, value)
        if not str(row.get("team") or "").strip():
            missing_club += 1
        for key in nonempty:
            if str(row.get(key) or "").strip():
                nonempty[key] += 1
        if kind == "outfield":
            for field in ("pac", "sho", "pas", "dri", "def", "phy"):
                rating(row.get(field), field, row_number)
        else:
            for field in ("gkDiving", "gkHandling", "gkKicking", "gkPositioning", "gkReflexes"):
                rating(row.get(field), field, row_number)
        total += 1
    if total == 0:
        raise ValueError("CSV sin jugadores")
    return {
        "category": kind, "records": total, "distinct_player_ids": len(ids),
        "overall_min": min_rating, "overall_max": max_rating,
        "missing_club": missing_club,
        "columns_found": reader.fieldnames,
        "nonempty_by_field": nonempty,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def audit_sources(outfield: bytes, goalkeepers: bytes, timestamp: str | None = None) -> dict:
    a = audit_csv(outfield, "outfield")
    b = audit_csv(goalkeepers, "goalkeepers")
    return {
        "dataset": REPO,
        "source_url": SOURCE,
        "source_revision": REVISION,
        "edition_claimed": "FC26",
        "license": "NO_VERIFICADA",
        "source_type": "user-uploaded dataset (no acreditado como fuente oficial EA)",
        "checked_at_utc": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_rows": a["records"] + b["records"],
        "tables": [a, b],
        "training_ready": False,
        "why_not_training_ready": [
            "Licencia de contenido EA y de reutilización del dataset por verificar",
            "Falta comprobar las valoraciones con fuentes oficiales",
            "Faltan mapeos revisados entre IDs de FIFA y proveedores de resultados",
            "No hay fecha fiable de publicación de cada valoración para backtesting histórico",
            "FC26 no representa automáticamente valoraciones FC27",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditar el CSV público FC26 sin redistribuirlo")
    parser.add_argument("--local-dir", type=Path, help="Usar archivos locales en vez de red")
    parser.add_argument("--report", type=Path, default=Path("outputs/hf_fc26_audit.json"))
    args = parser.parse_args()
    def get(filename):
        if args.local_dir:
            return (args.local_dir / filename).read_bytes()
        return download(filename)
    result = audit_sources(get(FILENAMES[0]), get(FILENAMES[1]))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source": result["dataset"], "edition": "FC26",
        "total_rows": result["total_rows"],
        "categories": {x["category"]: x["records"] for x in result["tables"]},
        "license": result["license"], "training_ready": False,
        "report": str(args.report)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
