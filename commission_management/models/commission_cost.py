# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date


class CommissionCost(models.Model):
    _name = 'commission.cost'
    _description = 'Costos y Gastos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'
    
    # Identificación
    name = fields.Char(
        string='Descripción',
        required=True,
        tracking=True
    )
    
    code = fields.Char(
        string='Código',
        readonly=True,
        copy=False,
        default='Nuevo'
    )
    
    # Fechas
    date = fields.Date(
        string='Fecha del Costo',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Fecha en que se generó el costo'
    )
    
    liquidation_date = fields.Date(
        string='Fecha de Liquidación',
        tracking=True,
        help='Fecha en que se liquida/aplica el costo'
    )
    
    # Tipo de costo
    cost_type = fields.Selection([
        ('CF', 'Costo Fijo'),
        ('CV', 'Costo Variable'),
        ('CI', 'Costo de Inversión'),
        ('IMP', 'Impuesto')
    ], string='Tipo de Costo', required=True, tracking=True)
    
    cost_subtype = fields.Selection([
        ('bien', 'Bien'),
        ('servicio', 'Servicio')
    ], string='Subtipo', required=True, tracking=True)
    
    # Categoría adicional
    category_id = fields.Many2one(
        'commission.cost.category',
        string='Categoría',
        help='Categoría específica del costo'
    )
    
    # Montos
    amount = fields.Float(
        string='Monto',
        required=True,
        tracking=True
    )
    
    currency = fields.Selection([
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('USDT', 'USDT')
    ], string='Moneda', default='ARS', required=True, tracking=True)
    
    # Monto en ARS (para costos en otras monedas)
    amount_ars = fields.Float(
        string='Monto en ARS',
        compute='_compute_amount_ars',
        store=True,
        help='Monto convertido a pesos argentinos'
    )
    
    exchange_rate = fields.Float(
        string='Tipo de Cambio',
        help='Tipo de cambio usado para la conversión'
    )
    
    # Reinversión
    is_reinvestment = fields.Boolean(
        string='Es Reinversión',
        tracking=True,
        help='Marcar si este costo es una reinversión (queda en caja)'
    )
    
    # Relación con operación de caja
    cashbox_operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación de Caja',
        tracking=True,
        help='Operación de caja relacionada si el costo salió de caja'
    )
    
    # Proveedor
    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        tracking=True
    )
    
    # Referencia/Comprobante
    reference = fields.Char(
        string='Referencia/Comprobante',
        tracking=True
    )
    
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('applied', 'Aplicado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True, required=True)
    
    # Período de aplicación
    period_year = fields.Integer(
        string='Año',
        compute='_compute_period',
        store=True
    )
    
    period_month = fields.Integer(
        string='Mes',
        compute='_compute_period',
        store=True
    )
    
    # Liquidación de socios donde se aplicó
    partner_liquidation_id = fields.Many2one(
        'commission.partner.liquidation',
        string='Liquidación de Socios',
        readonly=True
    )
    
    # Notas
    notes = fields.Text(
        string='Observaciones'
    )
    
    # Adjuntos
    attachment_count = fields.Integer(
        string='Adjuntos',
        compute='_compute_attachment_count'
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
        """Override para generar código"""
        for vals in vals_list:
            if vals.get('code', 'Nuevo') == 'Nuevo':
                # Generar código según tipo
                cost_type = vals.get('cost_type', 'CF')
                sequence = self.env['ir.sequence'].next_by_code('commission.cost') or '001'
                vals['code'] = f'{cost_type}/{sequence}'
        return super().create(vals_list)
    
    @api.depends('date')
    def _compute_period(self):
        """Calcula el período del costo"""
        for record in self:
            if record.date:
                record.period_year = record.date.year
                record.period_month = record.date.month
            else:
                record.period_year = 0
                record.period_month = 0
    
    @api.depends('amount', 'currency', 'exchange_rate')
    def _compute_amount_ars(self):
        """Calcula el monto en ARS"""
        for record in self:
            if record.currency == 'ARS':
                record.amount_ars = record.amount
                record.exchange_rate = 1.0
            else:
                # Si hay tipo de cambio manual, usarlo
                if record.exchange_rate and record.exchange_rate > 0:
                    record.amount_ars = record.amount * record.exchange_rate
                else:
                    # Buscar tipo de cambio del módulo de divisas
                    # Por ahora, usar valor por defecto
                    record.amount_ars = record.amount
    
    def _compute_attachment_count(self):
        """Cuenta los adjuntos"""
        Attachment = self.env['ir.attachment']
        for record in self:
            record.attachment_count = Attachment.search_count([
                ('res_model', '=', 'commission.cost'),
                ('res_id', '=', record.id)
            ])
    
    @api.constrains('amount')
    def _check_amount(self):
        """Valida el monto"""
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('El monto debe ser mayor a cero.'))
    
    @api.constrains('date', 'liquidation_date')
    def _check_dates(self):
        """Valida las fechas"""
        for record in self:
            if record.liquidation_date and record.liquidation_date < record.date:
                raise ValidationError(_('La fecha de liquidación no puede ser anterior a la fecha del costo.'))
    
    @api.onchange('currency')
    def _onchange_currency(self):
        """Ajusta el tipo de cambio al cambiar la moneda"""
        if self.currency == 'ARS':
            self.exchange_rate = 1.0
        else:
            # Buscar último tipo de cambio conocido
            # Por implementar cuando se integre con el módulo de divisas
            pass
    
    @api.onchange('cashbox_operation_id')
    def _onchange_cashbox_operation(self):
        """Al seleccionar operación de caja, obtener datos"""
        if self.cashbox_operation_id:
            # Sugerir el monto
            if not self.amount:
                self.amount = self.cashbox_operation_id.amount
            
            # Obtener la moneda
            if self.cashbox_operation_id.currency_type:
                self.currency = self.cashbox_operation_id.currency_type
    
    def action_confirm(self):
        """Confirma el costo"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Solo se pueden confirmar costos en borrador.'))
        
        # Si no tiene fecha de liquidación, usar la fecha del costo
        if not self.liquidation_date:
            self.liquidation_date = self.date
        
        self.write({'state': 'confirmed'})
        
        return True
    
    def action_cancel(self):
        """Cancela el costo"""
        self.ensure_one()
        
        if self.state == 'applied':
            raise UserError(_('No se pueden cancelar costos ya aplicados en liquidaciones.'))
        
        self.write({'state': 'cancelled'})
        
        return True
    
    def action_reset_draft(self):
        """Vuelve a borrador"""
        self.ensure_one()
        
        if self.state == 'applied':
            raise UserError(_('No se pueden modificar costos ya aplicados.'))
        
        self.write({'state': 'draft'})
        
        return True
    
    def action_create_cashbox_operation(self):
        """Crea una operación de caja para este costo"""
        self.ensure_one()
        
        if self.cashbox_operation_id:
            raise UserError(_('Este costo ya tiene una operación de caja asociada.'))
        
        if self.state != 'confirmed':
            raise UserError(_('El costo debe estar confirmado para crear la operación de caja.'))
        
        # Abrir wizard para seleccionar caja
        return {
            'name': _('Crear Salida de Caja'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.cost.cashbox.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_cost_id': self.id,
                'default_amount': self.amount,
                'default_currency_type': self.currency,
            }
        }
    
    def action_view_attachments(self):
        """Ver adjuntos"""
        self.ensure_one()
        return {
            'name': _('Adjuntos'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'tree,form',
            'domain': [
                ('res_model', '=', 'commission.cost'),
                ('res_id', '=', self.id)
            ],
            'context': {
                'default_res_model': 'commission.cost',
                'default_res_id': self.id,
            }
        }
    
    @api.model
    def get_costs_by_period(self, year, month=None, cost_type=None):
        """Obtiene costos por período"""
        domain = [
            ('state', 'in', ['confirmed', 'applied']),
            ('period_year', '=', year)
        ]
        
        if month:
            domain.append(('period_month', '=', month))
        
        if cost_type:
            if isinstance(cost_type, list):
                domain.append(('cost_type', 'in', cost_type))
            else:
                domain.append(('cost_type', '=', cost_type))
        
        return self.search(domain)
    
    @api.model
    def get_total_by_type(self, year, month=None):
        """Obtiene totales por tipo de costo"""
        costs = self.get_costs_by_period(year, month)
        
        totals = {
            'CF': 0.0,
            'CV': 0.0,
            'CI': 0.0,
            'IMP': 0.0,
            'total': 0.0,
            'reinvestment': 0.0
        }
        
        for cost in costs:
            amount = cost.amount_ars
            totals[cost.cost_type] += amount
            totals['total'] += amount
            
            if cost.is_reinvestment:
                totals['reinvestment'] += amount
        
        return totals
    
    def name_get(self):
        """Personaliza el display name"""
        result = []
        for record in self:
            name = f'[{record.code}] {record.name}'
            result.append((record.id, name))
        return result


class CommissionCostCategory(models.Model):
    _name = 'commission.cost.category'
    _description = 'Categoría de Costo'
    _order = 'name'
    
    name = fields.Char(
        string='Nombre',
        required=True
    )
    
    code = fields.Char(
        string='Código'
    )
    
    parent_id = fields.Many2one(
        'commission.cost.category',
        string='Categoría Padre'
    )
    
    child_ids = fields.One2many(
        'commission.cost.category',
        'parent_id',
        string='Subcategorías'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'El código debe ser único'),
    ]
    
    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('No se puede crear una referencia recursiva en categorías.'))