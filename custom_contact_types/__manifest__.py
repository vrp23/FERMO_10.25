{
    'name': 'Tipos de Contacto Personalizados',
    'version': '1.2',  # MODIFICADO: de 1.1 a 1.2
    'summary': 'Personaliza los tipos de contactos y añade campos personalizados para tasas diferenciadas',
    'description': """
        Este módulo permite:
        - Crear diferentes tipos de contactos
        - Asignar múltiples tipos a cada contacto
        - Añadir campos personalizados para tasas y comisiones
        - Configurar tasas diferenciadas para compra y venta
        - Asignar operador por defecto a cada contacto
        - Identificar tipos de contacto como socios comisionistas
        
        Changelog v1.2:
        - Cambio de Many2one a Many2many para permitir múltiples tipos
        - Añadido campo is_commission_partner para integración con commission_management
        
        Changelog v1.1:
        - Añadidas tasas diferenciadas para compra y venta
        - Campos legacy mantenidos para compatibilidad
        - Migración automática de datos existentes
    """,
    'category': 'Contacts',
    'author': 'VRP',
    'website': 'https://virtualremotepartner.com/',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_type_views.xml',
        'views/res_partner_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}