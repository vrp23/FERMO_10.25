# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class DivisasOpenPosition(models.Model):
    """Posiciones abiertas cuando se vende sin inventario"""
    _name = 'divisas.open.position'
    _description = 'Posición Abierta FIFO'
    _order = 'create_date asc'  # FIFO para cubrir
    _rec_name = 'name'
    
    name = fields.Char(string='Referencia', required=True, 
                      readonly=True, default=lambda self: _('Nuevo'))
    
    # Operación de venta original
    sale_operation_id = fields.Many2one('divisas.currency',
                                       string='Venta Original',
                                       required=True,
                                       readonly=True,
                                       domain=[('operation_type', '=', 'sell')])
    
    partner_id = fields.Many2one('res.partner',
                                string='Cliente',
                                related='sale_operation_id.partner_id',
                                store=True)
    
    currency_type = fields.Selection([
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)')
    ], string='Divisa', required=True, readonly=True)
    
    # Cantidades
    quantity_open = fields.Float(string='Cantidad Abierta',
                                required=True,
                                readonly=True,
                                digits=(16, 2))
    
    quantity_covered = fields.Float(string='Cantidad Cubierta',
                                   default=0.0,
                                   readonly=True,
                                   digits=(16, 2))
    
    quantity_pending = fields.Float(string='Cantidad Pendiente',
                                   compute='_compute_quantity_pending',
                                   store=True,
                                   digits=(16, 2))
    
    # Tasas
    sale_rate = fields.Float(string='TC de Venta',
                           required=True,
                           readonly=True,
                           digits=(16, 6))
    
    payment_currency = fields.Selection([
        ('ARS', 'Pesos (ARS)'),
        ('USD', 'Dólares (USD)'),
        ('USDT', 'Tether (USDT)')
    ], string='Moneda de Pago', required=True, readonly=True)
    
    # Estado
    state = fields.Selection([
        ('open', 'Abierta'),
        ('partial', 'Parcialmente Cubierta'),
        ('closed', 'Cerrada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='open', readonly=True)
    
    # Coberturas
    coverage_ids = fields.One2many('divisas.position.coverage',
                                  'position_id',
                                  string='Coberturas')
    
    # Ganancias/Pérdidas al cerrar
    profit_ars = fields.Float(string='Ganancia/Pérdida ARS',
                            compute='_compute_profits',
                            store=True,
                            digits=(16, 2))
    
    profit_usd = fields.Float(string='Ganancia/Pérdida USD',
                            compute='_compute_profits',
                            store=True,
                            digits=(16, 2))
    
    date_opened = fields.Date(string='Fecha Apertura',
                             default=fields.Date.context_today,
                             readonly=True)
    
    date_closed = fields.Date(string='Fecha Cierre',
                            readonly=True)
    
    company_id = fields.Many2one('res.company',
                                string='Compañía',
                                required=True,
                                default=lambda self: self.env.company)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('divisas.open.position') or _('Nuevo')
        return super().create(vals_list)
    
    @api.depends('quantity_open', 'quantity_covered')
    def _compute_quantity_pending(self):
        for record in self:
            record.quantity_pending = record.quantity_open - record.quantity_covered
    
    @api.depends('coverage_ids.profit_ars', 'coverage_ids.profit_usd')
    def _compute_profits(self):
        for record in self:
            record.profit_ars = sum(record.coverage_ids.mapped('profit_ars'))
            record.profit_usd = sum(record.coverage_ids.mapped('profit_usd'))
    
    def action_cancel(self):
        """Cancela la posición abierta"""
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se puede cancelar una posición cerrada'))
        if self.quantity_covered > 0:
            raise UserError(_('No se puede cancelar una posición parcialmente cubierta'))
        self.state = 'cancelled'


class DivisasPositionCoverage(models.Model):
    """Registro de coberturas de posiciones abiertas"""
    _name = 'divisas.position.coverage'
    _description = 'Cobertura de Posición'
    _order = 'create_date desc'
    
    position_id = fields.Many2one('divisas.open.position',
                                 string='Posición',
                                 required=True,
                                 ondelete='cascade')
    
    purchase_operation_id = fields.Many2one('divisas.currency',
                                           string='Compra de Cobertura',
                                           required=True,
                                           readonly=True,
                                           domain=[('operation_type', '=', 'buy')])
    
    quantity_covered = fields.Float(string='Cantidad Cubierta',
                                   required=True,
                                   readonly=True,
                                   digits=(16, 2))
    
    purchase_rate = fields.Float(string='TC de Compra',
                               required=True,
                               readonly=True,
                               digits=(16, 6))
    
    sale_rate = fields.Float(string='TC de Venta Original',
                           related='position_id.sale_rate',
                           store=True)
    
    # Ganancias calculadas
    profit_ars = fields.Float(string='Ganancia ARS',
                            readonly=True,
                            digits=(16, 2))
    
    profit_usd = fields.Float(string='Ganancia USD',
                            readonly=True,
                            digits=(16, 2))
    
    profit_currency = fields.Selection([
        ('ARS', 'ARS'),
        ('USD', 'USD')
    ], string='Moneda Ganancia', readonly=True)
    
    date = fields.Date(string='Fecha',
                      default=fields.Date.context_today,
                      readonly=True)
    
    company_id = fields.Many2one('res.company',
                                string='Compañía',
                                related='position_id.company_id',
                                store=True)