# Fuentes FIFA / EA FC encontradas en Kaggle y Hugging Face

## Selección verificada

1. **Hugging Face: Kishohar/footballIQ**, CSV `ea_fc26_outfield.csv` y `ea_fc26_goalkeepers.csv`.
   - URL: https://huggingface.co/datasets/Kishohar/footballIQ
   - Versión fija para auditoría: `b3338a3319b8fe33f40bcdc2c21e4da19adad07f`.
   - Hay campos `id`, `overallRating`, `team`, `position`, valores `pac,sho,pas,dri,def,phy` de jugadores de campo y `gkDiving,gkHandling,gkKicking,gkPositioning,gkReflexes` de porteros.
   - **Advertencia:** el visor conjunto de Hugging Face da error porque los porteros y jugadores de campo tienen diferente esquema. El adaptador descarga y valida ambos CSV por separado, sin invocar el visor.
   - **Licencia**: no se observó una licencia explícita para este repositorio; la accesibilidad pública del archivo NO demuestra derechos de reutilización comercial o redistribución. Tampoco acredita que todos los datos sean auténticos de EA. No incluir copias masivas en Git público.
2. **Kaggle: flynn28/eafc26-player-database**:
   - URL: https://www.kaggle.com/datasets/flynn28/eafc26-player-database
   - Publicado como EAFC 26, con conjuntos de futbolistas de ambos géneros. Falta verificar contenido exacto, cambios y licencia antes de importar.
3. **Kaggle European Soccer Database, espejo en Hugging Face**:
   - https://huggingface.co/datasets/julien-c/kaggle-hugomathien-soccer
   - Repositorio con licencia indicada ODbL y datos de más de 25.000 partidos y 10.000 futbolistas, 2008–2016, con atributos históricos FIFA.
   - Útil para un benchmark histórico que combine FIFA y marcadores, NO para valorar los equipos de 2026.
   - Aun cuando la tarjeta indique ODbL, verificar posibles derechos subyacentes de EA, ligas y cuotas antes de reutilizar comercialmente.

## Estado de la integración

El código `scripts/audit_hf_fc26.py` descarga automáticamente los dos CSV públicos FC26 mediante URLs directas fijadas a un commit, comprueba rangos de atributos, duplicados y conteos, y guarda exclusivamente el informe de calidad **local** en `outputs/hf_fc26_audit.json`.

Ejecutar: `python scripts/audit_hf_fc26.py`

Las pruebas y la descarga real de archivos se ejecutan en GitHub Actions sin claves ni gastos; solo se publica un resumen de conteos, nunca los datos masivos. Por defecto NO conecta dichos atributos al predictor porque todavía faltan pruebas de procedencia y derechos, IDs revisados y fecha de disponibilidad histórica. No utilizaremos datos futuros para predecir partidos pasados.

Para acceder al CSV original autorizado en la propia plataforma, usar su enlace de descarga; no publicar copias en `Machine-Betano`.

**EA Sports FC 27**, la edición vigente a noviembre 2026, todavía no está cubierta por este dataset FC26. No confundir edición con temporada ni inventar valoraciones de FC27.

## Siguiente fase

- Comprobar licencia y derechos de uso para el fin propuesto.
- Verificar cobertura de jugadores relevantes frente a EA o fuentes equivalentes.
- Crear tabla revisada de equivalencias `fc_player_id -> proveedor_player_id`, nunca empatar por nombre automáticamente.
- Preservar cada versión de ratings con fecha real de publicación para backtesting temporal.
- Comparar modelos de resultados y goleadores con/sin ratings, nunca asumir mejora automática.
