from odoo import models, fields, api

class ChequeraBank(models.Model):
    _name = 'chequera.bank'
    _description = 'Banco para Cheques'
    _order = 'name'

    name = fields.Char(string='Nombre del Banco', required=True)
    code = fields.Char(string='Código', required=True)
    active = fields.Boolean(string='Activo', default=True)
    
    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'El código del banco debe ser único.')
    ]
    
    def name_get(self):
        """Personalizar la visualización del nombre para mostrar código y nombre"""
        result = []
        for bank in self:
            name = f"{bank.code} - {bank.name}"
            result.append((bank.id, name))
        return result
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Permitir búsqueda por código o nombre"""
        if args is None:
            args = []
        
        domain = args.copy()
        
        if name:
            # Buscar por código o nombre
            domain_filter = ['|', ('code', operator, name), ('name', operator, name)]
            domain = domain_filter + domain
        
        # Buscar registros
        banks = self.search(domain, limit=limit)
        
        return banks.name_get()