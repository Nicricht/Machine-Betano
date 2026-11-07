# Kaggle: EA SPORTS FC 27 Player Ratings

- Dataset señalado por el usuario: https://www.kaggle.com/datasets/mikedpad/ea-sports-fc27-player-ratings
- Referencia independiente: https://www.ea.com/games/ea-sports-fc/ratings
- La ficha pública indica aprox. **19.789 futbolistas** y snapshot declarado **2026-09-12**. Es un dataset **publicado por un tercero**, no una licencia oficial de EA.
- El sitio de Kaggle no expone aquí un detalle legible de todos sus archivos ni una licencia confirmada. No se debe afirmar que sus columnas, fechas o derechos están verificados antes de ejecutar la auditoría.
- `scripts/audit_kaggle_fc27.py` descarga el dataset público con `kagglehub.dataset_download("mikedpad/ea-sports-fc27-player-ratings")`, inspecciona archivos CSV, número de filas, campos, IDs duplicados, atributos fuera de rango y SHA256.
- El informe guarda solo metadatos en `outputs/auditoria_kaggle_fc27.json`. La descarga queda en caché de KaggleHub; **no se publica** el archivo de jugadores ni se realiza scraping de EA.
- La cobertura de Kaggle puede cambiar con versiones. Si no hay CSV válidos, el job falla y no se fingen estadísticas.
- La información FIFA es un conjunto de ratings del videojuego, no goles, xG, tiros observados, lesiones o probabilidades de mercado.
- Para unir a API-Football u OpenLigaDB, se requiere mapeo controlado de IDs y fechas históricas correctas. La presencia de un jugador en un club a septiembre de 2026 no significa que siga allí en otra fecha.

## Ejecución

```bash
python -m pip install "kagglehub>=1.0,<2"
python scripts/audit_kaggle_fc27.py
```

La tarea de GitHub Actions se ejecuta en el PR para comprobar el dataset real. No es un cron diario: los ratings FIFA se revisarán cuando EA publique actualizaciones y cuando las licencias lo permitan.

## Bloqueos para producción

1. Verificar condiciones de licencia del publicador y derechos subyacentes de EA.
2. Comprobar que el archivo sea auténtico y que los 19.789 identificadores estén bien formados.
3. Integrar un extractor de versión con retención privada autorizada; no republicar el dataset en un repositorio público.
4. Emparejar jugadores con fuentes deportivas reales mediante IDs verificados antes de incorporarlos como features.

## Auditoría verificada en GitHub Actions

La descarga real del dataset Kaggle con `kagglehub` aprobó en [esta ejecución](https://github.com/Nicricht/Machine-Betano/actions/runs/42409557338): `players.csv` tiene **19.789 filas y 60 columnas**.

El segundo paso `scripts/normalize_kaggle_fc27.py` convierte el archivo local a la estructura estándar del proyecto, con `edition=FC27`, fecha del snapshot tomada de cada fila, ID EA, club, posición y ratings OVR/PAC/SHO/PAS/DRI/DEF/PHY. El archivo generado permanece en la ejecución temporal o en la computadora local; no se distribuye públicamente. Si faltan fechas o columnas requeridas, falla antes de declarar importación correcta.

La auditoría e importación de formato **no** acreditan derechos comerciales ni una unión con las estadísticas deportivas reales. La verificación de autenticidad y licencia sigue siendo requisito previo a utilizarlo en modelos predictivos o redistribuirlo.
