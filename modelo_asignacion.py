"""
Modelo de asignación de tareas — JFV S.A.S.
Parte 2: implementación con Python + PuLP.

Ejecutar:  python modelo_asignacion.py
"""
from __future__ import annotations

import pandas as pd
import pulp

# ---------------------------------------------------------------------------
# Datos del enunciado (tiempos base + 1000, según la instrucción del docente)
# ---------------------------------------------------------------------------
PROFESIONALES = ["Ana", "Carlos", "Laura", "Miguel", "Sofía", "Andrés"]
TAREAS = ["T1", "T2", "T3", "T4", "T5", "T6"]

TIEMPOS_BASE = [
    [12, 18, 15, 20, 14, 16],  # Ana
    [16, 11, 19, 14, 17, 13],  # Carlos
    [14, 16, 10, 18, 15, 17],  # Laura
    [18, 13, 16, 11, 19, 15],  # Miguel
    [15, 17, 14, 16, 9, 18],   # Sofía
    [17, 14, 18, 15, 16, 10],  # Andrés
]
INCREMENTO = 1000

DESCRIPCION_TAREAS = {
    "T1": "Diseño de un sistema de control de inventarios",
    "T2": "Desarrollo de un tablero de indicadores",
    "T3": "Automatización de reportes de producción",
    "T4": "Optimización de un proceso logístico",
    "T5": "Diseño de un sistema de mantenimiento",
    "T6": "Implementación de un sistema de seguimiento de proyectos",
}

# Condiciones adicionales del enunciado (el docente indicó IGNORARLAS;
# se dejan aquí para poder activarlas desde la app si se desea).
CONDICIONES_ENUNCIADO = {
    "prohibidas": [("Ana", "T4")],        # competencia (certificación)
    "no_disponibles": [("Carlos", "T3")],  # disponibilidad
    "obligatorias": [("Sofía", "T5")],     # asignación obligatoria
}


def tiempos_enunciado() -> pd.DataFrame:
    """Matriz de tiempos del enunciado con +1000 h en cada celda."""
    df = pd.DataFrame(TIEMPOS_BASE, index=PROFESIONALES, columns=TAREAS)
    return df + INCREMENTO


# ---------------------------------------------------------------------------
# Modelo general (sirve para el caso balanceado y los no balanceados)
# ---------------------------------------------------------------------------
def resolver_asignacion(
    tiempos: pd.DataFrame,
    prohibidas=(),
    obligatorias=(),
    modo: str = "balanceado",
    max_por_profesional: int = 1,
    min_por_profesional: int = 0,
) -> dict:
    """
    Resuelve el problema de asignación de mínima suma de horas.

    modo = "balanceado":   cada tarea = 1 profesional, cada profesional = 1 tarea.
    modo = "no_balanceado": cada tarea = 1 profesional,
                            min_por_profesional <= tareas de cada profesional <= max_por_profesional.

    prohibidas:  pares (profesional, tarea) con x_ij = 0 (competencia o disponibilidad).
    obligatorias: pares (profesional, tarea) con x_ij = 1.
    """
    I = list(tiempos.index)
    J = list(tiempos.columns)
    c = {(i, j): float(tiempos.loc[i, j]) for i in I for j in J}

    modelo = pulp.LpProblem("Asignacion_JFV", pulp.LpMinimize)
    # x[i][j] = 1 si el profesional i ejecuta la tarea j
    x = {i: {j: pulp.LpVariable(f"x_{a}_{b}", cat="Binary") for b, j in enumerate(J)}
         for a, i in enumerate(I)}

    # Función objetivo: minimizar la suma de horas
    modelo += pulp.lpSum(c[i, j] * x[i][j] for i in I for j in J), "Horas_totales"

    # Cada tarea es asignada exactamente a un profesional
    for j in J:
        modelo += pulp.lpSum(x[i][j] for i in I) == 1, f"Tarea_{J.index(j)}"

    # Tareas por profesional
    for i in I:
        carga = pulp.lpSum(x[i][j] for j in J)
        if modo == "balanceado":
            modelo += carga == 1, f"Prof_{I.index(i)}"
        else:
            modelo += carga <= max_por_profesional, f"ProfMax_{I.index(i)}"
            if min_por_profesional > 0:
                modelo += carga >= min_por_profesional, f"ProfMin_{I.index(i)}"

    # Combinaciones prohibidas / no disponibles
    for k, (i, j) in enumerate(prohibidas):
        if i in I and j in J:
            modelo += x[i][j] == 0, f"Prohibida_{k}"

    # Asignaciones obligatorias
    for k, (i, j) in enumerate(obligatorias):
        if i in I and j in J:
            modelo += x[i][j] == 1, f"Obligatoria_{k}"

    modelo.solve(pulp.PULP_CBC_CMD(msg=False))
    estado = pulp.LpStatus[modelo.status]
    optimo = estado == "Optimal"

    resultado = {"estado": estado, "optimo": optimo, "modelo": modelo}
    if not optimo:
        return resultado

    binaria = pd.DataFrame(
        [[int(round(x[i][j].value() or 0)) for j in J] for i in I], index=I, columns=J
    )
    filas = [
        {"Profesional": i, "Tarea": j, "Descripción": DESCRIPCION_TAREAS.get(j, ""),
         "Horas": c[i, j]}
        for i in I for j in J if binaria.loc[i, j] == 1
    ]
    asignacion = pd.DataFrame(filas)
    por_prof = (
        pd.DataFrame({"Profesional": I})
        .merge(asignacion.groupby("Profesional", as_index=False)
               .agg(Tareas=("Tarea", lambda s: ", ".join(s)), Horas=("Horas", "sum"),
                    N_tareas=("Tarea", "count")),
               on="Profesional", how="left")
        .fillna({"Tareas": "— sin asignación —", "Horas": 0, "N_tareas": 0})
    )
    por_prof["N_tareas"] = por_prof["N_tareas"].astype(int)

    # Verificación de restricciones
    ver = []
    for j in J:
        s = int(binaria[j].sum())
        ver.append(("Cada tarea con exactamente 1 profesional", j, s, s == 1))
    for i in I:
        s = int(binaria.loc[i].sum())
        if modo == "balanceado":
            ok, regla = s == 1, "Cada profesional con exactamente 1 tarea"
        else:
            ok = min_por_profesional <= s <= max_por_profesional
            regla = f"Profesional con {min_por_profesional}–{max_por_profesional} tareas"
        ver.append((regla, i, s, ok))
    for i, j in prohibidas:
        if i in I and j in J:
            ver.append(("Prohibida / no disponible (x=0)", f"{i}–{j}",
                        int(binaria.loc[i, j]), binaria.loc[i, j] == 0))
    for i, j in obligatorias:
        if i in I and j in J:
            ver.append(("Obligatoria (x=1)", f"{i}–{j}",
                        int(binaria.loc[i, j]), binaria.loc[i, j] == 1))
    verificacion = pd.DataFrame(ver, columns=["Restricción", "Elemento", "Valor", "Cumple"])

    resultado.update(
        total=float(pulp.value(modelo.objective)),
        asignacion=asignacion,
        por_profesional=por_prof,
        binaria=binaria,
        verificacion=verificacion,
    )
    return resultado


# ---------------------------------------------------------------------------
# Datos por defecto para la Parte 4 (escenarios no balanceados)
# Las celdas que no existen en el enunciado se generan con una regla
# determinística y se pueden editar en la app.
# ---------------------------------------------------------------------------
NOMBRES_EXTRA = ["Valentina", "Jorge", "Paula", "Diego", "Camila", "Felipe",
                 "Natalia", "Sergio", "Daniela", "Julián"]


def tiempos_por_defecto(n_prof: int, n_tareas: int) -> pd.DataFrame:
    nombres = (PROFESIONALES + NOMBRES_EXTRA)[:n_prof]
    if n_prof > len(PROFESIONALES + NOMBRES_EXTRA):
        nombres += [f"P{k+1}" for k in range(len(nombres), n_prof)]
    tareas = [f"T{j+1}" for j in range(n_tareas)]
    datos = []
    for i in range(n_prof):
        fila = []
        for j in range(n_tareas):
            if i < 6 and j < 6:
                fila.append(TIEMPOS_BASE[i][j] + INCREMENTO)
            else:
                fila.append(INCREMENTO + 9 + (3 * i + 7 * j) % 12)
        datos.append(fila)
    return pd.DataFrame(datos, index=nombres, columns=tareas)


def _imprimir(titulo, r):
    print("\n" + "=" * 70 + f"\n{titulo}\n" + "=" * 70)
    print("Estado:", r["estado"])
    if not r["optimo"]:
        print("⚠ Modelo infactible o sin solución óptima.")
        return
    print(r["asignacion"].to_string(index=False))
    print("\nTiempo por profesional:")
    print(r["por_profesional"].to_string(index=False))
    print("\nMatriz binaria x_ij:")
    print(r["binaria"].to_string())
    print(f"\nSuma mínima de horas: {r['total']:,.0f}")
    print("Todas las restricciones se cumplen:", bool(r["verificacion"]["Cumple"].all()))


if __name__ == "__main__":
    c = tiempos_enunciado()
    print("Matriz de tiempos (+1000):\n", c.to_string())

    # Parte 2 — modelo base (condiciones adicionales ignoradas, según instrucción)
    r = resolver_asignacion(c)
    _imprimir("PARTE 2 — Asignación balanceada 6×6", r)
    print("\nVerificación:\n", r["verificacion"].to_string(index=False))

    # Referencia: con las condiciones adicionales activadas
    r2 = resolver_asignacion(
        c,
        prohibidas=CONDICIONES_ENUNCIADO["prohibidas"] + CONDICIONES_ENUNCIADO["no_disponibles"],
        obligatorias=CONDICIONES_ENUNCIADO["obligatorias"],
    )
    _imprimir("Referencia — con condiciones adicionales activadas", r2)

    # Parte 4 — Escenario A: 7 profesionales, 5 tareas
    rA = resolver_asignacion(tiempos_por_defecto(7, 5), modo="no_balanceado",
                             max_por_profesional=1)
    _imprimir("PARTE 4 — Escenario A (7 profesionales × 5 tareas)", rA)

    # Parte 4 — Escenario B: 5 profesionales, 7 tareas, máx. 2 por profesional
    rB = resolver_asignacion(tiempos_por_defecto(5, 7), modo="no_balanceado",
                             max_por_profesional=2)
    _imprimir("PARTE 4 — Escenario B (5 profesionales × 7 tareas, máx. 2)", rB)
