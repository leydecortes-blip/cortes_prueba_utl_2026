PRAGMA foreign_keys = ON;

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


CREATE TABLE IF NOT EXISTS votos (
    id           INTEGER PRIMARY KEY,
    mesa_id      INTEGER NOT NULL REFERENCES mesas(id),
    candidato_id INTEGER NOT NULL REFERENCES candidatos(id),
    votos        INTEGER NOT NULL CHECK (votos >= 0),
    UNIQUE (mesa_id, candidato_id)          -- <- clave de IDEMPOTENCIA del scraper
);

CREATE TABLE IF NOT EXISTS carga_log (
    id               INTEGER PRIMARY KEY,
    ts               TEXT DEFAULT CURRENT_TIMESTAMP,
    municipio        TEXT,
    corporacion      TEXT,
    filas_insertadas INTEGER DEFAULT 0,
    filas_omitidas   INTEGER DEFAULT 0,     -- ya existían (INSERT OR IGNORE)
    notas            TEXT
);

CREATE INDEX IF NOT EXISTS idx_votos_mesa      ON votos(mesa_id);
CREATE INDEX IF NOT EXISTS idx_votos_candidato ON votos(candidato_id);
CREATE INDEX IF NOT EXISTS idx_cand_partido    ON candidatos(partido_id);
CREATE INDEX IF NOT EXISTS idx_part_canonico   ON partidos(canonico, corporacion);
CREATE INDEX IF NOT EXISTS idx_puestos_muni    ON puestos(municipio_id);
