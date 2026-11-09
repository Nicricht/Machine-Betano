# Auditoría de Hugging Face: eatpizzanot/soccer-dataset

**Fuente:** https://huggingface.co/datasets/eatpizzanot/soccer-dataset

**Estado:** CANDIDATO EN EVALUACIÓN. No integrado al maestro ni al entrenamiento.

## Qué declara el editor

La ficha se presenta bajo CC BY 4.0 y atribuye su origen a **API-Football y football-data.co.uk**. Anuncia ~673.966 partidos de 2008 a 2027, 271 ligas, 182.125 fichas de jugadores, ~9,96 millones de apariciones y ~4,9 millones de estadísticas individuales. Estas cifras son del editor, no una auditoría de LaLiga/Bundesliga.

Los archivos de interés son fixtures.parquet (partidos), fixture_players.parquet (apariciones), fixture_players_stats_flat.parquet (minutos, tiros, tarjetas), match_stats.parquet (estadística de equipos), league_catalogue.parquet (catálogo pequeño de cobertura). Los archivos masivos llegan a decenas de MB y no se descargan en esta auditoría.

El editor advierte que la cobertura por liga/temporada es desigual y que el xG es una aproximación agregada por zonas de tiro, NO xG por disparo. Su catálogo distingue full/recent_only/partial; esto no demuestra cobertura completa de cada jugador.

## Condición de derechos de uso

La licencia CC BY 4.0 declarada por el agregador no demuestra por sí sola que pueda sublicenciar datos de terceros.

- Football-Data.co.uk limita el uso gratuito a particulares para usos personales o académicos y no permite asumir autorización para productos comerciales o entrenamiento intensivo: https://football-data.co.uk/contact.php
- API-SPORTS restringe la reventa y advierte de derechos de ligas y federaciones: https://api-sports.io/terms
- https://datalicense.uk/d/eatpizzanot/soccer-dataset/ describe la licencia publicada, pero no sustituye derechos de origen.

La confirmación del usuario de autorización de ratings FC27 no implica autorización sobre estas otras tablas. Hasta aclarar su alcance, el conjunto queda fuera de los datasets de entrenamiento y del maestro público.

## Auditoría implementada

Ejecutar python -m scripts.audit_hf_soccer_metadata.

1. Fija una revisión SHA completa del repositorio Hugging Face.
2. Descarga solamente README.md, data_dictionary.md, datapackage.json, QUALITY_REPORT.md y el pequeño league_catalogue.parquet (~40 KB).
3. Identifica las columnas exigidas a nivel de schema y busca específicamente LaLiga y Bundesliga de primera división por país y nombre.
4. Registra estado histórico y años **declarados por el editor**, sin fingir que se han medido filas de partidos o jugadores de esas ligas.
5. Guarda únicamente informes agregados en outputs/auditoria_hf_soccer.json (ignorado por Git). GitHub Actions publica conteos y estados, no datos de terceros.
6. Declara explícitamente approved_for_master_dataset=false y approved_for_model_training=false.

**No hay entrenamiento, compras ni acceso a endpoints de API-Football o Football-Data.** No se publican datos de jugadores ni se asocian IDs por nombre.

## Qué falta medir cuando se aclaren derechos

- Número real de partidos, participaciones y estadísticas por jugador de las temporadas deseadas de LaLiga y Bundesliga.
- Porcentaje no nulo de minutos, tiros, tarjetas y alineaciones por liga y por temporada.
- Integridad de claves fixture_id, player_id, team_id y correspondencias revisadas con OpenLigaDB y FIFA FC27.
- Fecha conocida de cada feature para impedir fuga de información de un partido futuro.
- Atribución, versión y permisos comerciales de las fuentes de datos originales.

## SoccerNet

https://huggingface.co/SoccerNet está dirigido principalmente a tareas de visión con video (tracking y detección de eventos). Es potencialmente útil más adelante, pero no reemplaza por sí solo la estadística tabular individual que requiere Machine-Betano.

El dataset maestro actual datasets/maestro/ continúa construido sólo con OpenLigaDB; los modelos definitivos no se entrenan.
