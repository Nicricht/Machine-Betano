# Fuente y cobertura del dataset incluido

- Fuente primaria: StatsBomb Open Data (Hudl), https://github.com/hudl/open-data
- Fuente exacta de resultados: https://github.com/hudl/open-data/blob/master/data/matches/37/90.json
- Competición: FA Women's Super League, temporada 2020/21.
- Registros encontrados: **131 partidos**, **50 fechas de calendario**.
- Datos de partidos y resultados verificados contra el JSON original de StatsBomb.
- Archivo de features: 12 variables numéricas por partido, usando únicamente resultados previos en la misma temporada. Las celdas vacías representan información todavía no existente antes de ese partido, no cero.
- Las columnas de goles finales y 'outcome' son **variables objetivo/resultados conocidos después del partido**, NUNCA deben utilizarse como features para predecir ese mismo partido.
- Los eventos de jugadores se recopilan por separado. Los datos FIFA/EA Sports FC, lesiones y probabilidades actuales todavía NO están incluidos.
- Esta es una temporada histórica de aprendizaje; no refleja plantillas actuales ni garantiza cobertura completa.

Este repositorio se mantiene en fase educativa, sin apuestas reales ni garantías de rentabilidad.
