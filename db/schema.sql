-- ============================================================================
-- schema.sql  ·  Pipeline Electoral Boyacá 2026  ·  Reto 2.1
-- Modelo normalizado (3FN). El grano más fino del dato es la MESA.
-- Jerarquía geográfica:  municipio -> puesto -> mesa
-- Clave analítica:        partido.canonico  (homologa CA <-> SE)
-- ============================================================================
PRAGMA foreign_keys = ON;

-- --- Geografía ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS municipios (
    id       INTEGER PRIMARY KEY,
    nombre   TEXT    NOT NULL,
    divipol  TEXT,
    UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS puestos (
    id           INTEGER PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id),
    codigo       TEXT    NOT NULL,
    nombre       TEXT,
    UNIQUE (municipio_id, codigo)          -- idempotencia geográfica
);

CREATE TABLE IF NOT EXISTS mesas (
    id        INTEGER PRIMARY KEY,
    puesto_id INTEGER NOT NULL REFERENCES puestos(id),
    numero    TEXT    NOT NULL,
    UNIQUE (puesto_id, numero)
);

-- --- Política ----------------------------------------------------------------
-- Un partido tiene codpar DISTINTO por corporación (Verde = 5 en CA, 57 en SE).
-- 'canonico' es la llave que une la misma fuerza política entre CA y SE.
CREATE TABLE IF NOT EXISTS partidos (
    id          INTEGER PRIMARY KEY,
    codpar      INTEGER NOT NULL,
    corporacion TEXT    NOT NULL CHECK (corporacion IN ('CA','SE')),
    nombre      TEXT    NOT NULL,
    canonico    TEXT    NOT NULL,          -- 'VERDE','PACTO','CD','CONSERVADOR'...
    color       TEXT,
    UNIQUE (codpar, corporacion)
);

CREATE TABLE IF NOT EXISTS candidatos (
    id          INTEGER PRIMARY KEY,
    partido_id  INTEGER NOT NULL REFERENCES partidos(id),
    numero      TEXT,
    nombre_raw  TEXT,                       -- como llegó de la API
    nombre_norm TEXT    NOT NULL,           -- normalizado (mayúsculas, sin tildes)
    UNIQUE (partido_id, nombre_norm)        -- dedup de candidatos
);

-- --- Hechos ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS votos (
    id           INTEGER PRIMARY KEY,
    mesa_id      INTEGER NOT NULL REFERENCES mesas(id),
    candidato_id INTEGER NOT NULL REFERENCES candidatos(id),
    votos        INTEGER NOT NULL CHECK (votos >= 0),
    UNIQUE (mesa_id, candidato_id)          -- <- clave de IDEMPOTENCIA del scraper
);

-- --- Auditoría ETL -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS carga_log (
    id               INTEGER PRIMARY KEY,
    ts               TEXT DEFAULT CURRENT_TIMESTAMP,
    municipio        TEXT,
    corporacion      TEXT,
    filas_insertadas INTEGER DEFAULT 0,
    filas_omitidas   INTEGER DEFAULT 0,     -- ya existían (INSERT OR IGNORE)
    notas            TEXT
);

-- ============================================================================
-- ÍNDICES  ·  Bonus 2.1 (+2 pts): 3+ índices con justificación
-- ----------------------------------------------------------------------------
-- idx_votos_mesa      -> Reto 3.2 agrega votos POR MESA; evita full scan por mesa.
-- idx_votos_candidato -> Retos 3.2/3.3 hacen JOIN votos->candidatos por candidato.
-- idx_cand_partido    -> Todos los rollups por partido pasan candidatos->partidos.
-- idx_part_canonico   -> Homologación CA<->SE (3.1 y 3.3) filtra/junta por canonico.
-- idx_puestos_muni    -> 3.1 agrupa por puesto dentro de municipio.
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_votos_mesa      ON votos(mesa_id);
CREATE INDEX IF NOT EXISTS idx_votos_candidato ON votos(candidato_id);
CREATE INDEX IF NOT EXISTS idx_cand_partido    ON candidatos(partido_id);
CREATE INDEX IF NOT EXISTS idx_part_canonico   ON partidos(canonico, corporacion);
CREATE INDEX IF NOT EXISTS idx_puestos_muni    ON puestos(municipio_id);
