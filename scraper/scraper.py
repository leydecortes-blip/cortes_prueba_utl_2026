"""
scraper.py  ·  Reto 1  ·  Extraccion API Registraduria — Boyaca 2026

Extrae los resultados a nivel de MESA. El nomenclador no lista las mesas una
por una, pero cada puesto (nivel 6) trae en el campo "m" cuantas mesas tiene.
El codigo de cada mesa es el codigo del puesto (13 digitos) mas el numero de
mesa rellenado con ceros. El ancho de ese relleno (6 o 7) se detecta solo
probando una mesa real contra la API.

Uso:
  python scraper/scraper.py
  python scraper/scraper.py --municipios TUNJA PAIPA
  python scraper/scraper.py --preflight
  python scraper/scraper.py --offline
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
    return f"{BASE_URL}/json/ACT/{corp}/{codigo}.json"


def _nombre_partido(codpar, corp):
    NOMBRES = {
        (87, "CA"): "Pacto Historico", (92, "SE"): "Pacto Historico",
        (5,  "CA"): "Alianza Verde",   (57, "SE"): "Alianza Verde",
        (10, "CA"): "Centro Democratico", (10, "SE"): "Centro Democratico",
        (2,  "CA"): "Partido Conservador", (2,  "SE"): "Partido Conservador",
        (121,"CA"): "Partido Liberal", (122,"CA"): "Colombia Justa Libres",
        (120,"CA"): "MIRA", (15, "CA"): "Partido de la U",
    }
    return NOMBRES.get((codpar, corp), f"Partido {codpar}")


def parse_json(payload, municipio, divipol, corp, puesto_cod, puesto_nom, mesa_num):
    records = []
    camaras = payload.get("camaras", [])
    if not camaras:
        return records
    for partido_bloque in camaras[0].get("partotabla", []):
        act    = partido_bloque.get("act", {})
        codpar = act.get("codpar")
        if codpar is None:
            continue
        for cand in act.get("cantotabla", []):
            nomcan = cand.get("nomcan", "").strip()
            apecan = cand.get("apecan", "").strip()
            nombre = f"{nomcan} {apecan}".strip() or "SOLO POR LA LISTA"
            records.append(dict(
                municipio=municipio, divipol=divipol,
                puesto_codigo=puesto_cod, puesto_nombre=puesto_nom,
                mesa=str(mesa_num), corporacion=corp,
                codpar=int(codpar), partido_nombre=_nombre_partido(int(codpar), corp),
                candidato_numero=str(cand.get("codcan", "0")),
                candidato_nombre=nombre, votos=int(cand.get("vot", 0) or 0),
            ))
    return records


def fetch_json(url, retries=4, backoff=1.5, timeout=30):
    last = None
    for intento in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except json.JSONDecodeError:
            return None
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return None
            last = e
            time.sleep(backoff ** intento)
        except Exception as e:
            last = e
            time.sleep(backoff ** intento)
    raise RuntimeError(f"Fallo tras {retries} intentos: {url} -> {last}")


def fetch_seguro(url):
    """Como fetch_json pero nunca lanza excepcion (para la deteccion)."""
    try:
        return fetch_json(url)
    except Exception:
        return None


def cargar_offline(identificador, corp):
    for carpeta in (os.path.join(DB_DIR, "raw"), os.path.join(ROOT, "sample_data")):
        ruta = os.path.join(carpeta, f"{identificador}_{corp}.json")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
    return None


def obtener_nomenclador(offline):
    if offline:
        ruta = os.path.join(ROOT, "nomenclator.json")
        if not os.path.exists(ruta):
            sys.exit("Error: no se encuentra nomenclator.json local (modo offline).")
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    datos = fetch_json(f"{BASE_URL}/json/nomenclator.json")
    with open(os.path.join(ROOT, "nomenclator.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    return datos


def puestos_de(nom, divipol):
    """Puestos (nivel 6) unicos de un municipio: [{codigo, nombre, m}]."""
    vistos = {}
    for bloque in nom.get("amb", []):
        for item in bloque.get("ambitos", []):
            if item.get("l") == 6:
                cod = item.get("c", "")
                if cod.startswith(divipol) and cod not in vistos:
                    vistos[cod] = {"codigo": cod,
                                   "nombre": item.get("n", f"PUESTO {cod}"),
                                   "m": int(item.get("m", 0) or 0)}
    return list(vistos.values())


def codigo_mesa(cod_puesto, numero, pad):
    return cod_puesto + str(numero).zfill(pad)


def detectar_padding(puestos):
    """Prueba una mesa real para saber si el codigo lleva relleno de 6 o 7 digitos."""
    for p in puestos:
        if p["m"] > 0:
            for pad in (6, 7):
                payload = fetch_seguro(url_votos(codigo_mesa(p["codigo"], 1, pad), "CA"))
                if payload and payload.get("camaras"):
                    return pad
    return None


def preflight(municipios, offline=False):
    print("PREFLIGHT - Conteo de mesas de votacion...")
    nom = obtener_nomenclador(offline)
    todos = []
    total = 0
    for muni in municipios:
        puestos = puestos_de(nom, MUNICIPIOS[muni])
        mesas = sum(p["m"] for p in puestos)
        print(f"  {muni}: {len(puestos)} puestos, {mesas} mesas.")
        total += mesas
        todos += puestos
    print(f"TOTAL estimado: {total} mesas ({total * 2} consultas de API).")

    if not offline:
        pad = detectar_padding(todos)
        if pad:
            print(f"Formato de codigo de mesa detectado: puesto + numero a {pad} digitos "
                  f"(codigo de {13 + pad} digitos). La API respondio correctamente.")
        else:
            print("ADVERTENCIA: ninguna variante de codigo de mesa respondio. Revisar antes de scrapear.")


def run(municipios, offline=False):
    raw_dir = os.path.join(DB_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    print("Cargando nomenclador...")
    nom = obtener_nomenclador(offline)
    puestos_por_muni = {m: puestos_de(nom, MUNICIPIOS[m]) for m in municipios}
    todos = [p for lst in puestos_por_muni.values() for p in lst]

    if offline:
        pad = 6  # en offline se reconstruye; cargar_offline probara ambos si hace falta
    else:
        pad = detectar_padding(todos)
        if pad is None:
            sys.exit("No se pudo confirmar el formato del codigo de mesa (ninguna variante respondio). "
                     "Revisa tu conexion o si la API cambio.")
        print(f"Formato de mesa detectado: relleno a {pad} digitos (codigo de {13 + pad}).")

    conn = etl.get_connection()
    etl.apply_schema(conn)
    gran = {"ins": 0, "skip": 0}

    for muni in municipios:
        divipol = MUNICIPIOS[muni]
        puestos = puestos_por_muni[muni]
        total_mesas = sum(p["m"] for p in puestos)
        print(f"\n[{muni}] {len(puestos)} puestos, {total_mesas} mesas...")

        procesadas = 0
        for p in puestos:
            cod_puesto = p["codigo"]
            puesto_nom = p["nombre"]
            for numero in range(1, p["m"] + 1):
                cod_mesa = codigo_mesa(cod_puesto, numero, pad)
                for corp in CORPORACIONES:
                    if offline:
                        payload = (cargar_offline(cod_mesa, corp)
                                   or cargar_offline(codigo_mesa(cod_puesto, numero, 7), corp))
                        if payload is None:
                            continue
                    else:
                        try:
                            payload = fetch_json(url_votos(cod_mesa, corp))
                            time.sleep(0.05)
                            if payload is None:
                                continue
                            with open(os.path.join(raw_dir, f"{cod_mesa}_{corp}.json"), "w", encoding="utf-8") as fr:
                                json.dump(payload, fr, ensure_ascii=False)
                        except Exception:
                            payload = cargar_offline(cod_mesa, corp)
                            if payload is None:
                                continue

                    records = parse_json(payload, muni, divipol, corp,
                                         cod_puesto, puesto_nom, cod_mesa)
                    if records:
                        stats = etl.load_records(conn, records,
                                                 municipio_hint=f"{muni}-{corp}-Mesa{cod_mesa}")
                        gran["ins"]  += sum(s["ins"]  for s in stats.values())
                        gran["skip"] += sum(s["skip"] for s in stats.values())

                procesadas += 1
                if procesadas % 50 == 0:
                    print(f"    ... {procesadas}/{total_mesas} mesas procesadas")

        print(f"  Finalizado {muni}. Acumulado: +{gran['ins']} insertados.")

    conn.close()
    print(f"\nLISTO - Proceso completado. Total insertadas: {gran['ins']} | omitidas: {gran['skip']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scraper electoral Boyaca 2026 (nivel mesa)")
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