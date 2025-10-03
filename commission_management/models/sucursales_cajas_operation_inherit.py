# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SucursalesCajasOperationInherit(models.Model):
    _inherit = 'sucursales_cajas.operation'
    
    # Campos para comisiones
    has_commission = fields.Boolean(
        string='Genera Comisión',
        default=False,
        tracking=True,
        help='Marcar si esta operación genera comisión para el operador'
    )
    
    commission_operator_id = fields.Many2one(
        'res.users',
        string='Operador que Comisiona',
        tracking=True,
        help='Operador que recibirá la comisión por esta operación'
    )
    
    commission_rate = fields.Float(
        string='Comisión (%)',
        default=0.0,
        tracking=True,
        help='Porcentaje de comisión sobre el monto de la operación'
    )
    
    commission_included = fields.Boolean(
        string='Comisión Incluida en el Monto',
        default=False,
        help='Si está marcado, la comisión ya está incluida en el monto de la operación'
    )
    
    commission_amount = fields.Float(
        string='Monto de Comisión',
        compute='_compute_commission_amount',
        store=True,
        help='Monto calculado de la comisión'
    )
    
    # Estado de liquidación
    commission_liquidated = fields.Boolean(
        string='Comisión Liquidada',
        readonly=True,
        default=False,
        tracking=True
    )
    
    commission_liquidation_id = fields.Many2one(
        'commission.liquidation',
        string='Liquidación de Comisión',
        readonly=True
    )
    
    @api.depends('has_commission', 'amount', 'commission_rate', 'commission_included')
    def _compute_commission_amount(self):
        """Calcula el monto de la comisión"""
        for operation in self:
            if operation.has_commission and operation.commission_rate > 0:
                if operation.commission_included:
                    # Si la comisión está incluida, calcular hacia atrás
                    # Monto = Base + Comisión
                    # Monto = Base + (Base * Rate/100)
                    # Monto = Base * (1 + Rate/100)
                    # Base = Monto / (1 + Rate/100)
                    base = operation.amount / (1 + operation.commission_rate / 100)
                    operation.commission_amount = operation.amount - base
                else:
                    # La comisión es adicional al monto
                    operation.commission_amount = operation.amount * operation.commission_rate / 100
            else:
                operation.commission_amount = 0.0
    
    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        """Valida la tasa de comisión"""
        for operation in self:
            if operation.commission_rate < 0:
                raise ValidationError(_('La tasa de comisión no puede ser negativa.'))
            if operation.commission_rate > 100:
                raise ValidationError(_('La tasa de comisión no puede ser mayor al 100%.'))
    
    @api.onchange('has_commission')
    def _onchange_has_commission(self):
        """Limpia campos de comisión si se desmarca"""
        if not self.has_commission:
            self.commission_operator_id = False
            self.commission_rate = 0.0
            self.commission_included = False
        else:
            # Sugerir el operador del partner si existe
            if self.partner_id and hasattr(self.partner_id, 'assigned_seller_id'):
                self.commission_operator_id = self.partner_id.assigned_seller_id
    
    @api.onchange('commission_operator_id')
    def _onchange_commission_operator(self):
        """Sugiere la tasa de comisión según el operador"""
        if self.commission_operator_id and self.has_commission:
            # Buscar el partner del operador
            partner = self.commission_operator_id.partner_id
            if partner and hasattr(partner, 'commission_transfers'):
                # Usar la comisión de transferencias como default
                self.commission_rate = partner.commission_transfers
    
    def action_complete(self):
        """Override para validar comisión antes de completar"""
        # Validar campos de comisión si aplica
        for operation in self:
            if operation.has_commission:
                if not operation.commission_operator_id:
                    raise ValidationError(_('Debe especificar el operador que comisiona.'))
                if operation.commission_rate <= 0:
                    raise ValidationError(_('La tasa de comisión debe ser mayor a cero.'))
        
        return super().action_complete()
    
    def action_view_commission_liquidation(self):
        """Ver la liquidación de comisión relacionada"""
        self.ensure_one()
        
        if not self.commission_liquidation_id:
            raise ValidationError(_('Esta operación no tiene una liquidación de comisión asociada.'))
        
        return {
            'name': _('Liquidación de Comisión'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.liquidation',
            'res_id': self.commission_liquidation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }