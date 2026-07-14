"""
generar_manifest.py
Uso: python outputs/generar_manifest.py
Valida retos 1, 2 y 3 y genera outputs/evaluation_manifest.json
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
SQL_DIR = os.path.join(ROOT, "sql")

META = {
    "nombre"   : "CORTES PINTO LEYDE KATERINE",
    "email"    : "cortesleidyk@gmail.com",
    "repo_url" : "https://github.com/leydecortes-blip/cortes_prueba_utl_2026",
    "generado" : datetime.now().isoformat(timespec="seconds"),
}

MUNICIPIOS_ESPERADOS = {"TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"}


def run_sql(conn, archivo):
    ruta = os.path.join(SQL_DIR, archivo)
    if not os.path.exists(ruta):
        print(f"  {archivo}: no encontrado")
        return {"ok": False, "filas": [], "error": "archivo no encontrado"}
    try:
        sql  = open(ruta, encoding="utf-8").read()
        cur  = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        print(f"  {archivo}: {len(rows)} filas - OK")
        return {"ok": True, "columnas": cols, "filas": rows[:10]}
    except Exception as e:
        print(f"  {archivo}: ERROR - {e}")
        return {"ok": False, "filas": [], "error": str(e)}


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
        
    ok_raw = len(archivos_raw) > 0 # Si hay más de 0, marca OK
    print(f"Archivos JSON raw: {len(archivos_raw)} encontrados ({'OK' if ok_raw else 'VACIO'})")

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
    print("RETO 3 - SQL analitico")

    r3_1 = run_sql(conn, "tarea_3_1.sql")
    r3_2 = run_sql(conn, "tarea_3_2.sql")
    r3_3 = run_sql(conn, "tarea_3_3.sql")

    sql_ok = all([r3_1["ok"], r3_2["ok"], r3_3["ok"]])

    print("")
    print("RESUMEN")
    print(f"  Municipios : {n_muni}/4 ({'OK' if ok_muni else 'INCOMPLETO'})")
    print(f"  JSON raw   : {len(archivos_raw)} archivos ({'OK' if ok_raw else 'INCOMPLETO'})")
    print(f"  Votos BD   : {filas_tabla.get('votos', 0)}")
    print(f"  carga_log  : {filas_tabla.get('carga_log', 0)} registros")
    print(f"  SQL Reto 3 : {'OK 3/3' if sql_ok else 'revisar errores'}")
    
    print("")
    print("Resultados tarea_3_1 (Arrastre Verde CA->SE):")
    print("  municipio | votos_ca_verde | votos_se_verde | arrastre_se_ca")
    for r in r3_1.get("filas", []):
        print(f"  {r['municipio']} | {r['votos_ca_verde']} | {r['votos_se_verde']} | {r['arrastre_se_ca']}")

    print("")
    print("Resultados tarea_3_2 (Dominancia extrema >60%):")
    print("  municipio | candidato | partido | pct_dentro_partido")
    for r in r3_2.get("filas", [])[:5]:
        print(f"  {r['municipio']} | {r['candidato']} | {r['partido']} | {r['pct_dentro_partido']}%")

    print("")
    print("Resultados tarea_3_3 (Top 5 atribucion SE):")
    print("  candidato | partido | votos_CA | atribucion_SE")
    for r in r3_3.get("filas", []):
        print(f"  {r['candidato']} | {r['partido']} | {r['votos_cand']} | {r['atribucion_se']}")

    print("")
    print("RETO 5 - Visualizaciones Python")

    VIZ_DIR = os.path.join(ROOT, "viz")
    heatmap_path  = os.path.join(VIZ_DIR, "heatmap_municipios.png")
    scatter_path  = os.path.join(VIZ_DIR, "scatter_ca_se.png")

    ok_heatmap  = os.path.exists(heatmap_path)  and os.path.getsize(heatmap_path)  > 10_000
    ok_scatter  = os.path.exists(scatter_path)  and os.path.getsize(scatter_path)  > 10_000

    scatter_stats = {"r": None, "pendiente": None, "n_mesas": None}
    # Leer las stats que scatter.py deja en viz/scatter_stats.txt al correr.
    # Esto evita problemas de interprete: el usuario corre scatter.py con el Python
    # que tenga numpy, y el manifest solo lee el archivo resultante.
    stats_txt = os.path.join(VIZ_DIR, "scatter_stats.txt")
    if os.path.exists(stats_txt):
        try:
            linea = open(stats_txt, encoding="utf-8").readline().strip()
            if linea.startswith("r=") and "pendiente=" in linea and "n_mesas=" in linea:
                partes = dict(p.split("=") for p in linea.split(" | "))
                scatter_stats["r"]         = float(partes.get("r", 0))
                scatter_stats["pendiente"] = float(partes.get("pendiente", 0))
                scatter_stats["n_mesas"]   = int(partes.get("n_mesas", 0))
        except Exception as e:
            print(f"  scatter_stats.txt: ERROR al leer -> {e}")
    else:
        print("  scatter_stats.txt: no encontrado. Corre primero: python viz/scatter.py")

    print(f"  heatmap_municipios.png: {'OK' if ok_heatmap else 'FALTA o <10KB'}")
    print(f"  scatter_ca_se.png     : {'OK' if ok_scatter else 'FALTA o <10KB'}")
    if scatter_stats['r'] is not None:
        print(f"  r de Pearson = {scatter_stats['r']} | pendiente = {scatter_stats['pendiente']} | n_mesas = {scatter_stats['n_mesas']}")

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
        "reto_3" : {
            "tarea_3_1"        : r3_1,
            "tarea_3_2"        : r3_2,
            "tarea_3_3"        : r3_3,
        },
        "reto_5": {
            "heatmap_ok"   : ok_heatmap,
            "scatter_ok"   : ok_scatter,
            "scatter_stats": scatter_stats,
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