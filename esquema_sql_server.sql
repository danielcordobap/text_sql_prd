/* =====================================================================
   Esquema de la base de datos de ejemplo: Supermercado
   Motor: SQL Server (T-SQL)
   ---------------------------------------------------------------------
   Crea las 7 tablas con sus llaves primarias y foraneas. Ejecuta este
   script ANTES de importar los CSV. El orden respeta las dependencias:
   primero las parametricas, luego las transaccionales.
   ===================================================================== */

-- Ejecuta dentro de tu base de datos (ajusta el nombre si es necesario):
-- USE supermercado;
-- GO

/* ---------- Parametricas (dimensiones) ---------- */

CREATE TABLE categorias (
    categoria_id     INT           NOT NULL PRIMARY KEY,
    nombre_categoria VARCHAR(50)   NOT NULL,
    descripcion      VARCHAR(200)  NULL
);

CREATE TABLE proveedores (
    proveedor_id     INT           NOT NULL PRIMARY KEY,
    nombre_proveedor VARCHAR(100)  NOT NULL,
    ciudad           VARCHAR(50)   NULL,
    pais             VARCHAR(50)   NULL,
    email_contacto   VARCHAR(100)  NULL
);

CREATE TABLE tiendas (
    tienda_id     INT          NOT NULL PRIMARY KEY,
    nombre_tienda VARCHAR(50)  NOT NULL,
    ciudad        VARCHAR(50)  NULL
);

CREATE TABLE clientes (
    cliente_id     INT          NOT NULL PRIMARY KEY,
    nombre_cliente VARCHAR(100) NOT NULL,
    ciudad         VARCHAR(50)  NULL,
    segmento       VARCHAR(20)  NULL,
    fecha_registro DATE         NULL
);

CREATE TABLE productos (
    producto_id     VARCHAR(10)    NOT NULL PRIMARY KEY,  -- SKU, p. ej. 'SKU0001'
    nombre_producto VARCHAR(100)   NOT NULL,
    categoria_id    INT            NOT NULL,
    proveedor_id    INT            NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    unidad_medida   VARCHAR(20)    NULL,
    CONSTRAINT fk_productos_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias (categoria_id),
    CONSTRAINT fk_productos_proveedor
        FOREIGN KEY (proveedor_id) REFERENCES proveedores (proveedor_id)
);

/* ---------- Transaccionales (hechos) ---------- */

-- Transacciones de clientes: una fila por linea de un ticket de compra.
CREATE TABLE ventas (
    venta_id        INT            NOT NULL PRIMARY KEY,
    ticket_id       INT            NOT NULL,  -- agrupa las lineas de una misma compra
    fecha           DATE           NOT NULL,
    cliente_id      INT            NOT NULL,
    tienda_id       INT            NOT NULL,
    producto_id     VARCHAR(10)    NOT NULL,
    cantidad        INT            NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,  -- precio al momento de la venta
    descuento       DECIMAL(4, 2)  NOT NULL,  -- fraccion: 0.00 a 0.50
    total_linea     DECIMAL(12, 2) NOT NULL,  -- cantidad * precio * (1 - descuento)
    CONSTRAINT fk_ventas_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes (cliente_id),
    CONSTRAINT fk_ventas_tienda
        FOREIGN KEY (tienda_id) REFERENCES tiendas (tienda_id),
    CONSTRAINT fk_ventas_producto
        FOREIGN KEY (producto_id) REFERENCES productos (producto_id)
);

-- Transacciones de inventario: entradas (compras a proveedor), salidas y ajustes.
CREATE TABLE movimientos_inventario (
    movimiento_id   INT            NOT NULL PRIMARY KEY,
    fecha           DATE           NOT NULL,
    tienda_id       INT            NOT NULL,
    producto_id     VARCHAR(10)    NOT NULL,
    proveedor_id    INT            NULL,       -- solo en ENTRADA; NULL en SALIDA/AJUSTE
    tipo_movimiento VARCHAR(10)    NOT NULL,   -- 'ENTRADA' | 'SALIDA' | 'AJUSTE'
    cantidad        INT            NOT NULL,
    costo_unitario  DECIMAL(10, 2) NULL,
    CONSTRAINT fk_mov_tienda
        FOREIGN KEY (tienda_id) REFERENCES tiendas (tienda_id),
    CONSTRAINT fk_mov_producto
        FOREIGN KEY (producto_id) REFERENCES productos (producto_id),
    CONSTRAINT fk_mov_proveedor
        FOREIGN KEY (proveedor_id) REFERENCES proveedores (proveedor_id),
    CONSTRAINT ck_mov_tipo
        CHECK (tipo_movimiento IN ('ENTRADA', 'SALIDA', 'AJUSTE'))
);
