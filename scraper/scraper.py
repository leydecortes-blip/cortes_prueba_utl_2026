"""
scraper.py  ·  Reto 1  ·  Extraccion API Registraduria — Boyaca 2026

Uso:
  python scraper/scraper.py
  python scraper/scraper.py --municipios TUNJA PAIPA
  python scraper/scraper.py --preflight

URL real descubierta con F12:
  https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/{CORP}/{divipol}.json
  CORP = CA (Camara) o SE (Senado)

Campos JSON extraidos:
  codpar, nomcan, apecan, codcan, cedula, vot, pvot, amb, metota
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(HERE)
DB_DIR = os.path.join(ROOT, "db")
sys.path.insert(0, DB_DIR)
import etl

BASE_URL = "https://resultadospreccongreso2026.registraduria.gov.co"

HEADERS = {
    "User-Agent"      : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept"          : "application/json, text/plain, */*",
    "Accept-Language" : "es-CO,es;q=0.9,en;q=0.8",
    "Referer"         : BASE_URL + "/",
    "Origin"          : BASE_URL,
    "sec-fetch-dest"  : "empty",
    "sec-fetch-mode"  : "cors",
    "sec-fetch-site"  : "same-origin",
}

MUNICIPIOS = {
    "TUNJA":    "0700001",
    "PAIPA":    "0700181",
    "SOGAMOSO": "0700277",
    "DUITAMA":  "0700079",
}

CORPORACIONES = ["CA", "SE"]


def url_votos(divipol, corp):
    return f"{BASE_URL}/json/ACT/{corp}/{divipol}.json"


def _nombre_partido(codpar, corp):
    NOMBRES = {
        (87, "CA"): "Pacto Historico",
        (92, "SE"): "Pacto Historico",
        (5,  "CA"): "Alianza Verde",
        (57, "SE"): "Alianza Verde",
        (10, "CA"): "Centro Democratico",
        (10, "SE"): "Centro Democratico",
        (2,  "CA"): "Partido Conservador",
        (2,  "SE"): "Partido Conservador",
        (121,"CA"): "Partido Liberal",
        (122,"CA"): "Colombia Justa Libres",
        (120,"CA"): "MIRA",
        (15, "CA"): "Partido de la U",
    }
    return NOMBRES.get((codpar, corp), f"Partido {codpar}")


def parse_json(payload, municipio, divipol, corp):
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
                partido_nombre   = _nombre_partido(int(codpar), corp),
                candidato_numero = str(cand.get("codcan", "0")),
                candidato_nombre = nombre,
                votos            = votos,
            ))
    return records


def fetch_json(url, retries=4, backoff=1.5, timeout=30):
    last = None
    for intento in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last   = e
            espera = backoff ** intento
            print(f"  [retry {intento}/{retries}] ({e}) espero {espera:.1f}s")
            time.sleep(espera)
    raise RuntimeError(f"Fallo tras {retries} intentos: {url} -> {last}")


def cargar_offline(municipio, corp):
    for carpeta in (os.path.join(DB_DIR, "raw"), os.path.join(ROOT, "sample_data")):
        ruta = os.path.join(carpeta, f"{municipio}_{corp}.json")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
    return None


def preflight(municipios):
    print("PREFLIGHT - conteo de mesas por municipio (sin descargar votos):")
    total = 0
    for muni in municipios:
        divipol = MUNICIPIOS[muni]
        try:
            payload = fetch_json(url_votos(divipol, "CA"))
            mesas   = payload.get("totales", {}).get("act", {}).get("metota", "?")
            print(f"  {muni}  divipol {divipol}  {mesas} mesas")
            if str(mesas).isdigit():
                total += int(mesas)
        except Exception as e:
            print(f"  {muni}  error: {e}")
    print(f"TOTAL estimado: {total} mesas en {len(municipios)} municipios")


def run(municipios, offline=False):
    raw_dir = os.path.join(DB_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    conn = etl.get_connection()
    etl.apply_schema(conn)
    gran = {"ins": 0, "skip": 0}

    for muni in municipios:
        divipol = MUNICIPIOS[muni]
        print(f"\n[{muni}]  divipol {divipol}")

        for corp in CORPORACIONES:
            print(f"  {corp} ...", end=" ", flush=True)

            if offline:
                payload = cargar_offline(muni, corp)
                if payload is None:
                    print("sin datos offline, saltando.")
                    continue
                fuente = "offline"
            else:
                try:
                    url     = url_votos(divipol, corp)
                    payload = fetch_json(url)
                    ruta_raw = os.path.join(raw_dir, f"{muni}_{corp}.json")
                    with open(ruta_raw, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False)
                    fuente = "API"
                except Exception as e:
                    print(f"\n  API fallo ({e}), intentando offline...")
                    payload = cargar_offline(muni, corp)
                    if payload is None:
                        print(f"  Sin datos offline. Saltando {muni}-{corp}.")
                        continue
                    fuente = "offline"

            records = parse_json(payload, muni, divipol, corp)
            stats   = etl.load_records(conn, records, municipio_hint=f"{muni}-{corp}")
            ins     = sum(s["ins"]  for s in stats.values())
            skip    = sum(s["skip"] for s in stats.values())
            gran["ins"]  += ins
            gran["skip"] += skip
            print(f"{len(records)} registros ({fuente}) +{ins} insertados, {skip} omitidos")

    conn.close()
    print(f"\nLISTO - Total insertadas: {gran['ins']} | omitidas: {gran['skip']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scraper electoral Boyaca 2026")
    ap.add_argument("--municipios", nargs="+", default=list(MUNICIPIOS.keys()))
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--offline",   action="store_true")
    args = ap.parse_args()

    munis     = [m.upper() for m in args.municipios]
    invalidos = [m for m in munis if m not in MUNICIPIOS]
    if invalidos:
        sys.exit(f"Municipios no reconocidos: {invalidos}. Validos: {list(MUNICIPIOS)}")

    if args.preflight:
        preflight(munis)
    else:
        run(munis, offline=args.offline)