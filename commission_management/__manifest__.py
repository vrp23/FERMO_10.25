# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Comisiones',
    'version': '1.0',
    'category': 'Finance',
    'summary': 'Gestión de comisiones de operadores, socios y costos',
    'description': """
Módulo de Gestión de Comisiones
================================

Este módulo implementa la gestión completa de comisiones para:
- Operadores por operaciones de cheques, divisas y caja
- Socios por ganancias netas
- Gestión de costos y reinversión

Características principales:
---------------------------
* Liquidación de comisiones por cheques (compra-venta)
* Liquidación de comisiones por divisas (por período)
* Liquidación de comisiones por operaciones de caja
* Gestión de costos mensuales (CF, CV, CI, IMP)
* Liquidación de comisiones de socios
* Reportes de rentabilidad
* Integración con wallets existentes

Desarrollado por VRP - Virtual Remote Partner
    """,
    'author': 'VRP - Virtual Remote Partner',
    'website': 'https://virtualremotepartner.com/',
    'depends': [
        'base',
        'mail',
        'custom_contact_types',
        'chequera',
        'divisas',
        'sucursales_cajas',
    ],
    'data': [
        # Seguridad
        'security/commission_security.xml',
        'security/ir.model.access.csv',
        
        # Datos
        'data/commission_sequences.xml',
        'data/commission_cost_types.xml',
        
        # Vistas principales
        'views/commission_liquidation_views.xml',
        'views/commission_liquidation_line_views.xml',
        'views/commission_cost_views.xml',
        'views/commission_partner_liquidation_views.xml',
        
        # Vistas heredadas
        'views/res_partner_inherit_views.xml',
        'views/chequera_check_inherit_views.xml',
        'views/divisas_currency_inherit_views.xml',
        'views/sucursales_cajas_operation_inherit_views.xml',
        
        # Wizards
        'wizard/commission_liquidation_wizard_views.xml',
        'wizard/commission_cheques_wizard_views.xml',
        'wizard/commission_divisas_wizard_views.xml',
        'wizard/commission_caja_wizard_views.xml',
        'wizard/commission_reversal_wizard_views.xml',
        'wizard/commission_cost_cashbox_wizard_views.xml',
        
        # Reportes (ANTES del dashboard y menús)
        'reports/commission_report_actions.xml',
        'reports/commission_liquidation_report.xml',
        'reports/partner_commission_report.xml',
        
        # Dashboard
        'views/commission_dashboard_view.xml',
        
        # Menús (al final)
        'views/commission_menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 10,
}