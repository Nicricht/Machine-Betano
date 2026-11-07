# Machine-Betano: 1X2 exploratorio y cobertura observada por jugador

## Qué funciona

Los CSV de OpenLigaDB disponibles en `datasets/actualizados/` se actualizan automáticamente con un manifiesto que registra fecha y origen. En cada refresco:

1. Se obtienen resultados, goles y goleadores sin imputar ausencias como ceros.
2. Se calculan `*_features_prepartido.csv` basados solo en partidos anteriores del mismo club y temporada, con ventana de hasta cinco encuentros.
3. Se exportan `*_goleadores_resumen.csv`. Contienen **únicamente goles observados**, penales, autogoles y cantidad de **partidos donde el futbolista marcó**. No equivalen a partidos jugados totales. `minutes_known`, `shots_known` y `games_played_known` quedan vacíos, nunca cero inventado.
4. Se prepara un primer modelo de **probabilidad de resultado local / empate / visitante** con regresión logística y comparación contra una distribución de frecuencias histórica del entrenamiento.

## Validación temporal

`python -m scripts.train_live_1x2` produce:

- `outputs/modelo_actual/modelo_1x2_validacion.json`: número de partidos, rango de entrenamiento y prueba, exactitud, `log_loss` multiclase y Brier multiclase, tanto del modelo como de una referencia basada solo en clases conocidas del pasado.
- `outputs/modelo_actual/partidos_proximos_1x2_exploratorio.csv`: probabilidades **no calibradas**, exclusivamente para encuentros dentro de los próximos 7 días con al menos tres partidos anteriores por equipo.

El corte temporal se hace por día, nunca aleatorio. Se evalúa un modelo entrenado con las fechas anteriores a un bloque de prueba posterior; después de evaluar, se permite reentrenar con todos los resultados conocidos para el próximo pronóstico. La predicción de un partido nunca utiliza su propio marcador, estadísticas posteriores ni ratings FIFA unidos con IDs inciertos.

Estos resultados NO son apuestas ni pronósticos con ventaja probada sobre las cuotas. Con menos partidos que un estudio multitemporada, una sola prueba temporal no demuestra robustez; faltan calibración y una evaluación walk-forward de varias temporadas.

## FIFA FC 27 y autorización

El usuario declaró que el uso de los datos está autorizado. Esa confirmación habilita la continuidad de la investigación en este proyecto, pero **no sustituye la verificación de los términos del titular de los datos para redistribución pública/comercial**. Conservamos las copias de ratings EA/Kaggle y propuestas de equivalencia fuera del repositorio público.

Se auditaron previamente **19.789 fichas FIFA** y se generaron **165 propuestas de enlace** con goleadores reales; **0 están validadas como identidades confirmadas para entrenar**. El proceso solo conoce goleadores, no plantillas completas ni participación en cada encuentro. No se usan atributos FC 27 en el baseline 1X2 hasta resolver identidades y fechas de publicación de ratings.

## Qué bloquea los modelos por jugador

- Minutos, tiros, pases y tarjetas de todos los futbolistas actuales: falta conexión a un proveedor de eventos de partido con cobertura suficiente. El conector a API-Football ya existe, pero no se ha acreditado una clave funcional en el workflow.
- El acceso a FC 27 no equivale a estadísticas reales de partidos; ratings como SHO y PAC son opiniones del videojuego.
- La unificación entre IDs EA FC, API-Football y OpenLigaDB requiere correspondencias verificadas, no nombres similares solamente.
- Los xG reales actuales tampoco están disponibles de forma exhaustiva para las dos ligas.
- Sin mediciones de todos los futbolistas no se puede evaluar legítimamente quién tendrá más tiros o tarjetas.

## No introducir datos de Football-Data.co.uk en entrenamiento

Aunque los CSV son visibles gratuitamente, su política publicada restringe el uso en productos de AI/model training y automatizaciones intensivas: https://football-data.co.uk/contact.php. Por tanto este proyecto no usa esa fuente en la nueva canalización. Las fuentes empleadas son los resultados OpenLigaDB y su ODbL, con la licencia y procedencia registradas.

## Reproducción

```bash
python -m pip install -r requirements-model.txt
python -m unittest discover -s tests -p "test_live_model.py" -v
python -m unittest discover -s tests -p "test_scorer_summary.py" -v
python -m scripts.build_scorer_summary
python -m scripts.train_live_1x2
```

En GitHub Actions, estos pasos generan CSV de goles de jugador en `datasets/actualizados/` y un artifact `machine-betano-modelo-1x2` de auditoría/modelo. Si faltan partidos suficientes al inicio de una temporada, la evaluación del modelo puede omitirse sin impedir que se publiquen los resultados deportivos.

## Siguiente fase

1. Aumentar temporadas históricas con permisos de uso para validar distintas campañas y equipos.
2. Conseguir cobertura de participantes y estadísticas individuales mediante una API autorizada.
3. Consolidar mapeos de IDs confirmados por fuentes independientes y fecha histórica.
4. Calibrar probabilidades, medir deriva y comparar con un baseline robusto en múltiples periodos.
