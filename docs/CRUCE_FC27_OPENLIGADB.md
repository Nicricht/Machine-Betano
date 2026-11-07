# Cruce EA FC 27 ↔ goleadores OpenLigaDB

## Estado de implementación

Se creó `scripts/link_fc27_openligadb.py`. Combina dos fuentes ya disponibles:

- `Kaggle: mikedpad/ea-sports-fc27-player-ratings` (19.789 jugadores, 60 columnas). Su CSV se normaliza localmente usando `scripts/normalize_kaggle_fc27.py`.
- `OpenLigaDB` (LaLiga y Bundesliga): `*_partidos.csv` y `*_goleadores.csv`. Información comunitaria con licencia ODbL.

**Importante:** el dataset FC27 de Kaggle no tiene verificada una licencia para uso comercial ni confirmación independiente de todas sus valoraciones. El cruce de identidades no convierte ninguna estadística en dato oficial.

## Método de evidencia

1. Para cada partido terminado, reconstruir el equipo al que pertenece cada goleador basándose en las variaciones sucesivas del marcador tras cada gol. Si un marcador es incompleto o contradictorio, descartar la evidencia de ese partido.
2. Para un autogol, atribuir el futbolista al equipo contrario a aquel cuyo marcador aumentó.
3. Comparar el equipo observado en OpenLigaDB con el club del jugador FC27 mediante normalización estricta de mayúsculas, acentos y puntuación; **sin** equivalencias inventadas entre nombres de clubes.
4. Comparar los nombres normalizados: nombre completo exacto, inicial y apellido, o solo apellido.
5. Descartar datos sin equipo o nombre compatible. Las colisiones entre IDs y los candidatos múltiples quedan marcados explícitamente.
6. Escribir el CSV de propuestas `datasets/ratings/fc27_openligadb_candidates.csv` con evidencias y `review_status`:
   - `PROVISIONAL_EXACT`: nombre completo y club iguales, pero todavía NO verificado externamente.
   - `REVIEW_INITIAL_SURNAME`: inicial y apellido coinciden; revisión necesaria.
   - `REVIEW_SURNAME_ONLY`: solo apellido, revisión especialmente importante.
   - `REVIEW_AMBIGUOUS`: varios jugadores FC posibles.
   - `REVIEW_EA_ID_COLLISION`: un ID FC aparece asociado a más de un ID de OpenLigaDB.
7. Guardar únicamente métricas agregadas en el registro de GitHub Actions. **Cero equivalencias se aprueban automáticamente para ML**.

## Frecuencia

El workflow `.github/workflows/cruce-fc27-goleadores.yml` puede ejecutarse manualmente y está programado diariamente a las 23:47, hora de Santiago, una vez actualizado el dataset básico de partidos a las 23:17. GitHub Actions puede retrasar ejecuciones. No funciona como servicio de tiempo real.

Se descargan y normalizan los datos de Kaggle temporalmente; no hay commits ni artifacts de los CSV de ratings y del cruce de identidad. Esto evita redistribuir datos de terceros con derechos aún no verificados.

### Resultado del comando

```bash
python -m pip install "kagglehub>=1.0,<2"
python -m scripts.normalize_kaggle_fc27
python -m scripts.link_fc27_openligadb
```

Los resultados quedan en `datasets/ratings/` (excluidos de Git). El JSON incluye cantidad de goles, identidades observadas, clubes compatibles, propuestas y ambigüedades.

## Limitaciones

- OpenLigaDB reporta **goleadores**, no todos los participantes de un partido. La ausencia de goles NO implica que un jugador no participó ni que tuvo 0 tiros.
- FC27 incluye plantillas y valoraciones de una fecha determinada; los traspasos y cambios de club posteriores pueden impedir o invalidar enlaces por nombre de club.
- Los jugadores que solo figuran en uno de los proveedores quedan sin equivalencia, nunca se rellenan IDs.
- No se pueden consultar actualmente estadísticas avanzadas de todos los jugadores, porque API-Football necesita una clave válida y no se ha verificado cobertura.
- No se debe utilizar el snapshot FC27 para un partido anterior a la fecha `as_of_date` ni usar eventos posteriores al inicio para pronosticar.
- Las propuestas no se usan en los modelos ni se publican como dataset redistribuible hasta una auditoría de identidades y derechos de reutilización.

## Próximos pasos

1. Revisar las coincidencias más prometedoras con fuentes de identificación independientes.
2. Aprobar solo equivalencias de IDs respaldadas por evidencia adicional.
3. Conectar datos actuales de minutos, tiros, tarjetas y xG mediante fuentes autorizadas.
4. Añadir pruebas que comparen modelos con y sin ratings, con evaluación temporal y calibración.
