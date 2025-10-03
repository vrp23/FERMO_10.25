# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DivisasCurrencyInherit(models.Model):
    _inherit = 'divisas.currency'
    
    # Campos para comisiones
    commission_liquidated = fields.Boolean(
        string='Comisión Liquidada',
        readonly=True,
        default=False,
        tracking=True,
        help='Indica si esta operación fue incluida en una liquidación de comisiones'
    )
    
    commission_liquidation_id = fields.Many2one(
        'commission.liquidation',
        string='Liquidación de Comisión',
        readonly=True,
        help='Liquidación donde se procesó esta operación'
    )
    
    commission_period = fields.Char(
        string='Período Liquidado',
        readonly=True,
        help='Período en el que se liquidó esta operación (YYYY-MM)'
    )
    
    # Campo para el operador (tomado del partner)
    commission_operator_id = fields.Many2one(
        'res.users',
        string='Operador Asignado',
        compute='_compute_commission_operator',
        store=True,
        help='Operador asignado según el partner de la operación'
    )
    
    @api.depends('partner_id', 'partner_id.assigned_seller_id')
    def _compute_commission_operator(self):
        """Obtiene el operador asignado del partner"""
        for operation in self:
            if operation.partner_id and hasattr(operation.partner_id, 'assigned_seller_id'):
                operation.commission_operator_id = operation.partner_id.assigned_seller_id
            else:
                operation.commission_operator_id = False
    
    def write(self, vals):
        """Override para validar cambios en operaciones con comisión liquidada"""
        if self.filtered('commission_liquidated'):
            # Campos que no se pueden modificar si hay comisión liquidada
            protected_fields = [
                'amount', 'payment_amount', 
                'exchange_rate', 'partner_id',
                'currency_type', 'payment_currency_type'
            ]
            
            for field in protected_fields:
                if field in vals:
                    raise ValidationError(
                        _('No se puede modificar el campo "%s" porque la operación tiene comisión liquidada.') 
                        % self._fields[field].string
                    )
        
        return super().write(vals)
    
    @api.model
    def get_unliquidated_by_period(self, operator_id, date_from, date_to):
        """Obtiene operaciones no liquidadas de un operador en un período"""
        # Buscar partners del operador
        partners = self.env['res.partner'].search([
            ('assigned_seller_id', '=', operator_id)
        ])
        
        domain = [
            ('state', '=', 'confirmed'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('partner_id', 'in', partners.ids),
            ('commission_liquidated', '=', False)
        ]
        
        return self.search(domain)