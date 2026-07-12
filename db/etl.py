"""
etl.py  ·  Reto 2.2  ·  Pipeline Electoral Boyacá 2026
------------------------------------------------------------------------------
Responsabilidades:
  1. Aplicar schema.sql (idempotente).
  2. Normalizar nombres de candidatos.
  3. Cargar partidos con deduplicación + homologación CA<->SE (canonico).
  4. Insertar votos con INSERT OR IGNORE (idempotente).
  5. Registrar en carga_log: filas insertadas vs. omitidas por municipio/corporación.

Se usa de dos formas:
  - importado por scraper.py  (load_records(...) tras descargar de la API)
  - ejecutado directo:  python db/etl.py   -> reconstruye la BD desde db/raw/*.json
------------------------------------------------------------------------------
Contrato de un "record" (dict) que produce el scraper:
  municipio, divipol, puesto_codigo, puesto_nombre, mesa,
  corporacion ('CA'|'SE'), codpar (int), partido_nombre,
  candidato_numero, candidato_nombre, votos (int)
"""
import os
import re
import glob
import json
import sqlite3
import unicodedata
from collections import defaultdict

HERE      = os.path.dirname(os.path.abspath(__file__))
SCHEMA    = os.path.join(HERE, "schema.sql")
DB_PATH   = os.path.join(HERE, "puestos_2026.db")
RAW_DIR   = os.path.join(HERE, "raw")

# --- Tabla maestra de homologación de partidos ------------------------------
# Fuente: tabla de colores oficiales del enunciado (Reto 4).
# Cada fuerza política tiene un 'canonico' estable que une su codpar de CA y de SE.
PARTIDOS_REF = {
    ("CA",  5): dict(canonico="VERDE",       nombre="Alianza Verde",       color="#007C34"),
    ("SE", 57): dict(canonico="VERDE",       nombre="Alianza Verde",       color="#007C34"),
    ("CA", 87): dict(canonico="PACTO",       nombre="Pacto Histórico",     color="#7B2D8B"),
    ("SE", 92): dict(canonico="PACTO",       nombre="Pacto Histórico",     color="#7B2D8B"),
    ("CA", 10): dict(canonico="CD",          nombre="Centro Democrático",  color="#1E477D"),
    ("SE", 10): dict(canonico="CD",          nombre="Centro Democrático",  color="#1E477D"),
    ("CA",  2): dict(canonico="CONSERVADOR", nombre="Partido Conservador", color="#E07B00"),
    ("SE",  2): dict(canonico="CONSERVADOR", nombre="Partido Conservador", color="#E07B00"),
}
COLOR_DEFAULT = "#8A8A8A"


def normalize_nombre(texto: str) -> str:
    """MAYÚSCULAS, sin tildes, sin puntuación, espacios colapsados."""
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))   # quita tildes
    t = t.upper()
    t = re.sub(r"[^A-Z0-9ÑñÜü ]", " ", t)                        # quita puntuación
    t = re.sub(r"\s+", " ", t).strip()
    return t


def resolver_partido(corporacion, codpar, partido_nombre):
    """Devuelve (canonico, nombre, color) usando la tabla maestra o un fallback."""
    ref = PARTIDOS_REF.get((corporacion, int(codpar)))
    if ref:
        return ref["canonico"], ref["nombre"], ref["color"]
    canonico = normalize_nombre(partido_nombre).replace(" ", "_") or f"COD{codpar}"
    return canonico, (partido_nombre or f"Partido {codpar}"), COLOR_DEFAULT


def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def apply_schema(conn):
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def load_records(conn, records, municipio_hint=None):
    """Carga una lista de records. Devuelve dict de conteos por (municipio,corp)."""
    cur = conn.cursor()
    stats = defaultdict(lambda: {"ins": 0, "skip": 0})

    for r in records:
        muni   = r["municipio"]
        corp   = r["corporacion"]
        canon, pnom, color = resolver_partido(corp, r["codpar"], r.get("partido_nombre"))

        # --- upserts idempotentes de dimensiones ---
        cur.execute("INSERT OR IGNORE INTO municipios(nombre, divipol) VALUES (?,?)",
                    (muni, r.get("divipol")))
        muni_id = cur.execute("SELECT id FROM municipios WHERE nombre=?", (muni,)).fetchone()[0]

        cur.execute("INSERT OR IGNORE INTO puestos(municipio_id, codigo, nombre) VALUES (?,?,?)",
                    (muni_id, str(r["puesto_codigo"]), r.get("puesto_nombre")))
        puesto_id = cur.execute("SELECT id FROM puestos WHERE municipio_id=? AND codigo=?",
                                (muni_id, str(r["puesto_codigo"]))).fetchone()[0]

        cur.execute("INSERT OR IGNORE INTO mesas(puesto_id, numero) VALUES (?,?)",
                    (puesto_id, str(r["mesa"])))
        mesa_id = cur.execute("SELECT id FROM mesas WHERE puesto_id=? AND numero=?",
                              (puesto_id, str(r["mesa"]))).fetchone()[0]

        cur.execute("""INSERT OR IGNORE INTO partidos(codpar, corporacion, nombre, canonico, color)
                       VALUES (?,?,?,?,?)""", (int(r["codpar"]), corp, pnom, canon, color))
        partido_id = cur.execute("SELECT id FROM partidos WHERE codpar=? AND corporacion=?",
                                 (int(r["codpar"]), corp)).fetchone()[0]

        nombre_norm = normalize_nombre(r["candidato_nombre"])
        cur.execute("""INSERT OR IGNORE INTO candidatos(partido_id, numero, nombre_raw, nombre_norm)
                       VALUES (?,?,?,?)""",
                    (partido_id, str(r.get("candidato_numero") or ""), r["candidato_nombre"], nombre_norm))
        cand_id = cur.execute("SELECT id FROM candidatos WHERE partido_id=? AND nombre_norm=?",
                              (partido_id, nombre_norm)).fetchone()[0]

        # --- hecho: votos (idempotente) ---
        before = conn.total_changes
        cur.execute("INSERT OR IGNORE INTO votos(mesa_id, candidato_id, votos) VALUES (?,?,?)",
                    (mesa_id, cand_id, int(r["votos"])))
        if conn.total_changes > before:
            stats[(muni, corp)]["ins"] += 1
        else:
            stats[(muni, corp)]["skip"] += 1

    # --- log de auditoría ---
    for (muni, corp), s in stats.items():
        cur.execute("""INSERT INTO carga_log(municipio, corporacion, filas_insertadas, filas_omitidas, notas)
                       VALUES (?,?,?,?,?)""",
                    (muni, corp, s["ins"], s["skip"], municipio_hint or "load_records"))
    conn.commit()
    return stats


def rebuild_from_raw(db_path=DB_PATH, raw_dir=RAW_DIR):
    """Reconstruye la BD leyendo todos los db/raw/*.json (uso: python db/etl.py)."""
    conn = get_connection(db_path)
    apply_schema(conn)
    archivos = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    if not archivos:
        print(f"[ETL] No hay archivos en {raw_dir}. Ejecuta el scraper primero.")
        return
    total_ins = total_skip = 0
    for path in archivos:
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
        stats = load_records(conn, records, municipio_hint=os.path.basename(path))
        ins  = sum(s["ins"]  for s in stats.values())
        skip = sum(s["skip"] for s in stats.values())
        total_ins += ins; total_skip += skip
        print(f"[ETL] {os.path.basename(path):28s}  +{ins:5d} insertadas  ({skip} omitidas)")
    print(f"[ETL] TOTAL  +{total_ins} insertadas  |  {total_skip} omitidas (idempotencia OK)")
    conn.close()


if __name__ == "__main__":
    rebuild_from_raw()
