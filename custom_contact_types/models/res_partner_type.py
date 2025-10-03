from odoo import models, fields, api

class ResPartnerType(models.Model):
    _name = 'res.partner.type'
    _description = 'Tipo de Contacto'
    
    name = fields.Char(string='Nombre del Tipo', required=True)
    code = fields.Char(string='Código', required=True)
    description = fields.Text(string='Descripción')
    active = fields.Boolean(default=True)
    
    # NUEVO: Campo para identificar socios comisionistas (usado por commission_management)
    is_commission_partner = fields.Boolean(
        string='Es Socio Comisionista',
        default=False,
        help='Marcar si este tipo de contacto participa en la distribución de ganancias'
    )
    
    _sql_constraints = [
        ('code_uniq', 'unique (code)', '¡El código del tipo de contacto debe ser único!')
    ]