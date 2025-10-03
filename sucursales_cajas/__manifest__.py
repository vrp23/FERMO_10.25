{
    'name': 'Sucursales y Cajas',
    'version': '1.0.0',
    'category': 'Finance',
    'summary': 'Gestión de sucursales, cajas y operaciones de efectivo',
    'description': """
        Módulo para gestionar sucursales y cajas con soporte para:
        - Múltiples sucursales y cajas
        - Gestión de efectivo en múltiples monedas
        - Cuentas bancarias y wallets crypto
        - Control de sesiones de caja
        - Operaciones de depósito y retiro
        - Integración con módulos de chequera y divisas
    """,
    'author': 'VRP',
    'website': 'https://virtualremotepartner.com/',
    'depends': [
        'base',
        'mail',
        'web',
        'chequera',  # Dependencia del módulo de cheques
        'divisas',   # Dependencia del módulo de divisas
    ],
    'data': [
        # Seguridad
        'security/sucursales_cajas_security.xml',
        'security/ir.model.access.csv',
        
        # Datos
        'data/sucursales_cajas_sequence.xml',
        'data/bill_denominations_data.xml',
        
        # Vistas principales
        'views/sucursales_cajas_branch_view.xml',
        'views/sucursales_cajas_cashbox_view.xml',
        'views/sucursales_cajas_session_view.xml',
        'views/sucursales_cajas_operation_view.xml',
        'views/res_partner_inherit_view.xml',
        
        # Wizards
        'wizard_views/send_to_cashbox_wizard_view.xml',
        'wizard_views/send_to_cashbox_wizard_actions.xml',  # NUEVO ARCHIVO
        'wizard_views/cash_count_wizard_view.xml',
        'wizard_views/session_login_wizard_view.xml',
        'wizard_views/process_operation_wizard_view.xml',
        'wizard_views/close_session_wizard_view.xml',
        
        # Dashboard (después de las acciones)
        'views/sucursales_cajas_dashboard_view.xml',
        
        # Reportes
        'reports/report_actions.xml',
        'reports/operation_receipt_report.xml',
        'reports/operation_voucher_report.xml',  # CORREGIDA LA RUTA
        'reports/cash_closing_report.xml',
        
        # Menús (al final)
        'views/sucursales_cajas_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sucursales_cajas/static/src/css/sucursales_cajas.css',
            'sucursales_cajas/static/src/js/dashboard.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
}