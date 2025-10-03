# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime
import calendar
import logging

_logger = logging.getLogger(__name__)


class CommissionPartnerLiquidation(models.Model):
    _name = 'commission.partner.liquidation'
    _description = 'Liquidación de Comisiones de Socios'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'
    
    # Identificación
    name = fields.Char(
        string='Número',
        required=True,
        readonly=True,
        default='Nueva',
        copy=False,
        tracking=True
    )
    
    # Fecha
    date = fields.Date(
        string='Fecha de Liquidación',
        required=True,
        default=fields.Date.today,
        tracking=True,
        states={'confirmed': [('readonly', True)], 'paid': [('readonly', True)]}
    )
    
    # Período
    period_year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: date.today().year,
        tracking=True,
        states={'confirmed': [('readonly', True)], 'paid': [('readonly', True)]}
    )
    
    period_month = fields.Integer(
        string='Mes',
        required=True,
        default=lambda self: date.today().month,
        tracking=True,
        states={'confirmed': [('readonly', True)], 'paid': [('readonly', True)]}
    )
    
    period_display = fields.Char(
        string='Período',
        compute='_compute_period_display',
        store=True
    )
    
    # Cálculo de ganancia
    gross_income = fields.Float(
        string='Ingresos Brutos',
        compute='_compute_profit_calculation',
        store=True,
        help='Total de ingresos del período'
    )
    
    gross_expenses = fields.Float(
        string='Egresos Brutos',
        compute='_compute_profit_calculation',
        store=True,
        help='Total de egresos del período'
    )
    
    gross_profit = fields.Float(
        string='Ganancia Bruta',
        compute='_compute_profit_calculation',
        store=True,
        help='Ingresos - Egresos'
    )
    
    total_operator_commissions = fields.Float(
        string='Comisiones de Operadores',
        compute='_compute_profit_calculation',
        store=True,
        help='Total de comisiones pagadas a operadores en el período'
    )
    
    total_costs = fields.Float(
        string='Total de Costos',
        compute='_compute_profit_calculation',
        store=True,
        help='Total de costos del período'
    )
    
    # Desglose de costos
    cost_cf = fields.Float(
        string='Costos Fijos',
        compute='_compute_profit_calculation',
        store=True
    )
    
    cost_cv = fields.Float(
        string='Costos Variables',
        compute='_compute_profit_calculation',
        store=True
    )
    
    cost_ci = fields.Float(
        string='Costos de Inversión',
        compute='_compute_profit_calculation',
        store=True
    )
    
    cost_imp = fields.Float(
        string='Impuestos',
        compute='_compute_profit_calculation',
        store=True
    )
    
    reinvestment_amount = fields.Float(
        string='Monto Reinvertido',
        compute='_compute_profit_calculation',
        store=True,
        help='Monto de costos marcados como reinversión'
    )
    
    net_profit = fields.Float(
        string='Ganancia Neta',
        compute='_compute_profit_calculation',
        store=True,
        help='Ganancia Bruta - Comisiones Operadores - Costos'
    )
    
    # Líneas de socios
    line_ids = fields.One2many(
        'commission.partner.liquidation.line',
        'liquidation_id',
        string='Distribución entre Socios',
        states={'confirmed': [('readonly', True)], 'paid': [('readonly', True)]}
    )
    
    # Total de comisiones
    total_commission = fields.Float(
        string='Total Comisiones Socios',
        compute='_compute_total_commission',
        store=True
    )
    
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Calculado'),
        ('confirmed', 'Confirmado'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True, required=True)
    
    # IDs de registros incluidos
    operator_liquidation_ids = fields.Many2many(
        'commission.liquidation',
        'partner_liquidation_operator_rel',
        'partner_liquidation_id',
        'operator_liquidation_id',
        string='Liquidaciones de Operadores Incluidas',
        domain=[('state', '=', 'paid')]
    )
    
    cost_ids = fields.Many2many(
        'commission.cost',
        'partner_liquidation_cost_rel',
        'partner_liquidation_id',
        'cost_id',
        string='Costos Incluidos',
        domain=[('state', '=', 'confirmed')]
    )
    
    # Notas
    notes = fields.Text(
        string='Observaciones'
    )
    
    # Compañía
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override para generar número de secuencia"""
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                year = vals.get('period_year', date.today().year)
                month = vals.get('period_month', date.today().month)
                vals['name'] = f'LIQ-SOC/{year}/{month:02d}'
        return super().create(vals_list)
    
    @api.depends('period_year', 'period_month')
    def _compute_period_display(self):
        """Calcula el período para mostrar"""
        months = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        
        for record in self:
            if record.period_year and record.period_month:
                month_name = months.get(record.period_month, '')
                record.period_display = f'{month_name} {record.period_year}'
            else:
                record.period_display = ''
    
    @api.depends('period_year', 'period_month', 'operator_liquidation_ids', 'cost_ids')
    def _compute_profit_calculation(self):
        """Calcula todos los componentes de la ganancia"""
        for record in self:
            # Inicializar valores
            income = 0.0
            expenses = 0.0
            operator_commissions = 0.0
            
            # Fechas del período
            period_start = date(record.period_year, record.period_month, 1)
            period_end = date(record.period_year, record.period_month, 
                            calendar.monthrange(record.period_year, record.period_month)[1])
            
            # 1. Calcular ingresos y egresos de CHEQUES
            cheques_vendidos = self.env['chequera.check'].search([
                ('state', '=', 'vendido'),
                '|',
                    '&',
                        ('sale_operation_id', '!=', False),
                        ('sale_operation_id.fecha_operacion', '>=', period_start),
                        ('sale_operation_id.fecha_operacion', '<=', period_end),
                    '&',
                        ('sale_operation_id', '=', False),
                        ('write_date', '>=', datetime.combine(period_start, datetime.min.time())),
                        ('write_date', '<=', datetime.combine(period_end, datetime.max.time()))
            ])
            
            income_cheques = sum(cheques_vendidos.mapped('precio_venta'))
            expenses_cheques = sum(cheques_vendidos.mapped('precio_compra'))
            
            _logger.info(f"Cheques del período: {len(cheques_vendidos)}, Ingresos: {income_cheques}, Egresos: {expenses_cheques}")
            
            # 2. Calcular ingresos y egresos de DIVISAS
            divisas_operations = self.env['divisas.currency'].search([
                ('state', '=', 'confirmed'),
                ('date', '>=', period_start),
                ('date', '<=', period_end)
            ])
            
            # Separar compras y ventas
            divisas_ventas = divisas_operations.filtered(lambda x: x.operation_type == 'sell')
            divisas_compras = divisas_operations.filtered(lambda x: x.operation_type == 'buy')
            
            # Para divisas, necesitamos considerar el monto en ARS
            income_divisas = sum(divisas_ventas.mapped('payment_amount'))  # Lo que recibimos en ARS
            expenses_divisas = sum(divisas_compras.mapped('payment_amount'))  # Lo que pagamos en ARS
            
            _logger.info(f"Divisas del período: {len(divisas_operations)}, Ingresos: {income_divisas}, Egresos: {expenses_divisas}")
            
            # 3. Calcular ingresos y egresos de OPERACIONES DE CAJA
            caja_operations = self.env['sucursales_cajas.operation'].search([
                ('state', '=', 'done'),
                ('completion_date', '>=', period_start),
                ('completion_date', '<=', period_end)
            ])
            
            # Para caja, los retiros son egresos y los depósitos son ingresos
            caja_ingresos = caja_operations.filtered(lambda x: x.operation_type == 'deposit')
            caja_egresos = caja_operations.filtered(lambda x: x.operation_type == 'withdrawal')
            
            income_caja = sum(caja_ingresos.mapped('amount'))
            expenses_caja = sum(caja_egresos.mapped('amount'))
            
            _logger.info(f"Operaciones de caja del período: {len(caja_operations)}, Ingresos: {income_caja}, Egresos: {expenses_caja}")
            
            # Totalizar
            income = income_cheques + income_divisas + income_caja
            expenses = expenses_cheques + expenses_divisas + expenses_caja
            
            # 4. Comisiones de operadores del período
            if record.operator_liquidation_ids:
                operator_commissions = sum(record.operator_liquidation_ids.mapped('total_commission'))
            else:
                # Buscar liquidaciones del período automáticamente
                domain = [
                    ('state', '=', 'paid'),
                    ('date', '>=', period_start),
                    ('date', '<=', period_end)
                ]
                liquidations = self.env['commission.liquidation'].search(domain)
                operator_commissions = sum(liquidations.mapped('total_commission'))
            
            # 5. Costos del período
            cost_totals = {
                'CF': 0.0,
                'CV': 0.0,
                'CI': 0.0,
                'IMP': 0.0,
                'total': 0.0,
                'reinvestment': 0.0
            }
            
            if record.cost_ids:
                for cost in record.cost_ids:
                    amount = cost.amount_ars
                    cost_totals[cost.cost_type] += amount
                    cost_totals['total'] += amount
                    if cost.is_reinvestment:
                        cost_totals['reinvestment'] += amount
            else:
                # Buscar costos del período automáticamente
                costs = self.env['commission.cost'].get_costs_by_period(
                    record.period_year, 
                    record.period_month
                )
                for cost in costs:
                    amount = cost.amount_ars
                    cost_totals[cost.cost_type] += amount
                    cost_totals['total'] += amount
                    if cost.is_reinvestment:
                        cost_totals['reinvestment'] += amount
            
            # Asignar valores
            record.gross_income = income
            record.gross_expenses = expenses
            record.gross_profit = income - expenses
            record.total_operator_commissions = operator_commissions
            record.cost_cf = cost_totals['CF']
            record.cost_cv = cost_totals['CV']
            record.cost_ci = cost_totals['CI']
            record.cost_imp = cost_totals['IMP']
            record.total_costs = cost_totals['total']
            record.reinvestment_amount = cost_totals['reinvestment']
            record.net_profit = record.gross_profit - operator_commissions - cost_totals['total']
    
    @api.depends('line_ids.commission_amount')
    def _compute_total_commission(self):
        """Calcula el total de comisiones de socios"""
        for record in self:
            record.total_commission = sum(record.line_ids.mapped('commission_amount'))
    
    @api.constrains('period_year', 'period_month')
    def _check_period(self):
        """Valida el período"""
        for record in self:
            if record.period_month < 1 or record.period_month > 12:
                raise ValidationError(_('El mes debe estar entre 1 y 12.'))
            
            # Verificar que no exista otra liquidación para el mismo período
            existing = self.search([
                ('id', '!=', record.id),
                ('period_year', '=', record.period_year),
                ('period_month', '=', record.period_month),
                ('state', '!=', 'cancelled')
            ])
            
            if existing:
                raise ValidationError(
                    _('Ya existe una liquidación de socios para el período %s.') 
                    % record.period_display
                )
    
    def action_calculate(self):
        """Calcula la distribución entre socios"""
        self.ensure_one()
        
        if self.state not in ['draft', 'calculated']:
            raise UserError(_('Solo se pueden calcular liquidaciones en borrador.'))
        
        # Limpiar líneas existentes
        self.line_ids.unlink()
        
        # Buscar socios activos
        partners = self.env['res.partner'].search([
            ('is_commission_partner', '=', True),
            ('active', '=', True),
            ('commission_percentage', '>', 0)
        ])
        
        if not partners:
            raise UserError(_('No hay socios configurados con porcentaje de comisión para liquidar.'))
        
        # Verificar que la suma de porcentajes sea 100%
        total_percentage = sum(partners.mapped('commission_percentage'))
        if abs(total_percentage - 100.0) > 0.01:
            raise UserError(
                _('La suma de porcentajes de los socios debe ser 100%%. Actualmente es %.2f%%') 
                % total_percentage
            )
        
        # Crear líneas de distribución
        for partner in partners:
            if partner.commission_percentage > 0:
                self.env['commission.partner.liquidation.line'].create({
                    'liquidation_id': self.id,
                    'partner_id': partner.id,
                    'commission_rate': partner.commission_percentage,
                    'base_amount': self.net_profit,
                })
        
        # Marcar costos como aplicados
        if self.cost_ids:
            self.cost_ids.write({
                'state': 'applied',
                'partner_liquidation_id': self.id
            })
        
        self.write({'state': 'calculated'})
        
        return True
    
    def action_confirm(self):
        """Confirma la liquidación"""
        self.ensure_one()
        
        if self.state != 'calculated':
            raise UserError(_('Debe calcular la distribución antes de confirmar.'))
        
        if not self.line_ids:
            raise UserError(_('No hay líneas de distribución para confirmar.'))
        
        if self.net_profit < 0:
            raise UserError(_('No se puede confirmar una liquidación con ganancia neta negativa.'))
        
        self.write({'state': 'confirmed'})
        
        return True
    
    def action_pay(self):
        """Paga las comisiones a los socios"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise UserError(_('Solo se pueden pagar liquidaciones confirmadas.'))
        
        # Crear movimientos en wallet para cada socio
        for line in self.line_ids:
            if line.commission_amount > 0:
                movement_vals = {
                    'partner_id': line.partner_id.id,
                    'tipo': 'partner_commission',
                    'monto': line.commission_amount,
                    'fecha': fields.Date.today(),
                    'notes': f'Comisión de socio - {self.name} - {self.period_display}',
                    'state': 'confirmado'
                }
                
                movement = self.env['chequera.wallet.movement'].create(movement_vals)
                line.wallet_movement_id = movement.id
        
        self.write({'state': 'paid'})
        
        return True
    
    def action_cancel(self):
        """Cancela la liquidación"""
        self.ensure_one()
        
        if self.state == 'paid':
            raise UserError(_('No se pueden cancelar liquidaciones pagadas.'))
        
        # Si había costos aplicados, revertirlos
        if self.cost_ids and self.state == 'calculated':
            self.cost_ids.write({
                'state': 'confirmed',
                'partner_liquidation_id': False
            })
        
        self.write({'state': 'cancelled'})
        
        return True
    
    def action_view_operator_liquidations(self):
        """Ver liquidaciones de operadores incluidas"""
        self.ensure_one()
        
        return {
            'name': _('Liquidaciones de Operadores'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.liquidation',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.operator_liquidation_ids.ids)],
            'context': {'create': False}
        }
    
    def action_view_costs(self):
        """Ver costos incluidos"""
        self.ensure_one()
        
        return {
            'name': _('Costos del Período'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.cost',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.cost_ids.ids)],
            'context': {'create': False}
        }
    
    def action_print_report(self):
        """Imprime reporte de liquidación"""
        self.ensure_one()
        # TODO: Implementar reporte
        raise UserError(_('Reporte en desarrollo.'))


class CommissionPartnerLiquidationLine(models.Model):
    _name = 'commission.partner.liquidation.line'
    _description = 'Línea de Liquidación de Socio'
    _order = 'liquidation_id, sequence'
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    liquidation_id = fields.Many2one(
        'commission.partner.liquidation',
        string='Liquidación',
        required=True,
        ondelete='cascade'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Socio',
        required=True,
        domain=[('is_commission_partner', '=', True)]
    )
    
    commission_rate = fields.Float(
        string='Porcentaje (%)',
        required=True
    )
    
    base_amount = fields.Float(
        string='Base (Ganancia Neta)',
        required=True
    )
    
    commission_amount = fields.Float(
        string='Comisión',
        compute='_compute_commission_amount',
        store=True
    )
    
    wallet_movement_id = fields.Many2one(
        'chequera.wallet.movement',
        string='Movimiento de Pago',
        readonly=True
    )
    
    notes = fields.Text(
        string='Observaciones'
    )
    
    @api.depends('base_amount', 'commission_rate')
    def _compute_commission_amount(self):
        """Calcula el monto de comisión"""
        for line in self:
            line.commission_amount = line.base_amount * line.commission_rate / 100.0