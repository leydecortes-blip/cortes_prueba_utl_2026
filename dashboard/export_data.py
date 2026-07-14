"""
export_data.py  ·  Dashboard  ·  Exportacion de datos a data.json

Uso:
  python dashboard/export_data.py

Lee db/puestos_2026.db y genera dashboard/data.json con los datos
que usa el dashboard. El archivo generar_dashboard.py los embebe
directamente en el HTML; este script los exporta tambien como JSON
para cumplir con la estructura obligatoria del repositorio.
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# Reutiliza la logica de construccion de datos del generador del dashboard.
from generar_dashboard import construir_datos
import sqlite3

DB_PATH = os.path.join(ROOT, "db", "puestos_2026.db")
OUT     = os.path.join(HERE, "data.json")


def main():
    if not os.path.exists(DB_PATH):
        sys.exit(f"No se encuentra {DB_PATH}. Corre primero el scraper.")
    conn = sqlite3.connect(DB_PATH)
    try:
        datos = construir_datos(conn)
    finally:
        conn.close()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"data.json generado en dashboard/data.json ({os.path.getsize(OUT)/1024:.1f} KB)")


if __name__ == "__main__":
    main()