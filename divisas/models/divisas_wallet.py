# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class DivisasWalletMovement(models.Model):
    _name = 'divisas.wallet.movement'
    _description = 'Movimiento de Wallet'
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, 
                      readonly=True, default=lambda self: _('Nuevo'))
    
    partner_id = fields.Many2one('res.partner', string='Cliente/Contacto', 
                                required=True, readonly=True)
    
    currency_operation_id = fields.Many2one('divisas.currency', string='Operación de Divisa', 
                                           readonly=True)
    
    operation_type = fields.Selection([
        ('buy', 'Compra'),
        ('sell', 'Venta'),
        ('adjustment', 'Ajuste')
    ], string='Tipo de Operación', required=True, readonly=True)
    
    currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
        ('ARS', 'Pesos (ARS)')
    ], string='Moneda', required=True, readonly=True)
    
    payment_currency_type = fields.Selection([
        ('ARS', 'Pesos (ARS)'),
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)')
    ], string='Moneda de Pago', required=True, readonly=True)
    
    amount = fields.Float(string='Monto Moneda', required=True, readonly=True)
    payment_amount = fields.Float(string='Monto de Pago', required=True, readonly=True)
    
    date = fields.Date(string='Fecha', required=True, readonly=True, 
                      default=fields.Date.context_today)
    
    state = fields.Selection([
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='confirmed', readonly=True)
    
    notes = fields.Text(string='Notas')
    
    # Multi-compañía
    company_id = fields.Many2one('res.company', string='Compañía', 
                                required=True, default=lambda self: self.env.company)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('divisas.wallet.movement') or _('Nuevo')
        
        movements = super(DivisasWalletMovement, self).create(vals_list)
        
        # Actualizar los saldos de wallet
        for movement in movements:
            movement._update_wallet_balances()
        
        return movements
    
    def _update_wallet_balances(self):
        """Actualiza los saldos de wallet según el movimiento"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            return
        
        # Determinar qué wallet actualizar y cómo
        if self.operation_type == 'buy':
            # La empresa COMPRA divisa al partner, por lo que:
            # 1. Disminuye la wallet del partner en la moneda comprada (que entrega)
            # 2. Aumenta la wallet del partner en la moneda de pago (que recibe)
            
            # Actualizar la wallet de la moneda comprada (la que entrega el partner)
            if self.currency_type == 'USD':
                self.partner_id.wallet_usd_balance -= self.amount
            elif self.currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance -= self.amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
            
            # Actualizar la wallet de la moneda de pago (la que recibe el partner)
            if self.payment_currency_type == 'USD':
                self.partner_id.wallet_usd_balance += self.payment_amount
            elif self.payment_currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance += self.payment_amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
                
        elif self.operation_type == 'sell':
            # La empresa VENDE divisa al partner, por lo que:
            # 1. Aumenta la wallet del partner en la moneda vendida (que recibe)
            # 2. Disminuye la wallet del partner en la moneda de pago (que entrega)
            
            # Actualizar la wallet de la moneda vendida (la que recibe el partner)
            if self.currency_type == 'USD':
                self.partner_id.wallet_usd_balance += self.amount
            elif self.currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance += self.amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
            
            # Actualizar la wallet de la moneda de pago (la que entrega el partner)
            if self.payment_currency_type == 'USD':
                self.partner_id.wallet_usd_balance -= self.payment_amount
            elif self.payment_currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance -= self.payment_amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
        
        elif self.operation_type == 'adjustment':
            # Ajuste manual de wallet
            if self.currency_type == 'USD':
                self.partner_id.wallet_usd_balance += self.amount
            elif self.currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance += self.amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
    
    def action_cancel(self):
        """Cancela el movimiento y revierte los saldos de wallet"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise UserError(_('El movimiento ya ha sido cancelado'))
        
        # Invertir el movimiento para revertir los saldos
        if self.operation_type == 'buy':
            # Revertir compra
            # 1. Aumenta la wallet del partner en la moneda comprada (que había entregado)
            # 2. Disminuye la wallet del partner en la moneda de pago (que había recibido)
            
            if self.currency_type == 'USD':
                self.partner_id.wallet_usd_balance += self.amount
            elif self.currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance += self.amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
            
            if self.payment_currency_type == 'USD':
                self.partner_id.wallet_usd_balance -= self.payment_amount
            elif self.payment_currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance -= self.payment_amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
                
        elif self.operation_type == 'sell':
            # Revertir venta
            # 1. Disminuye la wallet del partner en la moneda vendida (que había recibido)
            # 2. Aumenta la wallet del partner en la moneda de pago (que había entregado)
            
            if self.currency_type == 'USD':
                self.partner_id.wallet_usd_balance -= self.amount
            elif self.currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance -= self.amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
            
            if self.payment_currency_type == 'USD':
                self.partner_id.wallet_usd_balance += self.payment_amount
            elif self.payment_currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance += self.payment_amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
                
        elif self.operation_type == 'adjustment':
            # Revertir ajuste
            if self.currency_type == 'USD':
                self.partner_id.wallet_usd_balance -= self.amount
            elif self.currency_type == 'USDT':
                self.partner_id.wallet_usdt_balance -= self.amount
            # Para ARS, el saldo se actualiza automáticamente con el método compute extendido
        
        self.state = 'cancelled'
        return True


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Campos para saldos de USD y USDT
    wallet_usd_balance = fields.Float(string='Saldo Wallet USD', default=0.0)
    wallet_usdt_balance = fields.Float(string='Saldo Wallet USDT', default=0.0)
    
    # Relación con movimientos de divisas
    divisas_movement_ids = fields.One2many('divisas.wallet.movement', 'partner_id', 
                                          string='Movimientos de Divisas')
    
    @api.depends('wallet_cheques_ids', 'wallet_cheques_ids.monto', 
                'wallet_cheques_ids.tipo', 'wallet_cheques_ids.active',
                'wallet_cheques_ids.state',
                'divisas_movement_ids', 'divisas_movement_ids.amount',
                'divisas_movement_ids.payment_amount',
                'divisas_movement_ids.currency_type', 
                'divisas_movement_ids.payment_currency_type',
                'divisas_movement_ids.operation_type',
                'divisas_movement_ids.state')
    def _compute_wallet_balance(self):
        """
        Sobrescribe el método del módulo chequera para incluir también los movimientos de divisas
        """
        # Primero calculamos el saldo basado en movimientos de cheques
        super(ResPartner, self)._compute_wallet_balance()
        
        # Luego sumamos/restamos los movimientos de divisas que involucran ARS
        for partner in self:
            # Solo considerar movimientos confirmados
            divisas_movements = partner.divisas_movement_ids.filtered(
                lambda m: m.state == 'confirmed'
            )
            
            for movement in divisas_movements:
                if movement.operation_type == 'buy':
                    # La empresa compra divisa al partner
                    if movement.currency_type == 'ARS':
                        # Partner entrega ARS
                        partner.wallet_balance -= movement.amount
                    if movement.payment_currency_type == 'ARS':
                        # Partner recibe ARS
                        partner.wallet_balance += movement.payment_amount
                        
                elif movement.operation_type == 'sell':
                    # La empresa vende divisa al partner
                    if movement.currency_type == 'ARS':
                        # Partner recibe ARS
                        partner.wallet_balance += movement.amount
                    if movement.payment_currency_type == 'ARS':
                        # Partner entrega ARS
                        partner.wallet_balance -= movement.payment_amount
                        
                elif movement.operation_type == 'adjustment':
                    # Ajuste directo
                    if movement.currency_type == 'ARS':
                        partner.wallet_balance += movement.amount
    
    def action_view_wallet_movements(self):
        """Acción para ver los movimientos de wallet del contacto"""
        self.ensure_one()
        return {
            'name': _('Movimientos de Wallet'),
            'type': 'ir.actions.act_window',
            'res_model': 'divisas.wallet.movement',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
            'target': 'current',
        }