**README - Módulo de Divisas**

Contexto del Proyecto

PROYECTO ODOO V17 CE – SISTEMA DE GESTIÓN FINANCIERA

Sistema desarrollado sobre Odoo v17 Community Edition para la administración integral de una empresa financiera. El proyecto consta de 5 módulos personalizados que reemplazan los módulos nativos de Odoo (excepto contactos y configuración):



custom\_contact\_types - Gestión de tipos de contacto personalizados

chequera - Administración de cheques y wallet ARS

divisas - Compra/venta de divisas y criptomonedas con sistema FIFO

sucursales\_cajas - Control de sucursales y cajas

commission\_management - Gestión de comisiones



Resumen del Módulo Divisas

El módulo Divisas implementa un sistema completo de gestión de operaciones cambiarias con las siguientes características principales:

Características Clave



Multi-moneda: Soporte para USD, USDT y ARS

Sistema FIFO: Cálculo automático de ganancias mediante método First-In-First-Out

Doble registro de ganancias: Ganancias en ARS por operaciones con pesos y ganancias en USD por conversiones USD/USDT

Wallets integradas: Una wallet por moneda para cada contacto

Tipos de cambio flexibles: Configuración de tasas de compra/venta personalizables

Dashboard operativo: Vista centralizada con balance de posición compra/venta

Integración con módulo Chequera: Sincronización automática con wallet ARS existente

Stock negativo permitido: Posibilidad de vender divisas antes de comprarlas



Flujos del Proceso

1\. Operación de COMPRA (La empresa compra divisas al partner)

Partner → Entrega divisa → Empresa

Partner ← Recibe pago ← Empresa

Proceso:



Seleccionar contacto/proveedor

Elegir divisa a comprar (USD/USDT/ARS)

Elegir moneda de pago (diferente a la comprada)

Sistema sugiere tipo de cambio configurado (modificable)

Confirmar operación

Actualización de wallets:



Disminuye wallet del partner en divisa comprada

Aumenta wallet del partner en moneda de pago





Proceso FIFO: Se crea lote de inventario con TC de adquisición



2\. Operación de VENTA (La empresa vende divisas al partner)

Partner ← Recibe divisa ← Empresa

Partner → Entrega pago → Empresa

Proceso:



Seleccionar contacto/cliente

Elegir divisa a vender (USD/USDT/ARS)

Elegir moneda de pago (diferente a la vendida)

Sistema sugiere tipo de cambio configurado (modificable)

Confirmar operación

Actualización de wallets:



Aumenta wallet del partner en divisa vendida

Disminuye wallet del partner en moneda de pago





Proceso FIFO:



Consume lotes más antiguos primero

Calcula ganancia/pérdida según tipo de operación:



Operaciones con ARS: Ganancia en ARS

Conversiones USD/USDT: Ganancia en USD





Registra consumos detallados







3\. Sistema FIFO con Doble Registro de Ganancias

Compras: Generan lotes de inventario con:



Cantidad comprada

Tipo de cambio de adquisición

Fecha de compra

Moneda de referencia para ganancia



Ventas: Consumen lotes FIFO calculando:



Para operaciones con ARS: Ganancia = (TC venta - TC compra) × cantidad en ARS

Para conversiones USD/USDT: Ganancia = diferencia de TC × cantidad en USD

Registro separado de ganancias por tipo de moneda

Permite stock negativo con advertencia



Resumen de Funciones

**Dashboard Principal**



Vista rápida de últimas operaciones (compras/ventas)

Balance de posición compra/venta:



Inventario actual por divisa (cantidad y TC promedio ponderado)

Posición neta (comprado - vendido)

Indicador visual de desbalance (exceso de compra o venta)

TC promedio ponderada de compras pendientes de vender

Sugerencia de TC objetivo para mantener margen

Alertas cuando hay desequilibrio significativo





Tipos de cambio actuales con comparativa de mercado

Botones de acceso rápido para nuevas operaciones

Resumen de ganancias: Total en ARS y total en USD



Gestión de Operaciones



Compra de divisas: Wizard intuitivo con cálculo automático

Venta de divisas: Control de inventario FIFO automático

Registro dual de ganancias: ARS y USD según corresponda

Estados: Borrador → Confirmado → Cancelado

Cancelación: Reversión completa de movimientos y consumos FIFO



Wallets por Contacto



Saldo independiente para USD, USDT y ARS

Integración con wallet ARS del módulo chequera

Histórico de movimientos por contacto

Permitido saldo negativo (representa deuda)



Configuración



Tipos de cambio: Mantenimiento de tasas compra/venta

Actualización masiva: Wizard para actualizar tipos de cambio

Historial: Registro temporal de cambios en tasas



Inventario FIFO



Lotes de inventario: Vista de stock disponible con TC de adquisición

Consumos: Detalle de ventas y ganancias por lote

Reportes de rentabilidad:



Ganancias en ARS por operaciones con pesos

Ganancias en USD por conversiones USD/USDT

Análisis de márgenes por tipo de operación







Resumen Técnico

Estructura Completa del Módulo

divisas/

├── __manifest__.py                  # Definición del módulo

├── __init__.py                      # Import de modelos

├── README.txt                       # Documentación

├── security/

│   ├── divisas_security.xml        # Grupos y reglas de seguridad

│   └── ir.model.access.csv         # Permisos de acceso a modelos

├── data/

│   └── divisas_data.xml            # Datos iniciales (secuencias, TC)

├── static/

│   └── src/

│       ├── scss/

│       │   └── divisas.scss        # Estilos CSS personalizados

│       └── img/

│           └── icon.png    # Icono del módulo

├── models/

│   ├── __init__.py                 # Import de modelos

│   ├── divisas_currency.py         # Modelo principal operaciones

│   ├── divisas_currency_compute.py # Cálculos de montos

│   ├── divisas_currency_operations.py # Lógica FIFO y operaciones

│   ├── divisas_inventory_lot.py    # Lotes FIFO de inventario

│   ├── divisas_wallet.py           # Movimientos wallet y res.partner

│   ├── divisas_exchange_rate.py    # Tipos de cambio

│   ├── divisas_exchange_wizard.py  # Wizards de operación
    
    └── divisas_dashboard.py  # Dashboard principal del módulo

└── views/

&nbsp;   ├── divisas_dashboard_view.xml   # Dashboard principal

&nbsp;   ├── divisas_currency_view.xml    # Vistas de operaciones

&nbsp;   ├── divisas_exchange_wizard_view.xml # Vistas de wizards

&nbsp;   ├── divisas_wallet_view.xml      # Vistas de movimientos

&nbsp;   ├── divisas_exchange_rate_view.xml # Vistas de tipos de cambio

&nbsp;   ├── divisas_inventory_lot_view.xml # Vistas FIFO

&nbsp;   ├── partner_view_inherit.xml     # Extensión vista contacto

&nbsp;   └── divisas_menus.xml            # Estructura de menús

Modelos Principales



divisas.currency: Operaciones de compra/venta con campos para ganancias duales

divisas.inventory.lot: Lotes FIFO de inventario

divisas.lot.consumption: Consumos de lotes con registro de tipo de ganancia

divisas.wallet.movement: Movimientos de wallet

divisas.exchange.rate: Tipos de cambio



Campos Adicionales para Implementar

Para soportar el registro dual de ganancias:



profit\_usd: Campo para ganancias en USD (conversiones USD/USDT)

profit\_currency\_type: Indicador del tipo de moneda de la ganancia

Campos de balance en Dashboard para posición neta



Integración con Módulo Chequera



Extiende \_compute\_wallet\_balance para incluir movimientos de divisas en ARS

Comparte la wallet ARS existente

Mantiene compatibilidad total con operaciones de cheques



Características Técnicas Especiales



Stock negativo permitido: Sin restricción en saldos de wallet

Cálculo dual de ganancias: En ARS para operaciones con pesos, en USD para conversiones

Balance de posición: Cálculo en tiempo real de inventario y sugerencias de TC

Reversión completa: Cancelación revierte todos los efectos

Multi-compañía: Soporte completo para múltiples empresas

Trazabilidad: Registro detallado de todas las operaciones



Dependencias



Odoo 17 Community Edition

Módulo chequera (requerido para wallet ARS)

Módulos base de Odoo: base, mail, web





Desarrollado por: VRP - Virtual Remote Partner

Versión: 1.1

Licencia: LGPL-3

