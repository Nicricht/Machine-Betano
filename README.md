# Machine-Betano

Proyecto de investigación y aprendizaje automático aplicado a datos históricos de fútbol. No realiza apuestas reales ni promete rentabilidad.

## Fuentes y estado
- **OpenLigaDB, activo:** resultados de LaLiga y Bundesliga (temporada 2026/27) y goleadores de la comunidad. Se actualiza mediante [GitHub Actions](.github/workflows/actualizacion-datos.yml) en [datasets/actualizados](datasets/actualizados/).
- **API-Football, conector implementado, pendiente de acceso:** extracción de partidos, estadísticas individuales, tiros, córners, tarjetas, lesiones y alineaciones. Necesita una clave autorizada en el secreto `API_FOOTBALL_KEY`. Sus datos no se publican en este repositorio público por limitaciones contractuales. [Metodología y cobertura](docs/FUENTES_AVANZADAS.md).
- **StatsBomb Open Data, histórico:** hay una versión exploratoria y archivos de ejemplo en el [PR #1](https://github.com/Nicricht/Machine-Betano/pull/1); no garantiza cobertura actual ni total.
- **EA Sports FC27:** 19.789 registros descargados y normalizados en runner privado; IDs deportivos aún sin verificar. **xG actual:** pendiente de fuente suficiente.

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

## Dataset EA FC27 de Kaggle

El usuario seleccionó [EA SPORTS FC 27 Player Ratings](https://www.kaggle.com/datasets/mikedpad/ea-sports-fc27-player-ratings). La auditoría sin credenciales está en `scripts/audit_kaggle_fc27.py`, con pruebas y workflow. Su resultado es exclusivamente metadatos (calidad/filas/columnas, sin copiar datos de terceros al repositorio); ver [documentación](docs/KAGGLE_FC27.md). Antes de entrenar, se debe verificar licencia, autenticidad, snapshot y correspondencias entre IDs de EA y jugadores de las ligas.

## Cruce de jugadores FC 27 con goles reales (experimental)

Se añadió un proceso que intenta asociar IDs de futbolistas de FC27 (Kaggle) con goleadores de OpenLigaDB (LaLiga y Bundesliga) usando **nombre, club y evidencia de marcador**, sin confiar en equivalencias por nombre únicamente. Ejecuta a diario una auditoría privada y informa cobertura agregada; las propuestas nunca se convierten por sí solas en identificaciones confirmadas ni se utilizan para predecir. [Método y límites](docs/CRUCE_FC27_OPENLIGADB.md).


## Primer modelo de resultados y cobertura de jugadores

Como exploración técnica anterior se generaron:
- Un **resumen observado de goles por jugador**, sin suponer minutos, tiros o participación en partidos donde no anotó.
- Un **modelo exploratorio 1X2** (local, empate, visitante) con corte cronológico, accuracy, log-loss y Brier, comparado con un baseline del entrenamiento.
- La publicación de probabilidades estuvo bloqueada cuando el modelo no superó al baseline. **El modelo no se entrena automáticamente mientras completamos el dataset maestro.**

```bash
python -m pip install -r requirements-model.txt
python -m scripts.build_scorer_summary
python -m scripts.train_live_1x2
```

La ejecución automática publica un artifact de evaluación. **No se han integrado todavía ratings FC27 al entrenamiento**, porque los IDs de FIFA y los de los proveedores deportivos todavía no se han confirmado, aunque la descarga y normalización técnica ya funcionan. Ver [alcance y requisitos pendientes](docs/MODELO_1X2_Y_COBERTURA_JUGADORES.md).


## Preparación antes de entrenar: dataset maestro

El proceso de datos ahora genera `datasets/maestro/master_partidos.csv`, `master_eventos_gol.csv`, `master_goleadores_observados.csv` y `calidad_y_cobertura.json`. Cada tabla declara origen, fecha y nulos; las 12 variables de los partidos se recalculan para impedir filtración de resultados futuros. Los goles del propio partido están separados de las variables predictoras.

Los ratings EA FC27 se procesan en un catálogo **privado**; únicamente pasan a una ficha unificada si hay un mapa revisado de identificadores FIFA ↔ OpenLigaDB. Ninguna coincidencia por nombre se confirma automáticamente. No hay todavía minutos, tiros, tarjetas y participación de todos los jugadores.

**No se ejecutan entrenamientos automáticos del modelo 1X2 ni predicciones finales mientras cerramos la calidad de los datos.** El modelo histórico permanece disponible como experimento reproducible, no como producto listo. [Esquema, pruebas y pendientes](docs/DATASET_MAESTRO.md).

## Fuente Hugging Face en evaluación (NO integrada)

El usuario localizó el [Global Football Soccer Data Lake](https://huggingface.co/datasets/eatpizzanot/soccer-dataset). Incluye potencialmente minutos, tiros, tarjetas y apariciones por partido, pero el autor declara procedencia API-Football y football-data.co.uk, con permisos aguas arriba aún sin comprobar. El lector `scripts/audit_hf_soccer_metadata.py` analiza solo el diccionario, metadatos y catálogo pequeño de ligas; no descarga los millones de filas individuales ni alimenta modelos. Ver [auditoría y bloqueos](docs/AUDITORIA_HF_SOCCER.md).
