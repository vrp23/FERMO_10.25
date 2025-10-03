from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class CommissionCostCashboxWizard(models.TransientModel):
    _name = 'commission.cost.cashbox.wizard'
    _description = 'Wizard para registrar costos de caja'
    
    # Campo opcional ahora
    liquidation_id = fields.Many2one(
        'commission.liquidation',
        string='Liquidación',
        required=False,  # CAMBIO: Ya no es requerido
        readonly=True,
        default=lambda self: self.env.context.get('default_liquidation_id')
    )
    
    description = fields.Char(
        string='Descripción',
        required=True,
        default=lambda self: self.env.context.get('default_description', 'Gasto de caja')
    )
    
    amount = fields.Float(
        string='Monto',
        required=True,
        default=lambda self: self.env.context.get('default_amount', 0.0)
    )
    
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.today
    )
    
    cost_type = fields.Selection([
        ('expense', 'Gasto'),
        ('adjustment', 'Ajuste'),
        ('other', 'Otro')
    ], string='Tipo', default='expense', required=True)
    
    notes = fields.Text(string='Notas')
    
    # Campo para operación de caja si viene de ahí
    cashbox_operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación de Caja',
        default=lambda self: self.env.context.get('default_cashbox_operation_id')
    )
    
    def action_confirm(self):
        """Confirma y crea el registro de costo o gasto"""
        self.ensure_one()
        
        if self.amount <= 0:
            raise UserError(_('El monto debe ser mayor a cero.'))
        
        # Si hay liquidación, crear costo asociado
        if self.liquidation_id:
            cost = self.env['commission.cost'].create({
                'liquidation_id': self.liquidation_id.id,
                'description': self.description,
                'amount': self.amount,
                'date': self.date,
                'cost_type': self.cost_type,
                'notes': self.notes,
            })
            return {'type': 'ir.actions.act_window_close'}
        
        # Si no hay liquidación, es un gasto general de caja
        # Aquí deberías crear el registro correspondiente en el módulo de cajas
        if self.cashbox_operation_id:
            # Actualizar la operación de caja o crear un registro relacionado
            self.cashbox_operation_id.write({
                'notes': (self.cashbox_operation_id.notes or '') + f'\nGasto: {self.description} - ${self.amount}'
            })
        
        return {'type': 'ir.actions.act_window_close'}