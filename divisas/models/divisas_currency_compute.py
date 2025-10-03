# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, timedelta

class DivisasCurrencyCompute(models.Model):
    _inherit = 'divisas.currency'
    
    @api.depends('amount', 'exchange_rate', 'operation_type')
    def _compute_payment_amount(self):
        for record in self:
            # Asegurarse de que hay valores válidos
            if not record.amount:
                record.amount = 0.0
            
            if not record.exchange_rate or record.exchange_rate <= 0:
                record.exchange_rate = 1.0
                
            # Tanto para compra como venta, multiplicamos por el tipo de cambio
            # Ejemplo: 100 USD a 1200 ARS/USD = 120,000 ARS
            record.payment_amount = record.amount * record.exchange_rate
    
    @api.onchange('amount', 'exchange_rate', 'operation_type')
    def _onchange_amount_rate(self):
        """Recalcula el monto a pagar cuando cambia el monto o el tipo de cambio"""
        if not self.amount:
            self.amount = 0.0
            
        if not self.exchange_rate or self.exchange_rate <= 0:
            self.exchange_rate = 1.0
            
        # Tanto para compra como venta, multiplicamos por el tipo de cambio
        self.payment_amount = self.amount * self.exchange_rate