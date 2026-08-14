"""Genera el dataset de ejemplo del supermercado como archivos CSV.

Determinístico (semilla fija): cualquiera que lo ejecute obtiene EXACTAMENTE los
mismos datos, con integridad referencial garantizada entre tablas. Solo usa la
librería estándar.

Uso:  python scripts/generar_dataset.py
Salida: 7 archivos .csv en la subcarpeta datos/ del proyecto.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEMILLA = 42
RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "datos"  # los CSV viven en la subcarpeta datos/

# --- Parámetros de volumen ---
# Las paramétricas (clientes, productos, etc.) se mantienen pequeñas; solo crecen
# las transaccionales, para que los JOINs siempre encuentren su fila de dimensión.
N_CLIENTES = 50
N_TICKETS = 2500
N_MOVIMIENTOS = 3000
# Rango FIJO (no dinámico) para que el dataset sea reproducible y sirva de BD congelada.
# Cubre de enero 2024 hasta fin de julio 2026, permitiendo comparaciones entre años.
FECHA_INICIO = date(2024, 1, 1)
FECHA_FIN = date(2026, 7, 31)
DIAS_RANGO = (FECHA_FIN - FECHA_INICIO).days

# --- Tendencia sintética (para que las comparaciones entre años sean interesantes) ---
ANIO_FACTOR = {2024: 1.00, 2025: 1.20, 2026: 1.40}  # +20% de volumen de ventas por año
MES_FACTOR = [
    0.95,
    0.90,
    1.00,
    1.00,
    1.05,
    1.05,  # ene..jun
    1.05,
    1.00,
    1.00,
    1.05,
    1.10,
    1.30,
]  # jul..dic (pico en diciembre)
INFLACION = {2024: 1.00, 2025: 1.08, 2026: 1.16}  # +8% de precios por año

CIUDADES = [
    "Bogota",
    "Medellin",
    "Cali",
    "Barranquilla",
    "Bucaramanga",
    "Cartagena",
    "Pereira",
    "Manizales",
    "Cucuta",
    "Ibague",
]

CATEGORIAS = [
    (1, "Lacteos", "Leche, quesos, yogures y derivados"),
    (2, "Panaderia", "Pan, ponques y productos horneados"),
    (3, "Bebidas", "Aguas, gaseosas, jugos y cafe"),
    (4, "Snacks", "Pasabocas dulces y salados"),
    (5, "Limpieza", "Productos de aseo del hogar"),
    (6, "Frutas y Verduras", "Productos frescos agricolas"),
    (7, "Carnes", "Carnes de res, cerdo y pollo"),
    (8, "Cuidado Personal", "Higiene y cuidado personal"),
]

PROVEEDORES = [
    (1, "Distribuidora Andina", "correo@andina.example"),
    (2, "Alimentos del Valle", "ventas@delvalle.example"),
    (3, "Lacteos La Pradera", "contacto@lapradera.example"),
    (4, "Bebidas Tropicales SAS", "pedidos@tropicales.example"),
    (5, "Importados del Norte", "info@delnorte.example"),
    (6, "Panaderia Central", "central@panaderia.example"),
    (7, "Carnes Premium", "ventas@carnespremium.example"),
    (8, "Aseo Total SAS", "contacto@aseototal.example"),
    (9, "Frutas del Campo", "pedidos@frutasdelcampo.example"),
    (10, "Snacks y Dulces SA", "info@snacksydulces.example"),
]

TIENDAS = [
    (1, "Supermercado Central", "Bogota"),
    (2, "Supermercado Norte", "Medellin"),
    (3, "Supermercado Sur", "Cali"),
    (4, "Supermercado Caribe", "Barranquilla"),
    (5, "Supermercado Oriente", "Bucaramanga"),
]

SEGMENTOS = ["Regular", "Premium", "Mayorista"]

# Nombre de producto -> (categoria_id, unidad_medida, precio_min, precio_max)
PRODUCTOS_BASE = [
    ("Leche Entera 1L", 1, "litro", 3500, 4500),
    ("Leche Deslactosada 1L", 1, "litro", 4000, 5000),
    ("Yogurt Natural 200g", 1, "unidad", 2000, 3000),
    ("Queso Campesino 500g", 1, "unidad", 9000, 12000),
    ("Mantequilla 250g", 1, "unidad", 6000, 8000),
    ("Kumis 200g", 1, "unidad", 2000, 2800),
    ("Pan Tajado 500g", 2, "unidad", 4000, 5500),
    ("Pan Baguette", 2, "unidad", 3000, 4000),
    ("Croissant", 2, "unidad", 2500, 3500),
    ("Ponque Vainilla", 2, "unidad", 8000, 11000),
    ("Galletas Integrales", 2, "paquete", 3500, 4500),
    ("Agua 600ml", 3, "unidad", 1500, 2200),
    ("Gaseosa Cola 1.5L", 3, "unidad", 4500, 6000),
    ("Jugo Naranja 1L", 3, "litro", 5000, 6500),
    ("Jugo Mango 1L", 3, "litro", 5000, 6500),
    ("Cerveza Lata 330ml", 3, "unidad", 3000, 4500),
    ("Cafe Molido 500g", 3, "unidad", 12000, 16000),
    ("Papas Fritas 150g", 4, "paquete", 3500, 5000),
    ("Mani Salado 100g", 4, "paquete", 2500, 3500),
    ("Chocolatina", 4, "unidad", 1500, 2500),
    ("Galletas Dulces", 4, "paquete", 3000, 4000),
    ("Palomitas 90g", 4, "paquete", 2500, 3500),
    ("Detergente 1kg", 5, "unidad", 9000, 13000),
    ("Jabon Barra", 5, "unidad", 2000, 3000),
    ("Limpiavidrios 500ml", 5, "unidad", 6000, 8500),
    ("Cloro 1L", 5, "litro", 4000, 5500),
    ("Suavizante 1L", 5, "litro", 7000, 9500),
    ("Banano", 6, "kg", 2500, 3500),
    ("Manzana", 6, "kg", 6000, 8000),
    ("Tomate", 6, "kg", 3000, 4500),
    ("Cebolla", 6, "kg", 2500, 3800),
    ("Papa", 6, "kg", 2000, 3200),
    ("Zanahoria", 6, "kg", 2500, 3500),
    ("Aguacate", 6, "unidad", 3000, 5000),
    ("Pechuga Pollo", 7, "kg", 12000, 16000),
    ("Carne Molida", 7, "kg", 18000, 24000),
    ("Costilla Cerdo", 7, "kg", 15000, 20000),
    ("Salchicha 500g", 7, "paquete", 8000, 11000),
    ("Shampoo 400ml", 8, "unidad", 12000, 16000),
    ("Crema Dental 100ml", 8, "unidad", 5000, 7000),
    ("Papel Higienico x4", 8, "paquete", 6000, 9000),
    ("Desodorante", 8, "unidad", 9000, 13000),
]

# Categoría -> proveedores plausibles que la surten.
PROVEEDOR_POR_CATEGORIA = {
    1: [3, 1, 2],
    2: [6, 1],
    3: [4, 1, 5],
    4: [10, 5],
    5: [8, 5],
    6: [9, 1],
    7: [7, 1],
    8: [8, 5],
}


def precio_inflado(base: int, anio: int) -> int:
    """Aplica el factor de inflación del año y redondea a la cincuentena."""
    return round(base * INFLACION[anio] / 50) * 50


def escribir_csv(nombre: str, cabecera: list[str], filas: list[tuple]) -> None:
    ruta = SALIDA / nombre
    with ruta.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(cabecera)
        escritor.writerows(filas)
    print(f"  {nombre}: {len(filas)} filas")


def main() -> None:
    rng = random.Random(SEMILLA)
    SALIDA.mkdir(exist_ok=True)
    print("Generando dataset del supermercado...")

    # --- Paramétricas ---
    escribir_csv(
        "categorias.csv",
        ["categoria_id", "nombre_categoria", "descripcion"],
        CATEGORIAS,
    )
    escribir_csv(
        "proveedores.csv",
        ["proveedor_id", "nombre_proveedor", "ciudad", "pais", "email_contacto"],
        [(pid, nom, rng.choice(CIUDADES), "Colombia", email) for pid, nom, email in PROVEEDORES],
    )
    escribir_csv(
        "tiendas.csv",
        ["tienda_id", "nombre_tienda", "ciudad"],
        TIENDAS,
    )

    clientes = [
        (
            cid,
            f"Cliente {cid:03d}",
            rng.choice(CIUDADES),
            rng.choice(SEGMENTOS),
            (FECHA_INICIO - timedelta(days=rng.randint(0, 1000))).isoformat(),
        )
        for cid in range(1, N_CLIENTES + 1)
    ]
    escribir_csv(
        "clientes.csv",
        ["cliente_id", "nombre_cliente", "ciudad", "segmento", "fecha_registro"],
        clientes,
    )

    productos = []
    for i, (nombre, cat_id, unidad, pmin, pmax) in enumerate(PRODUCTOS_BASE, start=1):
        sku = f"SKU{i:04d}"
        proveedor = rng.choice(PROVEEDOR_POR_CATEGORIA[cat_id])
        precio = round(rng.randint(pmin, pmax) / 100) * 100  # redondeado a centenas
        productos.append((sku, nombre, cat_id, proveedor, precio, unidad))
    escribir_csv(
        "productos.csv",
        [
            "producto_id",
            "nombre_producto",
            "categoria_id",
            "proveedor_id",
            "precio_unitario",
            "unidad_medida",
        ],
        productos,
    )

    # Índices rápidos para las transaccionales
    precio_de = {p[0]: p[4] for p in productos}
    proveedor_de = {p[0]: p[3] for p in productos}
    skus = [p[0] for p in productos]
    tienda_ids = [t[0] for t in TIENDAS]
    cliente_ids = [c[0] for c in clientes]
    descuentos_posibles = [0.0, 0.0, 0.0, 0.0, 0.05, 0.10, 0.15]

    # Fechas con tendencia: crecimiento interanual + estacionalidad mensual.
    dias = [FECHA_INICIO + timedelta(days=d) for d in range(DIAS_RANGO + 1)]
    pesos = [ANIO_FACTOR[d.year] * MES_FACTOR[d.month - 1] for d in dias]
    fechas_ventas = rng.choices(dias, weights=pesos, k=N_TICKETS)
    fechas_mov = rng.choices(dias, weights=pesos, k=N_MOVIMIENTOS)

    # --- Transaccional 1: ventas (una fila por linea de un ticket) ---
    ventas = []
    venta_id = 1
    for ticket_id in range(1, N_TICKETS + 1):
        cliente = rng.choice(cliente_ids)
        tienda = rng.choice(tienda_ids)
        fecha_obj = fechas_ventas[ticket_id - 1]
        fecha = fecha_obj.isoformat()
        productos_ticket = rng.sample(skus, rng.randint(1, 6))
        for sku in productos_ticket:
            cantidad = rng.randint(1, 5)
            precio = precio_inflado(precio_de[sku], fecha_obj.year)
            descuento = rng.choice(descuentos_posibles)
            total = round(cantidad * precio * (1 - descuento), 2)
            ventas.append(
                (
                    venta_id,
                    ticket_id,
                    fecha,
                    cliente,
                    tienda,
                    sku,
                    cantidad,
                    precio,
                    descuento,
                    total,
                )
            )
            venta_id += 1
    escribir_csv(
        "ventas.csv",
        [
            "venta_id",
            "ticket_id",
            "fecha",
            "cliente_id",
            "tienda_id",
            "producto_id",
            "cantidad",
            "precio_unitario",
            "descuento",
            "total_linea",
        ],
        ventas,
    )

    # --- Transaccional 2: movimientos de inventario ---
    tipos = ["ENTRADA", "ENTRADA", "SALIDA", "SALIDA", "AJUSTE"]
    movimientos = []
    for mid in range(1, N_MOVIMIENTOS + 1):
        sku = rng.choice(skus)
        tienda = rng.choice(tienda_ids)
        fecha_obj = fechas_mov[mid - 1]
        fecha = fecha_obj.isoformat()
        tipo = rng.choice(tipos)
        cantidad = rng.randint(1, 100)
        costo = round(precio_inflado(precio_de[sku], fecha_obj.year) * rng.uniform(0.55, 0.75), 2)
        # SALIDA/AJUSTE no tienen proveedor -> queda vacio (NULL en la BD)
        proveedor = proveedor_de[sku] if tipo == "ENTRADA" else ""
        movimientos.append((mid, fecha, tienda, sku, proveedor, tipo, cantidad, costo))
    escribir_csv(
        "movimientos_inventario.csv",
        [
            "movimiento_id",
            "fecha",
            "tienda_id",
            "producto_id",
            "proveedor_id",
            "tipo_movimiento",
            "cantidad",
            "costo_unitario",
        ],
        movimientos,
    )

    print("Listo. Dataset generado en la subcarpeta datos/.")


if __name__ == "__main__":
    main()
