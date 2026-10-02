# Resumen del análisis exploratorio — Proyecto P12

Datos base: `data/P12 Anexo A Datos.xlsx` (Anexo A entregado por el profesor).

## 1. Validación del árbol de escenarios

- Suma de probabilidades de nodos hoja (finales): 1.000000 (OK)
- Nodo 1: suma de prob. condicionales de sus hijos = 1.000000 (OK)
- Nodo 2: suma de prob. condicionales de sus hijos = 1.000000 (OK)
- Nodo 3: suma de prob. condicionales de sus hijos = 1.000000 (OK)
- Nodo 4: suma de prob. condicionales de sus hijos = 1.000000 (OK)

## 2. Estadística descriptiva de la demanda por producto

| producto   |   media |   desv_std |   minimo |   maximo |    cv |   demanda_esperada |
|:-----------|--------:|-----------:|---------:|---------:|------:|-------------------:|
| (1,1)      | 35643.2 |    21028.6 |    10426 |    81856 | 0.59  |            40664.9 |
| (1,2)      | 32563.8 |    13171.7 |    15184 |    57965 | 0.404 |            33451.4 |
| (1,3)      | 19631.4 |    10954.6 |     4920 |    38150 | 0.558 |            16901.1 |
| (2,1)      | 25911   |     8605.9 |    12646 |    39387 | 0.332 |            26732.1 |
| (2,2)      | 24928.1 |     8114.8 |    14949 |    38048 | 0.326 |            25164.8 |

## 3. Correlación de demanda entre productos

| producto   |   (1,1) |   (1,2) |   (1,3) |   (2,1) |   (2,2) |
|:-----------|--------:|--------:|--------:|--------:|--------:|
| (1,1)      |   1     |  -0.664 |   0.199 |   0.789 |   0.836 |
| (1,2)      |  -0.664 |   1     |  -0.399 |  -0.718 |  -0.813 |
| (1,3)      |   0.199 |  -0.399 |   1     |   0.618 |   0.59  |
| (2,1)      |   0.789 |  -0.718 |   0.618 |   1     |   0.978 |
| (2,2)      |   0.836 |  -0.813 |   0.59  |   0.978 |   1     |

Nota del enunciado: se espera correlación **negativa** entre los productos del Vino 1 y **positiva** entre los del Vino 2.

## 4. Chequeo de capacidad (caso base, sin postergación)

Horas requeridas **nodo a nodo** (no sumadas por período, ya que los nodos de un mismo período son escenarios mutuamente excluyentes) si todo se produce con embotellado y etiquetado **acoplados** — el peor caso posible para la holgura de capacidad, porque no aprovecha la postergación — y con un set-up conjunto por vino en el nodo como cota inferior de los set-ups.

|   nodo |   periodo |   demanda_total_nodo |   horas_proceso_min |   horas_setup_min |   horas_totales_min |   capacidad_h | excede_capacidad   |
|-------:|----------:|---------------------:|--------------------:|------------------:|--------------------:|--------------:|:-------------------|
|      1 |         1 |               112292 |               31.44 |                 3 |               34.44 |            84 | False              |
|      2 |         2 |               183987 |               51.52 |                 3 |               54.52 |            84 | False              |
|      3 |         2 |               142292 |               39.84 |                 3 |               42.84 |            84 | False              |
|      4 |         2 |                98307 |               27.53 |                 3 |               30.53 |            84 | False              |
|      5 |         3 |               178877 |               50.09 |                 3 |               53.09 |            84 | False              |
|      6 |         3 |               148035 |               41.45 |                 3 |               44.45 |            84 | False              |
|      7 |         3 |               181168 |               50.73 |                 3 |               53.73 |            84 | False              |
|      8 |         3 |               150873 |               42.24 |                 3 |               45.24 |            84 | False              |
|      9 |         3 |               120576 |               33.76 |                 3 |               36.76 |            84 | False              |
|     10 |         3 |               109877 |               30.77 |                 3 |               33.77 |            84 | False              |
|     11 |         3 |                99168 |               27.77 |                 3 |               30.77 |            84 | False              |

Ningún nodo supera las 84 horas disponibles incluso en este escenario extremo (todo embotellado y etiquetado acoplado, sin aprovechar la postergación); la holgura mínima observada es de 29.5 horas (nodo con más demanda). Es decir, la capacidad no es la restricción activa en el caso base — la pregunta relevante del proyecto pasa más bien por el manejo de los estanques intermedios, los inventarios y el costo de backorder bajo incertidumbre, no por si la línea alcanza a producir.

## 5. Figuras generadas

- `resultados/figuras/arbol_escenarios.png`
- `resultados/figuras/boxplot_demanda_por_producto.png`
- `resultados/figuras/correlacion_demanda.png`
- `resultados/figuras/demanda_esperada_por_producto.png`
- `resultados/figuras/demanda_por_nodo.png`
- `resultados/figuras/heatmap_demanda.png`