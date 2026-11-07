# Datos, metodología y limitaciones

## Procedencia

- Proveedor inicial: StatsBomb Open Data, https://github.com/hudl/open-data.
- El paquete obtiene JSON públicos, sin autenticación y sin copiar datasets masivos al repositorio.
- La cobertura NO es exhaustiva: determinadas temporadas solo tienen partidos seleccionados. El código no presupone que todas las jornadas de una liga estén disponibles.
- El catálogo oficial indica qué pares competition_id/season_id se pueden consultar. Por defecto se utiliza FA Women's Super League 2020/21, 37/90, para empezar con un caso de aprendizaje, no para predecir partidos de noviembre de 2026.
- Antes de publicar un análisis, cumplir los requisitos de atribución de StatsBomb, incluido logo cuando corresponda, y verificar licencias adicionales aplicables.

## Tablas

- matches_ID_ID.csv: un registro por partido con fecha, clubes, resultado y fuente.
- player_shots_sample_ID_ID.csv: resumen individual de tiros, goles a partir de tiros y xG, SOLO de los primeros N partidos descargados. No presenta estadísticas acumuladas de toda la liga.
- La fuente raw se conserva en data/raw/; archivos generados y resultados están excluidos del control de versiones.

## Features que realmente usa la versión 0.1

Para local y visitante, por separado, en sus últimos cinco partidos disponibles anteriores a la fecha: número de encuentros registrados, promedio de goles a favor, goles en contra, puntos por partido, fracción de victorias y días de descanso. Se reinicia el historial por competición y temporada. Los partidos del mismo día no se filtran entre sí.

No se usan los goles finales, eventos posteriores ni xG postpartido del propio encuentro como variables de entrada. Esto reduce la fuga temporal, pero NO soluciona la selección no aleatoria de encuentros publicados.

## Evaluación

- Se excluyen partidos cuyos dos equipos no tengan al menos tres encuentros anteriores disponibles.
- Partición cronológica por fechas, aproximadamente 80 % entrenamiento y 20 % test. El test es posterior al entrenamiento.
- Se calcula accuracy y log-loss frente a una referencia de frecuencias históricas suavizadas; se guardan probabilidades por clase y modelo.
- Si faltan partidos o clases para una prueba mínima, se detiene y explica la limitación.
- Tests de software ejecutados en GitHub Actions no equivalen a backtesting deportivo válido ni prueban valor económico.

## Camino hacia predicción de mercados

1. Auditar cobertura completa, jornadas faltantes y definición consistente de métricas.
2. Obtener fuentes con permisos de uso y temporadas completas de LaLiga y otras ligas.
3. Incorporar alineaciones confirmadas o probables y stats individuales anteriores a cada partido.
4. Incorporar valoraciones EA Sports FC solo después de verificar la licencia y mapeo de IDs, como variables auxiliares; no como datos deportivos oficiales.
5. Comparar modelos de goles (Poisson y variantes), jugadores (minutos y xG90 históricos) y córners/tarjetas (series históricas); evaluar calibración y drift.
6. Establecer backtesting temporal con cuotas históricas y comisiones/márgenes; registrar incertidumbre y abstenerse de predicciones sin cobertura suficiente.

El proyecto no ejecuta apuestas reales, no extrae datos privados de Betano y no promete rentabilidad.
