-- tarea_3_3.sql  -  ATRIBUCION DETERMINISTICA SE  (8 pts)
--
-- Top 5 candidatos de Camara por atribucion de Senado consolidada (4 municipios).
-- Formula: A_ij = (votos_cand_CA / votos_partido_CA) * votos_SE_partido
-- La homologacion CA<->SE se hace por el campo canonico del partido.
--
-- Por que el top CA no siempre coincide con el top atribucion SE:
-- La formula pondera los votos del candidato por la fuerza de su partido
-- en Senado. Si un candidato tiene muchos votos CA pero su partido es debil
-- en SE, su atribucion sera baja. En cambio, un candidato con menos votos CA
-- pero de un partido fuerte en SE puede obtener mayor atribucion. Por ejemplo,
-- un candidato del Pacto Historico con votos moderados en Camara puede superar
-- en atribucion a un candidato de Verde con mas votos, si el Pacto tiene
-- mayor caudal en Senado para ese conjunto de municipios.
--
-- Nota: se excluye "SOLO POR LA LISTA" (voto no preferente) del ranking de
-- candidatos, porque no es una persona. Ese voto permanece dentro del total
-- del partido en Camara (denominador), pues es voto real del partido; de esa
-- forma cada candidato conserva su participacion real y la porcion del voto de
-- lista simplemente no se atribuye a ninguna persona.

WITH cand_ca AS (
    SELECT c.id AS candidato_id, c.nombre_norm, pa.canonico,
           SUM(v.votos) AS votos_cand
    FROM votos v
    JOIN candidatos c  ON c.id  = v.candidato_id
    JOIN partidos   pa ON pa.id = c.partido_id
    WHERE pa.corporacion = 'CA'
      AND c.nombre_norm <> 'SOLO POR LA LISTA'
    GROUP BY c.id
),
partido_ca AS (
    SELECT pa.canonico, SUM(v.votos) AS votos_partido_ca
    FROM votos v
    JOIN candidatos c  ON c.id  = v.candidato_id
    JOIN partidos   pa ON pa.id = c.partido_id
    WHERE pa.corporacion = 'CA'
    GROUP BY pa.canonico
),
partido_se AS (
    SELECT pa.canonico, SUM(v.votos) AS votos_se_partido
    FROM votos v
    JOIN candidatos c  ON c.id  = v.candidato_id
    JOIN partidos   pa ON pa.id = c.partido_id
    WHERE pa.corporacion = 'SE'
    GROUP BY pa.canonico
)
SELECT
    cc.nombre_norm                                                          AS candidato,
    cc.canonico                                                             AS partido,
    cc.votos_cand,
    pca.votos_partido_ca,
    pse.votos_se_partido,
    ROUND(1.0 * cc.votos_cand / NULLIF(pca.votos_partido_ca, 0) * pse.votos_se_partido, 1)
                                                                            AS atribucion_se
FROM cand_ca cc
JOIN partido_ca pca ON pca.canonico = cc.canonico
JOIN partido_se pse ON pse.canonico = cc.canonico
ORDER BY atribucion_se DESC
LIMIT 5;