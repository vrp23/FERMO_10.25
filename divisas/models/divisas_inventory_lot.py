# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class DivisasInventoryLot(models.Model):
    _name = 'divisas.inventory.lot'
    _description = 'Lote de Inventario FIFO de Divisas'
    _order = 'date asc, id asc'  # FIFO: los más antiguos primero
    _rec_name = 'name'
    
    name = fields.Char(string='Referencia', required=True, copy=False, 
                       readonly=True, default=lambda self: _('Nuevo'))
    
    # Operación de compra original
    purchase_operation_id = fields.Many2one('divisas.currency', 
                                           string='Operación de Compra',
                                           required=True,
                                           readonly=True,
                                           domain=[('operation_type', '=', 'buy')])
    
    # Partner de la compra
    partner_id = fields.Many2one('res.partner', 
                                string='Proveedor',
                                related='purchase_operation_id.partner_id',
                                store=True)
    
    # Divisa del lote
    currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)')
    ], string='Divisa', required=True, readonly=True)
    
    # Cantidades
    quantity_purchased = fields.Float(string='Cantidad Comprada', 
                                     required=True, 
                                     readonly=True,
                                     digits=(16, 2))
    
    quantity_available = fields.Float(string='Cantidad Disponible', 
                                     required=True,
                                     digits=(16, 2))
    
    quantity_consumed = fields.Float(string='Cantidad Consumida',
                                    compute='_compute_quantity_consumed',
                                    store=True,
                                    digits=(16, 2))
    
    # Tipo de cambio de adquisición
    acquisition_rate = fields.Float(string='TC de Adquisición',
                                   required=True,
                                   readonly=True,
                                   digits=(16, 6),
                                   help='Tipo de cambio al momento de la compra')
    
    # NUEVO: Moneda de referencia para el TC de adquisición
    reference_currency = fields.Selection([
        ('ARS', 'ARS'),
        ('USD', 'USD'),
        ('USDT', 'USDT')
    ], string='Moneda de Referencia',
       required=True,
       readonly=True,
       help='Moneda en la que se registra el TC de adquisición')
    
    # Costo total
    total_cost = fields.Float(string='Costo Total',
                             compute='_compute_total_cost',
                             store=True,
                             digits=(16, 2))
    
    # Fecha de la compra
    date = fields.Date(string='Fecha de Compra', 
                      required=True, 
                      readonly=True)
    
    # Estado del lote
    state = fields.Selection([
        ('available', 'Disponible'),
        ('exhausted', 'Agotado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='available', readonly=True)
    
    # Consumos del lote
    consumption_ids = fields.One2many('divisas.lot.consumption', 
                                     'lot_id',
                                     string='Consumos')
    
    # Multi-compañía
    company_id = fields.Many2one('res.company', 
                                string='Compañía',
                                required=True,
                                default=lambda self: self.env.company)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('divisas.inventory.lot') or _('Nuevo')
        return super(DivisasInventoryLot, self).create(vals_list)
    
    @api.depends('quantity_purchased', 'quantity_available')
    def _compute_quantity_consumed(self):
        for record in self:
            record.quantity_consumed = record.quantity_purchased - record.quantity_available
    
    @api.depends('quantity_purchased', 'acquisition_rate', 'reference_currency')
    def _compute_total_cost(self):
        for record in self:
            if record.reference_currency:
                record.total_cost = record.quantity_purchased * record.acquisition_rate
            else:
                record.total_cost = 0.0
    
    @api.constrains('quantity_available')
    def _check_quantity_available(self):
        for record in self:
            if record.quantity_available < 0:
                raise ValidationError(_('La cantidad disponible no puede ser negativa'))
            if record.quantity_available > record.quantity_purchased:
                raise ValidationError(_('La cantidad disponible no puede ser mayor a la cantidad comprada'))
    
    def action_cancel(self):
        """Cancela el lote y revierte todos sus consumos activos"""
        self.ensure_one()
        
        if self.state == 'cancelled':
            raise UserError(_('El lote ya está cancelado'))
        
        # Revertir SOLO los consumos activos (no los ya revertidos)
        active_consumptions = self.consumption_ids.filtered(lambda c: c.state == 'active')
        for consumption in active_consumptions:
            consumption.action_revert()
        
        self.state = 'cancelled'
        return True


class DivisasLotConsumption(models.Model):
    _name = 'divisas.lot.consumption'
    _description = 'Consumo de Lote FIFO'
    _order = 'date desc, id desc'
    
    # Lote consumido
    lot_id = fields.Many2one('divisas.inventory.lot',
                            string='Lote',
                            required=True,
                            readonly=True,
                            ondelete='cascade')
    
    # Operación de venta
    sale_operation_id = fields.Many2one('divisas.currency',
                                       string='Operación de Venta',
                                       required=True,
                                       readonly=True,
                                       domain=[('operation_type', '=', 'sell')])
    
    # Cantidades y tasas
    quantity_consumed = fields.Float(string='Cantidad Consumida',
                                    required=True,
                                    readonly=True,
                                    digits=(16, 2))
    
    acquisition_rate = fields.Float(string='TC de Adquisición',
                                   related='lot_id.acquisition_rate',
                                   store=True)
    
    consumption_rate = fields.Float(string='TC de Venta',
                                   required=True,
                                   readonly=True,
                                   digits=(16, 6))
    
    # CAMPO EXISTENTE: Ganancia en ARS
    profit_ars = fields.Float(string='Ganancia (ARS)',
                             readonly=True,
                             digits=(16, 2))
    
    # NUEVO: Ganancia en USD
    profit_usd = fields.Float(string='Ganancia (USD)',
                             readonly=True,
                             digits=(16, 2))
    
    # NUEVO: Moneda de la ganancia
    profit_currency = fields.Selection([
        ('ARS', 'ARS'),
        ('USD', 'USD')
    ], string='Moneda', readonly=True)
    
    # Datos relacionados
    currency_type = fields.Selection(related='lot_id.currency_type',
                                    store=True)
    
    reference_currency = fields.Selection(related='lot_id.reference_currency',
                                         store=True)
    
    date = fields.Date(string='Fecha',
                      related='sale_operation_id.date',
                      store=True)
    
    partner_id = fields.Many2one('res.partner',
                                string='Cliente',
                                related='sale_operation_id.partner_id',
                                store=True)
    
    # Estado
    state = fields.Selection([
        ('active', 'Activo'),
        ('reverted', 'Revertido')
    ], string='Estado', default='active', readonly=True)
    
    # Multi-compañía
    company_id = fields.Many2one('res.company',
                                string='Compañía',
                                related='lot_id.company_id',
                                store=True)
    
    def action_revert(self):
        """Revierte el consumo devolviendo la cantidad al lote"""
        self.ensure_one()
        
        if self.state == 'reverted':
            raise UserError(_('El consumo ya fue revertido'))
        
        # Devolver la cantidad al lote
        self.lot_id.quantity_available += self.quantity_consumed
        
        # Si el lote estaba agotado, volver a disponible
        if self.lot_id.state == 'exhausted':
            self.lot_id.state = 'available'
        
        # Marcar como revertido
        self.state = 'reverted'
        
        return True