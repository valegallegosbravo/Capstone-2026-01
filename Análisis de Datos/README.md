# Análisis de Datos — Proyecto P12 (Capstone, Grupo 8)

Postergación del Etiquetado en una Viña Exportadora bajo Incertidumbre en la
Demanda (ICS2122 – Taller de Investigación Operativa).

Análisis exploratorio de los datos base entregados por el profesor
(`Anexo A Datos.xlsx`), como punto de partida antes de construir el modelo
de optimización.

## Estructura

```
Análisis de Datos/
├── data/
│   └── P12 Anexo A Datos.xlsx     # copia de los datos fuente (no editar)
├── cargar_datos.py                # funciones para leer y ordenar cada hoja del Excel
├── analisis_exploratorio.py       # script principal: valida, calcula y grafica
├── requirements.txt
└── resultados/
    ├── tablas/                    # CSVs (demanda tidy, resumen, correlación, etc.)
    └── figuras/                   # PNGs
    └── resumen_datos.md           # informe generado automáticamente
```

## Cómo correrlo

```bash
pip install -r requirements.txt
python3 analisis_exploratorio.py
```

Esto regenera todo lo que hay en `resultados/` a partir del Excel en `data/`.

## Qué hace `analisis_exploratorio.py`

1. **Valida el árbol de escenarios**: que las probabilidades condicionales de
   cada nodo sumen 1 y que las probabilidades de los 6 nodos hoja sumen 1.
2. **Estadística descriptiva** de la demanda por producto (media, desviación,
   min/max, coeficiente de variación) y la **demanda esperada** (ponderada
   por la probabilidad de cada nodo hoja).
3. **Matriz de correlación** de demanda entre los 5 productos — confirma lo
   que dice el enunciado: los productos del Vino 1 correlacionan negativo
   entre sí, los del Vino 2 positivo.
4. **Chequeo de capacidad** (caso base, sin postergación): horas requeridas
   **en cada nodo** del árbol (no sumadas por período, ya que los nodos de
   un mismo período son escenarios mutuamente excluyentes) vs. las 84 horas
   disponibles, asumiendo embotellado y etiquetado acoplados (el escenario
   que menos aprovecha la postergación).
5. Exporta todo a `resultados/tablas` (CSV) y `resultados/figuras` (PNG), y
   escribe `resultados/resumen_datos.md` con los hallazgos.

## Módulo `cargar_datos.py`

Si más adelante necesitas los datos para el modelo de optimización (por
ejemplo en Pyomo/Gurobi), importa directamente desde acá en vez de releer el
Excel a mano:

```python
from cargar_datos import cargar_todo
datos = cargar_todo()  # dict con todas las hojas ya limpias
datos["demanda_tidy"]  # una fila por (producto, nodo), con período/estado/prob ya unidos
```

## Nota

Si el profesor actualiza el Excel (nuevos valores, misma estructura de
hojas), basta con reemplazar el archivo en `data/` y volver a correr el
script.
