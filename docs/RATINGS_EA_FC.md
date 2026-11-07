# EA SPORTS FC: fuente adicional del modelo Machine-Betano

## Datos de origen

Fuente principal verificada: https://www.ea.com/games/ea-sports-fc/ratings
Edición actual en noviembre de 2026: **EA SPORTS FC 27**. La base oficial muestra más de 19 mil futbolistas, con atributos OVR, PAC, SHO, PAS, DRI, DEF y PHY. Los porteros requieren atributos específicos como GK diving/handling/reflexes, que **aún no** gestiona el CSV inicial.

**IMPORTANTE:** la base oficial que se consulta públicamente corresponde a los ítems base de Ultimate Team en el lanzamiento, no a las valoraciones dinámicas de modos de juego. Los ratings son valoraciones subjetivas del videojuego, no mediciones de rendimiento deportivo, y no representan resultados reales ni probabilidades de goles.

## Derechos y método

La política de EA (https://help.ea.com/en/articles/security-and-rules/ea-content-policy/) y su acuerdo de usuario (https://www.ea.com/legal/user-agreement) restringen el uso comercial, minería de datos y redistribución no autorizada. Este repositorio **no hace scraping**, no ejecuta descargas masivas de EA y **no incluye copias de su base de jugadores**.

Cuando exista un CSV obtenido de forma autorizada, usar:
```sh
python scripts/import_fc_ratings.py ruta/al/archivo_autorizado.csv
```

El archivo se valida y guarda localmente en `datasets/ratings/fc_ratings.csv`, excluido del repositorio público. Columnas obligatorias:
```csv
edition,as_of_date,fc_player_id,name,club,position,ovr,pac,sho,pas,dri,def,phy,source_url
```
Si un atributo está ausente, queda **vacío**, no se inventa ni se convierte a cero. OVR, nombre, posición, club, fecha, edición, ID y fuente son obligatorios. El importador no certifica autenticidad ni licencia de quien entregue el CSV.

## Integración al predictor

1. Verificar derechos de uso y procedencia de snapshots por edición y fecha.
2. Resolver mapeo **revisado** entre `fc_player_id` y los IDs de API-Football u otros proveedores. No unir por nombre, porque pueden existir homónimos y transferencias.
3. Una vez verificado, incorporar los ratings anteriores a la fecha del partido como features opcionales y contrastar métricas **con y sin ratings**.
4. Las estadísticas oficiales del futbolista (minutos, xG, tiros reales, titularidad) tienen prioridad. Los ratings deben actualizarse cuando EA publique nuevos valores, no necesariamente todos los días.
5. Para partidos históricos se debe usar la valoración que existía **antes de ese partido**, nunca la de la edición posterior.

**Estado:** importador validado y automatizable; **ninguna base masiva oficial de FC27 ha sido descargada ni integrada**. No confundir estas pruebas con la conexión real o un dataset completo.
