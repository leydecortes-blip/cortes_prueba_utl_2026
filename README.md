# CORTES — Prueba Técnica UTL Senado 2026

## Candidato

**Nombre:** CORTES PINTO LEYDE KATERINE
**Email:** cortesleidyk@gmail.com
**Repositorio:** https://github.com/leydecortes-blip/cortes_prueba_utl_2026

## Instalación

Requiere Python 3.10 o superior. Todas las dependencias están listadas en `requirements.txt`.

```bash
git clone https://github.com/leydecortes-blip/cortes_prueba_utl_2026.git
cd cortes_prueba_utl_2026
pip install -r requirements.txt
```

Dependencias principales: `pandas`, `matplotlib`, `numpy`, `scipy`.
La base de datos y los archivos raw se generan al correr el pipeline; no se incluyen en el repositorio.

## Pipeline de ejecución

Ejecutar en orden desde la raiz del repositorio:

```bash
# 1. Verificar conteo de mesas antes de descargar (bonus preflight)
python scraper/scraper.py --preflight

# 2. Extraer datos de los 4 municipios (tarda entre 4 y 8 minutos)
python scraper/scraper.py

# 3. Generar y validar el manifest (Retos 1, 2, 3 y 5)
python outputs/generar_manifest.py

# 4. Generar el dashboard HTML autocontenido
python dashboard/generar_dashboard.py

# 5. Generar las visualizaciones Python (Reto 5)
python viz/heatmap.py
python viz/scatter.py
```

Para municipios adicionales de Boyaca (bonus):

```bash
python scraper/scraper.py --municipios CHIQUINQUIRA "VILLA DE LEYVA" MONIQUIRA
```

## API

**URL base:** `https://resultadospreccongreso2026.registraduria.gov.co`

**Patron de URL de votos:**
```
/json/ACT/{CORP}/{codigo}.json
```
donde `CORP` es `CA` (Camara) o `SE` (Senado), y `{codigo}` puede ser:

| Longitud | Nivel | Ejemplo |
|----------|-------|---------|
| 2 digitos | Nacional | `00` |
| 7 digitos | Municipio (divipol) | `0700079` |
| 13 digitos | Puesto de votacion | `0700079010002` |
| 19 digitos | Mesa individual | `0700079010002000001` |

**Nomenclador:** `https://resultadospreccongreso2026.registraduria.gov.co/json/nomenclator.json`
Archivo JSON nacional con la jerarquia territorial. Cada puesto (nivel 6) trae el campo `m` con su numero de mesas. El nivel 7 (mesa) no se lista en el nomenclador; los codigos de mesa se construyen como `codigo_puesto + numero_mesa.zfill(6)`.

**8 campos JSON relevantes por mesa:**

| Campo | Descripcion |
|-------|-------------|
| `camaras[0].partotabla` | Lista de bloques por partido |
| `act.codpar` | Codigo del partido |
| `act.cantotabla` | Lista de candidatos del partido |
| `nomcan` | Nombre del candidato |
| `apecan` | Apellido del candidato |
| `codcan` | Numero del candidato en la lista |
| `vot` | Votos obtenidos por el candidato |
| `pvot` | Porcentaje de votos |

**Cabeceras HTTP necesarias:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Accept: application/json, text/plain, */*
Accept-Language: es-CO,es;q=0.9,en;q=0.8
Referer: https://resultadospreccongreso2026.registraduria.gov.co/
Origin: https://resultadospreccongreso2026.registraduria.gov.co
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-origin
```
Sin estas cabeceras la API devuelve 403.

## Municipios en la BD

| Municipio | Divipol | Puestos | Mesas |
|-----------|---------|---------|-------|
| TUNJA | 0700001 | 26 | 424 |
| PAIPA | 0700181 | 7 | 95 |
| SOGAMOSO | 0700277 | 18 | 301 |
| DUITAMA | 0700079 | 22 | 287 |
| **Total** | | **73** | **1107** |

Base de datos: 1.216.033 filas de votos, 1127 candidatos, 25 partidos.

## Hallazgos principales

**Partido lider en Senado por municipio:**

| Municipio | Partido lider SE | Votos SE |
|-----------|-----------------|---------|
| TUNJA | Pacto Historico | 20.147 |
| DUITAMA | Pacto Historico | 15.026 |
| SOGAMOSO | Pacto Historico | 13.749 |
| PAIPA | Alianza Verde | 3.963 |

**Arrastre del voto Verde (Camara a Senado):**
La Alianza Verde muestra arrastre positivo en todos los municipios (ratio SE/CA mayor a 1.0 en la mayoria de puestos), siendo Duitama el municipio con los puestos de mayor arrastre (hasta 1.71 en el puesto mas alto). Paipa es el unico municipio donde Verde lidera el Senado, lo que refleja una base territorial mas solida en ese municipio.

**Top 5 candidatos por atribucion deterministica en Senado:**

| Candidato | Partido | Votos CA | Atribucion SE |
|-----------|---------|---------|--------------|
| YAMIT NOE HURTADO NEIRA | Verde | 10.969 | 10.776,7 |
| JAIME RAUL SALAMANCA TORRES | Verde | 9.209 | 9.047,6 |
| RAMIRO BARRAGAN ADAME | Verde | 8.703 | 8.550,4 |
| HECTOR DAVID CHAPARRO CHAPARRO | Conservador | 13.497 | 8.170,1 |
| EDUAR ALEXIS TRIANA RINCON | CD | 4.349 | 6.522,0 |

**Scatter CA vs SE por mesa:** r de Pearson = 0.959, lo que indica una correlacion muy alta entre la participacion en Camara y en Senado a nivel de mesa individual. La pendiente de 0.928 sugiere que el Senado recibe ligeramente menos votos que la Camara en promedio por mesa.

**Limitacion documentada:** solo se homologan 4 partidos (Verde, Pacto Historico, Centro Democratico, Partido Conservador) porque el JSON de la API no incluye el nombre del partido a nivel de bloque; los demas partidos se identifican unicamente por su codpar numerico y se agrupan como "Otros" en el dashboard.

## Bonus implementados

**+3 pts — Flag `--preflight` en el scraper (Reto 1.2)**

El scraper soporta `python scraper/scraper.py --preflight`. Consulta el nomenclador, cuenta las mesas por municipio usando el campo `m` de cada puesto, y ademas detecta automaticamente el formato del codigo de mesa probando una llamada real a la API (confirma si el relleno es de 6 o 7 digitos). No escribe nada en la base de datos.

**+2 pts — Indices SQLite con justificacion (Reto 2.1)**

Se crearon 5 indices en `db/schema.sql`:

- `idx_votos_candidato` sobre `votos(candidato_id)`: optimiza los JOIN frecuentes entre votos y candidatos en todas las consultas analiticas.
- `idx_votos_mesa` sobre `votos(mesa_id)`: optimiza los JOIN con mesas en tarea_3_1 y tarea_3_2.
- `idx_candidatos_partido` sobre `candidatos(partido_id)`: acelera el filtro por partido al calcular totales por canonico.
- `idx_mesas_puesto` sobre `mesas(puesto_id)`: optimiza la agregacion por puesto en tarea_3_1.
- `idx_puestos_municipio` sobre `puestos(municipio_id)`: acelera el filtro por municipio en el dashboard y el manifest.

**+2 pts — Por que el top CA no siempre coincide con el top atribucion SE (Reto 3.3)**

La formula de atribucion es `A_ij = (votos_cand_CA / votos_partido_CA) * votos_SE_partido`. Esta formula pondera los votos del candidato por la fuerza de su partido en Senado, no por sus votos absolutos. Un candidato con muchos votos en Camara pero de un partido debil en Senado obtiene una atribucion baja, porque el multiplicador `votos_SE_partido` es pequeño. Por ejemplo, HECTOR DAVID CHAPARRO tiene 13.497 votos en Camara (el mas alto entre los homologados) pero su atribucion SE queda en cuarto lugar porque el Partido Conservador tiene menos caudal en Senado que la Alianza Verde en estos cuatro municipios. El top por atribucion premia a los candidatos cuyo partido traslada bien el voto de Camara a Senado, no solo a los mas votados en Camara.

**+3 pts — Dark mode toggle con CSS custom properties (Reto 4)**

El dashboard implementa modo oscuro mediante el atributo `data-theme="dark"` en el `body` y variables CSS (`:root` para modo claro, `[data-theme="dark"]` para oscuro). El boton en el header alterna entre los dos modos y las graficas de Plotly se redibujan automaticamente con la paleta del tema activo.

**+2 pts — Boton Exportar CSV funcional (Reto 4)**

Cada pestana del dashboard tiene un boton "Exportar CSV" que descarga los datos visibles en ese momento. El CSV incluye BOM UTF-8 para que Excel lo abra correctamente con tildes y caracteres especiales.

**+3 pts — Municipios adicionales de Boyaca (Bonus libre)**

El diccionario `MUNICIPIOS` en `scraper.py` incluye 5 municipios adicionales de Boyaca: Chiquinquira (0700116), Villa de Leyva (0700401), Ramiriqui (0700237), Moniquira (0700168) y Aquitania (0700040). Se pueden extraer con:

```bash
python scraper/scraper.py --municipios CHIQUINQUIRA "VILLA DE LEYVA" MONIQUIRA
```
