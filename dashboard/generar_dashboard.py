"""
generar_dashboard.py  ·  Reto 4  ·  Dashboard HTML

Uso:
  python dashboard/generar_dashboard.py

Lee db/puestos_2026.db y escribe dashboard/index.html autocontenido (datos
embebidos). Se abre con doble clic en Chrome o Firefox; no necesita servidor.
Plotly se carga desde CDN.

Secciones, organizadas en pestanas:
  1. Comparativo  : votos CA totales de los 4 municipios (barras apiladas por partido).
  2. Por Municipio: selector -> top 10 candidatos CA + partido lider SE.
  3. Arrastre     : selector -> ratio Verde por puesto, linea de referencia en 1.0.
"""
import os
import sys
import json
import sqlite3

HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT    = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "db", "puestos_2026.db")
OUT     = os.path.join(HERE, "index.html")

CANONICOS = ["VERDE", "PACTO", "CD", "CONSERVADOR"]
NOMBRE_LARGO = {
    "VERDE":       "Alianza Verde",
    "PACTO":       "Pacto Historico",
    "CD":          "Centro Democratico",
    "CONSERVADOR": "Partido Conservador",
    "OTROS":       "Otros partidos",
}


def q(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def bucket(canon):
    return canon if canon in CANONICOS else "OTROS"


def construir_datos(conn):
    datos = {}

    datos["kpi"] = {
        "votos":      conn.execute("SELECT COALESCE(SUM(votos),0) FROM votos").fetchone()[0],
        "partidos":   conn.execute("SELECT COUNT(*) FROM partidos").fetchone()[0],
        "puestos":    conn.execute("SELECT COUNT(*) FROM puestos").fetchone()[0],
        "municipios": conn.execute("SELECT COUNT(*) FROM municipios").fetchone()[0],
    }

    # Seccion 1 - Comparativo: total de votos de Camara por municipio, por partido + Otros.
    filas = q(conn, """
        SELECT mu.nombre AS municipio, pa.canonico AS canonico, SUM(v.votos) AS total
        FROM votos v
        JOIN candidatos c  ON c.id  = v.candidato_id
        JOIN partidos   pa ON pa.id = c.partido_id
        JOIN mesas      me ON me.id = v.mesa_id
        JOIN puestos    pu ON pu.id = me.puesto_id
        JOIN municipios mu ON mu.id = pu.municipio_id
        WHERE pa.corporacion = 'CA'
        GROUP BY mu.nombre, pa.canonico
    """)
    comp = {}
    for f in filas:
        comp.setdefault(f["municipio"], {k: 0 for k in CANONICOS + ["OTROS"]})
        comp[f["municipio"]][bucket(f["canonico"])] += f["total"]
    datos["comparativo"] = comp

    # Seccion 2 - Top 10 candidatos de Camara por municipio (sin voto de lista).
    filas = q(conn, """
        SELECT mu.nombre AS municipio, c.nombre_norm AS cand,
               pa.canonico AS canonico, SUM(v.votos) AS total
        FROM votos v
        JOIN candidatos c  ON c.id  = v.candidato_id
        JOIN partidos   pa ON pa.id = c.partido_id
        JOIN mesas      me ON me.id = v.mesa_id
        JOIN puestos    pu ON pu.id = me.puesto_id
        JOIN municipios mu ON mu.id = pu.municipio_id
        WHERE pa.corporacion = 'CA' AND c.nombre_norm <> 'SOLO POR LA LISTA'
        GROUP BY mu.nombre, c.id
        ORDER BY mu.nombre, total DESC
    """)
    por_muni = {}
    for f in filas:
        por_muni.setdefault(f["municipio"], [])
        if len(por_muni[f["municipio"]]) < 10:
            por_muni[f["municipio"]].append({
                "cand": f["cand"], "canonico": f["canonico"], "votos": f["total"],
            })
    datos["por_municipio"] = por_muni

    # Partido lider en Senado por municipio.
    filas = q(conn, """
        SELECT mu.nombre AS municipio, pa.canonico AS canonico, SUM(v.votos) AS total
        FROM votos v
        JOIN candidatos c  ON c.id  = v.candidato_id
        JOIN partidos   pa ON pa.id = c.partido_id
        JOIN mesas      me ON me.id = v.mesa_id
        JOIN puestos    pu ON pu.id = me.puesto_id
        JOIN municipios mu ON mu.id = pu.municipio_id
        WHERE pa.corporacion = 'SE'
        GROUP BY mu.nombre, pa.canonico
        ORDER BY mu.nombre, total DESC
    """)
    lider = {}
    for f in filas:
        if f["municipio"] not in lider:
            lider[f["municipio"]] = {"canonico": f["canonico"], "votos": f["total"]}
    datos["lider_se"] = lider

    # Seccion 3 - Arrastre Verde por puesto (logica de tarea_3_1).
    filas = q(conn, """
        SELECT mu.nombre AS municipio, pu.nombre AS puesto,
               SUM(CASE WHEN pa.codpar = 5  AND pa.corporacion = 'CA'
                        THEN v.votos ELSE 0 END) AS ca,
               SUM(CASE WHEN pa.codpar = 57 AND pa.corporacion = 'SE'
                        THEN v.votos ELSE 0 END) AS se
        FROM votos v
        JOIN candidatos c  ON c.id  = v.candidato_id
        JOIN partidos   pa ON pa.id = c.partido_id
        JOIN mesas      me ON me.id = v.mesa_id
        JOIN puestos    pu ON pu.id = me.puesto_id
        JOIN municipios mu ON mu.id = pu.municipio_id
        WHERE pa.canonico = 'VERDE'
        GROUP BY mu.nombre, pu.codigo, pu.nombre
        HAVING ca > 0
    """)
    arrastre = {}
    for f in filas:
        ratio = round(f["se"] / f["ca"], 3) if f["ca"] else 0
        arrastre.setdefault(f["municipio"], [])
        arrastre[f["municipio"]].append({
            "puesto": f["puesto"], "ca": f["ca"], "se": f["se"], "ratio": ratio,
        })
    for m in arrastre:
        arrastre[m].sort(key=lambda x: x["ratio"], reverse=True)
    datos["arrastre"] = arrastre

    datos["municipios"] = sorted(comp.keys())
    datos["nombre_largo"] = NOMBRE_LARGO
    return datos


HTML = r"""<!doctype html>
<html lang="es" translate="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resultados Congreso 2026 - Boyaca</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  :root{
    --marca:#1C283D; --marca-2:#47658F;
    --bg:#F5F6F8; --panel:#FFFFFF; --linea:#E4E8EE;
    --texto:#1A1F2E; --suave:#5B6472; --tenue:#8A94A6;
  }
  [data-theme="dark"]{
    --marca:#A6C0E6; --marca-2:#6E8CBB;
    --bg:#0E1420; --panel:#161D2B; --linea:#28303F;
    --texto:#E7EBF1; --suave:#9CA6B6; --tenue:#6B788C;
  }
  *{box-sizing:border-box}
  body{margin:0; background:var(--bg); color:var(--texto);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;}
  .banda{height:5px;display:flex}
  .banda span{flex:1}
  header{background:var(--marca); color:#fff; padding:26px 28px 22px; position:relative}
  [data-theme="dark"] header{background:#111725; color:var(--texto)}
  .eyebrow{font-size:11px; letter-spacing:.22em; text-transform:uppercase; color:#B9C6DC; margin:0 0 6px}
  [data-theme="dark"] .eyebrow{color:var(--marca-2)}
  header h1{margin:0; font-size:26px; font-weight:700; letter-spacing:-.01em}
  header p.sub{margin:8px 0 0; color:#C7D2E4; font-size:14px; max-width:66ch; line-height:1.5}
  [data-theme="dark"] header p.sub{color:var(--suave)}
  .toggle{position:absolute; top:24px; right:24px; background:rgba(255,255,255,.12); color:#fff;
    border:1px solid rgba(255,255,255,.25); border-radius:999px; padding:7px 14px; font-size:12.5px; cursor:pointer}
  [data-theme="dark"] .toggle{background:var(--panel); color:var(--texto); border-color:var(--linea)}
  main{max-width:980px; margin:0 auto; padding:26px 20px 50px}
  .kpis{display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:24px}
  .kpi{background:var(--panel); border:1px solid var(--linea); border-radius:12px; padding:16px 18px 14px}
  .kpi .n{font-size:25px; font-weight:700; font-variant-numeric:tabular-nums; letter-spacing:-.02em}
  .kpi .l{font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--tenue); margin-top:5px}
  .tabs{display:flex; gap:4px; border-bottom:1px solid var(--linea); margin-bottom:0}
  .tab{background:none; border:none; padding:13px 18px; font-size:14px; font-family:inherit; cursor:pointer;
    color:var(--suave); border-bottom:2px solid transparent; margin-bottom:-1px; letter-spacing:.01em}
  .tab:hover{color:var(--texto)}
  .tab.activo{color:var(--marca-2); border-bottom-color:var(--marca-2); font-weight:600}
  [data-theme="dark"] .tab.activo{color:var(--texto); border-bottom-color:var(--marca-2)}
  .panel{display:none; background:var(--panel); border:1px solid var(--linea); border-top:none;
    border-radius:0 0 14px 14px; padding:22px 24px 20px}
  .panel.activo{display:block}
  .cab{display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin-bottom:4px; flex-wrap:wrap}
  .cab h2{margin:0; font-size:18px; font-weight:700; letter-spacing:-.01em}
  .cab p{margin:7px 0 0; color:var(--suave); font-size:13.5px; max-width:66ch; line-height:1.5}
  .controles{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
  select{background:var(--bg); color:var(--texto); border:1px solid var(--linea);
    border-radius:9px; padding:8px 12px; font-size:13.5px; font-family:inherit; cursor:pointer}
  .btn-csv{background:transparent; color:var(--marca-2); border:1px solid var(--linea);
    border-radius:9px; padding:8px 12px; font-size:12.5px; cursor:pointer; font-family:inherit}
  .btn-csv:hover{border-color:var(--marca-2)}
  .badge{display:inline-flex; align-items:center; gap:8px; margin-top:14px;
    background:var(--bg); border:1px solid var(--linea); border-radius:999px; padding:6px 14px; font-size:13px}
  .badge b{font-weight:700}
  .dot{width:10px; height:10px; border-radius:50%}
  .grafica{width:100%; margin-top:10px}
  @media(max-width:640px){ header h1{font-size:21px} .kpis{grid-template-columns:repeat(2,1fr)}
    main{padding:18px 12px 36px} .tab{padding:11px 12px; font-size:13px} }
</style>
</head>
<body>
<div class="banda">
  <span style="background:#007C34"></span><span style="background:#7B2D8B"></span>
  <span style="background:#1E477D"></span><span style="background:#E07B00"></span>
</div>
<header>
  <button class="toggle" id="toggle">Modo oscuro</button>
  <p class="eyebrow">Elecciones Congreso de la Republica 2026</p>
  <h1>Resultados de Boyaca por puesto de votacion</h1>
  <p class="sub">Tunja, Paipa, Sogamoso y Duitama. Datos oficiales de la Registraduria consolidados a nivel de puesto, comparando Camara y Senado.</p>
</header>

<main>
  <div class="kpis" id="kpis"></div>

  <div class="tabs">
    <button class="tab activo" data-tab="comparativo">Comparativo</button>
    <button class="tab" data-tab="municipio">Por municipio</button>
    <button class="tab" data-tab="arrastre">Arrastre Verde</button>
  </div>

  <div class="panel activo" id="p-comparativo">
    <div class="cab">
      <div>
        <h2>Votos de Camara por municipio</h2>
        <p>Votos a Camara de cada municipio, separados por partido. El bloque gris agrupa a los partidos sin homologacion.</p>
      </div>
      <button class="btn-csv" data-csv="comparativo">Exportar CSV</button>
    </div>
    <div id="g-comparativo" class="grafica" style="height:420px"></div>
  </div>

  <div class="panel" id="p-municipio">
    <div class="cab">
      <div>
        <h2>Top 10 candidatos de Camara</h2>
        <p>Los diez candidatos con mas votos a Camara en el municipio que elijas.</p>
      </div>
      <div class="controles">
        <select id="sel-muni"></select>
        <button class="btn-csv" data-csv="municipio">Exportar CSV</button>
      </div>
    </div>
    <div id="badge-lider"></div>
    <div id="g-municipio" class="grafica" style="height:430px"></div>
  </div>

  <div class="panel" id="p-arrastre">
    <div class="cab">
      <div>
        <h2>Arrastre del voto Verde hacia Senado</h2>
      <div class="controles">
        <select id="sel-arr"></select>
        <button class="btn-csv" data-csv="arrastre">Exportar CSV</button>
      </div>
    </div>
    <div id="g-arrastre" class="grafica" style="height:470px"></div>
  </div>
</main>

<script>
const DATA = __DATA__;
const COLOR = {VERDE:"#007C34", PACTO:"#7B2D8B", CD:"#1E477D", CONSERVADOR:"#E07B00", OTROS:"#8A94A6"};
const ORDEN = ["VERDE","PACTO","CD","CONSERVADOR","OTROS"];
const NL = DATA.nombre_largo;

function etiqueta(c){ return NL[c] || c || "Otro"; }
function colorDe(c){ return COLOR[c] || "#8A94A6"; }
function css(v){ return getComputedStyle(document.body).getPropertyValue(v).trim(); }
function miles(n){ return Number(n).toLocaleString('es-CO'); }

function layoutBase(){
  const texto=css('--texto'), linea=css('--linea'), suave=css('--suave');
  return {
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    font:{color:texto, family:'-apple-system,Segoe UI,Roboto,sans-serif', size:12.5},
    margin:{l:60,r:24,t:14,b:52},
    xaxis:{gridcolor:linea, zerolinecolor:linea, tickfont:{color:suave}, automargin:true},
    yaxis:{gridcolor:linea, zerolinecolor:linea, tickfont:{color:suave}, automargin:true},
    legend:{orientation:'h', y:1.14, x:0, font:{color:suave, size:12}},
    hoverlabel:{font:{family:'-apple-system,Segoe UI,Roboto,sans-serif'}},
    bargap:0.35,
  };
}
const CONF = {responsive:true, displayModeBar:false};

function renderComparativo(){
  const munis = DATA.municipios;
  const trazas = ORDEN.map(part => ({
    x:munis, y:munis.map(m => DATA.comparativo[m][part]),
    name:etiqueta(part), type:'bar', marker:{color:colorDe(part)},
    hovertemplate:'%{x}<br>'+etiqueta(part)+': %{y:,} votos<extra></extra>',
  }));
  const lay = layoutBase();
  lay.barmode='stack';
  lay.yaxis.title={text:'Votos de Camara', font:{color:css('--suave')}};
  lay.annotations = munis.map(m => {
    const tot = ORDEN.reduce((s,p)=>s+DATA.comparativo[m][p],0);
    return {x:m, y:tot, text:miles(tot), showarrow:false, yshift:12, font:{color:css('--suave'), size:12}};
  });
  Plotly.react('g-comparativo', trazas, lay, CONF);
}

function renderMunicipio(){
  const muni = document.getElementById('sel-muni').value;
  const filas = (DATA.por_municipio[muni]||[]).slice().reverse();
  const traza = [{
    x:filas.map(f=>f.votos), y:filas.map(f=>f.cand), type:'bar', orientation:'h',
    marker:{color:filas.map(f=>colorDe(f.canonico))},
    text:filas.map(f=>miles(f.votos)), textposition:'outside', textfont:{color:css('--suave'), size:11},
    customdata:filas.map(f=>etiqueta(f.canonico)),
    hovertemplate:'%{y}<br>%{customdata}<br>%{x:,} votos<extra></extra>', cliponaxis:false,
  }];
  const lay = layoutBase();
  lay.margin.l=210; lay.margin.r=70;
  lay.xaxis.title={text:'Votos Camara', font:{color:css('--suave')}};
  Plotly.react('g-municipio', traza, lay, CONF);

  const l = DATA.lider_se[muni];
  document.getElementById('badge-lider').innerHTML = l
    ? '<span class="badge"><span class="dot" style="background:'+colorDe(l.canonico)+'"></span>'
      + 'Partido lider en Senado: <b>'+etiqueta(l.canonico)+'</b> ('+miles(l.votos)+' votos)</span>' : '';
}

function renderArrastre(){
  const muni = document.getElementById('sel-arr').value;
  const filas = DATA.arrastre[muni]||[];
  const traza = [{
    x:filas.map(f=>f.ratio), y:filas.map(f=>f.puesto), type:'bar', orientation:'h',
    marker:{color:filas.map(f=> f.ratio>=1 ? COLOR.VERDE : '#C0553B')},
    text:filas.map(f=>f.ratio.toFixed(2)), textposition:'outside', textfont:{color:css('--suave'), size:11},
    customdata:filas.map(f=>[f.ca,f.se]),
    hovertemplate:'%{y}<br>Ratio SE/CA: %{x}<br>Verde CA: %{customdata[0]:,}  Verde SE: %{customdata[1]:,}<extra></extra>',
    cliponaxis:false,
  }];
  const lay = layoutBase();
  lay.margin.l=220; lay.margin.r=50;
  lay.xaxis.title={text:'Votos Senado por cada voto Camara (Verde)', font:{color:css('--suave')}};
  lay.shapes=[{type:'line', x0:1, x1:1, y0:-0.5, y1:filas.length-0.5,
    line:{color:css('--suave'), width:1.5, dash:'dash'}}];
  Plotly.react('g-arrastre', traza, lay, CONF);
}

const RENDER = {comparativo:renderComparativo, municipio:renderMunicipio, arrastre:renderArrastre};
let TAB_ACTUAL = 'comparativo';

function descargarCSV(nombre, filas){
  const csv = filas.map(r=>r.map(c=>{
    const s=String(c); return /[",\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
  }).join(',')).join('\n');
  const blob = new Blob(["\ufeff"+csv], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = nombre; a.click(); URL.revokeObjectURL(a.href);
}
function exportar(tipo){
  if(tipo==='comparativo'){
    const f=[['municipio','partido','votos_camara']];
    DATA.municipios.forEach(m=>ORDEN.forEach(p=>f.push([m, etiqueta(p), DATA.comparativo[m][p]])));
    descargarCSV('comparativo_camara_municipios.csv', f);
  } else if(tipo==='municipio'){
    const m=document.getElementById('sel-muni').value;
    const f=[['municipio','candidato','partido','votos_camara']];
    (DATA.por_municipio[m]||[]).forEach(r=>f.push([m, r.cand, etiqueta(r.canonico), r.votos]));
    descargarCSV('top10_camara_'+m+'.csv', f);
  } else {
    const m=document.getElementById('sel-arr').value;
    const f=[['municipio','puesto','verde_ca','verde_se','arrastre_se_ca']];
    (DATA.arrastre[m]||[]).forEach(r=>f.push([m, r.puesto, r.ca, r.se, r.ratio]));
    descargarCSV('arrastre_verde_'+m+'.csv', f);
  }
}

function mostrarTab(nombre){
  TAB_ACTUAL = nombre;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('activo', t.dataset.tab===nombre));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('activo', p.id==='p-'+nombre));
  RENDER[nombre]();  // se dibuja con el panel ya visible, asi toma el tamano correcto
}

(function init(){
  const k = DATA.kpi;
  const items = [
    [miles(k.votos), 'Votos totales'],
    [k.partidos, 'Partidos'],
    [k.puestos, 'Puestos'],
    [k.municipios, 'Municipios'],
  ];
  document.getElementById('kpis').innerHTML = items.map(
    it => '<div class="kpi"><div class="n">'+it[0]+'</div><div class="l">'+it[1]+'</div></div>').join('');

  const selM=document.getElementById('sel-muni'), selA=document.getElementById('sel-arr');
  DATA.municipios.forEach(m=>{
    selM.insertAdjacentHTML('beforeend','<option>'+m+'</option>');
    if(DATA.arrastre[m]) selA.insertAdjacentHTML('beforeend','<option>'+m+'</option>');
  });
  selM.addEventListener('change', renderMunicipio);
  selA.addEventListener('change', renderArrastre);
  document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>mostrarTab(t.dataset.tab)));
  document.querySelectorAll('[data-csv]').forEach(b=>b.addEventListener('click',()=>exportar(b.dataset.csv)));

  const toggle=document.getElementById('toggle');
  toggle.addEventListener('click',()=>{
    const oscuro=document.body.getAttribute('data-theme')==='dark';
    document.body.setAttribute('data-theme', oscuro?'light':'dark');
    toggle.textContent = oscuro?'Modo oscuro':'Modo claro';
    RENDER[TAB_ACTUAL]();  // re-dibuja la pestana visible con el nuevo tema
  });

  mostrarTab('comparativo');
})();
</script>
</body>
</html>
"""


def main():
    if not os.path.exists(DB_PATH):
        sys.exit(f"No se encuentra la base de datos en {DB_PATH}. Corre primero el scraper.")
    conn = sqlite3.connect(DB_PATH)
    try:
        datos = construir_datos(conn)
    finally:
        conn.close()
    html = HTML.replace("__DATA__", json.dumps(datos, ensure_ascii=False))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("Dashboard generado en dashboard/index.html")
    print(f"  votos totales: {datos['kpi']['votos']:,}  |  partidos: {datos['kpi']['partidos']}")
    print("Abrelo con doble clic en Chrome o Firefox.")


if __name__ == "__main__":
    main()