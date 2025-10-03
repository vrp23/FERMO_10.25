# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class DivisasExchangeWizard(models.TransientModel):
    _name = 'divisas.exchange.wizard'
    _description = 'Asistente de Operaciones de Divisas'
    
    # Tipo de operación
    operation_type = fields.Selection([
        ('buy', 'Compra'),
        ('sell', 'Venta')
    ], string='Tipo de Operación', required=True, default='buy')
    
    # Cliente
    partner_id = fields.Many2one('res.partner', string='Cliente/Contacto', required=True)
    
    # Información de wallet
    wallet_ars_balance = fields.Float(string='Saldo ARS', compute='_compute_wallet_ars_balance', readonly=True)
    wallet_usd_balance = fields.Float(string='Saldo USD', related='partner_id.wallet_usd_balance', readonly=True)
    wallet_usdt_balance = fields.Float(string='Saldo USDT', related='partner_id.wallet_usdt_balance', readonly=True)
    
    # Monedas de la operación
    currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
        ('ARS', 'Pesos (ARS)')
    ], string='Moneda', required=True)
    
    payment_currency_type = fields.Selection([
        ('ARS', 'Pesos (ARS)'),
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)')
    ], string='Moneda de Pago', required=True)
    
    # Montos
    amount = fields.Float(string='Monto', required=True, default=1.0)  # Valor por defecto para evitar errores
    payment_amount = fields.Float(string='Monto a Pagar', compute='_compute_payment_amount', store=True)
    
    # Tipo de cambio
    exchange_rate = fields.Float(string='Tipo de Cambio', digits=(16, 6), required=True, default=1.0)  # Valor por defecto para evitar errores
    is_custom_rate = fields.Boolean(string='Tipo de Cambio Personalizado', default=False)
    
    # Fecha
    date = fields.Date(string='Fecha de Operación', required=True, default=fields.Date.context_today)
    
    # Notas
    notes = fields.Text(string='Notas')
    
    @api.depends('partner_id')
    def _compute_wallet_ars_balance(self):
        """Computa el saldo ARS desde el campo del módulo chequera"""
        for record in self:
            if record.partner_id:
                record.wallet_ars_balance = record.partner_id.wallet_balance
            else:
                record.wallet_ars_balance = 0.0
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Actualiza la información cuando cambia el contacto"""
        if not self.partner_id:
            return
    
    @api.onchange('currency_type', 'payment_currency_type', 'operation_type')
    def _onchange_currencies(self):
        """Carga el tipo de cambio actual cuando cambian las monedas"""
        if self.currency_type and self.payment_currency_type:
            if self.currency_type == self.payment_currency_type:
                self.payment_currency_type = False
                return {
                    'warning': {
                        'title': _('Monedas iguales'),
                        'message': _('La moneda de operación y de pago no pueden ser iguales')
                    }
                }
            
            # Buscar el tipo de cambio actual
            try:
                exchange_rate_obj = self.env['divisas.exchange.rate']
                rate = exchange_rate_obj.get_current_rate(
                    self.currency_type, 
                    self.payment_currency_type,
                    self.operation_type
                )
                
                # Asegurarse de que el tipo de cambio no sea cero o negativo
                if rate <= 0:
                    rate = 1.0
                    
                self.exchange_rate = rate
                self.is_custom_rate = False
                
                # Recalcular el payment_amount
                self._compute_payment_amount()
                
            except Exception as e:
                # En caso de error, establecer un tipo de cambio por defecto
                self.exchange_rate = 1.0
                self.is_custom_rate = True
                return {
                    'warning': {
                        'title': _('Error al cargar tipo de cambio'),
                        'message': _('No se pudo cargar el tipo de cambio automáticamente. Por favor ingrese un valor manualmente.')
                    }
                }
    
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
    
    @api.onchange('amount', 'exchange_rate', 'operation_type')
    def _onchange_amount(self):
        """Recalcula el monto a pagar cuando cambia el monto o el tipo de cambio"""
        if not self.amount:
            self.amount = 0.0
            
        if not self.exchange_rate or self.exchange_rate <= 0:
            self.exchange_rate = 1.0
            
        # Tanto para compra como venta, multiplicamos por el tipo de cambio
        self.payment_amount = self.amount * self.exchange_rate
    
    def action_confirm(self):
        """Confirma la operación y crea el registro de divisa"""
        self.ensure_one()
        
        if not self.currency_type or not self.payment_currency_type:
            raise UserError(_('Debe seleccionar ambas monedas para la operación'))
        
        if self.currency_type == self.payment_currency_type:
            raise UserError(_('La moneda de operación y de pago no pueden ser iguales'))
        
        if self.amount <= 0:
            raise UserError(_('El monto debe ser mayor a cero'))
        
        if not self.exchange_rate or self.exchange_rate <= 0:
            raise UserError(_('El tipo de cambio debe ser mayor a cero'))
        
        # Recalcular el monto de pago para asegurar que sea correcto
        payment_amount = self.amount * self.exchange_rate
        
        # Crear la operación de divisa
        vals = {
            'partner_id': self.partner_id.id,
            'operation_type': self.operation_type,
            'currency_type': self.currency_type,
            'payment_currency_type': self.payment_currency_type,
            'amount': self.amount,
            'exchange_rate': self.exchange_rate,
            'is_custom_rate': self.is_custom_rate,
            'date': self.date,
            'notes': self.notes,
            'payment_amount': payment_amount,  # Incluir el monto de pago calculado
        }
        
        currency_operation = self.env['divisas.currency'].create(vals)
        
        # Confirmar la operación inmediatamente
        currency_operation.action_confirm()
        
        # Mostrar la operación creada
        return {
            'name': _('Operación de Divisa'),
            'type': 'ir.actions.act_window',
            'res_model': 'divisas.currency',
            'res_id': currency_operation.id,
            'view_mode': 'form',
            'target': 'current',
        }