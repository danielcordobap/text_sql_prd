"""Adversariales del grounding a nivel de grafo (extracción de literales del WHERE).

Bug A (VAL F2): el modelo casi siempre usa alias de tabla (`... productos p... p.nombre_producto`);
la extracción debe resolver el alias a la tabla real. Falla contra la implementación que solo
reconoce `tabla_real.columna`.
"""

from src.graph.agente import nodo_groundear
from src.grounding import extraer_literales_groundables as _extraer_literales_groundables


def test_extrae_literal_con_alias_de_tabla() -> None:
    sql = (
        "SELECT COUNT(*) AS n FROM ventas v "
        "JOIN productos p ON v.producto_id = p.producto_id "
        "WHERE p.nombre_producto = 'Agua'"
    )
    pares = _extraer_literales_groundables(sql)
    valores = [(tabla, col, lit) for (tabla, col, lit, _node) in pares]
    assert ("productos", "nombre_producto", "Agua") in valores, (
        f"no resolvió el alias de tabla 'p' → productos; extrajo: {valores}"
    )


def test_extrae_columna_sin_cualificar_una_sola_tabla() -> None:
    # FROM con una única tabla groundable → 'ciudad' sin cualificar debe resolver a clientes.
    sql = "SELECT COUNT(*) AS n FROM clientes WHERE ciudad = 'Bogota'"
    pares = _extraer_literales_groundables(sql)
    valores = [(tabla, col) for (tabla, col, _lit, _node) in pares]
    assert ("clientes", "ciudad") in valores


def test_groundear_reescribe_el_sql_que_se_ejecuta(monkeypatch) -> None:
    # el SQL que devuelve el nodo debe llevar el literal reescrito ('Bogotá'→'Bogota').
    # Falla si el nodo muta un AST distinto del que renderiza (bug de doble parseo).
    monkeypatch.setattr(
        "src.graph.agente.valores_distintos", lambda _t, _c: ["Bogota", "Medellin", "Cali"]
    )
    estado = {
        "sql": "SELECT COUNT(*) AS n FROM clientes WHERE ciudad = 'Bogotá'",
        "pregunta": "cuántos clientes hay en Bogota",
        "idioma": "es",
    }
    out = nodo_groundear(estado) # type: ignore[arg-type]
    sql_out = out.get("sql") or ""
    assert "Bogota" in sql_out and "Bogotá" not in sql_out, (
        f"el nodo no reescribió el literal en el SQL ejecutado: {sql_out!r}"
    )


def test_groundear_substituye_y_emite_nota(monkeypatch) -> None:
    # P0: la banda SUBSTITUIR por el NODO, end-to-end: reescribe + emite la nota de sustitución.
    monkeypatch.setattr(
        "src.graph.agente.valores_distintos", lambda _t, _c: ["Bebidas", "Lacteos", "Aseo"]
    )
    estado = {
        "sql": "SELECT COUNT(*) AS n FROM categorias WHERE nombre_categoria = 'Bevidas'",
        "pregunta": "cuántos productos en Bevidas",
        "idioma": "es",
    }
    out = nodo_groundear(estado) # type: ignore[arg-type]
    assert "Bebidas" in (out.get("sql") or "")
    nota = out.get("nota_grounding")
    assert nota and "Bevidas" in nota, f"no emitió la nota de sustitución: {nota!r}"


def test_groundear_ambiguo_emite_aclaracion(monkeypatch) -> None:
    # P0: el lado EMISOR de la aclaración — nodo_groundear produce tipo=aclaracion + pendiente.
    candidatos = ["Bebida Cola Zero", "Bebida Cola Light", "Aseo"]
    monkeypatch.setattr("src.graph.agente.valores_distintos", lambda _t, _c: candidatos)
    estado = {
        "sql": "SELECT COUNT(*) AS n FROM productos WHERE nombre_producto = 'Bebida Cola'",
        "pregunta": "ventas de bebida cola",
        "idioma": "es",
    }
    out = nodo_groundear(estado) # type: ignore[arg-type]
    resp = out.get("respuesta") or {}
    assert resp.get("tipo") == "aclaracion"
    pend = out.get("pendiente_aclaracion") or {}
    assert pend.get("candidatos"), "no pobló pendiente_aclaracion.candidatos"
    assert "Bebida Cola" in (resp.get("mensaje") or "") or pend.get("candidatos")


def test_no_extrae_columna_no_groundable() -> None:
    # Negativo REAL de la allowlist: email_contacto NO está en COLUMNAS_GROUNDABLES → no se extrae;
    # nombre_proveedor SÍ → se extrae.
    # Falla si se rompe el filtro de allowlist en _resolver_tabla_columna.
    sql = "SELECT * FROM proveedores WHERE email_contacto = 'a@b.com' AND nombre_proveedor = 'X'"
    columnas = {col for (_t, col, _l, _n) in _extraer_literales_groundables(sql)}
    assert "email_contacto" not in columnas, "extrajo una columna fuera de la allowlist"
    assert "nombre_proveedor" in columnas, "no extrajo la columna groundable real"


def test_no_extrae_columna_ambigua_sin_cualificar() -> None:
    # 'ciudad' está en clientes y tiendas; ambigua sin cualificar → no se extrae (R-C).
    sql = (
        "SELECT COUNT(*) AS n FROM clientes c "
        "JOIN tiendas t ON c.ciudad = t.ciudad WHERE ciudad = 'Bogota'"
    )
    columnas = {col for (_t, col, _l, _n) in _extraer_literales_groundables(sql)}
    assert "ciudad" not in columnas, f"resolvió una columna ambigua sin cualificar: {columnas}"
