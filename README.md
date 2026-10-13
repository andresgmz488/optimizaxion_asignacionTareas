# Asignación óptima de tareas — JFV S.A.S.

Proyecto de clase · Optimización · Modelo de asignación con Python, PuLP y Streamlit.

| Archivo | Contenido |
|---|---|
| `modelo_asignacion.py` | Parte 2: modelo en PuLP. `python modelo_asignacion.py` imprime la solución, la verificación y los escenarios A y B. |
| `app.py` | Partes 3 y 4: aplicación interactiva en Streamlit. |
| `requirements.txt` | Dependencias para Streamlit Community Cloud. |

> Se usa **PuLP 2.x** (`pulp>=2.8,<3`). PuLP 4.0 cambió por completo su API (`LpVariable(..., cat="Binary")` ya no existe), por eso se fija la versión.

---

## Resultado (Parte 2)

Tiempos del enunciado **+1000 h** en cada celda. Condiciones adicionales **ignoradas** por instrucción del docente.

| Profesional | Tarea | Horas |
|---|---|---|
| Ana | T1 – Control de inventarios | 1012 |
| Carlos | T2 – Tablero de indicadores | 1011 |
| Laura | T3 – Automatización de reportes | 1010 |
| Miguel | T4 – Optimización logística | 1011 |
| Sofía | T5 – Sistema de mantenimiento | 1009 |
| Andrés | T6 – Seguimiento de proyectos | 1010 |
| **Total** | | **6063** |

- Estado: **Optimal**. Todas las restricciones verificadas.
- Sin el +1000 el total sería 63 h: sumar una constante a toda la matriz suma 6 × 1000 al total y **no cambia la asignación**, porque toda asignación factible usa exactamente 6 celdas.
- Cada profesional recibe su tiempo mínimo de fila y esas tareas son todas distintas, así que el óptimo es inmediato.
- Si se activan las condiciones adicionales (Ana ≠ T4, Carlos ≠ T3, Sofía = T5), la solución no cambia: ya las cumplía.

---

## Formulación matemática (guía para la Parte 1, a mano)

**Conjuntos**
- I = {Ana, Carlos, Laura, Miguel, Sofía, Andrés} — profesionales, índice i
- J = {T1, …, T6} — tareas, índice j

**Parámetros**
- c_ij = horas estimadas (+1000) del profesional i en la tarea j
- P = pares (i, j) prohibidos (competencia) o no disponibles
- O = pares (i, j) de asignación obligatoria

**Variables de decisión**
- x_ij = 1 si el profesional i ejecuta la tarea j; 0 si no

**Función objetivo**
- min Z = Σ_i Σ_j c_ij · x_ij

**Restricciones**
1. Cada tarea, exactamente un profesional: Σ_i x_ij = 1, ∀ j ∈ J
2. Cada profesional, exactamente una tarea: Σ_j x_ij = 1, ∀ i ∈ I
3. Competencia: x_Ana,T4 = 0 (en general x_ij = 0, ∀ (i,j) ∈ P)
4. Disponibilidad: x_Carlos,T3 = 0
5. Obligatoria: x_Sofía,T5 = 1 (en general x_ij = 1, ∀ (i,j) ∈ O)
6. Dominio: x_ij ∈ {0, 1}, ∀ i, j

Interpretación: x_ij = 1 indica que el profesional i queda a cargo de la tarea j; la matriz de x tiene exactamente un 1 por fila y uno por columna (matriz de permutación). Las restricciones 3–5 solo aplican si se activan las condiciones adicionales.

---

## Parte 4 — Asignación no balanceada

**Escenario A (7 profesionales, 5 tareas).** La tarea conserva Σ_i x_ij = 1, pero la del profesional pasa a **Σ_j x_ij ≤ 1**: con igualdad sería infactible (7 profesionales no pueden recibir cada uno una de solo 5 tareas). Equivale a agregar 2 tareas ficticias de costo 0.

**Escenario B (5 profesionales, 7 tareas).** La tarea conserva Σ_i x_ij = 1 y la del profesional pasa a **Σ_j x_ij ≤ 2**. Se permite más de una tarea por profesional cuando |J| > |I|, porque con ≤ 1 solo se cubrirían 5 de 7 tareas. Condición de factibilidad: |I| · 2 = 10 ≥ 7.

Con los datos por defecto de la app (el enunciado no trae datos para el séptimo profesional ni la séptima tarea; se generan con valores de referencia editables):

| Escenario | Suma mínima | Sin asignación | Con 2 tareas | Mayor carga |
|---|---|---|---|---|
| Base 6×6 | 6063 h | — | — | 1012 h |
| A · 7×5 | 5052 h | Carlos, Andrés | — | 1012 h |
| B · 5×7 | 7075 h | — | Carlos (T2, T6), Laura (T3, T7) | 2024 h |

En A, el modelo escoge los 5 profesionales más eficientes para las 5 tareas. En B, todas las tareas se cubren pero dos profesionales asumen doble carga, lo que eleva el total y duplica la duración calendario. El +1000 suma una constante por tarea asignada (5000 en A, 7000 en B) y no altera la asignación óptima.

**Nota conceptual:** minimizar la suma de horas no minimiza el tiempo calendario si las tareas corren en paralelo; para eso habría que minimizar la mayor carga individual (min-max). La app muestra ese valor como "Mayor carga individual".

---

## Despliegue en Streamlit Community Cloud

1. Crear un repositorio público en GitHub (por ejemplo `jfv-asignacion`) y subir `app.py`, `modelo_asignacion.py`, `requirements.txt` y `README.md` en la raíz.
2. Entrar a https://share.streamlit.io con la cuenta de GitHub → **Create app** → **Deploy a public app from GitHub**.
3. Repositorio: `tu-usuario/jfv-asignacion`, rama `main`, archivo principal `app.py` → **Deploy**.
4. Copiar el enlace `https://<nombre>.streamlit.app` como entregable.

Ejecución local: `pip install -r requirements.txt` y luego `streamlit run app.py`.
