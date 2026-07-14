"""
scatter.py  ·  Reto 5.2  ·  Scatter CA vs SE por mesa

Uso:
  python viz/scatter.py

Lee db/puestos_2026.db (que ya trae las mesas individuales) y genera
viz/scatter_ca_se.png:
  cada punto = una mesa de votacion
  x = total de votos de Camara en la mesa
  y = total de votos de Senado en la mesa
  color = municipio
  linea de regresion OLS + r de Pearson anotado
Imprime r, pendiente y n_mesas.
"""
import os
import sqlite3
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT    = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "db", "puestos_2026.db")
OUT     = os.path.join(HERE, "scatter_ca_se.png")

COLOR_MUNI = {
    "TUNJA":    "#1E477D",
    "DUITAMA":  "#007C34",
    "SOGAMOSO": "#E07B00",
    "PAIPA":    "#7B2D8B",
}


def cargar_mesas():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"No se encuentra la base de datos en {DB_PATH}. Corre primero el scraper.")
    conn = sqlite3.connect(DB_PATH)
    filas = conn.execute("""
        SELECT mu.nombre AS municipio,
               SUM(CASE WHEN pa.corporacion = 'CA' THEN v.votos ELSE 0 END) AS ca,
               SUM(CASE WHEN pa.corporacion = 'SE' THEN v.votos ELSE 0 END) AS se
        FROM votos v
        JOIN candidatos c  ON c.id  = v.candidato_id
        JOIN partidos   pa ON pa.id = c.partido_id
        JOIN mesas      me ON me.id = v.mesa_id
        JOIN puestos    pu ON pu.id = me.puesto_id
        JOIN municipios mu ON mu.id = pu.municipio_id
        GROUP BY me.id
        HAVING ca > 0 AND se > 0
    """).fetchall()
    conn.close()
    return filas


def main():
    filas = cargar_mesas()
    if len(filas) < 3:
        raise SystemExit("Muy pocas mesas para graficar. Revisa que el scraper haya cargado mesas.")

    munis = [r[0] for r in filas]
    x = np.array([r[1] for r in filas], dtype=float)
    y = np.array([r[2] for r in filas], dtype=float)

    r, _ = stats.pearsonr(x, y)
    pendiente, intercepto = np.polyfit(x, y, 1)
    n = len(filas)

    fig, ax = plt.subplots(figsize=(9, 7))
    for muni, color in COLOR_MUNI.items():
        idx = [i for i, m in enumerate(munis) if m == muni]
        if idx:
            ax.scatter(x[idx], y[idx], s=22, alpha=0.65, color=color,
                       edgecolors="white", linewidths=0.3, label=muni.capitalize())

    linea_x = np.array([x.min(), x.max()])
    ax.plot(linea_x, pendiente * linea_x + intercepto,
            color="#1A1F2E", linewidth=1.8, linestyle="--", label="Regresion OLS")

    ax.set_xlabel("Votos de Camara por mesa", fontsize=11)
    ax.set_ylabel("Votos de Senado por mesa", fontsize=11)
    ax.set_title("Relacion entre votos de Camara y Senado por mesa\n(Tunja, Paipa, Sogamoso y Duitama)",
                 fontsize=13, weight="bold", loc="left")

    texto = f"r de Pearson = {r:.3f}\npendiente = {pendiente:.3f}\nmesas (n) = {n}"
    ax.text(0.03, 0.97, texto, transform=ax.transAxes, va="top", ha="left", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#E4E8EE"))

    ax.legend(loc="lower right", frameon=True, fontsize=10)
    ax.grid(True, color="#E4E8EE", linewidth=0.8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Scatter guardado en viz/scatter_ca_se.png ({os.path.getsize(OUT)/1024:.1f} KB)")
    # Formato exacto requerido por el enunciado:
    linea = f"r={r:.3f} | pendiente={pendiente:.3f} | n_mesas={n}"
    print(linea)
    # Guardar stats en archivo para que generar_manifest.py los capture sin problemas de interprete:
    stats_path = os.path.join(HERE, "scatter_stats.txt")
    with open(stats_path, "w", encoding="utf-8") as fs:
        fs.write(linea + "\n")


if __name__ == "__main__":
    main()