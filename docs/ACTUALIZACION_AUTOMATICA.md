# Actualización automática de datos en Machine-Betano

## Estado de fuentes

- Fuente activa inicial: https://openligadb.de (Open Database License, ODbL 1.0).
- LaLiga: `la1`; Bundesliga: `bl1`. Fuente comunitaria no oficial, con posibles retrasos en resultados y goles.
- No requiere claves, pagos ni scraping de casas de apuestas.
- Fuente diferente de StatsBomb histórico; NO mezclar IDs o campos directamente entre proveedores.
- No hay todavía feed de tarjetas, tiros, lesiones, xG, alineaciones probables o ratings EA Sports FC actuales.

## Calendario y funcionamiento

GitHub Actions `actualizacion-datos.yml`: 08:17, 14:17 y 23:17, zona `America/Santiago`, todos los días. GitHub puede demorar la ejecución programada. Solo ejecuta schedules desde la rama principal. También se puede disparar manualmente.

- Obtiene todos los partidos de la temporada europea que corresponde a la fecha de ejecución.
- Registra resultados completos **solo si** el partido terminó y la fuente tiene marcador final de 90 minutos. Un partido no finalizado nunca recibe resultado ficticio.
- Descarga eventos de goles y goleadores cuando la comunidad los ha informado. No confundir goles registrados con estadística individual exhaustiva.
- Guarda CSV en `datasets/actualizados/{liga}_{temporada}_partidos.csv` y `{liga}_{temporada}_goleadores.csv`, más `ultima_actualizacion.json` con fuente, fecha de consulta, cobertura y aviso de calidad.
- Conserva un snapshot de cada ejecución como artifact GitHub Actions por 90 días. GitHub hace un commit de los CSV más recientes al terminar con éxito; si la fuente falla se preservan los últimos datos publicados.
- La actualización no reentrena automáticamente modelos y no significa que existan predicciones fiables para todos los mercados.

## Calidad y licencias

- https://openligadb.de/lizenz (ODbL 1.0): revisar obligaciones de atribución y compartir bases derivadas.
- Fuente comunitaria; cruzar con datos profesionales/autorizados antes de utilizar el modelo para decisiones de dinero.
- Sin inventar marcadores, eventos ni fechas de partidos.
- El pipeline falla ante respuestas vacías, match IDs duplicados o equipos no identificados.
- Los archivos de snapshot archivados se pueden utilizar para preservar evidencia de cuándo se conocían datos: fundamental para evitar leakage histórico.
- Cuando la temporada cambia (julio), el nombre del archivo cambia; las temporadas anteriores quedan conservadas.
- GitHub puede desactivar workflows programados en repositorios públicos sin actividad durante 60 días. No es un servicio de tiempo real.

## Próximos conectores

API-Football u otro proveedor licenciado para lesiones, alineaciones, tiros, xG y estadísticas por jugador. Requiere credenciales y verificar cobertura del plan; ninguna clave debe almacenarse en archivos públicos ni logs.
