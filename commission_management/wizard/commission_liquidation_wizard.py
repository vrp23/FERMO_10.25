# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CommissionLiquidationWizard(models.TransientModel):
    _name = 'commission.liquidation.wizard'
    _description = 'Wizard para crear nueva liquidación'
    
    operator_id = fields.Many2one(
        'res.users',
        string='Operador',
        required=True,
        default=lambda self: self.env.user
    )
    
    liquidation_type = fields.Selection([
        ('cheques', 'Cheques'),
        ('divisas', 'Divisas'),
        ('caja', 'Operaciones de Caja'),
        ('manual', 'Manual')
    ], string='Tipo de Liquidación', required=True, default='cheques')
    
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.today
    )
    
    # Para divisas
    period_start = fields.Date(
        string='Período Desde'
    )
    
    period_end = fields.Date(
        string='Período Hasta'
    )
    
    @api.onchange('liquidation_type')
    def _onchange_liquidation_type(self):
        """Ajusta campos según el tipo"""
        if self.liquidation_type == 'divisas':
            # Sugerir el mes actual
            from datetime import date
            today = date.today()
            self.period_start = today.replace(day=1)
            
            # Último día del mes
            if today.month == 12:
                self.period_end = today.replace(day=31)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
                from datetime import timedelta
                self.period_end = next_month - timedelta(days=1)
    
    def action_create_liquidation(self):
        """Crea la liquidación y abre el formulario"""
        self.ensure_one()
        
        # Validaciones
        if self.liquidation_type == 'divisas':
            if not self.period_start or not self.period_end:
                raise UserError(_('Debe especificar el período para liquidaciones de divisas.'))
            if self.period_start > self.period_end:
                raise UserError(_('La fecha inicial no puede ser mayor a la fecha final.'))
        
        # Crear liquidación
        liquidation_vals = {
            'operator_id': self.operator_id.id,
            'liquidation_type': self.liquidation_type,
            'date': self.date,
            'state': 'draft',
        }
        
        if self.liquidation_type == 'divisas':
            liquidation_vals.update({
                'period_start': self.period_start,
                'period_end': self.period_end,
            })
        
        liquidation = self.env['commission.liquidation'].create(liquidation_vals)
        
        # Abrir la liquidación creada
        return {
            'name': _('Liquidación de Comisiones'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.liquidation',
            'res_id': liquidation.id,
            'view_mode': 'form',
            'target': 'current',
        }