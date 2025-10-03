{
    "name": "Chequera",
    "summary": "Gestión de compra y venta de cheques",
    "version": "1.0",
    "category": "Finance",
    "author": "VRP",
    "website": "https://virtualremotepartner.com/",
    "depends": [
        "base",
        "mail",
        "web",
        "custom_contact_types",
    ],
    "data": [
        # Seguridad
        "security/chequera_security.xml",
        "security/ir.model.access.csv",
        
        # Datos
        "data/chequera_sequence.xml",
        "data/chequera_sale_sequence.xml",
        "data/chequera_formula_data.xml",
        
        # Vistas - es importante el orden
        #"views/chequera_dashboard_view.xml",
        "views/chequera_bank_view.xml",
        "views/chequera_formula_view.xml",
        "views/chequera_emisor_view.xml",
        "views/chequera_partner_inherit.xml",
        "views/chequera_purchase_wizard_view.xml",
        "views/chequera_sale_wizard_view.xml",
        "views/chequera_rejection_wizard_view.xml",
        "views/chequera_reversion_confirmation_view.xml",
        "views/chequera_wallet_view.xml",
        "views/chequera_check_view.xml",
        "views/chequera_operations_view.xml",
        "views/chequera_dashboard_new_view.xml",
        "views/chequera_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/chequera/static/src/css/chequera_style.css",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "images": ["static/description/icon.png"],
}