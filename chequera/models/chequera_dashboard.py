from odoo import models, fields, api
from datetime import date, datetime, timedelta

class ChequeraDashboard(models.TransientModel):
    _name = 'chequera.dashboard'
    _description = 'Dashboard de Chequera'
    
    # Campos calculados
    compras_hoy = fields.Integer(string='Compras Hoy', compute='_compute_dashboard_data')
    total_compras_hoy = fields.Float(string='Total Comprado Hoy', compute='_compute_dashboard_data')
    ventas_hoy = fields.Integer(string='Ventas Hoy', compute='_compute_dashboard_data')
    total_ventas_hoy = fields.Float(string='Total Vendido Hoy', compute='_compute_dashboard_data')
    total_compras_semana = fields.Float(string='Total Comprado Semana', compute='_compute_dashboard_data')
    total_ventas_semana = fields.Float(string='Total Vendido Semana', compute='_compute_dashboard_data')
    cant_cheques_disponibles = fields.Integer(string='Cheques Disponibles', compute='_compute_dashboard_data')
    monto_cheques_disponibles = fields.Float(string='Monto Disponible', compute='_compute_dashboard_data')
    proximos_vencer_ids = fields.Many2many('chequera.check', string='Próximos a Vencer', compute='_compute_dashboard_data')
    proximos_pago_ids = fields.Many2many('chequera.check', string='Próximos a Pagar', compute='_compute_dashboard_data')
    
    @api.model
    def default_get(self, fields):
        """Calcular datos al abrir el dashboard"""
        res = super(ChequeraDashboard, self).default_get(fields)
        return res
    
    def _compute_dashboard_data(self):
        """Calcular todos los datos del dashboard"""
        for record in self:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Compras del día
            compras_hoy = self.env['chequera.purchase.wizard'].search([
                ('fecha_operacion', '=', today),
                ('state', '=', 'confirmado')
            ])
            record.compras_hoy = len(compras_hoy)
            record.total_compras_hoy = sum(compras_hoy.mapped('precio_total_confirmado'))
            
            # Compras de la semana
            compras_semana = self.env['chequera.purchase.wizard'].search([
                ('fecha_operacion', '>=', week_start),
                ('fecha_operacion', '<=', week_end),
                ('state', '=', 'confirmado')
            ])
            record.total_compras_semana = sum(compras_semana.mapped('precio_total_confirmado'))
            
            # Ventas del día
            ventas_hoy = self.env['chequera.sale.wizard'].search([
                ('fecha_operacion', '=', today),
                ('state', '=', 'confirmado')
            ])
            record.ventas_hoy = len(ventas_hoy)
            record.total_ventas_hoy = sum(ventas_hoy.mapped('precio_total_confirmado'))
            
            # Ventas de la semana
            ventas_semana = self.env['chequera.sale.wizard'].search([
                ('fecha_operacion', '>=', week_start),
                ('fecha_operacion', '<=', week_end),
                ('state', '=', 'confirmado')
            ])
            record.total_ventas_semana = sum(ventas_semana.mapped('precio_total_confirmado'))
            
            # Cheques disponibles
            cheques_disponibles = self.env['chequera.check'].search([
                ('state', '=', 'disponible')
            ])
            record.cant_cheques_disponibles = len(cheques_disponibles)
            record.monto_cheques_disponibles = sum(cheques_disponibles.mapped('monto'))
            
            # Próximos a vencer (15 días)
            record.proximos_vencer_ids = self.env['chequera.check'].search([
                ('state', 'in', ['disponible', 'vendido']),
                ('dias_para_vencimiento', '>', 0),
                ('dias_para_vencimiento', '<=', 15)
            ], limit=10, order='dias_para_vencimiento asc')
            
            # Próximos a fecha de pago (7 días)
            fecha_limite = today + timedelta(days=7)
            record.proximos_pago_ids = self.env['chequera.check'].search([
                ('state', '=', 'disponible'),
                ('fecha_pago', '<=', str(fecha_limite)),
                ('fecha_pago', '>=', str(today))
            ], limit=10, order='fecha_pago asc')