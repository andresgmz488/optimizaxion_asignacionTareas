"""
App Streamlit — Asignación óptima de tareas JFV S.A.S.
Partes 3 y 4 del proyecto.

Ejecutar localmente:  streamlit run app.py
"""
import math

import pandas as pd
import streamlit as st

from modelo_asignacion import (
    CONDICIONES_ENUNCIADO,
    DESCRIPCION_TAREAS,
    PROFESIONALES,
    TAREAS,
    resolver_asignacion,
    tiempos_enunciado,
    tiempos_por_defecto,
)

st.set_page_config(page_title="Asignación de tareas · JFV", page_icon="🧩", layout="wide")

st.title("🧩 Asignación óptima de tareas — JFV S.A.S.")
st.caption(
    "Modelo de programación lineal entera (PuLP + CBC) que minimiza la suma de horas "
    "de trabajo. Tiempos del enunciado con +1000 h por celda."
)


# ---------------------------------------------------------------------------
# Utilidades de presentación
# ---------------------------------------------------------------------------
def par(i, j):
    return f"{i} → {j}"


def desarmar(etiquetas):
    return [tuple(e.split(" → ")) for e in etiquetas]


def resaltar_binaria(df):
    return df.style.map(
        lambda v: "background-color:#2e7d32;color:white;font-weight:600" if v == 1 else "color:#9e9e9e"
    )


def diagnosticar(tiempos, prohibidas, obligatorias, modo, max_p=1, min_p=0):
    """Busca causas evidentes de infactibilidad para explicarlas al usuario."""
    I, J = list(tiempos.index), list(tiempos.columns)
    causas = []
    for i, j in set(prohibidas) & set(obligatorias):
        causas.append(f"**{i} → {j}** está marcada como obligatoria y prohibida/no disponible a la vez.")
    for j in J:
        n = sum(1 for (_, jj) in obligatorias if jj == j)
        if n > 1:
            causas.append(f"La tarea **{j}** tiene {n} profesionales obligatorios (debe tener exactamente 1).")
        if all((i, j) in set(prohibidas) for i in I):
            causas.append(f"Ningún profesional puede ejecutar la tarea **{j}**.")
    lim = 1 if modo == "balanceado" else max_p
    for i in I:
        n = sum(1 for (ii, _) in obligatorias if ii == i)
        if n > lim:
            causas.append(f"**{i}** tiene {n} tareas obligatorias y el máximo permitido es {lim}.")
        if modo == "balanceado" and all((i, j) in set(prohibidas) for j in J):
            causas.append(f"**{i}** no puede ejecutar ninguna tarea, pero debe recibir exactamente una.")
    if modo == "balanceado" and len(I) != len(J):
        causas.append("El modelo balanceado exige igual número de profesionales y tareas.")
    if modo != "balanceado":
        if len(I) * max_p < len(J):
            causas.append(
                f"Capacidad insuficiente: {len(I)} profesionales × {max_p} tareas máx. = "
                f"{len(I) * max_p} < {len(J)} tareas."
            )
        if len(I) * min_p > len(J):
            causas.append(
                f"Mínimo imposible: {len(I)} profesionales × {min_p} tareas mín. = "
                f"{len(I) * min_p} > {len(J)} tareas."
            )
    if not causas:
        causas.append("La combinación de restricciones prohibidas y obligatorias no deja ninguna asignación posible.")
    return causas


def mostrar_resultado(r, tiempos, prohibidas, obligatorias, modo, max_p=1, min_p=0):
    if not r["optimo"]:
        st.error(f"🚫 **Modelo infactible** — estado del solver: `{r['estado']}`")
        st.markdown("No existe ninguna asignación que cumpla todas las restricciones. Posibles causas:")
        for c in diagnosticar(tiempos, prohibidas, obligatorias, modo, max_p, min_p):
            st.markdown(f"- {c}")
        return

    pp = r["por_profesional"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tiempo total mínimo", f"{r['total']:,.0f} h")
    c2.metric("Estado del modelo", r["estado"])
    c3.metric("Tareas asignadas", int(r["binaria"].values.sum()))
    c4.metric("Mayor carga individual", f"{pp['Horas'].max():,.0f} h",
              help="Si las tareas se ejecutan en paralelo, esta es la duración calendario "
                   "(makespan). Minimizar la suma de horas no garantiza minimizar este valor.")

    if r["verificacion"]["Cumple"].all():
        st.success("✅ Solución óptima encontrada. Todas las restricciones se cumplen.")
    else:
        st.warning("Alguna restricción no se cumple; revisa la tabla de verificación.")

    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader("Asignación óptima")
        st.dataframe(r["asignacion"], hide_index=True, width="stretch",
                     column_config={"Horas": st.column_config.NumberColumn(format="%d")})
    with col_b:
        st.subheader("Tiempo por profesional")
        st.dataframe(pp.rename(columns={"N_tareas": "N.º tareas"}), hide_index=True,
                     width="stretch",
                     column_config={"Horas": st.column_config.NumberColumn(format="%d")})
    st.bar_chart(pp.set_index("Profesional")["Horas"], horizontal=True, height=260)

    col_c, col_d = st.columns([3, 2])
    with col_c:
        st.subheader("Matriz binaria de asignaciones  x₍ᵢⱼ₎")
        st.dataframe(resaltar_binaria(r["binaria"]), width="stretch")
    with col_d:
        st.subheader("Verificación de restricciones")
        st.dataframe(r["verificacion"], hide_index=True, width="stretch", height=320)


# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(
    ["⚖️ Asignación balanceada (6×6)", "📐 Asignación no balanceada", "📘 Modelo matemático"]
)

# ===========================================================================
# TAB 1 — Parte 3: modelo balanceado
# ===========================================================================
with tab1:
    for k in ("prohibidas", "no_disp", "oblig"):
        st.session_state.setdefault(k, [])

    def cargar_condiciones():
        st.session_state.prohibidas = [par(*p) for p in CONDICIONES_ENUNCIADO["prohibidas"]]
        st.session_state.no_disp = [par(*p) for p in CONDICIONES_ENUNCIADO["no_disponibles"]]
        st.session_state.oblig = [par(*p) for p in CONDICIONES_ENUNCIADO["obligatorias"]]

    def limpiar():
        st.session_state.prohibidas = []
        st.session_state.no_disp = []
        st.session_state.oblig = []

    def restaurar_tiempos():
        st.session_state.pop("editor_balanceado", None)

    st.subheader("1. Tiempos de ejecución (horas)")
    st.caption("Edita cualquier celda. Valores iniciales: enunciado + 1000 h.")
    tiempos = st.data_editor(
        tiempos_enunciado(),
        key="editor_balanceado",
        width="stretch",
        column_config={t: st.column_config.NumberColumn(t, min_value=0, step=1,
                                                        help=DESCRIPCION_TAREAS[t]) for t in TAREAS},
    )
    st.button("↺ Restaurar tiempos del enunciado", on_click=restaurar_tiempos)

    st.subheader("2. Restricciones")
    st.caption(
        "Por instrucción del docente, las condiciones adicionales se **ignoran** por defecto. "
        "Puedes cargarlas o definir otras."
    )
    b1, b2, _ = st.columns([1, 1, 3])
    b1.button("Cargar condiciones del enunciado", on_click=cargar_condiciones)
    b2.button("Limpiar restricciones", on_click=limpiar)

    opciones = [par(i, j) for i in PROFESIONALES for j in TAREAS]
    r1, r2, r3 = st.columns(3)
    with r1:
        sel_proh = st.multiselect("🚫 Combinaciones prohibidas (competencia)", opciones, key="prohibidas",
                                  help="x_ij = 0: el profesional no está habilitado para la tarea.")
    with r2:
        sel_nd = st.multiselect("📅 No disponibilidad", opciones, key="no_disp",
                                help="x_ij = 0: el profesional no estará disponible para la tarea.")
    with r3:
        sel_ob = st.multiselect("📌 Asignaciones obligatorias", opciones, key="oblig",
                                help="x_ij = 1: la tarea debe asignarse a ese profesional.")

    prohibidas = desarmar(sel_proh) + desarmar(sel_nd)
    obligatorias = desarmar(sel_ob)

    st.divider()
    if st.button("🚀 Optimizar asignación", type="primary", key="opt_bal"):
        if tiempos.isnull().values.any():
            st.error("Hay celdas vacías en la matriz de tiempos.")
        else:
            with st.spinner("Resolviendo con CBC…"):
                r = resolver_asignacion(tiempos.astype(float), prohibidas, obligatorias, modo="balanceado")
            mostrar_resultado(r, tiempos, prohibidas, obligatorias, "balanceado")

# ===========================================================================
# TAB 2 — Parte 4: modelo no balanceado
# ===========================================================================
with tab2:
    st.session_state.setdefault("n_prof", 7)
    st.session_state.setdefault("n_tar", 5)
    st.session_state.setdefault("max_p", 1)

    def escenario(p, t, m):
        st.session_state.n_prof, st.session_state.n_tar, st.session_state.max_p = p, t, m

    st.markdown(
        "Cambia el número de profesionales y tareas. Las celdas que no existen en el enunciado "
        "se generan con valores de referencia y **puedes editarlas**."
    )
    e1, e2, _ = st.columns([1, 1, 2])
    e1.button("Escenario A · 7 prof. × 5 tareas", on_click=escenario, args=(7, 5, 1), width="stretch")
    e2.button("Escenario B · 5 prof. × 7 tareas (máx. 2)", on_click=escenario, args=(5, 7, 2),
              width="stretch")

    c1, c2, c3, c4 = st.columns(4)
    n_prof = c1.number_input("Profesionales", 1, 15, key="n_prof")
    n_tar = c2.number_input("Tareas", 1, 15, key="n_tar")
    max_p = c3.number_input("Máx. tareas por profesional", 1, 15, key="max_p")
    exigir_min = c4.checkbox("Cada profesional recibe ≥ 1 tarea", value=False,
                             help="Útil cuando hay más tareas que profesionales y se quiere repartir.")
    min_p = 1 if exigir_min else 0

    if n_prof > n_tar:
        st.info(f"**Más profesionales que tareas:** {n_prof - n_tar} profesional(es) quedarán sin asignación. "
                "Restricción por profesional: Σⱼ xᵢⱼ ≤ " + str(max_p))
    elif n_tar > n_prof:
        st.info(f"**Más tareas que profesionales:** se requiere que al menos un profesional reciba varias "
                f"tareas. Capacidad: {n_prof} × {max_p} = {n_prof * max_p} vs. {n_tar} tareas "
                f"(mínimo necesario: {math.ceil(n_tar / n_prof)} por profesional).")
    else:
        st.info("Caso balanceado: con máximo 1 por profesional equivale al modelo 6×6.")

    base = tiempos_por_defecto(int(n_prof), int(n_tar))
    base.insert(0, "Profesional", base.index)
    editado = st.data_editor(
        base.reset_index(drop=True),
        key=f"editor_nb_{n_prof}_{n_tar}",
        hide_index=True,
        width="stretch",
        column_config={"Profesional": st.column_config.TextColumn(required=True)},
    )

    if st.button("🚀 Optimizar asignación", type="primary", key="opt_nb"):
        nombres = editado["Profesional"].astype(str).str.strip()
        if nombres.duplicated().any() or (nombres == "").any():
            st.error("Los nombres de los profesionales deben ser únicos y no vacíos.")
        elif editado.drop(columns="Profesional").isnull().values.any():
            st.error("Hay celdas vacías en la matriz de tiempos.")
        else:
            t_nb = editado.drop(columns="Profesional").astype(float)
            t_nb.index = nombres
            with st.spinner("Resolviendo con CBC…"):
                r = resolver_asignacion(t_nb, modo="no_balanceado",
                                        max_por_profesional=int(max_p), min_por_profesional=min_p)
            mostrar_resultado(r, t_nb, [], [], "no_balanceado", int(max_p), min_p)

    with st.expander("📊 Comparación de los escenarios A y B (datos por defecto)"):
        rA = resolver_asignacion(tiempos_por_defecto(7, 5), modo="no_balanceado", max_por_profesional=1)
        rB = resolver_asignacion(tiempos_por_defecto(5, 7), modo="no_balanceado", max_por_profesional=2)
        rBal = resolver_asignacion(tiempos_enunciado())

        def fila(nombre, r, P, T):
            pp = r["por_profesional"]
            return {
                "Escenario": nombre,
                "Profesionales × Tareas": f"{P} × {T}",
                "Suma mínima (h)": int(r["total"]),
                "Promedio por tarea (h)": round(r["total"] / T, 1),
                "Sin asignación": ", ".join(pp.loc[pp.N_tareas == 0, "Profesional"]) or "—",
                "Con 2 tareas": ", ".join(pp.loc[pp.N_tareas == 2, "Profesional"]) or "—",
                "Mayor carga (h)": int(pp["Horas"].max()),
            }

        st.dataframe(pd.DataFrame([
            fila("Base balanceado", rBal, 6, 6),
            fila("A · más profesionales", rA, 7, 5),
            fila("B · más tareas", rB, 5, 7),
        ]), hide_index=True, width="stretch")
        st.markdown(
            "- **A:** sobran profesionales, así que la restricción por profesional pasa de `= 1` a `≤ 1`; "
            "el modelo elige a los 5 más eficientes y deja a 2 sin tarea.\n"
            "- **B:** faltan profesionales, así que la restricción pasa a `≤ 2`; algunos asumen dos tareas. "
            "Al haber más tareas, la suma total crece y la mayor carga individual se duplica.\n"
            "- El +1000 h suma una constante por **tarea asignada**; como el número de tareas asignadas es fijo "
            "en cada escenario, no cambia la asignación óptima, solo desplaza el total (+5000 en A, +7000 en B)."
        )

# ===========================================================================
# TAB 3 — Modelo matemático (referencia)
# ===========================================================================
with tab3:
    st.markdown("### Conjuntos")
    st.latex(r"I=\{\text{Ana, Carlos, Laura, Miguel, Sofía, Andrés}\},\quad J=\{T1,\dots,T6\}")
    st.markdown("### Parámetros")
    st.latex(r"c_{ij} = \text{horas que tarda el profesional } i \text{ en la tarea } j \;(+1000)")
    st.latex(r"P \subseteq I\times J \text{ (prohibidas / no disponibles)},\quad O \subseteq I\times J \text{ (obligatorias)}")
    st.markdown("### Variables de decisión")
    st.latex(r"x_{ij}=\begin{cases}1 & \text{si } i \text{ ejecuta } j\\ 0 & \text{en otro caso}\end{cases}")
    st.markdown("### Función objetivo")
    st.latex(r"\min Z=\sum_{i\in I}\sum_{j\in J} c_{ij}\,x_{ij}")
    st.markdown("### Restricciones")
    st.latex(r"\sum_{i\in I} x_{ij}=1 \quad \forall j\in J \qquad\text{(cada tarea, un profesional)}")
    st.latex(r"\sum_{j\in J} x_{ij}=1 \quad \forall i\in I \qquad\text{(cada profesional, una tarea)}")
    st.latex(r"x_{ij}=0 \;\; \forall (i,j)\in P, \qquad x_{ij}=1 \;\; \forall (i,j)\in O")
    st.latex(r"x_{ij}\in\{0,1\}")
    st.markdown("### Parte 4 — cambios")
    st.latex(r"\text{A } (|I|>|J|):\; \sum_{j} x_{ij}\le 1 \;\forall i \qquad"
             r"\text{B } (|I|<|J|):\; \sum_{j} x_{ij}\le 2 \;\forall i")
    st.caption("La tarea siempre conserva Σᵢ xᵢⱼ = 1: todas las tareas se atienden.")
