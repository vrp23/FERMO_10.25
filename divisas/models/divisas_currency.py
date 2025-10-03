# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class DivisasCurrency(models.Model):
    _name = 'divisas.currency'
    _description = 'Operación de Divisa/Cripto'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    # Campos básicos
    name = fields.Char(string='Referencia', required=True, copy=False, 
                       readonly=True, default=lambda self: _('Nuevo'))
    
    # Estado de la operación
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    # Tipo de operación
    operation_type = fields.Selection([
        ('buy', 'Compra'),
        ('sell', 'Venta')
    ], string='Tipo de Operación', required=True, tracking=True)
    
    # Fechas
    date = fields.Date(string='Fecha de Operación', required=True, 
                       default=fields.Date.context_today, tracking=True)
    
    # Cliente/Proveedor
    partner_id = fields.Many2one('res.partner', string='Cliente/Contacto', 
                                 required=True, tracking=True)
    
    # Monedas de la operación (ahora como selección directa)
    currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
        ('ARS', 'Pesos (ARS)')
    ], string='Moneda', required=True, tracking=True)
    
    payment_currency_type = fields.Selection([
        ('ARS', 'Pesos (ARS)'),
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)')
    ], string='Moneda de Pago', required=True, tracking=True)
    
    # Montos
    amount = fields.Float(string='Monto', required=True, tracking=True, default=1.0)
    payment_amount = fields.Float(string='Monto a Pagar', compute='_compute_payment_amount', 
                                 store=True, tracking=True)
    
    # Tipo de cambio
    exchange_rate = fields.Float(string='Tipo de Cambio', digits=(16, 6), 
                                required=True, tracking=True, default=1.0)
    is_custom_rate = fields.Boolean(string='Tipo de Cambio Personalizado', default=False)
    
    # CAMPOS NUEVOS PARA FIFO
    # Ganancia calculada por FIFO en ARS (para operaciones con ARS)
    profit_ars = fields.Float(string='Ganancia (ARS)', 
                             readonly=True,
                             digits=(16, 2),
                             help='Ganancia calculada por método FIFO en ARS')
    
    # Ganancia calculada por FIFO en USD (para conversiones USD/USDT)
    profit_usd = fields.Float(string='Ganancia (USD)', 
                             readonly=True,
                             digits=(16, 2),
                             help='Ganancia calculada en USD para conversiones USD/USDT')
    
    # Indica en qué moneda se calcula la ganancia
    profit_currency = fields.Selection([
        ('ARS', 'ARS'),
        ('USD', 'USD')
    ], string='Moneda de Ganancia',
       compute='_compute_profit_currency',
       store=True)
    
    # Indica si es una conversión entre USD y USDT
    is_conversion = fields.Boolean(string='Es Conversión USD/USDT',
                                  compute='_compute_is_conversion',
                                  store=True)
    
    # Indica si se procesó FIFO
    is_fifo_processed = fields.Boolean(string='FIFO Procesado',
                                      readonly=True,
                                      default=False)
    
    # Lote de inventario creado (para compras)
    inventory_lot_id = fields.Many2one('divisas.inventory.lot',
                                      string='Lote de Inventario',
                                      readonly=True)
    
    # Consumos de lotes (para ventas)
    lot_consumption_ids = fields.One2many('divisas.lot.consumption',
                                         'sale_operation_id',
                                         string='Consumos de Lotes')
    
    # Total consumido (para validación)
    total_consumed = fields.Float(string='Total Consumido',
                                 compute='_compute_total_consumed',
                                 store=True)
    
    # Notas
    notes = fields.Text(string='Notas')
    
    # Wallet Movement
    wallet_movement_id = fields.Many2one('divisas.wallet.movement', string='Movimiento de Wallet', 
                                         readonly=True)
    
    # Multi-compañía
    company_id = fields.Many2one('res.company', string='Compañía', 
                                required=True, default=lambda self: self.env.company)
    
    @api.depends('currency_type', 'payment_currency_type')
    def _compute_is_conversion(self):
        """Determina si es una conversión entre USD y USDT"""
        for record in self:
            currencies = {record.currency_type, record.payment_currency_type}
            record.is_conversion = currencies == {'USD', 'USDT'}
    
    @api.depends('currency_type', 'payment_currency_type', 'profit_ars', 'profit_usd')
    def _compute_profit_currency(self):
        """Determina en qué moneda se registra la ganancia"""
        for record in self:
            # Si es conversión USD/USDT, la ganancia es en USD
            if record.is_conversion:
                record.profit_currency = 'USD'
            # Para todas las demás operaciones, la ganancia es en ARS
            else:
                record.profit_currency = 'ARS'
    
    @api.depends('lot_consumption_ids', 'lot_consumption_ids.quantity_consumed', 'lot_consumption_ids.state')
    def _compute_total_consumed(self):
        """Calcula el total consumido de los lotes"""
        for record in self:
            consumptions = record.lot_consumption_ids.filtered(lambda c: c.state == 'active')
            record.total_consumed = sum(consumptions.mapped('quantity_consumed'))
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                if vals.get('operation_type') == 'buy':
                    prefix = 'COMPRA'
                else:
                    prefix = 'VENTA'
                vals['name'] = prefix + self.env['ir.sequence'].next_by_code('divisas.currency') or _('Nuevo')
            
            # Asegurarse de que el tipo de cambio tenga un valor
            if 'exchange_rate' not in vals or not vals.get('exchange_rate'):
                vals['exchange_rate'] = 1.0
                
            # Asegurarse de que el monto tenga un valor
            if 'amount' not in vals or not vals.get('amount'):
                vals['amount'] = 1.0
                
        return super(DivisasCurrency, self).create(vals_list)
    
    @api.depends('amount', 'exchange_rate', 'operation_type')
    def _compute_payment_amount(self):
        for record in self:
            # Asegurarse de que hay valores válidos
            if not record.amount:
                record.amount = 0.0
            
            if not record.exchange_rate or record.exchange_rate <= 0:
                record.exchange_rate = 1.0
                
            # Tanto para compra como venta, multiplicamos por el tipo de cambio
            record.payment_amount = record.amount * record.exchange_rate
    
    @api.onchange('currency_type', 'payment_currency_type', 'operation_type')
    def _onchange_currencies(self):
        """Carga el tipo de cambio actual cuando cambian las monedas"""
        if self.currency_type and self.payment_currency_type:
            if self.currency_type == self.payment_currency_type:
                raise UserError(_('La moneda de operación y de pago no pueden ser iguales'))
            
            # Buscar el tipo de cambio actual
            try:
                exchange_rate_obj = self.env['divisas.exchange.rate']
                rate = exchange_rate_obj.get_current_rate(
                    self.currency_type, 
                    self.payment_currency_type,
                    self.operation_type
                )
                self.exchange_rate = rate
                self.is_custom_rate = False
            except Exception as e:
                # En caso de error, establecer un tipo de cambio por defecto
                self.exchange_rate = 1.0
                self.is_custom_rate = True
    
    def action_confirm(self):
        """Confirma la operación y crea el movimiento en la wallet"""
        self.ensure_one()
        
        if not self.currency_type or not self.payment_currency_type:
            raise UserError(_('Debe seleccionar ambas monedas para la operación'))
        
        if self.currency_type == self.payment_currency_type:
            raise UserError(_('La moneda de operación y de pago no pueden ser iguales'))
        
        if self.amount <= 0:
            raise UserError(_('El monto debe ser mayor a cero'))
        
        if not self.exchange_rate or self.exchange_rate <= 0:
            raise UserError(_('El tipo de cambio debe ser mayor a cero'))
        
        # Crear el movimiento en la wallet
        wallet_movement = self.env['divisas.wallet.movement'].create({
            'partner_id': self.partner_id.id,
            'currency_operation_id': self.id,
            'operation_type': self.operation_type,
            'currency_type': self.currency_type,
            'payment_currency_type': self.payment_currency_type,
            'amount': self.amount,
            'payment_amount': self.payment_amount,
            'date': self.date,
            'notes': self.notes,
        })
        
        self.wallet_movement_id = wallet_movement.id
        self.state = 'confirmed'
        return True
    
    def action_cancel(self):
        """Cancela la operación y revierte el movimiento en la wallet"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise UserError(_('Solo se pueden cancelar operaciones confirmadas'))
        
        if self.wallet_movement_id:
            self.wallet_movement_id.action_cancel()
            
        self.state = 'cancelled'
        return True
    
    def action_draft(self):
        """Regresa la operación a estado borrador"""
        self.ensure_one()
        
        if self.state != 'cancelled':
            raise UserError(_('Solo se pueden reactivar operaciones canceladas'))
        
        self.state = 'draft'
        return True