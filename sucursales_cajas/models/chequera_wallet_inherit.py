# -*- coding: utf-8 -*-

from odoo import models, fields


class ChequeraWalletMovementInherit(models.Model):
    _inherit = 'chequera.wallet.movement'
    
    # Extender el campo tipo para incluir operaciones de caja
    tipo = fields.Selection(
        selection_add=[
            ('cashbox_operation', 'Operación de Caja'),
        ],
        ondelete={'cashbox_operation': 'cascade'}
    )
    
    # Campo para relacionar con operaciones de caja
    cashbox_operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación de Caja',
        help='Operación de caja relacionada con este movimiento'
    )