-- tarea_3_2.sql  -  DOMINANCIA EXTREMA  (8 pts)
--
-- Identifica mesas donde un candidato concentra mas del 60% de los votos
-- de su propio partido en esa mesa. Construida desde cero con CTE.
--
-- Un porcentaje alto indica que el candidato es el unico referente del
-- partido en ese puesto de votacion, lo que puede reflejar liderazgo
-- local muy fuerte o lista cerrada con un unico candidato conocido.

WITH voto_partido_mesa AS (
    SELECT v.mesa_id, c.partido_id, SUM(v.votos) AS votos_partido
    FROM votos v
    JOIN candidatos c ON c.id = v.candidato_id
    GROUP BY v.mesa_id, c.partido_id
)
SELECT
    mu.nombre                                        AS municipio,
    pu.codigo                                        AS puesto,
    me.numero                                        AS mesa,
    ca.nombre_norm                                   AS candidato,
    pa.nombre                                        AS partido,
    pa.corporacion,
    v.votos                                          AS votos_candidato,
    vpm.votos_partido,
    ROUND(100.0 * v.votos / vpm.votos_partido, 1)   AS pct_dentro_partido
FROM votos v
JOIN candidatos        ca  ON ca.id       = v.candidato_id
JOIN partidos          pa  ON pa.id       = ca.partido_id
JOIN voto_partido_mesa vpm ON vpm.mesa_id = v.mesa_id
                          AND vpm.partido_id = ca.partido_id
JOIN mesas             me  ON me.id  = v.mesa_id
JOIN puestos           pu  ON pu.id  = me.puesto_id
JOIN municipios        mu  ON mu.id  = pu.municipio_id
WHERE vpm.votos_partido > 0
  AND 1.0 * v.votos / vpm.votos_partido > 0.60
ORDER BY pct_dentro_partido DESC, votos_candidato DESC;