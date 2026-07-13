"""
scraper.py  ·  Reto 1  ·  Extraccion API Registraduria — Boyaca 2026

Uso:
  python scraper/scraper.py
  python scraper/scraper.py --municipios TUNJA PAIPA
  python scraper/scraper.py --preflight

URL real descubierta con F12:
  https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/{CORP}/{divipol}.json
  CORP = CA (Camara) o SE (Senado)
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


def url_votos(codigo, corp):
    # La API soporta consultas agregadas al nivel del codigo que se le pase (Puesto, Zona o Municipio)
    return f"{BASE_URL}/json/ACT/{corp}/{codigo}.json"


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


def parse_json(payload, municipio, divipol, corp, puesto_cod="", puesto_nom="", mesa_num="TOTAL"):
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
                puesto_codigo    = puesto_cod or divipol,
                puesto_nombre    = puesto_nom or municipio,
                mesa             = str(mesa_num),
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
                data = r.read().decode("utf-8")
                return json.loads(data)
        except json.JSONDecodeError:
            return None
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return None
            last = e
            espera = backoff ** intento
            time.sleep(espera)
        except Exception as e:
            last = e
            espera = backoff ** intento
            time.sleep(espera)
    raise RuntimeError(f"Fallo tras {retries} intentos: {url} -> {last}")


def cargar_offline(identificador, corp):
    for carpeta in (os.path.join(DB_DIR, "raw"), os.path.join(ROOT, "sample_data")):
        ruta = os.path.join(carpeta, f"{identificador}_{corp}.json")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
    return None


def preflight(municipios, offline=False):
    print("PREFLIGHT - Conteo de puestos de votacion investigando el nomenclador...")
    url_nomenclator = f"{BASE_URL}/json/nomenclator.json"
    
    if offline:
        ruta_nomenclator_local = os.path.join(ROOT, "nomenclator.json")
        if not os.path.exists(ruta_nomenclator_local):
            print("Error: No se encuentra nomenclator.json local.")
            return
        with open(ruta_nomenclator_local, "r", encoding="utf-8") as f:
            datos_nomenclator = json.load(f)
    else:
        try:
            datos_nomenclator = fetch_json(url_nomenclator)
        except Exception as e:
            print(f"Error al descargar el nomenclador: {e}")
            return

    total_puestos_global = 0
    for muni in municipios:
        divipol = MUNICIPIOS[muni]
        # El nomenclador repite cada puesto en varios bloques; contamos codigos unicos.
        codigos_unicos = set()
        for ambito in datos_nomenclator.get("amb", []):
            for item in ambito.get("ambitos", []):
                # Contamos exclusivamente el Nivel 6 (Puestos de Votacion)
                if item.get("l") == 6:
                    codigo_puesto = item.get("c", "")
                    if codigo_puesto.startswith(divipol):
                        codigos_unicos.add(codigo_puesto)
        puestos_muni = len(codigos_unicos)
        print(f"  {muni} (divipol {divipol}): {puestos_muni} puestos encontrados.")
        total_puestos_global += puestos_muni
    print(f"TOTAL estimado a procesar: {total_puestos_global} puestos ({total_puestos_global * 2} consultas de API en total).")


def run(municipios, offline=False):
    raw_dir = os.path.join(DB_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    url_nomenclator = f"{BASE_URL}/json/nomenclator.json"
    
    if offline:
        print("Modo offline activo. Buscando copia local del nomenclador...")
        ruta_nomenclator_local = os.path.join(ROOT, "nomenclator.json")
        if not os.path.exists(ruta_nomenclator_local):
            sys.exit("Error: No se encuentra el nomenclator.json local.")
        with open(ruta_nomenclator_local, "r", encoding="utf-8") as f_nom:
            datos_nomenclator = json.load(f_nom)
    else:
        print("Investigando el nomenclador en vivo desde la Registraduria...")
        try:
            datos_nomenclator = fetch_json(url_nomenclator)
            with open(os.path.join(ROOT, "nomenclator.json"), "w", encoding="utf-8") as f_bak:
                json.dump(datos_nomenclator, f_bak, ensure_ascii=False)
        except Exception as e:
            sys.exit(f"Error critico al descargar el nomenclador: {e}")

    conn = etl.get_connection()
    etl.apply_schema(conn)
    gran = {"ins": 0, "skip": 0}

    for muni in municipios:
        divipol_muni = MUNICIPIOS[muni]
        print(f"\n[{muni}] Buscando puestos de votacion para divipol {divipol_muni}...")

        puestos_descubiertos = []
        codigos_vistos = set()
        for ambito in datos_nomenclator.get("amb", []):
            for item in ambito.get("ambitos", []):
                # Extraemos directamente los Puestos (Nivel 6) en lugar de las mesas
                if item.get("l") == 6:
                    codigo_puesto = item.get("c", "")
                    # El nomenclador repite cada puesto en varios bloques de eleccion;
                    # nos quedamos solo con la primera aparicion de cada codigo.
                    if codigo_puesto.startswith(divipol_muni) and codigo_puesto not in codigos_vistos:
                        codigos_vistos.add(codigo_puesto)
                        nombre_puesto = item.get("n", f"PUESTO {codigo_puesto}")

                        puestos_descubiertos.append({
                            "codigo": codigo_puesto,
                            "puesto_cod": codigo_puesto,
                            "puesto_nom": nombre_puesto,
                            "mesa_num": "TOTAL_PUESTO"
                        })

        print(f"  Se descubrieron {len(puestos_descubiertos)} puestos de votacion en {muni}.")

        if not puestos_descubiertos:
            continue

        puestos_procesados = 0
        for puesto in puestos_descubiertos:
            cod_puesto = puesto["codigo"]
            puesto_nom = puesto["puesto_nom"]
            num_mesa   = puesto["mesa_num"]

            for corp in CORPORACIONES:
                if offline:
                    payload = cargar_offline(cod_puesto, corp)
                    if payload is None:
                        continue
                else:
                    try:
                        url = url_votos(cod_puesto, corp)
                        payload = fetch_json(url)
                        
                        # Pausa leve de cortesia
                        time.sleep(0.1)
                        
                        if payload is None:
                            continue

                        ruta_raw = os.path.join(raw_dir, f"{cod_puesto}_{corp}.json")
                        with open(ruta_raw, "w", encoding="utf-8") as f_raw:
                            json.dump(payload, f_raw, ensure_ascii=False)
                    except Exception:
                        payload = cargar_offline(cod_puesto, corp)
                        if payload is None:
                            continue

                records = parse_json(
                    payload=payload,
                    municipio=muni,
                    divipol=divipol_muni,
                    corp=corp,
                    puesto_cod=cod_puesto,
                    puesto_nom=puesto_nom,
                    mesa_num=num_mesa
                )
                
                if records:
                    stats = etl.load_records(conn, records, municipio_hint=f"{muni}-{corp}-Puesto{cod_puesto}")
                    gran["ins"] += sum(s["ins"] for s in stats.values())
                    gran["skip"] += sum(s["skip"] for s in stats.values())
            
            puestos_procesados += 1
            if puestos_procesados % 10 == 0:
                print(f"    ... procesados {puestos_procesados}/{len(puestos_descubiertos)} puestos")

        print(f"  Finalizado procesamiento de {muni}. Acumulado en ejecucion: +{gran['ins']} insertados.")

    conn.close()
    print(f"\nLISTO - Proceso completado. Total insertadas: {gran['ins']} | omitidas: {gran['skip']}")


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
        preflight(munis, offline=args.offline)
    else:
        run(munis, offline=args.offline)