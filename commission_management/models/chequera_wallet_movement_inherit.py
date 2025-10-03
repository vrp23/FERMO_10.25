from odoo import models, fields, api

class ChequeraWalletMovement(models.Model):
    _inherit = 'chequera.wallet.movement'
    
    # Agregar campo para relación con operaciones de caja
    cashbox_operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación de Caja',
        ondelete='cascade',
        help='Operación de caja relacionada con este movimiento'
    )
    
    # Extender el campo tipo para incluir operación de caja
    tipo = fields.Selection(
        selection_add=[
            ('cashbox_operation', 'Operación de Caja'),
        ],
        ondelete={'cashbox_operation': 'cascade'}
    )
    
    @api.model
    def create(self, vals):
        """Override para manejar operaciones de caja"""
        # Si viene de una operación de caja, establecer el tipo correctamente
        if vals.get('cashbox_operation_id'):
            vals['tipo'] = 'cashbox_operation'
        
        return super(ChequeraWalletMovement, self).create(vals)