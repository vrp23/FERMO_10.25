from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

class CommissionCajaWizard(models.TransientModel):
    _name = 'commission.caja.wizard'
    _description = 'Wizard para liquidación de comisiones de operaciones de caja'
    
    # Campos básicos
    name = fields.Char(string='Referencia', default='Nueva Liquidación')
    operator_id = fields.Many2one('res.users', string='Operador', required=True)
    commission_rate = fields.Float(string='Tasa de Comisión (%)', default=30.0, required=True)
    
    # Período
    period_start = fields.Date(string='Fecha Desde', required=True, 
                              default=lambda self: date.today().replace(day=1))
    period_end = fields.Date(string='Fecha Hasta', required=True,
                            default=lambda self: date.today())
    
    # Filtros
    include_deposits = fields.Boolean(string='Incluir Depósitos', default=True)
    include_withdrawals = fields.Boolean(string='Incluir Retiros', default=True)
    include_transfers = fields.Boolean(string='Incluir Transferencias', default=True)
    
    # Líneas calculadas
    line_ids = fields.One2many('commission.caja.wizard.line', 'wizard_id', string='Líneas')
    
    # Totales
    total_base = fields.Float(string='Base Total', compute='_compute_totals', store=True)
    total_commission = fields.Float(string='Comisión Total', compute='_compute_totals', store=True)
    operation_count = fields.Integer(string='Cantidad de Operaciones', compute='_compute_totals', store=True)
    
    @api.depends('line_ids.base_amount', 'line_ids.commission_amount')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_base = sum(wizard.line_ids.mapped('base_amount'))
            wizard.total_commission = sum(wizard.line_ids.mapped('commission_amount'))
            wizard.operation_count = len(wizard.line_ids)
    
    @api.onchange('operator_id')
    def _onchange_operator_id(self):
        """Al cambiar el operador, actualizar la tasa de comisión si tiene configurada"""
        if self.operator_id:
            partner = self.env['res.partner'].search([
                ('user_id', '=', self.operator_id.id)
            ], limit=1)
            
            if partner and partner.commission_transfers:
                self.commission_rate = partner.commission_transfers
    
    def action_calculate(self):
        """Calcula las comisiones basándose en los parámetros"""
        self.ensure_one()
        self._calculate_commissions()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'commission.caja.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
    
    def _calculate_commissions(self):
        """Calcula las comisiones de operaciones de caja"""
        self.ensure_one()
        
        # Limpiar líneas existentes
        self.line_ids.unlink()
        
        # Construir dominio base
        domain = [
            ('state', '=', 'done'),
            ('completion_date', '>=', self.period_start),
            ('completion_date', '<=', self.period_end),
            ('has_commission', '=', True),
            ('commission_liquidated', '=', False),
        ]
        
        # Filtrar por tipo de operación
        operation_types = []
        if self.include_deposits:
            operation_types.append('deposit')
        if self.include_withdrawals:
            operation_types.append('withdrawal')
        if self.include_transfers:
            operation_types.extend(['transfer_in', 'transfer_out'])
        
        if operation_types:
            domain.append(('operation_type', 'in', operation_types))
        else:
            raise UserError(_('Debe seleccionar al menos un tipo de operación.'))
        
        # Filtrar por operador
        if self.operator_id:
            domain.append(('commission_operator_id', '=', self.operator_id.id))
        
        operations = self.env['sucursales_cajas.operation'].search(domain, order='completion_date')
        
        # Crear líneas para cada operación
        sequence = 10
        for operation in operations:
            commission_rate = operation.commission_rate or self.commission_rate
            
            self.env['commission.caja.wizard.line'].create({
                'wizard_id': self.id,
                'sequence': sequence,
                'cashbox_operation_id': operation.id,
                'operation_number': operation.name,
                'operation_date': operation.completion_date,
                'partner_id': operation.partner_id.id,
                'operation_type': operation.operation_type,
                'currency_type': operation.currency_type,
                'base_amount': operation.commission_amount,
                'commission_rate': commission_rate,
                'commission_amount': operation.commission_amount,
            })
            
            sequence += 10
        
        if not self.line_ids:
            raise UserError(_('No se encontraron operaciones para liquidar con los criterios especificados.'))
        
        return True
    
    def action_create_liquidation(self):
        """Crea la liquidación de comisiones"""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_('No hay líneas para liquidar. Primero debe calcular las comisiones.'))
        
        # Crear la liquidación
        liquidation = self.env['commission.liquidation'].create({
            'operator_id': self.operator_id.id,
            'liquidation_type': 'caja',
            'date': fields.Date.today(),
            'period_start': self.period_start,
            'period_end': self.period_end,
            'state': 'draft',
        })
        
        # Crear las líneas de liquidación
        for wizard_line in self.line_ids:
            self.env['commission.liquidation.line'].create({
                'liquidation_id': liquidation.id,
                'sequence': wizard_line.sequence,
                'description': f'{wizard_line.operation_number} - {wizard_line.partner_id.name}',
                'source_model': 'sucursales_cajas.operation',
                'source_reference': wizard_line.operation_number,
                'operation_date': wizard_line.operation_date,
                'partner_id': wizard_line.partner_id.id,
                'base_amount': wizard_line.base_amount,
                'commission_rate': wizard_line.commission_rate,
                'commission_amount': wizard_line.commission_amount,
                'cashbox_operation_id': wizard_line.cashbox_operation_id.id,
            })
            
            # Marcar la operación como liquidada
            wizard_line.cashbox_operation_id.write({
                'commission_liquidated': True,
                'commission_liquidation_id': liquidation.id,
            })
        
        # Abrir la liquidación creada
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'commission.liquidation',
            'view_mode': 'form',
            'res_id': liquidation.id,
            'target': 'current',
        }


class CommissionCajaWizardLine(models.TransientModel):
    _name = 'commission.caja.wizard.line'
    _description = 'Línea del Wizard de Comisiones de Caja'
    _order = 'sequence, id'
    
    wizard_id = fields.Many2one('commission.caja.wizard', string='Wizard', 
                                required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia', default=10)
    
    # Datos de la operación
    cashbox_operation_id = fields.Many2one('sucursales_cajas.operation', string='Operación', required=True)
    operation_number = fields.Char(string='Número Operación', required=True)
    operation_date = fields.Date(string='Fecha Operación')
    
    # Partner
    partner_id = fields.Many2one('res.partner', string='Cliente')
    
    # Tipo de operación
    operation_type = fields.Selection([
        ('deposit', 'Depósito'),
        ('withdrawal', 'Retiro'),
        ('transfer_in', 'Transferencia Entrada'),
        ('transfer_out', 'Transferencia Salida'),
    ], string='Tipo')
    
    # Moneda
    currency_type = fields.Selection([
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('EUR', 'Euros'),
    ], string='Moneda')
    
    # Valores
    base_amount = fields.Float(string='Monto Base', required=True)
    
    # Comisión
    commission_rate = fields.Float(string='Tasa (%)', required=True)
    commission_amount = fields.Float(string='Comisión', required=True)
    
    @api.onchange('base_amount', 'commission_rate')
    def _onchange_calculate_commission(self):
        """Recalcula la comisión cuando cambian los valores"""
        if self.base_amount and self.commission_rate:
            self.commission_amount = self.base_amount * self.commission_rate / 100