# -*- coding: utf-8 -*-
{
    'name': 'Compra y Venta de Divisas y Criptomonedas',
    'version': '1.1',
    'category': 'Finance',
    'summary': 'Gestión de operaciones de compra y venta de USD y USDT con método FIFO',
    'description': """
Módulo de Gestión de Compra-Venta de Divisas y Criptomonedas
============================================================

Este módulo implementa la gestión completa de operaciones de compra y venta de divisas (USD) y criptomonedas (USDT).

Características principales:
---------------------------
* Gestión de wallets en múltiples monedas (ARS, USD, USDT)
* Dashboard con acceso rápido a operaciones y visualización de últimas transacciones
* Compra y venta de divisas con tipos de cambio configurables
* Intercambio entre diferentes pares de monedas
* Historial detallado de operaciones por cliente
* Tipos de cambio personalizables con historial
* **NUEVO**: Sistema FIFO para cálculo de ganancias
* **NUEVO**: Tracking de inventario con tipo de cambio de adquisición
* **NUEVO**: Reporte de ganancias por diferencia de tipo de cambio

Sistema FIFO:
------------
* Registro automático de lotes de inventario en compras
* Consumo FIFO en ventas (primeras compras se venden primero)
* Cálculo automático de ganancias por diferencia de TC
* Las conversiones USD/USDT no generan ganancia

Desarrollado por VRP - Virtual Remote Partner
    """,
    'author': 'VRP - Virtual Remote Partner',
    'website': 'https://vrp.com.ar',
    'depends': [
        'base',
        'mail',
        'web',
        'chequera',
    ],
    'data': [
        'security/divisas_security.xml',
        'security/ir.model.access.csv',
        'data/divisas_data.xml',
        'views/divisas_dashboard_view.xml',
        'views/divisas_currency_view.xml',
        'views/divisas_exchange_wizard_view.xml',
        'views/divisas_wallet_view.xml',
        'views/divisas_exchange_rate_view.xml',
        'views/divisas_inventory_lot_view.xml',
        'views/divisas_open_position_view.xml',
        'views/partner_view_inherit.xml',
        'views/divisas_menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "images": ["static/description/icon.png"],
    'license': 'LGPL-3',
    'sequence': 1,
    'assets': {
        'web.assets_backend': [
            'divisas/static/src/scss/divisas.scss',
        ],
    },
}