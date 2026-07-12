-- tarea_3_1.sql  -  ARRASTRE VERDE CA -> SE 
--
-- Calcula el ratio votos_SE_Verde / votos_CA_Verde por puesto y municipio.
-- Homologacion: Alianza Verde usa codpar 5 en Camara y codpar 57 en Senado.
-- Tecnica: agregacion condicional en una sola pasada sobre la tabla votos.
--
-- Interpretacion del resultado:
--   ratio > 1.0  el partido Verde arrastra mas votos en Senado que en Camara
--   ratio < 1.0  el partido Verde pierde votos al pasar de Camara a Senado
--   ratio = 1.0  arrastre perfecto, mismo volumen en ambas corporaciones

SELECT
    mu.nombre                                        AS municipio,
    pu.codigo                                        AS puesto_codigo,
    pu.nombre                                        AS puesto,
    SUM(CASE WHEN pa.codpar = 5  AND pa.corporacion = 'CA'
             THEN v.votos ELSE 0 END)                AS votos_ca_verde,
    SUM(CASE WHEN pa.codpar = 57 AND pa.corporacion = 'SE'
             THEN v.votos ELSE 0 END)                AS votos_se_verde,
    ROUND(
        1.0 * SUM(CASE WHEN pa.codpar = 57 AND pa.corporacion = 'SE'
                       THEN v.votos ELSE 0 END)
            / NULLIF(
                SUM(CASE WHEN pa.codpar = 5 AND pa.corporacion = 'CA'
                         THEN v.votos ELSE 0 END), 0),
        3)                                           AS arrastre_se_ca
FROM votos v
JOIN candidatos c  ON c.id  = v.candidato_id
JOIN partidos   pa ON pa.id = c.partido_id
JOIN mesas      me ON me.id = v.mesa_id
JOIN puestos    pu ON pu.id = me.puesto_id
JOIN municipios mu ON mu.id = pu.municipio_id
WHERE pa.canonico = 'VERDE'
GROUP BY mu.nombre, pu.codigo, pu.nombre
HAVING votos_ca_verde > 0
ORDER BY mu.nombre, arrastre_se_ca DESC;