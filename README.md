# CORTES — Prueba Técnica UTL Senado 2026

Pipeline de datos electorales de Boyacá 2026 (Cámara y Senado) para los municipios
de Tunja, Paipa, Sogamoso y Duitama: extracción desde la API de la Registraduría,
carga en SQLite, análisis SQL de arrastre electoral, dashboard y visualizaciones.

## Candidato

- **Nombre:** leyde katerine cortes pinto
- **Email:** cortesleidyk@gmail.com
- **Repositorio:** https://github.com/leydecortes-blip/cortes_prueba_utl_2026

## Instalación

```bash
git clone https://github.com/leydecortes-blip/cortes_prueba_utl_2026.git
cd cortes_prueba_utl_2026
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requiere Python 3.10+. El scraper y el ETL usan solo librería estándar; las
visualizaciones usan pandas, matplotlib, numpy y scipy.

## Pipeline de ejecución

Reproduce todo el pipeline en menos de 10 minutos:

```bash
python scraper/scraper.py                 # extrae los 4 municipios -> db/puestos_2026.db
python db/etl.py                          # (opcional) reconstruye la BD desde db/raw
python outputs/generar_manifest.py        # valida conteos y ejecuta las 3 queries SQL
python viz/heatmap.py                      # genera viz/heatmap_municipios.png
python viz/scatter.py                      # genera viz/scatter_ca_se.png
# Dashboard: abrir dashboard/index.html en Chrome o Firefox
```

Sin conexión a la API se puede desarrollar con los datos de muestra:
`python scraper/scraper.py --offline`.

## API

**Base:** `https://resultadospreccongreso2026.registraduria.gov.co`

- **Patrón de URL de resultados:** [completar tras F12 → Network]
- **Nomenclador / divipol:** [completar]
- **Cabeceras HTTP necesarias:** User-Agent, Accept, Referer [ajustar según Network]
- **Campos JSON usados (8+):** [listar: puesto, mesa, codpar, nombre partido, número
  candidato, nombre candidato, votos, corporación, ...]
- **divipol Boyacá:** Tunja 15001 · Paipa 15516 · Sogamoso 15759 · Duitama 15238

Si la API no responde, el scraper cae automáticamente a `sample_data/` (documentado
en el flag `--offline`).

## Municipios en la BD

TUNJA · PAIPA · SOGAMOSO · DUITAMA (los 4 requeridos).

## Hallazgos principales

[Completar con los resultados reales. Estructura sugerida:]

- **Arrastre Verde (3.1):** en promedio el ratio SE/CA fue de X, con máximos en el
  puesto ... de ...
- **Dominancia extrema (3.2):** N mesas donde un candidato superó el 60% de su partido.
- **Atribución SE (3.3):** el top de atribución NO coincide con el top de votos de
  Cámara, porque la fórmula pondera la participación del candidato por la fuerza de su
  partido en Senado: un candidato con menos votos CA pero de un partido fuerte en SE
  supera a otro con más votos CA de un partido débil en Senado.

## Bonus implementados

- [x] **1.2** Flag `--preflight` en el scraper (conteo sin descargar). *(+3)*
- [x] **2.1** 5 índices SQLite con justificación en `schema.sql`. *(+2)*
- [x] **3.3** Explicación de por qué el top CA ≠ top atribución SE. *(+2)*
- [ ] **4** Dark mode toggle en el dashboard. *(+3)*
- [ ] **4** Botón Exportar CSV en el dashboard. *(+2)*
