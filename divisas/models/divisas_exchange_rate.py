# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class DivisasExchangeRate(models.Model):
    _name = 'divisas.exchange.rate'
    _description = 'Tipo de Cambio'
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    
    from_currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
        ('ARS', 'Pesos (ARS)')
    ], string='Desde Moneda', required=True)
    
    to_currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
        ('ARS', 'Pesos (ARS)')
    ], string='A Moneda', required=True)
    
    rate = fields.Float(string='Tipo de Cambio Compra', digits=(16, 6), required=True, 
                       help='Cuántas unidades de la moneda destino se necesitan para comprar una unidad de la moneda origen')
    
    sell_rate = fields.Float(string='Tipo de Cambio Venta', digits=(16, 6), required=True,
                            help='Cuántas unidades de la moneda destino se obtienen al vender una unidad de la moneda origen')
    
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    
    active = fields.Boolean(string='Activo', default=True)
    
    notes = fields.Text(string='Notas')
    
    # Multi-compañía
    company_id = fields.Many2one('res.company', string='Compañía', 
                                required=True, default=lambda self: self.env.company)
    
    @api.depends('from_currency_type', 'to_currency_type', 'date')
    def _compute_name(self):
        for record in self:
            if record.from_currency_type and record.to_currency_type and record.date:
                record.name = f"{record.from_currency_type} -> {record.to_currency_type} ({record.date})"
            else:
                record.name = _('Nuevo Tipo de Cambio')
    
    @api.constrains('from_currency_type', 'to_currency_type')
    def _check_currencies(self):
        for record in self:
            if record.from_currency_type == record.to_currency_type:
                raise ValidationError(_('Las monedas origen y destino no pueden ser iguales'))
    
    @api.constrains('rate', 'sell_rate')
    def _check_rates(self):
        for record in self:
            if record.rate <= 0:
                raise ValidationError(_('El tipo de cambio de compra debe ser mayor a cero'))
            if record.sell_rate <= 0:
                raise ValidationError(_('El tipo de cambio de venta debe ser mayor a cero'))
    
    @api.model
    def get_current_rate(self, from_currency_type, to_currency_type, operation_type='buy'):
        """
        Obtiene el tipo de cambio actual entre dos monedas
        :param from_currency_type: Tipo de moneda origen
        :param to_currency_type: Tipo de moneda destino
        :param operation_type: Tipo de operación ('buy' o 'sell')
        :return: Tipo de cambio (float)
        """
        self.env.cr.execute("""
            SELECT id, rate, sell_rate 
            FROM divisas_exchange_rate 
            WHERE from_currency_type = %s 
              AND to_currency_type = %s 
              AND date <= CURRENT_DATE 
              AND active = TRUE 
            ORDER BY date DESC, id DESC 
            LIMIT 1
        """, (from_currency_type, to_currency_type))
        
        direct_rate = self.env.cr.fetchone()
        
        if direct_rate:
            rate_id, rate, sell_rate = direct_rate
            if operation_type == 'buy':
                return rate
            else:
                return sell_rate
        
        # Intentar buscar el tipo inverso y calcularlo
        self.env.cr.execute("""
            SELECT id, rate, sell_rate 
            FROM divisas_exchange_rate 
            WHERE from_currency_type = %s 
              AND to_currency_type = %s 
              AND date <= CURRENT_DATE 
              AND active = TRUE 
            ORDER BY date DESC, id DESC 
            LIMIT 1
        """, (to_currency_type, from_currency_type))
        
        inverse_rate = self.env.cr.fetchone()
        
        if inverse_rate:
            rate_id, rate, sell_rate = inverse_rate
            if operation_type == 'buy':
                # Para tipos inversos en compra, usamos el tipo de venta inverso
                if sell_rate and sell_rate > 0:
                    return 1.0 / sell_rate
            else:
                # Para tipos inversos en venta, usamos el tipo de compra inverso
                if rate and rate > 0:
                    return 1.0 / rate
        
        # Si no se encuentra ningún tipo de cambio, usar un valor por defecto según el par de monedas
        default_rates = {
            ('USD', 'ARS'): 1200.0,
            ('ARS', 'USD'): 1/1200.0,
            ('USDT', 'ARS'): 1205.0,
            ('ARS', 'USDT'): 1/1205.0,
            ('USDT', 'USD'): 1.005,
            ('USD', 'USDT'): 0.995,
        }
        
        default_rate = default_rates.get((from_currency_type, to_currency_type), 1.0)
        
        # Registrar un tipo de cambio por defecto
        self.env['divisas.exchange.rate'].create({
            'from_currency_type': from_currency_type,
            'to_currency_type': to_currency_type,
            'rate': default_rate,
            'sell_rate': default_rate * 0.98,  # Tipo de venta ligeramente menor que el de compra
            'date': fields.Date.context_today(self),
            'notes': 'Tipo de cambio por defecto generado automáticamente',
        })
        
        return default_rate


class DivisasExchangeRateWizard(models.TransientModel):
    _name = 'divisas.exchange.rate.wizard'
    _description = 'Asistente de Actualización de Tipo de Cambio'
    
    from_currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
        ('ARS', 'Pesos (ARS)')
    ], string='Desde Moneda', required=True)
    
    to_currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)'),
        ('ARS', 'Pesos (ARS)')
    ], string='A Moneda', required=True)
    
    rate = fields.Float(string='Tipo de Cambio Compra', digits=(16, 6), required=True)
    
    sell_rate = fields.Float(string='Tipo de Cambio Venta', digits=(16, 6), required=True)
    
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    
    notes = fields.Text(string='Notas')
    
    def action_update_rate(self):
        """Crea o actualiza el tipo de cambio"""
        self.ensure_one()
        
        if self.from_currency_type == self.to_currency_type:
            raise UserError(_('Las monedas origen y destino no pueden ser iguales'))
        
        if self.rate <= 0 or self.sell_rate <= 0:
            raise UserError(_('Los tipos de cambio deben ser mayores a cero'))
        
        # Buscar si ya existe un tipo de cambio para la misma fecha y monedas
        domain = [
            ('from_currency_type', '=', self.from_currency_type),
            ('to_currency_type', '=', self.to_currency_type),
            ('date', '=', self.date),
        ]
        
        existing_rate = self.env['divisas.exchange.rate'].search(domain, limit=1)
        
        if existing_rate:
            # Actualizar el tipo existente
            existing_rate.write({
                'rate': self.rate,
                'sell_rate': self.sell_rate,
                'notes': self.notes,
            })
            rate_id = existing_rate.id
        else:
            # Crear un nuevo tipo de cambio
            rate_record = self.env['divisas.exchange.rate'].create({
                'from_currency_type': self.from_currency_type,
                'to_currency_type': self.to_currency_type,
                'rate': self.rate,
                'sell_rate': self.sell_rate,
                'date': self.date,
                'notes': self.notes,
            })
            rate_id = rate_record.id
        
        # Mostrar el tipo de cambio creado/actualizado
        return {
            'name': _('Tipo de Cambio'),
            'type': 'ir.actions.act_window',
            'res_model': 'divisas.exchange.rate',
            'res_id': rate_id,
            'view_mode': 'form',
            'target': 'current',
        }