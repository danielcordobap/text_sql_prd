"""Diccionario de significados de tablas, columnas y relaciones.

Transcrito literalmente desde datos/MODELO_DATOS.md (regla anti-alucinación).
"""

DESCRIPCIONES_TABLAS: dict[str, str] = {
    "categorias": "Categorías a las que pertenecen los productos.",
    "proveedores": "Empresas que abastecen los productos.",
    "tiendas": "Sucursales del supermercado.",
    "clientes": "Clientes registrados.",
    "productos": "Catálogo de productos (SKU).",
    "ventas": (
        "Transacciones de clientes. Una fila por línea de un ticket: varias filas con "
        "el mismo ticket_id forman una sola compra."
    ),
    "movimientos_inventario": "Transacciones de inventario del supermercado.",
}

DESCRIPCIONES_COLUMNAS: dict[str, dict[str, str]] = {
    "categorias": {
        "categoria_id": "Identificador de la categoría",
        "nombre_categoria": "Nombre (Lacteos, Bebidas, …)",
        "descripcion": "Descripción de la categoría",
    },
    "proveedores": {
        "proveedor_id": "Identificador del proveedor",
        "nombre_proveedor": "Razón social",
        "ciudad": "Ciudad del proveedor",
        "pais": 'País (todos "Colombia" en el ejemplo)',
        "email_contacto": "Correo de contacto (ficticio, dominio .example)",
    },
    "tiendas": {
        "tienda_id": "Identificador de la tienda",
        "nombre_tienda": "Nombre de la sucursal",
        "ciudad": "Ciudad donde opera",
    },
    "clientes": {
        "cliente_id": "Identificador del cliente",
        "nombre_cliente": 'Nombre (anonimizado: "Cliente 001")',
        "ciudad": "Ciudad del cliente",
        "segmento": "Regular, Premium o Mayorista",
        "fecha_registro": "Fecha de alta del cliente",
    },
    "productos": {
        "producto_id": "SKU, p. ej. SKU0001",
        "nombre_producto": "Nombre del producto",
        "categoria_id": "-> categorias",
        "proveedor_id": "-> proveedores",
        "precio_unitario": "Precio de venta de referencia (COP)",
        "unidad_medida": "unidad, kg, litro o paquete",
    },
    "ventas": {
        "venta_id": "Identificador de la línea",
        "ticket_id": "Agrupa las líneas de una misma compra",
        "fecha": "Fecha de la venta (2024-01-01 a 2026-07-31)",
        "cliente_id": "-> clientes",
        "tienda_id": "-> tiendas",
        "producto_id": "-> productos",
        "cantidad": "Unidades vendidas en la línea",
        "precio_unitario": "Precio al momento de la venta",
        "descuento": "Fracción de descuento (0.00–0.15)",
        "total_linea": "cantidad * precio_unitario * (1 - descuento)",
    },
    "movimientos_inventario": {
        "movimiento_id": "Identificador del movimiento",
        "fecha": "Fecha del movimiento (2024-01-01 a 2026-07-31)",
        "tienda_id": "-> tiendas",
        "producto_id": "-> productos",
        "proveedor_id": "-> proveedores. Solo en ENTRADA; NULL en SALIDA/AJUSTE",
        "tipo_movimiento": "ENTRADA, SALIDA o AJUSTE",
        "cantidad": "Unidades del movimiento (siempre positivo; el signo lo da el tipo)",
        "costo_unitario": "Costo unitario del producto",
    },
}

RELACIONES: list[str] = [
    "productos.categoria_id -> categorias.categoria_id",
    "productos.proveedor_id -> proveedores.proveedor_id",
    "ventas.cliente_id -> clientes.cliente_id",
    "ventas.tienda_id -> tiendas.tienda_id",
    "ventas.producto_id -> productos.producto_id",
    "movimientos_inventario.tienda_id -> tiendas.tienda_id",
    "movimientos_inventario.producto_id -> productos.producto_id",
    "movimientos_inventario.proveedor_id -> proveedores.proveedor_id (NULL si no es ENTRADA)",
]

__all__ = [
    "DESCRIPCIONES_COLUMNAS",
    "DESCRIPCIONES_TABLAS",
    "RELACIONES",
]
