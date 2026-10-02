"""
Archivo fuente: 'P12 Anexo A Datos.xlsx'
    Configuracion  -> parámetros del sistema de envasado
    Productos      -> vinos, etiquetas admisibles e inventarios iniciales
    Setups_Costos  -> tiempos/costos de set-up, tiempos unitarios y costos
    Arbol          -> árbol de escenarios de demanda (11 nodos)
    Demanda        -> demanda por producto y nodo (botellas)
    Niveles        -> niveles de referencia sugeridos para el análisis
"""

from pathlib import Path
import pandas as pd

RUTA_POR_DEFECTO = Path(__file__).parent / "data" / "P12 Anexo A Datos.xlsx"


def cargar_configuracion(path=RUTA_POR_DEFECTO) -> pd.DataFrame:
    """Parámetros del sistema de envasado (línea, capacidad, estanques, etc.)."""
    df = pd.read_excel(path, sheet_name="Configuracion", header=2)
    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = ["parametro", "valor", "unidad", "comentario"]
    return df


def cargar_productos(path=RUTA_POR_DEFECTO):
    """Devuelve (vinos_etiquetas, inventario_inicial)."""
    raw = pd.read_excel(path, sheet_name="Productos", header=None)

    vinos = raw.iloc[3:5, 0:3].copy()
    vinos.columns = ["vino", "etiquetas_admisibles", "productos_terminados"]
    vinos = vinos.reset_index(drop=True)

    inventario = raw.iloc[8:11, 0:3].copy()
    inventario.columns = ["concepto", "valor", "unidad"]
    inventario = inventario.reset_index(drop=True)
    inventario["valor"] = pd.to_numeric(inventario["valor"])

    return vinos, inventario


def cargar_setups_costos(path=RUTA_POR_DEFECTO):
    """Devuelve (setups, tiempos_unitarios, costos_inventario)."""
    raw = pd.read_excel(path, sheet_name="Setups_Costos", header=None)

    setups = raw.iloc[3:6, 0:4].copy()
    setups.columns = ["concepto", "tiempo_h", "costo_pesos", "comentario"]
    setups = setups.reset_index(drop=True)

    tiempos = raw.iloc[9:12, 0:3].copy()
    tiempos.columns = ["concepto", "valor", "unidad"]
    tiempos = tiempos.reset_index(drop=True)
    tiempos["valor"] = pd.to_numeric(tiempos["valor"])

    # Bloque de costos de inventario y servicio: ubicarlo buscando el
    # encabezado, ya que su fila exacta puede variar levemente.
    fila_header = raw.index[raw[0] == "Costos de inventario y servicio"][0]
    inicio = fila_header + 1
    costos = raw.iloc[inicio:inicio + 3, 0:3].copy()
    costos.columns = ["concepto", "valor", "unidad"]
    costos = costos.reset_index(drop=True)
    costos["valor"] = pd.to_numeric(costos["valor"])

    return setups, tiempos, costos


def cargar_arbol(path=RUTA_POR_DEFECTO) -> pd.DataFrame:
    """Árbol de escenarios de demanda: 11 nodos, 3 períodos."""
    df = pd.read_excel(path, sheet_name="Arbol", header=2)
    df.columns = [
        "nodo", "periodo", "estado", "nodo_antecesor",
        "prob_condicional", "prob_nodo",
    ]
    df["nodo"] = pd.to_numeric(df["nodo"], errors="coerce")
    df = df.dropna(subset=["nodo"]).reset_index(drop=True)
    df["nodo"] = df["nodo"].astype(int)
    df["periodo"] = df["periodo"].astype(int)
    df["prob_condicional"] = pd.to_numeric(df["prob_condicional"])
    df["prob_nodo"] = pd.to_numeric(df["prob_nodo"])
    return df


def cargar_demanda(path=RUTA_POR_DEFECTO):
    """Devuelve (demanda_wide, demanda_tidy).

    demanda_wide: productos en filas, nodos en columnas (tal como en el Excel).
    demanda_tidy: una fila por (producto, nodo), con vino/etiqueta separados
        y con período, estado y probabilidad del nodo ya unidos desde 'Arbol'.
    """
    raw = pd.read_excel(path, sheet_name="Demanda", header=2)
    raw = raw.dropna(how="all").reset_index(drop=True)
    raw = raw.rename(columns={raw.columns[0]: "producto"})
    raw = raw[raw["producto"].astype(str).str.startswith("(")].reset_index(drop=True)

    # Nodo 1..11 como columnas numéricas
    for col in raw.columns[1:]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    wide = raw.set_index("producto")
    wide.columns = [int(str(c).replace("Nodo", "").strip()) for c in wide.columns]

    tidy = wide.reset_index().melt(
        id_vars="producto", var_name="nodo", value_name="demanda"
    )
    tidy["vino"] = tidy["producto"].str.extract(r"\((\d+),\s*\d+\)").astype(int)
    tidy["etiqueta"] = tidy["producto"].str.extract(r"\(\d+,\s*(\d+)\)").astype(int)

    arbol = cargar_arbol(path)
    tidy = tidy.merge(arbol, on="nodo", how="left")

    return wide, tidy


def cargar_niveles(path=RUTA_POR_DEFECTO) -> pd.DataFrame:
    """Niveles de referencia sugeridos para el análisis de sensibilidad."""
    df = pd.read_excel(path, sheet_name="Niveles", header=2)
    df.columns = ["dimension", "niveles_referencia", "comentario"]
    df = df.dropna(subset=["niveles_referencia"]).reset_index(drop=True)
    return df


def cargar_todo(path=RUTA_POR_DEFECTO) -> dict:
    """Carga todas las hojas y devuelve un diccionario de DataFrames."""
    vinos, inventario = cargar_productos(path)
    setups, tiempos, costos_inv = cargar_setups_costos(path)
    demanda_wide, demanda_tidy = cargar_demanda(path)

    return {
        "configuracion": cargar_configuracion(path),
        "vinos_etiquetas": vinos,
        "inventario_inicial": inventario,
        "setups": setups,
        "tiempos_unitarios": tiempos,
        "costos_inventario": costos_inv,
        "arbol": cargar_arbol(path),
        "demanda_wide": demanda_wide,
        "demanda_tidy": demanda_tidy,
        "niveles": cargar_niveles(path),
    }


if __name__ == "__main__":
    datos = cargar_todo()
    for nombre, df in datos.items():
        print(f"\n=== {nombre} ({df.shape[0]}x{df.shape[1]}) ===")
        print(df.head())
