"""
Qué hace:
    1. Carga todas las hojas del Anexo A (via cargar_datos.py).
    2. Valida la consistencia del árbol de escenarios (probabilidades).
    3. Calcula estadística descriptiva de la demanda por producto.
    4. Calcula la demanda esperada (ponderada por prob. de nodo) por producto.
    5. Calcula la matriz de correlación de demanda entre productos.
    6. Chequea capacidad: horas requeridas vs. horas disponibles por período
       en el caso base (sin postergación).
    7. Exporta tablas (CSV) y figuras (PNG) a resultados/.
    8. Escribe un resumen en resultados/resumen_datos.md.
"""

from cargar_datos import cargar_todo
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")


BASE_DIR = Path(__file__).parent
DIR_TABLAS = BASE_DIR / "resultados" / "tablas"
DIR_FIGURAS = BASE_DIR / "resultados" / "figuras"
DIR_TABLAS.mkdir(parents=True, exist_ok=True)
DIR_FIGURAS.mkdir(parents=True, exist_ok=True)

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

CATEGORICAL = {
    1: "#2a78d6",  # azul
    2: "#eb6834",  # naranjo
    3: "#1baf7a",  # aqua
    4: "#eda100",  # amarillo
    5: "#e87ba4",  # magenta
}
# Mapeo fijo producto -> color (misma identidad en todos los gráficos)
COLOR_PRODUCTO = {
    "(1,1)": CATEGORICAL[1],
    "(1,2)": CATEGORICAL[2],
    "(1,3)": CATEGORICAL[3],
    "(2,1)": CATEGORICAL[4],
    "(2,2)": CATEGORICAL[5],
}
SEQ_BLUE = "#256abf"       # step 500, para heatmap secuencial
DIV_BLUE = "#2a78d6"
DIV_RED = "#e34948"
DIV_NEUTRAL = "#f0efec"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "grid.color": GRIDLINE,
    "axes.grid": True,
    "grid.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "font.size": 10,
})


def miles(x, pos):
    return f"{x:,.0f}".replace(",", ".")


FORMATO_MILES = mticker.FuncFormatter(miles)


# Validación del árbol de escenarios
def validar_arbol(arbol: pd.DataFrame) -> list[str]:
    mensajes = []

    hojas = arbol[~arbol["nodo"].isin(
        arbol["nodo_antecesor"].replace("-", np.nan).dropna().astype(int))]
    suma_hojas = hojas["prob_nodo"].sum()
    ok_hojas = np.isclose(suma_hojas, 1.0)
    mensajes.append(
        f"Suma de probabilidades de nodos hoja (finales): {suma_hojas:.6f} "
        f"({'OK' if ok_hojas else 'REVISAR'})"
    )

    for _, fila in arbol.iterrows():
        if fila["nodo_antecesor"] == "-":
            continue
        padre = int(fila["nodo_antecesor"])
        esperado = arbol.loc[arbol["nodo"] == padre,
                             "prob_nodo"].iloc[0] * fila["prob_condicional"]
        if not np.isclose(esperado, fila["prob_nodo"], atol=1e-6):
            mensajes.append(
                f"  Nodo {int(fila['nodo'])}: prob. calculada {esperado:.6f} "
                f"!= prob. reportada {fila['prob_nodo']:.6f}"
            )

    for padre in arbol["nodo_antecesor"].replace("-", np.nan).dropna().astype(int).unique():
        hijos = arbol[arbol["nodo_antecesor"] == padre]
        suma = hijos["prob_condicional"].sum()
        ok = np.isclose(suma, 1.0)
        mensajes.append(
            f"Nodo {padre}: suma de prob. condicionales de sus hijos = {suma:.6f} "
            f"({'OK' if ok else 'REVISAR'})"
        )

    return mensajes


# Estadística descriptiva y demanda esperada
def resumen_demanda(demanda_tidy: pd.DataFrame) -> pd.DataFrame:
    resumen = (
        demanda_tidy.groupby("producto")["demanda"]
        .agg(media="mean", desv_std="std", minimo="min", maximo="max")
        .round(1)
    )
    resumen["cv"] = (resumen["desv_std"] / resumen["media"]).round(3)

    hojas = demanda_tidy[~demanda_tidy["nodo"].isin(
        demanda_tidy.loc[demanda_tidy["nodo_antecesor"]
                         != "-", "nodo_antecesor"].astype(int).unique()
    )]
    esperada = (
        hojas.assign(contrib=hojas["demanda"] * hojas["prob_nodo"])
        .groupby("producto")["contrib"].sum()
        .round(1)
        .rename("demanda_esperada")
    )

    return resumen.join(esperada)


def matriz_correlacion(demanda_wide: pd.DataFrame) -> pd.DataFrame:
    return demanda_wide.T.corr().round(3)


# Chequeo de capacidad (caso base, sin postergación)
def chequeo_capacidad(datos: dict) -> pd.DataFrame:
    """Chequeo de capacidad NODO a NODO
    Se calcula el peor caso posible (embotellado
    y etiquetado acoplados), sin aprovechar la postergación- como cota
    superior de horas requeridas en cada nodo."""

    tiempos = datos["tiempos_unitarios"].set_index("concepto")["valor"]
    t_acoplado = float(tiempos["Llenado y etiquetado acoplados"])

    setups = datos["setups"].set_index("concepto")
    n_vinos = datos["vinos_etiquetas"].shape[0]
    setup_acoplado_h = float(
        setups.loc["Set-up conjunto de embotellado y etiquetado", "tiempo_h"])
    # cota inferior: 1 set-up por vino en el nodo
    horas_setup = n_vinos * setup_acoplado_h

    cfg = datos["configuracion"].set_index("parametro")["valor"]
    capacidad_periodo = float(cfg["Capacidad de la línea por período"])

    demanda_tidy = datos["demanda_tidy"]
    demanda_nodo = demanda_tidy.groupby(["nodo", "periodo"])[
        "demanda"].sum().reset_index()

    demanda_nodo["horas_proceso_min"] = (
        demanda_nodo["demanda"] * t_acoplado).round(2)
    demanda_nodo["horas_setup_min"] = horas_setup
    demanda_nodo["horas_totales_min"] = (
        demanda_nodo["horas_proceso_min"] + demanda_nodo["horas_setup_min"]
    ).round(2)
    demanda_nodo["capacidad_h"] = capacidad_periodo
    demanda_nodo["excede_capacidad"] = demanda_nodo["horas_totales_min"] > capacidad_periodo

    demanda_nodo = demanda_nodo.rename(
        columns={"demanda": "demanda_total_nodo"})
    demanda_nodo = demanda_nodo.sort_values(
        ["periodo", "nodo"]).reset_index(drop=True)
    return demanda_nodo


# Figuras
def fig_demanda_esperada(resumen: pd.DataFrame, ruta: Path):
    fig, ax = plt.subplots(figsize=(6.4, 4))
    productos = resumen.index.tolist()
    valores = resumen["demanda_esperada"]
    colores = [COLOR_PRODUCTO[p] for p in productos]

    barras = ax.bar(productos, valores, color=colores, width=0.6)
    ax.set_ylabel("Demanda esperada (botellas)")
    ax.set_title("Demanda esperada por producto\n(ponderada por prob. de nodo)",
                 loc="left", color=INK_PRIMARY, fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(FORMATO_MILES)
    ax.grid(axis="x", visible=False)

    for barra, val in zip(barras, valores):
        ax.annotate(f"{val:,.0f}".replace(",", "."),
                    (barra.get_x() + barra.get_width() / 2, val),
                    textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=9, color=INK_SECONDARY)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def fig_demanda_por_nodo(demanda_tidy: pd.DataFrame, ruta: Path):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for producto, color in COLOR_PRODUCTO.items():
        sub = demanda_tidy[demanda_tidy["producto"]
                           == producto].sort_values("nodo")
        ax.plot(sub["nodo"], sub["demanda"], marker="o", markersize=5,
                linewidth=2, color=color, label=producto)

    ax.set_xlabel("Nodo del árbol de escenarios")
    ax.set_ylabel("Demanda (botellas)")
    ax.set_title("Demanda por producto en cada nodo del árbol",
                 loc="left", color=INK_PRIMARY, fontsize=11, fontweight="bold")
    ax.set_xticks(range(1, 12))
    ax.yaxis.set_major_formatter(FORMATO_MILES)
    ax.legend(title="Producto (vino, etiqueta)", frameon=False, ncols=5,
              loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=9)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def fig_boxplot_demanda(demanda_tidy: pd.DataFrame, ruta: Path):
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    productos = list(COLOR_PRODUCTO.keys())
    datos_box = [demanda_tidy.loc[demanda_tidy["producto"]
                                  == p, "demanda"] for p in productos]

    caja = ax.boxplot(datos_box, patch_artist=True, widths=0.5,
                      medianprops=dict(color=INK_PRIMARY, linewidth=2))
    for parche, color in zip(caja["boxes"], [COLOR_PRODUCTO[p] for p in productos]):
        parche.set_facecolor(color)
        parche.set_alpha(0.75)
        parche.set_edgecolor(color)
    for elemento in ("whiskers", "caps"):
        for linea in caja[elemento]:
            linea.set_color(INK_MUTED)

    ax.set_xticklabels(productos)
    ax.set_ylabel("Demanda (botellas)")
    ax.set_title("Distribución de la demanda por producto (11 nodos)",
                 loc="left", color=INK_PRIMARY, fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(FORMATO_MILES)
    ax.grid(axis="x", visible=False)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def fig_heatmap_demanda(demanda_wide: pd.DataFrame, ruta: Path):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    datos = demanda_wide.values
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "seq_azul", ["#f0efec", SEQ_BLUE]
    )
    im = ax.imshow(datos, cmap=cmap, aspect="auto")

    ax.set_xticks(range(demanda_wide.shape[1]))
    ax.set_xticklabels([f"N{c}" for c in demanda_wide.columns])
    ax.set_yticks(range(demanda_wide.shape[0]))
    ax.set_yticklabels(demanda_wide.index)
    ax.set_title("Mapa de calor: demanda por producto y nodo (botellas)",
                 loc="left", color=INK_PRIMARY, fontsize=11, fontweight="bold")
    ax.grid(False)

    for i in range(datos.shape[0]):
        for j in range(datos.shape[1]):
            valor = datos[i, j]
            color_txt = SURFACE if valor > datos.max() * 0.55 else INK_PRIMARY
            ax.text(j, i, f"{valor/1000:.0f}k", ha="center", va="center",
                    fontsize=7.5, color=color_txt)

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.ax.tick_params(labelsize=8, color=INK_MUTED)
    cbar.outline.set_visible(False)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def fig_correlacion(corr: pd.DataFrame, ruta: Path):
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "div_azul_rojo", [DIV_BLUE, DIV_NEUTRAL, DIV_RED]
    )
    im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1)

    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index)
    ax.set_title("Correlación de demanda entre productos (entre nodos)",
                 loc="left", color=INK_PRIMARY, fontsize=10.5, fontweight="bold")
    ax.grid(False)

    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            valor = corr.values[i, j]
            color_txt = SURFACE if abs(valor) > 0.55 else INK_PRIMARY
            ax.text(j, i, f"{valor:.2f}", ha="center", va="center",
                    fontsize=8.5, color=color_txt)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8, color=INK_MUTED)
    cbar.outline.set_visible(False)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def fig_arbol_escenarios(arbol: pd.DataFrame, ruta: Path):
    """Diagrama simple del árbol de escenarios. Color diverge según estado
    de demanda: Baja=azul, Media=gris neutro, Alta=rojo (lectura ordinal)."""
    color_estado = {"Baja": DIV_BLUE, "Media": INK_MUTED, "Alta": DIV_RED}

    posiciones = {}
    for periodo in sorted(arbol["periodo"].unique()):
        nodos_periodo = arbol[arbol["periodo"] == periodo]["nodo"].tolist()
        n = len(nodos_periodo)
        for i, nodo in enumerate(nodos_periodo):
            y = (i - (n - 1) / 2)
            posiciones[nodo] = (periodo, y)

    fig, ax = plt.subplots(figsize=(8, 5))

    for _, fila in arbol.iterrows():
        if fila["nodo_antecesor"] == "-":
            continue
        padre = int(fila["nodo_antecesor"])
        x0, y0 = posiciones[padre]
        x1, y1 = posiciones[int(fila["nodo"])]
        ax.plot([x0, x1], [y0, y1], color=BASELINE, linewidth=1.4, zorder=1)
        ax.annotate(f"{fila['prob_condicional']:.2f}",
                    ((x0 + x1) / 2, (y0 + y1) / 2),
                    fontsize=7.5, color=INK_SECONDARY, ha="center", va="center",
                    backgroundcolor=SURFACE)

    for _, fila in arbol.iterrows():
        x, y = posiciones[int(fila["nodo"])]
        color = color_estado[fila["estado"]]
        ax.scatter([x], [y], s=520, color=color, zorder=2,
                   edgecolor=SURFACE, linewidth=1.5)
        ax.annotate(f"N{int(fila['nodo'])}\n{fila['prob_nodo']:.2f}",
                    (x, y), ha="center", va="center", fontsize=7.5,
                    color=SURFACE, fontweight="bold", zorder=3)

    for etiqueta, color in color_estado.items():
        ax.scatter([], [], color=color, s=120, label=etiqueta)
    ax.legend(title="Estado de demanda", frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.05), ncols=3, fontsize=9)

    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Período 1", "Período 2", "Período 3"])
    ax.set_yticks([])
    ax.set_title("Árbol de escenarios de demanda (11 nodos)",
                 loc="left", color=INK_PRIMARY, fontsize=11, fontweight="bold")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(False)

    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def main():
    datos = cargar_todo()

    mensajes_validacion = validar_arbol(datos["arbol"])
    resumen = resumen_demanda(datos["demanda_tidy"])
    corr = matriz_correlacion(datos["demanda_wide"])
    capacidad = chequeo_capacidad(datos)

    # --- Tablas ---
    datos["demanda_tidy"].to_csv(DIR_TABLAS / "demanda_tidy.csv", index=False)
    datos["arbol"].to_csv(DIR_TABLAS / "arbol.csv", index=False)
    resumen.to_csv(DIR_TABLAS / "resumen_demanda_por_producto.csv")
    corr.to_csv(DIR_TABLAS / "correlacion_demanda.csv")
    capacidad.to_csv(DIR_TABLAS / "chequeo_capacidad.csv")
    datos["configuracion"].to_csv(
        DIR_TABLAS / "configuracion.csv", index=False)
    datos["niveles"].to_csv(DIR_TABLAS / "niveles_referencia.csv", index=False)

    # --- Figuras ---
    fig_demanda_esperada(resumen, DIR_FIGURAS /
                         "demanda_esperada_por_producto.png")
    fig_demanda_por_nodo(datos["demanda_tidy"],
                         DIR_FIGURAS / "demanda_por_nodo.png")
    fig_boxplot_demanda(datos["demanda_tidy"],
                        DIR_FIGURAS / "boxplot_demanda_por_producto.png")
    fig_heatmap_demanda(datos["demanda_wide"],
                        DIR_FIGURAS / "heatmap_demanda.png")
    fig_correlacion(corr, DIR_FIGURAS / "correlacion_demanda.png")
    fig_arbol_escenarios(datos["arbol"], DIR_FIGURAS / "arbol_escenarios.png")

    # --- Resumen en Markdown ---
    lineas = []
    lineas.append("# Resumen del análisis exploratorio — Proyecto P12\n")
    lineas.append(
        "Datos base: `data/P12 Anexo A Datos.xlsx` (Anexo A entregado por el profesor).\n")

    lineas.append("## 1. Validación del árbol de escenarios\n")
    lineas.extend(f"- {m}" for m in mensajes_validacion)
    lineas.append("")

    lineas.append("## 2. Estadística descriptiva de la demanda por producto\n")
    lineas.append(resumen.to_markdown())
    lineas.append("")

    lineas.append("## 3. Correlación de demanda entre productos\n")
    lineas.append(corr.to_markdown())
    lineas.append(
        "\nNota del enunciado: se espera correlación **negativa** entre los "
        "productos del Vino 1 y **positiva** entre los del Vino 2."
    )
    lineas.append("")

    lineas.append("## 4. Chequeo de capacidad (caso base, sin postergación)\n")
    lineas.append(
        "Horas requeridas **nodo a nodo** (no sumadas por período, ya que los "
        "nodos de un mismo período son escenarios mutuamente excluyentes) si "
        "todo se produce con embotellado y etiquetado **acoplados** — el peor "
        "caso posible para la holgura de capacidad, porque no aprovecha la "
        "postergación — y con un set-up conjunto por vino en el nodo como "
        "cota inferior de los set-ups.\n"
    )
    lineas.append(capacidad.to_markdown(index=False))
    n_excede = int(capacidad["excede_capacidad"].sum())
    cap_h = capacidad["capacidad_h"].iloc[0]
    holgura_min = (cap_h - capacidad["horas_totales_min"]).min()
    if n_excede > 0:
        mensaje = (
            f"\n**{n_excede} de {len(capacidad)} nodos** superarían las "
            f"{cap_h:.0f} horas disponibles por período en este escenario "
            "extremo (todo acoplado, sin postergar)."
        )
    else:
        mensaje = (
            f"\nNingún nodo supera las {cap_h:.0f} horas disponibles incluso en "
            "este escenario extremo (todo embotellado y etiquetado acoplado, "
            f"sin aprovechar la postergación); la holgura mínima observada es de "
            f"{holgura_min:.1f} horas (nodo con más demanda). Es decir, la "
            "capacidad no es la restricción activa en el caso base — la "
            "pregunta relevante del proyecto pasa más bien por el manejo de "
            "los estanques intermedios, los inventarios y el costo de "
            "backorder bajo incertidumbre, no por si la línea alcanza a "
            "producir."
        )
    lineas.append(mensaje)
    lineas.append("")

    lineas.append("## 5. Figuras generadas\n")
    for nombre in sorted(DIR_FIGURAS.glob("*.png")):
        lineas.append(f"- `resultados/figuras/{nombre.name}`")

    (BASE_DIR / "resultados" /
     "resumen_datos.md").write_text("\n".join(lineas), encoding="utf-8")

    print("Análisis completo.")
    print(f"Tablas  -> {DIR_TABLAS}")
    print(f"Figuras -> {DIR_FIGURAS}")
    print(f"Resumen -> {BASE_DIR / 'resultados' / 'resumen_datos.md'}")
    print("\n".join(mensajes_validacion))


if __name__ == "__main__":
    main()
