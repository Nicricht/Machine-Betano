# Dataset maestro de Machine-Betano

## Objetivo

Primero normalizar y comprobar los datos, **después entrenar**. El flujo de actualización de OpenLigaDB ya NO ejecuta el modelo 1X2 de manera automática. El entrenamiento de exploración anterior permanece en `scripts/train_live_1x2.py`, pero requiere ejecución explícita y sigue bloqueando pronósticos cuando pierde frente al baseline.

El maestro se construye con:

```bash
python -m unittest discover -s tests -p "test_master_dataset.py" -v
python -m scripts.build_master_dataset
```

La acción `.github/workflows/actualizacion-datos.yml` genera y verifica automáticamente el maestro después de actualizar los partidos y goles. Publica las tablas bajo `datasets/maestro/` con licencia ODbL-1.0 y hashes SHA256.

## Tablas públicas derivadas de OpenLigaDB

| Archivo | Grano | Contenido | Prohibición |
|---|---|---|---|
| `master_partidos.csv` | Un registro por partido, por temporada y liga | IDs de equipos, fecha, 12 variables prepartido, resultado posterior y estado | Las columnas `*_postmatch` no se usan como features |
| `master_eventos_gol.csv` | Un evento goleador informado | ID del futbolista en OpenLigaDB, minuto, penal, autogol, marcador tras el gol, club inferido solo si secuencia completa | Es información del propio partido, no se introduce como predictor de ese partido |
| `master_goleadores_observados.csv` | Futbolista observado anotando en un club | Goles, goles de penal, autogoles, cantidad de partidos en que marcó | No equivale a plantilla; sin minutos, tiros ni partidos jugados totales |
| `calidad_y_cobertura.json` | Estado del snapshot | Conteos por temporada, cobertura, SHA256, campos faltantes y preparación | No declara completo un dataset por contar muchas filas |

Las temporadas históricas de Bundesliga 2024/25 y 2025/26 incluyen **resultados de partidos**, pero no se inventan eventos de gol por futbolista. LaLiga 2024/25 y 2025/26 sigue sin histórico equivalente confirmado desde la fuente actual.

## Comprobaciones que deben aprobar

- Sin pares duplicados `(liga, temporada, ID partido)`.
- Cada partido y cada conjunto de features corresponden al mismo ID.
- Cada feature prepartido es recalculado directamente desde el histórico anterior, **no** desde el propio resultado ni desde partidos posteriores.
- Timestamp de fuente y snapshot de features compatibles.
- El ganador coincide con el marcador; no hay resultados de partidos aún no terminados.
- El manifiesto coincide con el número de partidos y el número de eventos de gol.
- Los históricos no fueron alterados sin actualizar el checksum.
- El equipo del goleador se infiere solo si la secuencia de goles publicada explica exactamente el marcador final; los datos ambiguos conservan club vacío.
- Toda ausencia permanece vacía o figura como no cubierta, nunca se convierte silenciosamente en cero.

**Importante**: estas comprobaciones garantizan consistencia *interna*, no que los resultados de una fuente comunitaria coincidan con un organismo oficial. Para uso en producción se necesita una fuente deportiva adicional independiente.

## FIFA FC 27 (catálogo privado separado)

El usuario confirmó que dispone de autorización de uso de los datos, pero el workflow no verifica el alcance de esa autorización ni publica copias masivas de terceros. El dataset de Kaggle con 19.789 fichas fue descargado y normalizado anteriormente en el runner de CI.

Para preparar el catálogo privado enlazado:

```bash
python -m pip install "kagglehub>=1.0,<2"
python -m scripts.normalize_kaggle_fc27
python -m scripts.build_master_dataset
python -m scripts.enrich_master_fc27
```

Salida privada `datasets/ratings/master_fc27_jugadores_verificados.csv`, excluida de Git. Mantiene los campos OVR/PAC/SHO/PAS/DRI/DEF/PHY del FC 27 únicamente si existe una asociación entre IDs revisada con evidencia.

Formato del registro privado opcional `datasets/ratings/id_map_verificados.csv`:

```csv
league,openligadb_player_id,fc_player_id,review_status,evidence_url,reviewed_by,reviewed_on
```

Para que se acepte una fila, requiere `review_status=VERIFIED`, fecha ISO, URL HTTPS de evidencia y nombre de revisor. La validación comprueba coherencia de IDs y evita que un ID FC represente dos futbolistas deportivos. **No prueba que una URL sea cierta por sí sola**: una auditoría humana o una fuente oficial de correspondencias es indispensable.

El proceso anterior de coincidencias entre nombres de jugadores solo produce candidatos. No se promociona automáticamente un candidato a identidad verificada. En ausencia del registro privado, la unión devuelve **cero** ratings enlazados, con los campos FIFA vacíos. La fecha del snapshot FIFA no puede utilizarse para explicar partidos anteriores.

## Estado previo al entrenamiento definitivo

- Datos estructurados de partidos 1X2: disponibles con controles internos y procedencia.
- Datos de goles por futbolista: disponibles parcialmente; solo jugadores que figuran anotando.
- Ratings FC 27: catálogo privado listo para asociación por IDs revisados; asociaciones reales todavía pendientes.
- Estadísticas de minutos, tiros, tarjetas, asistencias y alineaciones por jugador actual: **incompletas**. El conector API-Football requiere una clave funcional y cobertura verificada.
- xG actual y datos equivalentes: no disponibles para todos los futbolistas y partidos.
- Entrenamiento completo de modelos por jugador o con apuesta: **NO LISTO**.

**Política:** no entrenar modelos definitivos hasta contar con una tabla verificable por futbolista y partido, fuentes autorizadas, IDs compatibles y una división temporal sin fuga. No realizar apuestas ni gastos reales.
