from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

CARPETA_ANALISIS = Path(__file__).resolve().parent.parent / "Análisis de Datos"
sys.path.insert(0, str(CARPETA_ANALISIS))
from cargar_datos import cargar_todo  # noqa: E402

N_AUX = 0  # nodo auxiliar


@dataclass
class Instancia:
    # Conjuntos
    I: list[int]  # vinos
    J: list[int]  # etiquetas
    N: list[int]  # nodos del árbol
    N_etapa: dict[int, list[int]]  # N_s, nodos de cada etapa, s = 1, 2, 3
    a: dict[int, int]  # antecesor inmediato

    # Parámetros
    D: dict[tuple[int, int, int], float]  # D_ijn (demanda botellas)
    p: dict[int, float]  # p_n
    # A_ij compatibilidad vino-etiqueta (1 si j surve para i)
    A: dict[tuple[int, int], int]
    V_bottle: float  # litros/botella
    V_tank: float  # litros/estanque
    K_tank: int  # estanques por nodo
    U: float  # subutilización máxima (fracción)
    T_wb: float  # horas/botella, embotellar
    T_wbl: float  # horas/botella, acoplado
    T_wl: float  # horas/botella, etiquetar
    T_zb: float  # horas/set-up embotellado
    T_zbl: float  # horas/set-up acoplado
    T_zl: float  # horas/set-up etiquetado
    C_zb: float  # $/set-up embotellado
    C_zbl: float  # $/set-up acoplado
    C_zl: float  # $/set-up etiquetado
    C_sb: float  # $/botella*período sin et.
    C_sbl: float  # $/botella*período terminada
    C_bbl: float  # $/botella*período atrasada

    # Condiciones iniciales (nodo auxiliar) diccionarios vacíos
    W_b0: dict[int, float] = field(default_factory=dict)
    W_bl0: dict[tuple[int, int], float] = field(default_factory=dict)
    S_b0: dict[int, float] = field(default_factory=dict)
    S_bl0: dict[tuple[int, int], float] = field(default_factory=dict)
    B_bl0: dict[tuple[int, int], float] = field(default_factory=dict)

    @property  # para inst.N_plus : N+ = N ∪ {n_aux}
    def N_plus(self) -> list[int]:
        return [N_AUX] + self.N

    @property  # creamos solamente para los pares compatibles
    def P(self) -> list[tuple[int, int]]:
        """Pares (i,j) con A_ij = 1: dominio de las variables indexadas en (i,j)."""
        return [(i, j) for i in self.I for j in self.J if self.A[i, j] == 1]


# buscar cada parámetro por su NOMBRE en el Excel
def _valor(df: pd.DataFrame, texto: str, col: str = "valor") -> float:
    clave = "concepto" if "concepto" in df.columns else "parametro"
    fila = df[df[clave].str.contains(texto, case=False, regex=False)]
    if len(fila) != 1:
        raise ValueError(
            f"No se encontró un único '{texto}' en {list(df[clave])}")
    return float(fila[col].iloc[0])

# leemos excel y creamos instancias


def cargar_instancia() -> Instancia:
    datos = cargar_todo()
    conf = datos["configuracion"]
    setups = datos["setups"]
    tiempos = datos["tiempos_unitarios"]
    costos = datos["costos_inventario"]
    arbol = datos["arbol"]
    tidy = datos["demanda_tidy"]
    inv0 = datos["inventario_inicial"]

    # conjuntos
    I = sorted(tidy["vino"].unique().tolist())
    J = sorted(tidy["etiqueta"].unique().tolist())
    N = arbol["nodo"].tolist()
    # N_s agrupa nodos por etapas
    N_etapa = {int(s): g["nodo"].tolist() for s, g in arbol.groupby("periodo")}
    # a(n) cuidando definir bien el antecesor
    a = {
        int(r.nodo): (N_AUX if str(r.nodo_antecesor).strip() == "-" else int(r.nodo_antecesor))
        for r in arbol.itertuples()
    }
    # prob incondicional
    p = dict(zip(arbol["nodo"], arbol["prob_nodo"]))

    # A_ij = 1 si el producto (i,j) aparece en la demanda
    pares = set(zip(tidy["vino"], tidy["etiqueta"]))
    A = {(i, j): int((i, j) in pares) for i in I for j in J}
    # D_ijn: diccionario {(vino, etiqueta, nodo): botellas}
    D = {(int(r.vino), int(r.etiqueta), int(r.nodo)): float(r.demanda)
         for r in tidy.itertuples()}

    # Inventarios iniciales (en la instancia base todos son 0 y se entregan agregados)
    s_b0 = _valor(inv0, "sin etiquetar")
    s_bl0 = _valor(inv0, "terminados")
    b_bl0 = _valor(inv0, "atrasados")
    P = [(i, j) for i in I for j in J if A[i, j] == 1]

    return Instancia(
        I=I, J=J, N=N, N_etapa=N_etapa, a=a, D=D, p=p, A=A,
        # congif
        V_bottle=_valor(conf, "botella"),
        V_tank=_valor(conf, "Capacidad de cada estanque"),
        K_tank=int(_valor(conf, "Estanques intermedios")),
        U=_valor(conf, "Subutilización"),
        # tiempos
        T_wb=_valor(tiempos, "solo embotellar"),
        T_wbl=_valor(tiempos, "acoplados"),
        T_wl=_valor(tiempos, "solo etiquetar"),
        # set ups
        T_zb=_valor(setups, "Set-up de embotellado", "tiempo_h"),
        T_zbl=_valor(setups, "Set-up conjunto", "tiempo_h"),
        T_zl=_valor(setups, "Set-up de etiquetado", "tiempo_h"),
        # costos
        C_zb=_valor(setups, "Set-up de embotellado", "costo_pesos"),
        C_zbl=_valor(setups, "Set-up conjunto", "costo_pesos"),
        C_zl=_valor(setups, "Set-up de etiquetado", "costo_pesos"),
        C_sb=_valor(costos, "sin etiquetar"),
        C_sbl=_valor(costos, "producto terminado"),
        C_bbl=_valor(costos, "backorder"),
        # cond. iniciales
        W_b0={i: 0.0 for i in I},
        W_bl0={ij: 0.0 for ij in P},
        S_b0={i: s_b0 for i in I},
        S_bl0={ij: s_bl0 for ij in P},
        B_bl0={ij: b_bl0 for ij in P},
    )


def cotas_M(inst: Instancia, C: float) -> tuple[float, float, float]:
    # big M ajustado
    M_b = max((C - inst.T_zb) / inst.T_wb, 0.0)
    M_bl = max((C - inst.T_zbl) / inst.T_wbl, 0.0)
    M_l = max((C - inst.T_zl) / inst.T_wl, 0.0)
    return M_b, M_bl, M_l


# variables, f.o., restricciones
def construir_modelo(inst: Instancia, C: float, PL: int, verbose: bool = False):
    I, N, N_plus, P, A, a = inst.I, inst.N, inst.N_plus, inst.P, inst.A, inst.a
    M_b, M_bl, M_l = cotas_M(inst, C)

    m = gp.Model(f"postergacion_C{C}_PL{PL}")
    # silenciamos gurobi en ek barrido
    m.Params.OutputFlag = int(verbose)

    # variables, continuas por defecto, todas positivas
    w_b = m.addVars(I, N_plus, lb=0.0, name="w_b")
    w_bl = m.addVars(P, N_plus, lb=0.0, name="w_bl")
    w_l = m.addVars(P, N, lb=0.0, name="w_l")
    z_b = m.addVars(I, N, vtype=GRB.BINARY, name="z_b")
    z_bl = m.addVars(P, N, vtype=GRB.BINARY, name="z_bl")
    z_l = m.addVars(P, N, vtype=GRB.BINARY, name="z_l")
    z_pos = m.addVars(P, vtype=GRB.BINARY, name="z_pos")
    s_b = m.addVars(I, N_plus, lb=0.0, name="s_b")
    s_bl = m.addVars(P, N_plus, lb=0.0, name="s_bl")
    b_bl = m.addVars(P, N_plus, lb=0.0, name="b_bl")
    y = m.addVars(I, N, lb=0, vtype=GRB.INTEGER, name="y")
    u = m.addVars(I, N, lb=0.0, name="u")

    # función objetivo
    # costos separados
    C_setup = {
        n: inst.C_zb * gp.quicksum(z_b[i, n] for i in I)
        + inst.C_zbl * gp.quicksum(A[i, j] * z_bl[i, j, n] for i, j in P)
        + inst.C_zl * gp.quicksum(A[i, j] * z_l[i, j, n] for i, j in P)
        for n in N
    }
    C_WIP = {n: inst.C_sb * gp.quicksum(s_b[i, n] for i in I) for n in N}
    C_FG = {n: inst.C_sbl * gp.quicksum(A[i, j] * s_bl[i, j, n]
                                        # (eq:costo-fg)
                                        for i, j in P) for n in N}
    C_BO = {n: inst.C_bbl * gp.quicksum(A[i, j] * b_bl[i, j, n]
                                        # (eq:costo-bo)
                                        for i, j in P) for n in N}
    # función
    m.setObjective(
        gp.quicksum(inst.p[n] * (C_setup[n] + C_WIP[n] +
                    C_FG[n] + C_BO[n]) for n in N),
        GRB.MINIMIZE,
    )

    # restricciones
    # sin etiquetar
    m.addConstrs(
        (
            s_b[i, n]
            == s_b[i, a[n]] + w_b[i, a[n]]
            - gp.quicksum(A[ii, j] * w_l[ii, j, n] for ii, j in P if ii == i)
            for i in I for n in N
        ),
        name="balance_wip",
    )
    # prod. terminado
    m.addConstrs(
        (
            s_bl[i, j, n] - b_bl[i, j, n]
            == s_bl[i, j, a[n]] - b_bl[i, j, a[n]] + w_bl[i, j, a[n]] + w_l[i, j, n]
            - inst.D[i, j, n]
            for i, j in P for n in N
        ),
        name="balance_fg",
    )
    # no se puede etiquetar más de las botellas sin etiquetar que hay
    m.addConstrs(
        (
            gp.quicksum(A[ii, j] * w_l[ii, j, n] for ii, j in P if ii == i)
            <= s_b[i, a[n]] + w_b[i, a[n]]
            for i in I for n in N
        ),
        name="disponibilidad_wip",
    )

    # postergación
    # set up de prod. si prod. está habilitado
    m.addConstrs(
        (z_l[i, j, n] <= A[i, j] * z_pos[i, j] for i, j in P for n in N),
        name="pos_activacion",
    )
    m.addConstr(
        gp.quicksum(A[i, j] * z_pos[i, j] for i, j in P) <= PL, name="pos_limite"
    )

    # activación, big Ms
    m.addConstrs((w_b[i, n] <= M_b * z_b[i, n]
                 for i in I for n in N), name="setup_b")
    m.addConstrs(
        (w_bl[i, j, n] <= A[i, j] * M_bl * z_bl[i, j, n]
         for i, j in P for n in N),
        name="setup_bl",
    )
    m.addConstrs(
        (w_l[i, j, n] <= A[i, j] * M_l * z_l[i, j, n]
         for i, j in P for n in N),
        name="setup_l",
    )

    # tanques
    m.addConstrs(
        (gp.quicksum(y[i, n] for i in I) <= inst.K_tank for n in N), name="tanques_cota"
    )
    m.addConstrs((u[i, n] <= inst.U for i in I for n in N),
                 name="tanques_subutil")
    m.addConstrs(
        (
            inst.V_tank * (y[i, n] - u[i, n])
            == inst.V_bottle
            * (w_b[i, n] + gp.quicksum(A[ii, j] * w_bl[ii, j, n] for ii, j in P if ii == i))
            for i in I for n in N
        ),
        name="tanques_balance",
    )

    # capacidad de línea env.
    # horas de proceso + horas de set-up <= C
    m.addConstrs(
        (
            inst.T_wb * gp.quicksum(w_b[i, n] for i in I)
            + inst.T_wbl * gp.quicksum(A[i, j] * w_bl[i, j, n] for i, j in P)
            + inst.T_wl * gp.quicksum(A[i, j] * w_l[i, j, n] for i, j in P)
            + inst.T_zb * gp.quicksum(z_b[i, n] for i in I)
            + inst.T_zbl * gp.quicksum(A[i, j] * z_bl[i, j, n] for i, j in P)
            + inst.T_zl * gp.quicksum(A[i, j] * z_l[i, j, n] for i, j in P)
            <= C
            for n in N
        ),
        name="capacidad_linea",
    )

    # condiciones iniciales en el nodo auxiliar
    m.addConstrs((s_b[i, N_AUX] == inst.S_b0[i] for i in I), name="ini_s_b")
    m.addConstrs((s_bl[i, j, N_AUX] == inst.S_bl0[i, j]
                 for i, j in P), name="ini_s_bl")
    m.addConstrs((b_bl[i, j, N_AUX] == inst.B_bl0[i, j]
                 for i, j in P), name="ini_b_bl")
    m.addConstrs((w_b[i, N_AUX] == inst.W_b0[i] for i in I), name="ini_w_b")
    m.addConstrs((w_bl[i, j, N_AUX] == inst.W_bl0[i, j]
                 for i, j in P), name="ini_w_bl")

    # nat. de variables y empaquetado
    variables = dict(
        w_b=w_b, w_bl=w_bl, w_l=w_l, z_b=z_b, z_bl=z_bl, z_l=z_l, z_pos=z_pos,
        s_b=s_b, s_bl=s_bl, b_bl=b_bl, y=y, u=u,
    )
    costos = dict(setup=C_setup, WIP=C_WIP, FG=C_FG, BO=C_BO)
    return m, variables, costos


# resolucio´n

# resuelve para C, PL  y calcula kpi1 y kpi2
def resolver(inst: Instancia, C: float, PL: int, verbose: bool = False, time_limit: float | None = None):
    m, v, costos = construir_modelo(inst, C, PL, verbose)
    # lim de tiempo
    if time_limit is not None:
        m.Params.TimeLimit = time_limit
    m.optimize()

    # si es infactible
    if m.SolCount == 0:
        raise RuntimeError(
            f"Sin solución (status {m.Status}) para C={C}, PL={PL}")

    N, P = inst.N, inst.P

    # costo esperado
    esperado = {k: sum(inst.p[n] * expr[n].getValue()
                       for n in N) for k, expr in costos.items()}

    # kpi2 : nivel de servicio
    # se asume fifo
    dem_total = sum(inst.p[n] * inst.D[i, j, n] for i, j in P for n in N)
    dem_atrasada = sum(
        inst.p[n] * min(inst.D[i, j, n], v["b_bl"][i, j, n].X) for i, j in P for n in N
    )
    ns = 100.0 * (dem_total - dem_atrasada) / dem_total

    resumen = {
        "C": C,
        "PL": PL,
        "status": m.Status,
        "CTE": m.ObjVal,  # kpi 1
        "gap": m.MIPGap,
        "C_setup": esperado["setup"],
        "C_WIP": esperado["WIP"],
        "C_FG": esperado["FG"],
        "C_BO": esperado["BO"],
        "NS_%": ns,  # kpi 2
        # comparamos con 0.5 por si la binaria vale 0.999...
        "productos_postergados": [ij for ij in P if v["z_pos"][ij].X > 0.5],
        "tiempo_s": m.Runtime,
    }
    return m, v, resumen


# tabla solución
def plan_por_nodo(inst: Instancia, v: dict) -> pd.DataFrame:
    filas = []
    for n in inst.N:
        for i, j in inst.P:
            filas.append({
                "nodo": n, "a(n)": inst.a[n], "vino": i, "etiqueta": j,
                "D": inst.D[i, j, n],
                "w_bl": v["w_bl"][i, j, n].X,
                "w_l": v["w_l"][i, j, n].X,
                "s_bl": v["s_bl"][i, j, n].X,
                "b_bl": v["b_bl"][i, j, n].X,
            })
    df = pd.DataFrame(filas)
    por_vino = pd.DataFrame([
        {"nodo": n, "vino": i, "w_b": v["w_b"][i, n].X, "s_b": v["s_b"][i, n].X,
         "y": v["y"][i, n].X, "u": v["u"][i, n].X}
        for n in inst.N for i in inst.I
    ])
    return df.merge(por_vino, on=["nodo", "vino"]).round(2)

# ejecución


def main():
    # argumentos opcionales
    # si no se entregan, corre caso base (MTS), postergación total y el barrido completo
    parser = argparse.ArgumentParser()
    parser.add_argument("--C", type=float, help="horas de línea por nodo")
    parser.add_argument(
        "--PL", type=int, help="máx. productos con postergación")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    inst = cargar_instancia()
    # guardado
    salida = Path(__file__).resolve().parent / "resultados"
    salida.mkdir(exist_ok=True)
    pd.set_option("display.width", 200)

    # op 1: una sola configuración (lo no especificado toma el valor del caso base)
    if args.C is not None or args.PL is not None:
        C = args.C if args.C is not None else 84
        PL = args.PL if args.PL is not None else 0
        _, v, res = resolver(inst, C, PL, args.verbose)
        print(pd.Series(res).to_string())
        print(plan_por_nodo(inst, v).to_string(index=False))
        return

    # op 2: caso base (MTS) + postergación total + barrido
    # caso base = sin postergación (PL=0): todo se embotella y etiqueta acoplado
    # en a(n), antes de conocer la demanda de n -> full MTS.
    extremos = [
        ("Caso base MTS (C=84, PL=0)", 0, "plan_caso_base_MTS.csv"),
        (f"Postergación total (C=84, PL={len(inst.P)})", len(
            inst.P), "plan_postergacion_total.csv"),
    ]
    for titulo, PL, archivo in extremos:
        _, v, res = resolver(inst, 84, PL, args.verbose)
        print(f"=== {titulo} ===")
        print(pd.Series(res).to_string())
        plan = plan_por_nodo(inst, v)
        plan.to_csv(salida / archivo, index=False)
        print(plan.to_string(index=False))
        print()

    # Barrido de configuraciones (niveles de referencia de hoja Niveles del excel)
    filas = []
    for C in [21, 42, 63, 84]:
        for PL in [0, 2, 3, 4, 5]:
            _, _, r = resolver(inst, C, PL)
            filas.append(r)
    df = pd.DataFrame(filas)
    # kpi 3: V^POST(PL; C) = CTE*(0; C) - CTE*(PL; C), con PL=0 (MTS) como referencia
    df["V_POST"] = df.groupby("C")["CTE"].transform("first") - df["CTE"]
    df.to_csv(salida / "barrido_C_PL.csv", index=False)
    print("\n=== Barrido C x PL ===")
    print(df.drop(columns=["status", "gap"]).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
