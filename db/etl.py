"""
etl.py  ·  Reto 2.2  ·  Pipeline Electoral Boyaca 2026

Responsabilidades:
  1. Aplicar schema.sql (idempotente).
  2. Parsear el JSON real de la API de la Registraduria.
  3. Normalizar nombres de candidatos.
  4. Cargar partidos con deduplicacion y homologacion CA-SE.
  5. Insertar votos con INSERT OR IGNORE (idempotente).
  6. Registrar en carga_log filas insertadas vs omitidas.

Uso:
  python db/etl.py
"""
import os
import re
import glob
import json
import sqlite3
import unicodedata
from collections import defaultdict

HERE    = os.path.dirname(os.path.abspath(__file__))
SCHEMA  = os.path.join(HERE, "schema.sql")
DB_PATH = os.path.join(HERE, "puestos_2026.db")
RAW_DIR = os.path.join(HERE, "raw")

PARTIDOS_REF = {
    ("CA",  5): dict(canonico="VERDE",       nombre="Alianza Verde",       color="#007C34"),
    ("SE", 57): dict(canonico="VERDE",       nombre="Alianza Verde",       color="#007C34"),
    ("CA", 87): dict(canonico="PACTO",       nombre="Pacto Historico",     color="#7B2D8B"),
    ("SE", 92): dict(canonico="PACTO",       nombre="Pacto Historico",     color="#7B2D8B"),
    ("CA", 10): dict(canonico="CD",          nombre="Centro Democratico",  color="#1E477D"),
    ("SE", 10): dict(canonico="CD",          nombre="Centro Democratico",  color="#1E477D"),
    ("CA",  2): dict(canonico="CONSERVADOR", nombre="Partido Conservador", color="#E07B00"),
    ("SE",  2): dict(canonico="CONSERVADOR", nombre="Partido Conservador", color="#E07B00"),
}
COLOR_DEFAULT = "#8A8A8A"


def normalize_nombre(texto):
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.upper()
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def resolver_partido(corporacion, codpar, partido_nombre=""):
    ref = PARTIDOS_REF.get((corporacion, int(codpar)))
    if ref:
        return ref["canonico"], ref["nombre"], ref["color"]
    canonico = normalize_nombre(partido_nombre).replace(" ", "_") or f"COD{codpar}"
    return canonico, (partido_nombre or f"Partido {codpar}"), COLOR_DEFAULT


def parsear_json_api(payload, municipio, divipol, corp):
    records = []
    camaras = payload.get("camaras", [])
    if not camaras:
        return records

    camara = camaras[0]

    for partido_bloque in camara.get("partotabla", []):
        act    = partido_bloque.get("act", {})
        codpar = act.get("codpar")
        if codpar is None:
            continue

        for cand in act.get("cantotabla", []):
            nomcan = cand.get("nomcan", "").strip()
            apecan = cand.get("apecan", "").strip()
            nombre = f"{nomcan} {apecan}".strip() or "SOLO POR LA LISTA"
            votos  = int(cand.get("vot", 0))

            records.append(dict(
                municipio        = municipio,
                divipol          = divipol,
                puesto_codigo    = divipol,
                puesto_nombre    = municipio,
                mesa             = "TOTAL",
                corporacion      = corp,
                codpar           = int(codpar),
                partido_nombre   = resolver_partido(corp, int(codpar))[1],
                candidato_numero = str(cand.get("codcan", "0")),
                candidato_nombre = nombre,
                votos            = votos,
            ))
    return records


def inferir_municipio_corp(nombre_archivo):
    DIVIPOL = {
        "TUNJA": "0700001", "PAIPA": "0700181",
        "SOGAMOSO": "0700277", "DUITAMA": "0700079",
    }
    base   = os.path.basename(nombre_archivo).replace(".json", "")
    partes = base.split("_")
    if len(partes) >= 2:
        muni = partes[0].upper()
        corp = partes[-1].upper()
        return muni, corp, DIVIPOL.get(muni, muni)
    return base, "CA", base


def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def apply_schema(conn):
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def load_records(conn, records, municipio_hint=None):
    cur   = conn.cursor()
    stats = defaultdict(lambda: {"ins": 0, "skip": 0})

    for r in records:
        muni  = r["municipio"]
        corp  = r["corporacion"]
        canon, pnom, color = resolver_partido(corp, r["codpar"], r.get("partido_nombre", ""))

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
                       VALUES (?,?,?,?,?)""",
                    (int(r["codpar"]), corp, pnom, canon, color))
        partido_id = cur.execute("SELECT id FROM partidos WHERE codpar=? AND corporacion=?",
                                 (int(r["codpar"]), corp)).fetchone()[0]

        nombre_norm = normalize_nombre(r["candidato_nombre"])
        cur.execute("""INSERT OR IGNORE INTO candidatos(partido_id, numero, nombre_raw, nombre_norm)
                       VALUES (?,?,?,?)""",
                    (partido_id, str(r.get("candidato_numero") or ""),
                     r["candidato_nombre"], nombre_norm))
        cand_id = cur.execute("SELECT id FROM candidatos WHERE partido_id=? AND nombre_norm=?",
                              (partido_id, nombre_norm)).fetchone()[0]

        before = conn.total_changes
        cur.execute("INSERT OR IGNORE INTO votos(mesa_id, candidato_id, votos) VALUES (?,?,?)",
                    (mesa_id, cand_id, int(r["votos"])))
        if conn.total_changes > before:
            stats[(muni, corp)]["ins"] += 1
        else:
            stats[(muni, corp)]["skip"] += 1

    for (muni, corp), s in stats.items():
        cur.execute("""INSERT INTO carga_log(municipio, corporacion, filas_insertadas, filas_omitidas, notas)
                       VALUES (?,?,?,?,?)""",
                    (muni, corp, s["ins"], s["skip"], municipio_hint or "load_records"))
    conn.commit()
    return stats


def rebuild_from_raw(db_path=DB_PATH, raw_dir=RAW_DIR):
    conn     = get_connection(db_path)
    apply_schema(conn)
    archivos = sorted(glob.glob(os.path.join(raw_dir, "*.json")))

    if not archivos:
        print(f"No hay archivos en {raw_dir}.")
        print("Ejecuta primero: python scraper/scraper.py")
        conn.close()
        return

    total_ins = total_skip = 0

    for path in archivos:
        nombre = os.path.basename(path)
        muni, corp, divipol = inferir_municipio_corp(path)

        with open(path, encoding="utf-8") as f:
            payload = json.load(f)

        records    = parsear_json_api(payload, muni, divipol, corp)
        stats      = load_records(conn, records, municipio_hint=nombre)
        ins        = sum(s["ins"]  for s in stats.values())
        skip       = sum(s["skip"] for s in stats.values())
        total_ins  += ins
        total_skip += skip
        print(f"{nombre:25s}  +{ins} insertadas  ({skip} omitidas)")

    print(f"\nTOTAL  +{total_ins} insertadas  |  {total_skip} omitidas")
    conn.close()


if __name__ == "__main__":
    rebuild_from_raw()