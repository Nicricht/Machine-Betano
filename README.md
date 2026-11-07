# Machine-Betano

Proyecto de investigación y aprendizaje automático aplicado a datos históricos de fútbol. No realiza apuestas reales ni promete rentabilidad.

## Fuentes y estado
- **OpenLigaDB, activo:** resultados de LaLiga y Bundesliga (temporada 2026/27) y goleadores de la comunidad. Se actualiza mediante [GitHub Actions](.github/workflows/actualizacion-datos.yml) en [datasets/actualizados](datasets/actualizados/).
- **API-Football, conector implementado, pendiente de acceso:** extracción de partidos, estadísticas individuales, tiros, córners, tarjetas, lesiones y alineaciones. Necesita una clave autorizada en el secreto `API_FOOTBALL_KEY`. Sus datos no se publican en este repositorio público por limitaciones contractuales. [Metodología y cobertura](docs/FUENTES_AVANZADAS.md).
- **StatsBomb Open Data, histórico:** hay una versión exploratoria y archivos de ejemplo en el [PR #1](https://github.com/Nicricht/Machine-Betano/pull/1); no garantiza cobertura actual ni total.
- **EA Sports FC y xG actual:** pendientes de acceso verificable y derechos de uso.

Los identificadores de equipos y jugadores son específicos de cada proveedor. No mezclar nombres o estadísticas de diferente origen sin validación.

## Pruebas
```bash
python -m unittest discover -s tests -v
```

## Uso avanzado autorizado
```bash
# Configurar API_FOOTBALL_KEY en el entorno, no en archivos públicos
python scripts/refresh_api_football.py --budget 35
```
CSV privados generados en `datasets/avanzados/` (excluidos por .gitignore). Las consultas programadas solo estarán activas en `main` y si el secreto existe. Si falta, el workflow declara PENDIENTE DE ACCESO y no simula una descarga.

Todos los resultados observados **después** de un partido se deben excluir de las variables predictoras de ese mismo partido. El proyecto no ha demostrado ventaja sobre cuotas de casas de apuestas.

## Kaggle y Hugging Face: EA FC 26

Encontramos bases recientes de FIFA/EA FC publicadas por terceros. El conector experimental `scripts/audit_hf_fc26.py` puede leer y auditar las valoraciones FC26 desde Hugging Face, con archivos distintos para porteros y jugadores de campo. **No son necesariamente datos oficiales ni tienen licencia de reutilización verificada**: de momento se auditan cantidades y calidad, sin redistribuir los CSV ni mezclarlos con los resultados. Ver [evaluación de datasets](docs/AUDITORIA_DATASETS_FC.md) y [valoraciones](docs/RATINGS_EA_FC.md).
