"""
export_data.py  ·  Dashboard  ·  Exportacion de datos a JSON

Uso:
  python dashboard/export_data.py

Genera dashboard/data.json con los datos que usa el dashboard.
El archivo generar_dashboard.py ya incluye este paso internamente,
por lo que este script es un alias de conveniencia para la estructura
obligatoria del repositorio.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from generar_dashboard import main

if __name__ == "__main__":
    main()
