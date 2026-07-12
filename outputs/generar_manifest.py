"""
generar_manifest.py  ·  outputs/  ·  Reto 1 — Validacion de extraccion
------------------------------------------------------------------------------
Uso:
    python outputs/generar_manifest.py

Valida para el Reto 1:
  - 4/4 municipios en la BD
  - Conteo de filas extraidas por municipio y corporacion
  - Genera outputs/evaluation_manifest.json
------------------------------------------------------------------------------
"""
import os
import sys
import json
import sqlite3
from datetime import datetime

# ── Rutas ────────────────────────────────────────────────────────────────────
HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT    = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "db", "puestos_2026.db")

# ── META — edita con tus datos ───────────────────────────────────────────────
META = {
    "nombre"   : "leyde katerine cortes",            
    "email"    : "cortesleidyk@gmail.com",     
    "repo_url" : "https://github.com/leydecortes-blip/cortes_prueba_utl_2026",
    "generado" : datetime.now().isoformat(timespec="seconds"),
}

MUNICIPIOS_ESPERADOS = {"TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"}

# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*55)
    print("  VALIDACION RETO 1 — Extraccion de datos")
    print("="*55)

    # verificar que existe la BD
    if not os.path.exists(DB_PATH):
        print(f"\n❌ No se encuentra: {DB_PATH}")
        print("   Ejecuta primero: python scraper/scraper.py")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # ── 1. Municipios en la BD ────────────────────────────────────────────────
    print("\n── Municipios en la BD:")
    filas = conn.execute("SELECT nombre FROM municipios ORDER BY nombre").fetchall()
    encontrados = {r[0] for r in filas}
    n   = len(encontrados & MUNICIPIOS_ESPERADOS)
    ok  = MUNICIPIOS_ESPERADOS.issubset(encontrados)

    for muni in sorted(encontrados):
        estado = "✅" if muni in MUNICIPIOS_ESPERADOS else "⚠️"
        print(f"  {estado} {muni}")

    print(f"\n  → {n}/4 municipios {'✅' if ok else '❌'}")

    # ── 2. Filas por municipio y corporacion ──────────────────────────────────
    print("\n── Filas extraidas por municipio:")
    sql = """
        SELECT mu.nombre, pa.corporacion, COUNT(v.id) as filas
        FROM votos v
        JOIN candidatos ca ON ca.id = v.candidato_id
        JOIN partidos   pa ON pa.id = ca.partido_id
        JOIN mesas      me ON me.id = v.mesa_id
        JOIN puestos    pu ON pu.id = me.puesto_id
        JOIN municipios mu ON mu.id = pu.municipio_id
        GROUP BY mu.nombre, pa.corporacion
        ORDER BY mu.nombre, pa.corporacion
    """
    filas_detalle = {}
    for r in conn.execute(sql).fetchall():
        muni, corp, n_filas = r
        print(f"  {muni:12s} {corp}: {n_filas:,} filas")
        if muni not in filas_detalle:
            filas_detalle[muni] = {}
        filas_detalle[muni][corp] = n_filas

    # ── 3. Total general ──────────────────────────────────────────────────────
    total = conn.execute("SELECT COUNT(*) FROM votos").fetchone()[0]
    print(f"\n  Total votos en BD: {total:,}")

    # ── 4. Archivos raw descargados ───────────────────────────────────────────
    raw_dir = os.path.join(ROOT, "db", "raw")
    archivos_raw = []
    if os.path.exists(raw_dir):
        archivos_raw = [f for f in os.listdir(raw_dir) if f.endswith(".json")]

    print(f"\n── Archivos JSON en db/raw/: {len(archivos_raw)}/8")
    for f in sorted(archivos_raw):
        print(f"  ✅ {f}")

    # ── Resumen ───────────────────────────────────────────────────────────────
    print("\n── RESUMEN:")
    print(f"  Municipios : {n}/4 {'✅' if ok else '❌'}")
    print(f"  Votos BD   : {total:,}")
    print(f"  JSON raw   : {len(archivos_raw)}/8")

    # ── Generar JSON ──────────────────────────────────────────────────────────
    manifest = {
        "meta"   : META,
        "reto_1" : {
            "municipios_ok"    : ok,
            "municipios_conteo": f"{n}/4",
            "municipios"       : sorted(encontrados),
            "filas_por_municipio": filas_detalle,
            "total_votos_bd"   : total,
            "archivos_raw"     : sorted(archivos_raw),
            "archivos_raw_conteo": f"{len(archivos_raw)}/8",
        }
    }

    ruta_out = os.path.join(HERE, "evaluation_manifest.json")
    with open(ruta_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ evaluation_manifest.json generado en outputs/")
    print("="*55 + "\n")
    conn.close()


if __name__ == "__main__":
    main()
