# Machine-Betano

Proyecto educativo de analítica y Machine Learning aplicado a fútbol. Esta primera versión investiga resultados históricos y estadísticas por jugador, sin apuestas reales, conexión con Betano ni promesas de ganancias.

## Estado de la versión 0.1

- [x] Conector de lectura a StatsBomb Open Data (sin API key).
- [x] Catálogo de competiciones y extracción de partidos históricos.
- [x] Datos de tiros, goles y xG de jugadores en un subconjunto configurable de encuentros.
- [x] Features previas a cada partido usando solo encuentros anteriores.
- [x] Modelo exploratorio 1X2 (local, empate, visitante) con separación temporal y baseline de frecuencias.
- [x] Pruebas automatizadas y CI.
- [ ] Estadísticas completas de todas las ligas y temporadas.
- [ ] Incorporar alineaciones y valoraciones EA Sports FC con permisos de uso.
- [ ] Modelos de goleadores, córners, tarjetas y otros mercados.
- [ ] Calibración y backtesting con cuotas históricas licenciadas.

## Inicio rápido

Requiere Python 3.10 o superior, conexión a internet para obtener los datos y un entorno virtual.

1. Instalar el paquete: python -m pip install -e .
2. Listar competiciones: machine-betano catalog
3. Obtener datos de ejemplo: machine-betano fetch --competition 37 --season 90 --events 10
4. Evaluar el modelo: machine-betano train --competition 37 --season 90
5. Ejecutar pruebas: python -m unittest discover -s tests -v

La competición 37, temporada 90 corresponde a FA Women's Super League 2020/21, únicamente como conjunto de aprendizaje. Para LaLiga se puede cambiar --competition y --season según el catálogo; la cobertura de su repositorio abierto puede ser parcial.

Se guardan archivos en data/ (ignorados por Git) y métricas en outputs/ (ignoradas por Git). No se insertan resultados inventados. Si la muestra no alcanza el mínimo requerido, el entrenamiento se detiene con un error explicativo.

## Ética y límites de los datos

Fuente: StatsBomb Open Data, https://github.com/hudl/open-data. Se reconoce expresamente a StatsBomb como proveedor. Si publicas investigaciones o visualizaciones, consulta sus términos y requisitos de atribución, incluido su logotipo.

IMPORTANTE: el repositorio abierto solo contiene una selección de partidos. La falta de partidos puede sesgar gravemente el entrenamiento; aprobar las pruebas de software no valida la utilidad predictiva. Los eventos de jugadores descargados son posteriores al partido y NO se utilizan como features previas del mismo partido. Un modelo rentable requiere validación temporal, calibración, cobertura, comparaciones contra cuotas y análisis de costos: nada de eso está demostrado aún.

Ver docs/DATOS_Y_LIMITACIONES.md para la metodología y los siguientes hitos.
