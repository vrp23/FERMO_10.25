from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

class CommissionDivisasWizard(models.TransientModel):
    _name = 'commission.divisas.wizard'
    _description = 'Wizard para liquidación de comisiones de divisas'
    
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
    include_usd = fields.Boolean(string='Incluir USD', default=True)
    include_usdt = fields.Boolean(string='Incluir USDT', default=True)
    
    # Líneas calculadas
    line_ids = fields.One2many('commission.divisas.wizard.line', 'wizard_id', string='Líneas')
    
    # Totales
    total_base = fields.Float(string='Base Total (ARS)', compute='_compute_totals', store=True)
    total_base_usd = fields.Float(string='Base Total (USD)', compute='_compute_totals', store=True)
    total_commission = fields.Float(string='Comisión Total', compute='_compute_totals', store=True)
    operation_count = fields.Integer(string='Cantidad de Operaciones', compute='_compute_totals', store=True)
    
    @api.depends('line_ids.base_amount', 'line_ids.commission_amount')
    def _compute_totals(self):
        for wizard in self:
            lines_ars = wizard.line_ids.filtered(lambda l: l.profit_currency == 'ARS')
            lines_usd = wizard.line_ids.filtered(lambda l: l.profit_currency == 'USD')
            
            wizard.total_base = sum(lines_ars.mapped('base_amount'))
            wizard.total_base_usd = sum(lines_usd.mapped('base_amount'))
            wizard.total_commission = sum(wizard.line_ids.mapped('commission_amount'))
            wizard.operation_count = len(wizard.line_ids)
    
    @api.onchange('operator_id')
    def _onchange_operator_id(self):
        """Al cambiar el operador, actualizar la tasa de comisión si tiene configurada"""
        if self.operator_id:
            partner = self.env['res.partner'].search([
                ('user_id', '=', self.operator_id.id)
            ], limit=1)
            
            if partner and partner.commission_dollars:
                self.commission_rate = partner.commission_dollars
    
    def action_calculate(self):
        """Calcula las comisiones basándose en los parámetros"""
        self.ensure_one()
        self._calculate_commissions()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'commission.divisas.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
    
    def _calculate_commissions(self):
        """Calcula las comisiones basándose en la ganancia FIFO real"""
        self.ensure_one()
        
        # Limpiar líneas existentes
        self.line_ids.unlink()
        
        # Buscar operaciones de VENTA en el período (solo las ventas tienen ganancia)
        domain = [
            ('operation_type', '=', 'sell'),
            ('state', '=', 'confirmed'),
            ('date', '>=', self.period_start),
            ('date', '<=', self.period_end),
            ('is_fifo_processed', '=', True)  # Solo operaciones con FIFO procesado
        ]
        
        # Filtrar por tipo de divisa
        currency_types = []
        if self.include_usd:
            currency_types.append('USD')
        if self.include_usdt:
            currency_types.append('USDT')
        
        if currency_types:
            domain.append(('currency_type', 'in', currency_types))
        else:
            raise UserError(_('Debe seleccionar al menos un tipo de divisa.'))
        
        # Filtrar por operador si está especificado
        if self.operator_id:
            # Buscar clientes asignados a este operador
            assigned_partners = self.env['res.partner'].search([
                ('assigned_seller_id', '=', self.operator_id.id)
            ])
            if assigned_partners:
                domain.append(('partner_id', 'in', assigned_partners.ids))
        
        operations = self.env['divisas.currency'].search(domain, order='date')
        
        # Procesar cada operación
        sequence = 10
        for operation in operations:
            # Solo procesar si tiene consumos FIFO
            if not operation.lot_consumption_ids:
                continue
            
            # Obtener consumos activos
            active_consumptions = operation.lot_consumption_ids.filtered(
                lambda c: c.state == 'active'
            )
            
            if not active_consumptions:
                continue
            
            # Sumar ganancias por moneda
            operation_profit_ars = sum(active_consumptions.mapped('profit_ars'))
            operation_profit_usd = sum(active_consumptions.mapped('profit_usd'))
            
            # Determinar el operador responsable
            responsible_operator = operation.partner_id.assigned_seller_id or self.operator_id
            
            # Si no hay operador asignado, saltar
            if not responsible_operator:
                continue
            
            # Obtener la tasa de comisión según el tipo
            commission_rate = self.commission_rate
            partner = operation.partner_id
            
            if operation.currency_type == 'USD' and hasattr(partner, 'commission_dollars'):
                if partner.commission_dollars > 0:
                    commission_rate = partner.commission_dollars
            elif operation.currency_type == 'USDT' and hasattr(partner, 'commission_crypto'):
                if partner.commission_crypto > 0:
                    commission_rate = partner.commission_crypto
            
            # Crear líneas según la moneda de ganancia
            if operation_profit_ars > 0:
                self.env['commission.divisas.wizard.line'].create({
                    'wizard_id': self.id,
                    'sequence': sequence,
                    'currency_operation_id': operation.id,
                    'operation_number': operation.name,
                    'operation_date': operation.date,
                    'partner_id': operation.partner_id.id,
                    'currency_type': operation.currency_type,
                    'amount': operation.amount,
                    'exchange_rate': operation.exchange_rate,
                    'base_amount': operation_profit_ars,
                    'commission_rate': commission_rate,
                    'commission_amount': operation_profit_ars * commission_rate / 100,
                    'profit_currency': 'ARS',
                })
                sequence += 10
            
            if operation_profit_usd > 0:
                # Para ganancias en USD (conversiones), usar tasa especial si existe
                usd_commission_rate = commission_rate
                if hasattr(partner, 'commission_dollars') and partner.commission_dollars > 0:
                    usd_commission_rate = partner.commission_dollars
                
                self.env['commission.divisas.wizard.line'].create({
                    'wizard_id': self.id,
                    'sequence': sequence,
                    'currency_operation_id': operation.id,
                    'operation_number': operation.name,
                    'operation_date': operation.date,
                    'partner_id': operation.partner_id.id,
                    'currency_type': operation.currency_type,
                    'amount': operation.amount,
                    'exchange_rate': operation.exchange_rate,
                    'base_amount': operation_profit_usd,
                    'commission_rate': usd_commission_rate,
                    'commission_amount': operation_profit_usd * usd_commission_rate / 100,
                    'profit_currency': 'USD',
                })
                sequence += 10
        
        if not self.line_ids:
            raise UserError(_('No se encontraron operaciones con ganancia para liquidar en el período especificado.'))
        
        return True
    
    def action_create_liquidation(self):
        """Crea la liquidación de comisiones"""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_('No hay líneas para liquidar. Primero debe calcular las comisiones.'))
        
        # Crear la liquidación
        liquidation = self.env['commission.liquidation'].create({
            'operator_id': self.operator_id.id,
            'liquidation_type': 'divisas',
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
                'description': f'{wizard_line.operation_number} - {wizard_line.currency_type} - {wizard_line.partner_id.name}',
                'source_model': 'divisas.currency',
                'source_reference': wizard_line.operation_number,
                'operation_date': wizard_line.operation_date,
                'partner_id': wizard_line.partner_id.id,
                'base_amount': wizard_line.base_amount,
                'commission_rate': wizard_line.commission_rate,
                'commission_amount': wizard_line.commission_amount,
                'currency_operation_id': wizard_line.currency_operation_id.id,
                'operation_type': 'sell',
                'profit_currency': wizard_line.profit_currency,
            })
            
            # Marcar la operación como liquidada
            wizard_line.currency_operation_id.write({
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


class CommissionDivisasWizardLine(models.TransientModel):
    _name = 'commission.divisas.wizard.line'
    _description = 'Línea del Wizard de Comisiones de Divisas'
    _order = 'sequence, id'
    
    wizard_id = fields.Many2one('commission.divisas.wizard', string='Wizard', 
                                required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia', default=10)
    
    # Datos de la operación
    currency_operation_id = fields.Many2one('divisas.currency', string='Operación', required=True)
    operation_number = fields.Char(string='Número Operación', required=True)
    operation_date = fields.Date(string='Fecha Operación')
    
    # Partner
    partner_id = fields.Many2one('res.partner', string='Cliente')
    
    # Divisa
    currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
    ], string='Divisa')
    
    # Valores
    amount = fields.Float(string='Cantidad')
    exchange_rate = fields.Float(string='Tipo de Cambio')
    base_amount = fields.Float(string='Ganancia', required=True)
    
    # Moneda de la ganancia
    profit_currency = fields.Selection([
        ('ARS', 'ARS'),
        ('USD', 'USD')
    ], string='Moneda', default='ARS')
    
    # Comisión
    commission_rate = fields.Float(string='Tasa (%)', required=True)
    commission_amount = fields.Float(string='Comisión', required=True)
    
    @api.onchange('base_amount', 'commission_rate')
    def _onchange_calculate_commission(self):
        """Recalcula la comisión cuando cambian los valores"""
        if self.base_amount and self.commission_rate:
            self.commission_amount = self.base_amount * self.commission_rate / 100