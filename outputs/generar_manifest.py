"""
generar_manifest.py  ·  outputs/
Uso: python outputs/generar_manifest.py
Valida retos 1 y 2 y genera outputs/evaluation_manifest.json
"""
import os
import sys
import json
import sqlite3
from datetime import datetime

HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT    = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "db", "puestos_2026.db")
RAW_DIR = os.path.join(ROOT, "db", "raw")

META = {
    "nombre"   : "CORTES PINTO LEYDE KATERINE",
    "email"    : "cortesleidyk@gmail.com",
    "repo_url" : "https://github.com/leydecortes-blip/cortes_prueba_utl_2026",
    "generado" : datetime.now().isoformat(timespec="seconds"),
}

MUNICIPIOS_ESPERADOS = {"TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"}


def main():

    if not os.path.exists(DB_PATH):
        print(f"ERROR: No se encuentra {DB_PATH}")
        print("Ejecuta primero: python scraper/scraper.py")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    print("RETO 1 - Extraccion de datos")

    filas       = conn.execute("SELECT nombre FROM municipios ORDER BY nombre").fetchall()
    encontrados = {r[0] for r in filas}
    n_muni      = len(encontrados & MUNICIPIOS_ESPERADOS)
    ok_muni     = MUNICIPIOS_ESPERADOS.issubset(encontrados)

    print(f"Municipios en BD: {n_muni}/4 ({'OK' if ok_muni else 'INCOMPLETO'})")
    for m in sorted(encontrados):
        print(f"  - {m}")

    archivos_raw = []
    if os.path.exists(RAW_DIR):
        archivos_raw = sorted([f for f in os.listdir(RAW_DIR) if f.endswith(".json")])
    ok_raw = len(archivos_raw) == 8
    print(f"Archivos JSON raw: {len(archivos_raw)}/8 ({'OK' if ok_raw else 'INCOMPLETO'})")

    print("")
    print("RETO 2 - Base de datos")

    tablas      = ["municipios", "puestos", "mesas", "partidos", "candidatos", "votos", "carga_log"]
    filas_tabla = {}
    for t in tablas:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            filas_tabla[t] = n
            print(f"  {t}: {n} filas")
        except Exception as e:
            filas_tabla[t] = f"ERROR: {e}"
            print(f"  {t}: ERROR - {e}")

    print("")
    print("Partido lider SE por municipio:")
    sql_lider = """
        SELECT mu.nombre, pa.canonico, SUM(v.votos) AS total
        FROM votos v
        JOIN candidatos ca ON ca.id = v.candidato_id
        JOIN partidos   pa ON pa.id = ca.partido_id
        JOIN mesas      me ON me.id = v.mesa_id
        JOIN puestos    pu ON pu.id = me.puesto_id
        JOIN municipios mu ON mu.id = pu.municipio_id
        WHERE pa.corporacion = 'SE'
        GROUP BY mu.nombre, pa.canonico
        ORDER BY mu.nombre, total DESC
    """
    lider_se = {}
    ultimo   = None
    for r in conn.execute(sql_lider).fetchall():
        muni, partido, votos = r
        if muni != ultimo:
            ultimo = muni
            lider_se[muni] = {"partido_lider": partido, "votos_se": votos}
            print(f"  {muni}: {partido} ({votos} votos SE)")

    print("")
    print("RESUMEN")
    print(f"  Municipios : {n_muni}/4 ({'OK' if ok_muni else 'INCOMPLETO'})")
    print(f"  JSON raw   : {len(archivos_raw)}/8 ({'OK' if ok_raw else 'INCOMPLETO'})")
    print(f"  Votos BD   : {filas_tabla.get('votos', 0)}")
    print(f"  carga_log  : {filas_tabla.get('carga_log', 0)} registros")

    manifest = {
        "meta"   : META,
        "reto_1" : {
            "municipios_ok"    : ok_muni,
            "municipios_conteo": f"{n_muni}/4",
            "municipios"       : sorted(encontrados),
            "archivos_raw"     : archivos_raw,
            "archivos_raw_ok"  : ok_raw,
        },
        "reto_2" : {
            "filas_por_tabla"  : filas_tabla,
            "lider_se"         : lider_se,
        },
    }

    ruta_out = os.path.join(HERE, "evaluation_manifest.json")
    with open(ruta_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("")
    print("Manifest generado en outputs/evaluation_manifest.json")
    conn.close()


if __name__ == "__main__":
    main()