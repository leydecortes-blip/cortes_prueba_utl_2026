"""
heatmap.py  ·  Reto 5.1  ·  Heatmap top 8 candidatos CA x municipios

Uso:
  python viz/heatmap.py

Genera viz/heatmap_municipios.png:
  filas    = los 8 candidatos de Camara mas votados (suma en los 4 municipios)
  columnas = los 4 municipios
  valores  = porcentaje que ese candidato representa sobre el total de votos
             de Camara del municipio (cada columna se calcula contra el total
             de su municipio). Cada celda va anotada con su porcentaje.
"""
import os
import sqlite3
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT    = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "db", "puestos_2026.db")
OUT     = os.path.join(HERE, "heatmap_municipios.png")

ORDEN_MUNI = ["TUNJA", "DUITAMA", "SOGAMOSO", "PAIPA"]


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"No se encuentra la base de datos en {DB_PATH}. Corre primero el scraper.")

    conn = sqlite3.connect(DB_PATH)

    # Los 8 candidatos de Camara mas votados en total (sin el voto de lista).
    top8 = conn.execute("""
        SELECT c.id, c.nombre_norm, SUM(v.votos) AS total
        FROM votos v
        JOIN candidatos c  ON c.id  = v.candidato_id
        JOIN partidos   pa ON pa.id = c.partido_id
        WHERE pa.corporacion = 'CA' AND c.nombre_norm <> 'SOLO POR LA LISTA'
        GROUP BY c.id
        ORDER BY total DESC
        LIMIT 8
    """).fetchall()
    ids     = [r[0] for r in top8]
    nombres = [r[1] for r in top8]

    # Municipios presentes, en un orden fijo si estan disponibles.
    presentes = {r[0] for r in conn.execute("SELECT nombre FROM municipios").fetchall()}
    municipios = [m for m in ORDEN_MUNI if m in presentes]
    for m in sorted(presentes):
        if m not in municipios:
            municipios.append(m)

    # Total de votos de Camara por municipio (denominador de cada columna).
    total_muni = {}
    for m in municipios:
        total_muni[m] = conn.execute("""
            SELECT COALESCE(SUM(v.votos),0)
            FROM votos v
            JOIN candidatos c  ON c.id  = v.candidato_id
            JOIN partidos   pa ON pa.id = c.partido_id
            JOIN mesas      me ON me.id = v.mesa_id
            JOIN puestos    pu ON pu.id = me.puesto_id
            JOIN municipios mu ON mu.id = pu.municipio_id
            WHERE pa.corporacion = 'CA' AND mu.nombre = ?
        """, (m,)).fetchone()[0]

    # Votos de cada candidato del top 8 en cada municipio.
    matriz = np.zeros((len(ids), len(municipios)))
    for i, cid in enumerate(ids):
        for j, m in enumerate(municipios):
            votos = conn.execute("""
                SELECT COALESCE(SUM(v.votos),0)
                FROM votos v
                JOIN mesas      me ON me.id = v.mesa_id
                JOIN puestos    pu ON pu.id = me.puesto_id
                JOIN municipios mu ON mu.id = pu.municipio_id
                WHERE v.candidato_id = ? AND mu.nombre = ?
            """, (cid, m)).fetchone()[0]
            den = total_muni[m] or 1
            matriz[i, j] = 100.0 * votos / den
    conn.close()

    # Figura.
    fig, ax = plt.subplots(figsize=(1.6 * len(municipios) + 3.5, 0.62 * len(ids) + 2))
    im = ax.imshow(matriz, cmap="YlGnBu", aspect="auto")

    ax.set_xticks(range(len(municipios)))
    ax.set_xticklabels([m.capitalize() for m in municipios], fontsize=11)
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels([n.title() for n in nombres], fontsize=10)
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

    umbral = matriz.max() * 0.55 if matriz.max() > 0 else 1
    for i in range(len(ids)):
        for j in range(len(municipios)):
            val = matriz[i, j]
            color = "white" if val > umbral else "#1A1F2E"
            ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                    color=color, fontsize=9.5)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("% de los votos de Camara del municipio", fontsize=10)

    ax.set_title("Top 8 candidatos de Camara por municipio\n(participacion sobre el total de Camara de cada municipio)",
                 fontsize=13, pad=42, loc="left", weight="bold")

    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)

    tam = os.path.getsize(OUT)
    print(f"Heatmap guardado en viz/heatmap_municipios.png ({tam/1024:.1f} KB)")
    print(f"  candidatos (filas): {len(ids)}   municipios (columnas): {len(municipios)}")


if __name__ == "__main__":
    main()
