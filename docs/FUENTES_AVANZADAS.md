# Conector avanzado: API-Football

## Estado real (noviembre 2026)

- El conector y sus tests están implementados, pero **NO hay garantía de que haya una API key configurada**.
- No se declara "en vivo" hasta que exista `API_FOOTBALL_KEY`, el workflow ejecute consultas y registre cobertura real.
- Acceso: https://www.api-football.com/ ; documentación https://www.api-football.com/documentation-v3
- Plan gratuito anunciado: 100 peticiones/día, con temporadas limitadas. El script usa como máximo **35 consultas por ejecución** y se detiene cuando la cuota del proveedor se acerca a 10 peticiones restantes. Dos ejecuciones por día no exceden el presupuesto programado de 70 consultas, salvo otras apps usando la misma cuenta.
- Liga española: API-Football ID 140; Bundesliga: ID 78. No equivale a IDs de OpenLigaDB ni de StatsBomb. **No unificar identificadores por nombre sin revisar una tabla de correspondencias**.
- Cron propuesto: 09:43 y 18:43 hora de Santiago. GitHub Actions puede retrasarse.

## Datos soportados

- `fixtures.csv`: identificador, fecha, estado y resultado solo para partidos terminados en FT (las prórrogas y penales no son objetivo 1X2 a 90 minutos).
- `players.csv`: rendimiento por jugador y partido (minutos, tiros, goles, pases, tarjetas).
- `team_stats.csv`: tiros, córners, posesión, tarjetas y faltas por partido/equipo.
- `injuries.csv`: jugadores con ausencias o dudas reportadas por la API.
- `lineups.csv`: titulares y suplentes. Incluye `collected_before_kickoff` para distinguir información previa/posterior.
- `estado.json`: fecha UTC, cuotas disponibles, cobertura y advertencias de representatividad.

**NO se incluyen xG o valoraciones EA Sports FC**, porque no están verificadas en esta fuente. Tampoco se infieren probabilidades de titulares ni lesiones faltantes.

## Cómo funciona el acceso

El script usa exclusivamente un secreto `API_FOOTBALL_KEY` en el entorno y nunca lo imprime. 
- Ejecutar localmente, en un entorno de acceso autorizado: `python scripts/refresh_api_football.py --budget 35`.
- En el repositorio, el workflow de datos avanzados tiene el secreto con ese nombre. Si falta, los tests pasan y el estado indica explícitamente **PENDIENTE DE ACCESO**, sin fingir que se descargó nada.
- El cron se ejecuta desde `main`, no desde ramas con PR abierto.
- Cuando no hay partidos en los días consultados, no se sustituye el último snapshot con ficheros vacíos.

## Derechos de uso y almacenamiento

El repositorio `Machine-Betano` es **público**. Los términos de API-Football advierten expresamente que el proveedor no concede derechos generales de publicación de los datos de cada competición y que pueden requerirse licencias adicionales, especialmente para servicios relacionados con apuestas. Ver https://www.api-football.com/terms.

**Por ese motivo, este workflow NO publica, sube como artefacto ni hace commit de estadísticas obtenidas con una clave privada.** Las procesa temporalmente durante la ejecución y solo informa conteos. Para conservar un histórico de dichos datos, crear un destino privado y comprobar que el almacenamiento y uso previsto están permitidos contractualmente. No usar un repositorio público para distribuir copias de datos restringidos.

La información básica de OpenLigaDB (ODbL, ver `docs/ACTUALIZACION_AUTOMATICA.md`) continúa guardándose en los CSV públicos ya existentes. StatsBomb Open Data aporta xG histórico en selecciones publicadas.

## Limitaciones pendientes

1. Obtener acceso de API-Football por cuenta autorizada. No abrir cuentas o contratar planes en nombre del usuario sin autorización.
2. Verificar que las ligas/temporadas tienen cobertura real por campo; `coverage=true` tampoco garantiza todos los partidos.
3. Revisar autorización para almacenar datos restringidos en un destino privado adecuado.
4. Definir pipeline histórico que use `retrieved_at_utc < kickoff_utc` para no filtrar datos del futuro en el entrenamiento.
5. Completar proveedor de xG fiable y legal para temporadas recientes.
6. Incorporar valoraciones FIFA/EA FC solo con condiciones adecuadas de uso.
7. Evaluar calibración, deriva, incertidumbre y retorno hipotético únicamente con datos y cuotas con permisos adecuados.

No se realizan apuestas, scraping a Betano ni cargos.
