# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from markupsafe import Markup


class DivisasDashboardWizard(models.TransientModel):
    """
    Dashboard de Divisas como TransientModel
    No persiste datos, solo calcula y muestra información
    """
    _name = 'divisas.dashboard.wizard'
    _description = 'Dashboard de Operaciones de Divisas'
    
    # ==========================================
    # CAMPOS DE CONFIGURACIÓN
    # ==========================================
    
    # Período seleccionado
    dashboard_period = fields.Selection([
        ('today', 'Hoy'),
        ('week', 'Esta Semana'),
        ('month', 'Este Mes'),
        ('year', 'Este Año'),
        ('yesterday', 'Ayer'),
        ('last_week', 'Semana Pasada'),
        ('last_month', 'Mes Pasado'),
        ('last_year', 'Año Pasado'),
        ('custom', 'Personalizado')
    ], string='Período', default='month')
    
    dashboard_date_from = fields.Date(string='Desde', default=lambda self: fields.Date.context_today(self).replace(day=1))
    dashboard_date_to = fields.Date(string='Hasta', default=fields.Date.context_today)
    
    # Límite de operaciones a mostrar
    operations_limit = fields.Integer(string='Límite de Operaciones', default=10)
    
    # Umbrales de inventario bajo
    inventory_low_usd = fields.Float(string='Inventario Bajo USD', default=5000.0)
    inventory_low_usdt = fields.Float(string='Inventario Bajo USDT', default=5000.0)
    
    # Umbrales de balance (% de ventas sobre compras)
    threshold_critical_low = fields.Float(string='Crítico Venta Baja (%)', default=10.0)
    threshold_warning_low = fields.Float(string='Advertencia Venta Baja (%)', default=50.0)
    threshold_balanced_min = fields.Float(string='Balanceado Mínimo (%)', default=50.0)
    threshold_balanced_max = fields.Float(string='Balanceado Máximo (%)', default=80.0)
    threshold_warning_high = fields.Float(string='Advertencia Stock Bajo (%)', default=80.0)
    threshold_critical_high = fields.Float(string='Crítico Stock Bajo (%)', default=90.0)
    
    # Margen objetivo
    suggested_margin = fields.Float(string='Margen Objetivo (%)', default=2.0)
    
    # ==========================================
    # CAMPOS COMPUTADOS - KPIs
    # ==========================================
    
    # KPIs de Inventario
    inventory_usd_quantity = fields.Float(
        string='Inventario USD',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    inventory_usdt_quantity = fields.Float(
        string='Inventario USDT',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    inventory_usd_avg_rate = fields.Float(
        string='TC Promedio USD',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    inventory_usdt_avg_rate = fields.Float(
        string='TC Promedio USDT',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    
    # KPIs de Posición Neta
    position_usd_bought = fields.Float(
        string='USD Comprados',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    position_usd_sold = fields.Float(
        string='USD Vendidos',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    position_usd_net = fields.Float(
        string='Posición Neta USD',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    position_usdt_bought = fields.Float(
        string='USDT Comprados',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    position_usdt_sold = fields.Float(
        string='USDT Vendidos',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    position_usdt_net = fields.Float(
        string='Posición Neta USDT',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    
    # NUEVOS CAMPOS: Posiciones Abiertas
    open_positions_usd = fields.Float(
        string='Posiciones Abiertas USD',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    open_positions_usdt = fields.Float(
        string='Posiciones Abiertas USDT',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    open_positions_count_usd = fields.Integer(
        string='Cantidad Posiciones USD',
        compute='_compute_all_metrics'
    )
    open_positions_count_usdt = fields.Integer(
        string='Cantidad Posiciones USDT',
        compute='_compute_all_metrics'
    )
    
    # KPIs de Balance SEPARADOS para cada divisa
    balance_usd_status = fields.Selection([
        ('critical_low', 'Crítico Venta Baja'),
        ('warning_low', 'Advertencia Venta Baja'),
        ('balanced', 'Balanceado'),
        ('warning_high', 'Advertencia Stock Bajo'),
        ('critical_high', 'Crítico Stock Bajo')
    ], string='Estado Balance USD', compute='_compute_all_metrics')
    
    balance_usdt_status = fields.Selection([
        ('critical_low', 'Crítico Venta Baja'),
        ('warning_low', 'Advertencia Venta Baja'),
        ('balanced', 'Balanceado'),
        ('warning_high', 'Advertencia Stock Bajo'),
        ('critical_high', 'Crítico Stock Bajo')
    ], string='Estado Balance USDT', compute='_compute_all_metrics')
    
    balance_usd_percentage = fields.Float(
        string='Porcentaje Balance USD',
        compute='_compute_all_metrics',
        digits=(5, 2)
    )
    
    balance_usdt_percentage = fields.Float(
        string='Porcentaje Balance USDT',
        compute='_compute_all_metrics',
        digits=(5, 2)
    )
    
    # KPIs de Ganancias
    profit_total_ars = fields.Float(
        string='Ganancia Total ARS',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    profit_total_usd = fields.Float(
        string='Ganancia Total USD',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    profit_count_ars = fields.Integer(
        string='Operaciones con Ganancia ARS',
        compute='_compute_all_metrics'
    )
    profit_count_usd = fields.Integer(
        string='Operaciones con Ganancia USD',
        compute='_compute_all_metrics'
    )
    
    # TC Objetivo Sugerido
    suggested_rate_usd = fields.Float(
        string='TC Sugerido USD/ARS',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    suggested_rate_usdt = fields.Float(
        string='TC Sugerido USDT/ARS',
        compute='_compute_all_metrics',
        digits=(16, 2)
    )
    
    # ==========================================
    # CAMPOS DE OPERACIONES
    # ==========================================
    
    recent_operations = fields.Many2many(
        'divisas.currency',
        string='Operaciones Recientes',
        compute='_compute_all_metrics'
    )
    
    # Campo para mostrar el operador
    recent_operations_with_operator = fields.Char(
        string='Operador',
        compute='_compute_operator_display'
    )
    
    def _compute_operator_display(self):
        """Campo dummy para evitar errores"""
        for record in self:
            record.recent_operations_with_operator = ''
    
    # ==========================================
    # CAMPOS HTML
    # ==========================================
    
    balance_usd_progress_html = fields.Html(
        string='Barra de Progreso USD',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    balance_usd_badge_html = fields.Html(
        string='Badge USD',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    balance_usdt_progress_html = fields.Html(
        string='Barra de Progreso USDT',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    balance_usdt_badge_html = fields.Html(
        string='Badge USDT',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    alerts_html = fields.Html(
        string='Alertas del Dashboard',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    position_usd_html = fields.Html(
        string='Posición USD HTML',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    position_usdt_html = fields.Html(
        string='Posición USDT HTML',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    # NUEVO: HTML para posiciones abiertas
    open_positions_html = fields.Html(
        string='Posiciones Abiertas HTML',
        compute='_compute_all_metrics',
        sanitize=False
    )
    
    # ==========================================
    # INICIALIZACIÓN
    # ==========================================
    
    @api.model
    def default_get(self, fields_list):
        """Carga valores por defecto incluyendo configuración guardada"""
        defaults = super().default_get(fields_list)
        
        # Cargar umbrales desde parámetros del sistema
        IrConfig = self.env['ir.config_parameter'].sudo()
        
        # Cargar todos los umbrales
        defaults['inventory_low_usd'] = float(IrConfig.get_param('divisas.inventory.low.usd', 5000.0))
        defaults['inventory_low_usdt'] = float(IrConfig.get_param('divisas.inventory.low.usdt', 5000.0))
        defaults['threshold_critical_low'] = float(IrConfig.get_param('divisas.threshold.critical.low', 10.0))
        defaults['threshold_warning_low'] = float(IrConfig.get_param('divisas.threshold.warning.low', 50.0))
        defaults['threshold_balanced_min'] = float(IrConfig.get_param('divisas.threshold.balanced.min', 50.0))
        defaults['threshold_balanced_max'] = float(IrConfig.get_param('divisas.threshold.balanced.max', 80.0))
        defaults['threshold_warning_high'] = float(IrConfig.get_param('divisas.threshold.warning.high', 80.0))
        defaults['threshold_critical_high'] = float(IrConfig.get_param('divisas.threshold.critical.high', 90.0))
        defaults['suggested_margin'] = float(IrConfig.get_param('divisas.margin.default', 2.0))
        
        # Establecer fechas según el período por defecto
        if defaults.get('dashboard_period') == 'month':
            today = fields.Date.context_today(self)
            defaults['dashboard_date_from'] = today.replace(day=1)
            defaults['dashboard_date_to'] = today
        
        return defaults
    
    # ==========================================
    # MÉTODO PRINCIPAL DE CÁLCULO
    # ==========================================
    
    @api.depends('dashboard_period', 'dashboard_date_from', 'dashboard_date_to', 
                 'operations_limit', 'inventory_low_usd', 'inventory_low_usdt',
                 'threshold_critical_low', 'threshold_warning_low',
                 'threshold_balanced_min', 'threshold_balanced_max',
                 'threshold_warning_high', 'threshold_critical_high', 
                 'suggested_margin')
    def _compute_all_metrics(self):
        """Calcula todas las métricas del dashboard de una vez"""
        for wizard in self:
            # Obtener fechas del período
            date_from, date_to = wizard._get_period_dates()
            
            # Calcular inventario
            wizard._calculate_inventory_metrics()
            
            # Calcular posiciones
            wizard._calculate_position_metrics(date_from, date_to)
            
            # Calcular balance
            wizard._calculate_balance_metrics()
            
            # Calcular ganancias
            wizard._calculate_profit_metrics(date_from, date_to)
            
            # Calcular TC sugeridos
            wizard._calculate_suggested_rates()
            
            # Generar HTML
            wizard._generate_html_elements()
            
            # Obtener operaciones recientes
            wizard._get_recent_operations()
    
    # ==========================================
    # MÉTODOS DE CÁLCULO INDIVIDUALES
    # ==========================================
    
    def _calculate_inventory_metrics(self):
        """Calcula métricas de inventario actual"""
        # Obtener lotes disponibles USD
        lots_usd = self.env['divisas.inventory.lot'].search([
            ('currency_type', '=', 'USD'),
            ('state', '=', 'available'),
            ('quantity_available', '>', 0)
        ])
        
        # Calcular inventario total USD
        total_usd = sum(lots_usd.mapped('quantity_available'))
        self.inventory_usd_quantity = total_usd
        
        # Calcular TC promedio ponderado USD (solo con ARS)
        if total_usd > 0:
            lots_usd_ars = lots_usd.filtered(lambda l: l.reference_currency == 'ARS')
            if lots_usd_ars:
                weighted_sum_usd = sum(
                    lot.quantity_available * lot.acquisition_rate 
                    for lot in lots_usd_ars
                )
                total_usd_ars = sum(lots_usd_ars.mapped('quantity_available'))
                self.inventory_usd_avg_rate = weighted_sum_usd / total_usd_ars if total_usd_ars else 0
            else:
                self.inventory_usd_avg_rate = 0
        else:
            self.inventory_usd_avg_rate = 0
        
        # Obtener lotes disponibles USDT
        lots_usdt = self.env['divisas.inventory.lot'].search([
            ('currency_type', '=', 'USDT'),
            ('state', '=', 'available'),
            ('quantity_available', '>', 0)
        ])
        
        # Calcular inventario total USDT
        total_usdt = sum(lots_usdt.mapped('quantity_available'))
        self.inventory_usdt_quantity = total_usdt
        
        # Calcular TC promedio ponderado USDT (solo con ARS)
        if total_usdt > 0:
            lots_usdt_ars = lots_usdt.filtered(lambda l: l.reference_currency == 'ARS')
            if lots_usdt_ars:
                weighted_sum_usdt = sum(
                    lot.quantity_available * lot.acquisition_rate 
                    for lot in lots_usdt_ars
                )
                total_usdt_ars = sum(lots_usdt_ars.mapped('quantity_available'))
                self.inventory_usdt_avg_rate = weighted_sum_usdt / total_usdt_ars if total_usdt_ars else 0
            else:
                self.inventory_usdt_avg_rate = 0
        else:
            self.inventory_usdt_avg_rate = 0
    
    def _calculate_position_metrics(self, date_from, date_to):
        """Calcula métricas de posición neta incluyendo posiciones abiertas"""
        # Operaciones USD
        ops_usd = self.env['divisas.currency'].search([
            ('currency_type', '=', 'USD'),
            ('state', '=', 'confirmed'),
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ])
        
        self.position_usd_bought = sum(
            ops_usd.filtered(lambda o: o.operation_type == 'buy').mapped('amount')
        )
        self.position_usd_sold = sum(
            ops_usd.filtered(lambda o: o.operation_type == 'sell').mapped('amount')
        )
        self.position_usd_net = self.position_usd_bought - self.position_usd_sold
        
        # Operaciones USDT
        ops_usdt = self.env['divisas.currency'].search([
            ('currency_type', '=', 'USDT'),
            ('state', '=', 'confirmed'),
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ])
        
        self.position_usdt_bought = sum(
            ops_usdt.filtered(lambda o: o.operation_type == 'buy').mapped('amount')
        )
        self.position_usdt_sold = sum(
            ops_usdt.filtered(lambda o: o.operation_type == 'sell').mapped('amount')
        )
        self.position_usdt_net = self.position_usdt_bought - self.position_usdt_sold
        
        # NUEVO: Calcular posiciones abiertas
        # Verificar si el modelo existe antes de buscar
        if 'divisas.open.position' in self.env:
            open_pos_usd = self.env['divisas.open.position'].search([
                ('currency_type', '=', 'USD'),
                ('state', 'in', ['open', 'partial'])
            ])
            self.open_positions_usd = sum(open_pos_usd.mapped('quantity_pending'))
            self.open_positions_count_usd = len(open_pos_usd)
            
            open_pos_usdt = self.env['divisas.open.position'].search([
                ('currency_type', '=', 'USDT'),
                ('state', 'in', ['open', 'partial'])
            ])
            self.open_positions_usdt = sum(open_pos_usdt.mapped('quantity_pending'))
            self.open_positions_count_usdt = len(open_pos_usdt)
        else:
            # Si el modelo no existe aún, valores por defecto
            self.open_positions_usd = 0.0
            self.open_positions_count_usd = 0
            self.open_positions_usdt = 0.0
            self.open_positions_count_usdt = 0
    
    def _calculate_balance_metrics(self):
        """Calcula el estado de balance SEPARADO para USD y USDT"""
        # Balance USD
        if self.position_usd_bought > 0:
            self.balance_usd_percentage = (self.position_usd_sold / self.position_usd_bought) * 100
        else:
            self.balance_usd_percentage = 0 if self.position_usd_sold == 0 else 100
        
        # Determinar estado USD
        if self.balance_usd_percentage < self.threshold_critical_low:
            self.balance_usd_status = 'critical_low'
        elif self.balance_usd_percentage < self.threshold_warning_low:
            self.balance_usd_status = 'warning_low'
        elif self.balance_usd_percentage <= self.threshold_balanced_max:
            self.balance_usd_status = 'balanced'
        elif self.balance_usd_percentage < self.threshold_critical_high:
            self.balance_usd_status = 'warning_high'
        else:
            self.balance_usd_status = 'critical_high'
        
        # Balance USDT
        if self.position_usdt_bought > 0:
            self.balance_usdt_percentage = (self.position_usdt_sold / self.position_usdt_bought) * 100
        else:
            self.balance_usdt_percentage = 0 if self.position_usdt_sold == 0 else 100
        
        # Determinar estado USDT
        if self.balance_usdt_percentage < self.threshold_critical_low:
            self.balance_usdt_status = 'critical_low'
        elif self.balance_usdt_percentage < self.threshold_warning_low:
            self.balance_usdt_status = 'warning_low'
        elif self.balance_usdt_percentage <= self.threshold_balanced_max:
            self.balance_usdt_status = 'balanced'
        elif self.balance_usdt_percentage < self.threshold_critical_high:
            self.balance_usdt_status = 'warning_high'
        else:
            self.balance_usdt_status = 'critical_high'
    
    def _calculate_profit_metrics(self, date_from, date_to):
        """Calcula métricas de ganancias"""
        # Operaciones con ganancias
        sales = self.env['divisas.currency'].search([
            ('operation_type', '=', 'sell'),
            ('state', '=', 'confirmed'),
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ])
        
        # Ganancias en ARS
        sales_ars = sales.filtered(lambda s: s.profit_currency == 'ARS')
        self.profit_total_ars = sum(sales_ars.mapped('profit_ars'))
        self.profit_count_ars = len(sales_ars)
        
        # Ganancias en USD
        sales_usd = sales.filtered(lambda s: s.profit_currency == 'USD')
        self.profit_total_usd = sum(sales_usd.mapped('profit_usd'))
        self.profit_count_usd = len(sales_usd)
    
    def _calculate_suggested_rates(self):
        """Calcula tipos de cambio sugeridos"""
        margin_factor = 1 + (self.suggested_margin / 100)
        
        # TC sugerido para USD
        if self.inventory_usd_avg_rate > 0:
            self.suggested_rate_usd = self.inventory_usd_avg_rate * margin_factor
        else:
            try:
                current_rate = self.env['divisas.exchange.rate'].get_current_rate('USD', 'ARS', 'sell')
                self.suggested_rate_usd = current_rate * margin_factor
            except:
                self.suggested_rate_usd = 0
        
        # TC sugerido para USDT
        if self.inventory_usdt_avg_rate > 0:
            self.suggested_rate_usdt = self.inventory_usdt_avg_rate * margin_factor
        else:
            try:
                current_rate = self.env['divisas.exchange.rate'].get_current_rate('USDT', 'ARS', 'sell')
                self.suggested_rate_usdt = current_rate * margin_factor
            except:
                self.suggested_rate_usdt = 0
    
    def _generate_html_elements(self):
        """Genera elementos HTML para el dashboard"""
        # Generar elementos para USD
        self._generate_balance_html_usd()
        
        # Generar elementos para USDT
        self._generate_balance_html_usdt()
        
        # Generar alertas
        self._generate_alerts()
        
        # Generar tablas de posición
        self._generate_position_tables()
        
        # NUEVO: Generar HTML de posiciones abiertas
        self._generate_open_positions_html()
    
    def _generate_balance_html_usd(self):
        """Genera HTML para balance USD"""
        # Determinar colores según el estado
        if self.balance_usd_status == 'balanced':
            progress_color = 'linear-gradient(90deg, #00b09b, #96c93d)'
            badge_color = '#28a745'
            badge_text = 'BALANCEADO'
        elif self.balance_usd_status in ['critical_low', 'critical_high']:
            progress_color = 'linear-gradient(90deg, #eb3349, #f45c43)'
            badge_color = '#dc3545'
            if self.balance_usd_status == 'critical_low':
                badge_text = 'CRÍTICO: VENTAS MUY BAJAS'
            else:
                badge_text = 'CRÍTICO: SOBREVENDIDO'
        else:
            progress_color = 'linear-gradient(90deg, #f093fb, #f5576c)'
            badge_color = '#ffc107'
            if self.balance_usd_status == 'warning_low':
                badge_text = 'ADVERTENCIA: VENTAS BAJAS'
            else:
                badge_text = 'ADVERTENCIA: STOCK BAJO'
        
        # Generar barra de progreso USD
        self.balance_usd_progress_html = Markup("""
            <div class="progress" style="height: 30px; background-color: #f0f0f0; border-radius: 15px;">
                <div class="progress-bar" role="progressbar" 
                     style="width: {percentage}%; background: {color}; border-radius: 15px; font-weight: bold; color: white;">
                    {percentage:.1f}% vendido
                </div>
            </div>
        """.format(percentage=min(self.balance_usd_percentage, 100), color=progress_color))
        
        # Generar badge USD
        self.balance_usd_badge_html = Markup("""
            <span class="badge" style="background-color: {color}; color: white; padding: 8px 15px; 
                  font-size: 14px; border-radius: 20px;">
                {text}
            </span>
        """.format(color=badge_color, text=badge_text))
    
    def _generate_balance_html_usdt(self):
        """Genera HTML para balance USDT"""
        # Determinar colores según el estado
        if self.balance_usdt_status == 'balanced':
            progress_color = 'linear-gradient(90deg, #00b09b, #96c93d)'
            badge_color = '#28a745'
            badge_text = 'BALANCEADO'
        elif self.balance_usdt_status in ['critical_low', 'critical_high']:
            progress_color = 'linear-gradient(90deg, #eb3349, #f45c43)'
            badge_color = '#dc3545'
            if self.balance_usdt_status == 'critical_low':
                badge_text = 'CRÍTICO: VENTAS MUY BAJAS'
            else:
                badge_text = 'CRÍTICO: SOBREVENDIDO'
        else:
            progress_color = 'linear-gradient(90deg, #f093fb, #f5576c)'
            badge_color = '#ffc107'
            if self.balance_usdt_status == 'warning_low':
                badge_text = 'ADVERTENCIA: VENTAS BAJAS'
            else:
                badge_text = 'ADVERTENCIA: STOCK BAJO'
        
        # Generar barra de progreso USDT
        self.balance_usdt_progress_html = Markup("""
            <div class="progress" style="height: 30px; background-color: #f0f0f0; border-radius: 15px;">
                <div class="progress-bar" role="progressbar" 
                     style="width: {percentage}%; background: {color}; border-radius: 15px; font-weight: bold; color: white;">
                    {percentage:.1f}% vendido
                </div>
            </div>
        """.format(percentage=min(self.balance_usdt_percentage, 100), color=progress_color))
        
        # Generar badge USDT
        self.balance_usdt_badge_html = Markup("""
            <span class="badge" style="background-color: {color}; color: white; padding: 8px 15px; 
                  font-size: 14px; border-radius: 20px;">
                {text}
            </span>
        """.format(color=badge_color, text=badge_text))
    
    def _generate_alerts(self):
        """Genera las alertas del dashboard incluyendo posiciones abiertas"""
        alerts = []
        
        # Alertas de balance USD
        if self.balance_usd_status == 'critical_low':
            alerts.append({
                'type': 'danger',
                'icon': 'fa-exclamation-triangle',
                'message': f'USD - Desbalance crítico: Solo se ha vendido el {self.balance_usd_percentage:.1f}% de lo comprado. Aumentar ventas urgentemente.'
            })
        elif self.balance_usd_status == 'warning_low':
            alerts.append({
                'type': 'warning',
                'icon': 'fa-arrow-down',
                'message': f'USD - Ventas bajas: Solo {self.balance_usd_percentage:.1f}% vendido. Considere aumentar las ventas.'
            })
        elif self.balance_usd_status == 'warning_high':
            alerts.append({
                'type': 'warning',
                'icon': 'fa-arrow-up',
                'message': f'USD - Stock bajo: {self.balance_usd_percentage:.1f}% vendido. Considere iniciar compras.'
            })
        elif self.balance_usd_status == 'critical_high':
            if self.balance_usd_percentage >= 100:
                alerts.append({
                    'type': 'danger',
                    'icon': 'fa-exclamation-triangle',
                    'message': f'¡ALERTA USD! Vendiendo más de lo comprado ({self.balance_usd_percentage:.1f}%). Comprar USD URGENTEMENTE.'
                })
            else:
                alerts.append({
                    'type': 'danger',
                    'icon': 'fa-stop-circle',
                    'message': f'USD - Stock crítico: {self.balance_usd_percentage:.1f}% vendido. Detener ventas e iniciar compras.'
                })
        
        # Alertas de balance USDT
        if self.balance_usdt_status == 'critical_low':
            alerts.append({
                'type': 'danger',
                'icon': 'fa-exclamation-triangle',
                'message': f'USDT - Desbalance crítico: Solo se ha vendido el {self.balance_usdt_percentage:.1f}% de lo comprado. Aumentar ventas urgentemente.'
            })
        elif self.balance_usdt_status == 'warning_low':
            alerts.append({
                'type': 'warning',
                'icon': 'fa-arrow-down',
                'message': f'USDT - Ventas bajas: Solo {self.balance_usdt_percentage:.1f}% vendido. Considere aumentar las ventas.'
            })
        elif self.balance_usdt_status == 'warning_high':
            alerts.append({
                'type': 'warning',
                'icon': 'fa-arrow-up',
                'message': f'USDT - Stock bajo: {self.balance_usdt_percentage:.1f}% vendido. Considere iniciar compras.'
            })
        elif self.balance_usdt_status == 'critical_high':
            if self.balance_usdt_percentage >= 100:
                alerts.append({
                    'type': 'danger',
                    'icon': 'fa-exclamation-triangle',
                    'message': f'¡ALERTA USDT! Vendiendo más de lo comprado ({self.balance_usdt_percentage:.1f}%). Comprar USDT URGENTEMENTE.'
                })
            else:
                alerts.append({
                    'type': 'danger',
                    'icon': 'fa-stop-circle',
                    'message': f'USDT - Stock crítico: {self.balance_usdt_percentage:.1f}% vendido. Detener ventas e iniciar compras.'
                })
        
        # NUEVO: Alertas de posiciones abiertas
        if self.open_positions_usd > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'fa-exclamation-circle',
                'message': f'USD - Hay {self.open_positions_count_usd} posiciones abiertas por {self.open_positions_usd:.2f} USD. Requieren cobertura.'
            })
        
        if self.open_positions_usdt > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'fa-exclamation-circle',
                'message': f'USDT - Hay {self.open_positions_count_usdt} posiciones abiertas por {self.open_positions_usdt:.2f} USDT. Requieren cobertura.'
            })
        
        # Alertas de inventario bajo (independientes del balance)
        if self.inventory_usd_quantity < self.inventory_low_usd:
            alerts.append({
                'type': 'info',
                'icon': 'fa-info-circle',
                'message': f'Inventario USD bajo: {self.inventory_usd_quantity:.2f} USD (mínimo: {self.inventory_low_usd:.0f})'
            })
        
        if self.inventory_usdt_quantity < self.inventory_low_usdt:
            alerts.append({
                'type': 'info',
                'icon': 'fa-info-circle',
                'message': f'Inventario USDT bajo: {self.inventory_usdt_quantity:.2f} USDT (mínimo: {self.inventory_low_usdt:.0f})'
            })
        
        # Generar HTML de alertas
        if alerts:
            alerts_html = ''
            for alert in alerts:
                alert_colors = {
                    'danger': {'bg': '#ffe0e0', 'border': '#eb3349', 'text': '#721c24'},
                    'warning': {'bg': '#fff3cd', 'border': '#f5576c', 'text': '#856404'},
                    'info': {'bg': '#d1ecf1', 'border': '#4facfe', 'text': '#0c5460'}
                }
                colors = alert_colors.get(alert['type'], alert_colors['info'])
                
                alerts_html += """
                    <div class="alert" style="background: {bg}; border-left: 4px solid {border}; 
                         color: {text}; padding: 10px 15px; margin-bottom: 10px; border-radius: 8px;">
                        <i class="fa {icon}"></i> {message}
                    </div>
                """.format(
                    bg=colors['bg'],
                    border=colors['border'],
                    text=colors['text'],
                    icon=alert.get('icon', 'fa-info'),
                    message=alert['message']
                )
            self.alerts_html = Markup(alerts_html)
        else:
            self.alerts_html = Markup("""
                <div class="alert" style="background: #d4edda; border-left: 4px solid #28a745; 
                     color: #155724; padding: 10px 15px; border-radius: 8px;">
                    <i class="fa fa-check-circle"></i> Sistema operando normalmente
                </div>
            """)
    
    def _generate_position_tables(self):
        """Genera las tablas HTML de posiciones incluyendo posiciones abiertas"""
        # Tabla USD
        if abs(self.position_usd_net) < 100:
            usd_color = '#28a745'
        elif abs(self.position_usd_net) < 1000:
            usd_color = '#ffc107'
        else:
            usd_color = '#dc3545'
        
        # Incluir fila de posiciones abiertas si existen
        open_pos_row_usd = ""
        if self.open_positions_usd > 0:
            open_pos_row_usd = f"""
                <tr>
                    <td style="color: #ff6b6b;">Posiciones Abiertas:</td>
                    <td class="text-right" style="color: #ff6b6b;">
                        <strong>{self.open_positions_usd:.2f}</strong>
                    </td>
                </tr>
            """
        
        self.position_usd_html = Markup("""
            <table class="table table-sm">
                <tr>
                    <td>Comprado:</td>
                    <td class="text-right"><strong>{bought:.2f}</strong></td>
                </tr>
                <tr>
                    <td>Vendido:</td>
                    <td class="text-right"><strong>{sold:.2f}</strong></td>
                </tr>
                {open_pos_row}
                <tr style="border-top: 2px solid #dee2e6;">
                    <td><strong>Neto:</strong></td>
                    <td class="text-right">
                        <strong style="color: {color};">{net:.2f}</strong>
                    </td>
                </tr>
            </table>
        """.format(
            bought=self.position_usd_bought,
            sold=self.position_usd_sold,
            open_pos_row=open_pos_row_usd,
            net=self.position_usd_net,
            color=usd_color
        ))
        
        # Tabla USDT
        if abs(self.position_usdt_net) < 100:
            usdt_color = '#28a745'
        elif abs(self.position_usdt_net) < 1000:
            usdt_color = '#ffc107'
        else:
            usdt_color = '#dc3545'
        
        # Incluir fila de posiciones abiertas si existen
        open_pos_row_usdt = ""
        if self.open_positions_usdt > 0:
            open_pos_row_usdt = f"""
                <tr>
                    <td style="color: #ff6b6b;">Posiciones Abiertas:</td>
                    <td class="text-right" style="color: #ff6b6b;">
                        <strong>{self.open_positions_usdt:.2f}</strong>
                    </td>
                </tr>
            """
        
        self.position_usdt_html = Markup("""
            <table class="table table-sm">
                <tr>
                    <td>Comprado:</td>
                    <td class="text-right"><strong>{bought:.2f}</strong></td>
                </tr>
                <tr>
                    <td>Vendido:</td>
                    <td class="text-right"><strong>{sold:.2f}</strong></td>
                </tr>
                {open_pos_row}
                <tr style="border-top: 2px solid #dee2e6;">
                    <td><strong>Neto:</strong></td>
                    <td class="text-right">
                        <strong style="color: {color};">{net:.2f}</strong>
                    </td>
                </tr>
            </table>
        """.format(
            bought=self.position_usdt_bought,
            sold=self.position_usdt_sold,
            open_pos_row=open_pos_row_usdt,
            net=self.position_usdt_net,
            color=usdt_color
        ))
    
    def _generate_open_positions_html(self):
        """Genera HTML para mostrar posiciones abiertas"""
        if self.open_positions_usd > 0 or self.open_positions_usdt > 0:
            html_content = """
                <div class="card" style="border: 2px solid #ff6b6b; background-color: #fff5f5;">
                    <div class="card-header" style="background-color: #ff6b6b; color: white;">
                        <h5><i class="fa fa-exclamation-triangle"></i> Posiciones Abiertas (Requieren Cobertura)</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
            """
            
            if self.open_positions_usd > 0:
                html_content += f"""
                    <div class="col-md-6">
                        <div class="text-center">
                            <h3 style="color: #ff6b6b;">{self.open_positions_usd:.2f} USD</h3>
                            <p class="text-muted">{self.open_positions_count_usd} posiciones abiertas</p>
                        </div>
                    </div>
                """
            
            if self.open_positions_usdt > 0:
                html_content += f"""
                    <div class="col-md-6">
                        <div class="text-center">
                            <h3 style="color: #ff6b6b;">{self.open_positions_usdt:.2f} USDT</h3>
                            <p class="text-muted">{self.open_positions_count_usdt} posiciones abiertas</p>
                        </div>
                    </div>
                """
            
            html_content += """
                        </div>
                    </div>
                </div>
            """
            self.open_positions_html = Markup(html_content)
        else:
            self.open_positions_html = Markup("")
    
    def _get_recent_operations(self):
        """Obtiene las operaciones recientes según el límite configurado"""
        date_from, date_to = self._get_period_dates()
        
        operations = self.env['divisas.currency'].search([
            ('state', '=', 'confirmed'),
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ], order='date desc, id desc', limit=self.operations_limit)
        
        self.recent_operations = operations
    
    # ==========================================
    # MÉTODOS AUXILIARES
    # ==========================================
    
    def _get_period_dates(self):
        """Obtiene las fechas según el período seleccionado"""
        today = fields.Date.context_today(self)
        
        if self.dashboard_period == 'today':
            return today, today
        elif self.dashboard_period == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif self.dashboard_period == 'week':
            start = today - timedelta(days=today.weekday())
            return start, today
        elif self.dashboard_period == 'last_week':
            start = today - timedelta(days=today.weekday() + 7)
            end = start + timedelta(days=6)
            return start, end
        elif self.dashboard_period == 'month':
            start = today.replace(day=1)
            return start, today
        elif self.dashboard_period == 'last_month':
            last_month = today.replace(day=1) - timedelta(days=1)
            start = last_month.replace(day=1)
            return start, last_month
        elif self.dashboard_period == 'year':
            start = today.replace(month=1, day=1)
            return start, today
        elif self.dashboard_period == 'last_year':
            last_year = today.replace(year=today.year - 1)
            start = last_year.replace(month=1, day=1)
            end = last_year.replace(month=12, day=31)
            return start, end
        elif self.dashboard_period == 'custom':
            return self.dashboard_date_from or today, self.dashboard_date_to or today
        else:
            return today, today
    
    @api.onchange('dashboard_period')
    def _onchange_dashboard_period(self):
        """Actualiza las fechas cuando cambia el período"""
        if self.dashboard_period != 'custom':
            self.dashboard_date_from, self.dashboard_date_to = self._get_period_dates()
    
    # ==========================================
    # MÉTODOS DE ACCIÓN
    # ==========================================
    
    def action_save_settings(self):
        """Guarda la configuración de umbrales"""
        IrConfig = self.env['ir.config_parameter'].sudo()
        
        # Guardar todos los umbrales
        IrConfig.set_param('divisas.inventory.low.usd', self.inventory_low_usd)
        IrConfig.set_param('divisas.inventory.low.usdt', self.inventory_low_usdt)
        IrConfig.set_param('divisas.threshold.critical.low', self.threshold_critical_low)
        IrConfig.set_param('divisas.threshold.warning.low', self.threshold_warning_low)
        IrConfig.set_param('divisas.threshold.balanced.min', self.threshold_balanced_min)
        IrConfig.set_param('divisas.threshold.balanced.max', self.threshold_balanced_max)
        IrConfig.set_param('divisas.threshold.warning.high', self.threshold_warning_high)
        IrConfig.set_param('divisas.threshold.critical.high', self.threshold_critical_high)
        IrConfig.set_param('divisas.margin.default', self.suggested_margin)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Configuración Guardada'),
                'message': _('Los umbrales se han guardado correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_open_buy_wizard(self):
        """Abre el wizard para comprar divisa"""
        return {
            'name': _('Comprar Divisa'),
            'type': 'ir.actions.act_window',
            'res_model': 'divisas.exchange.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_operation_type': 'buy'}
        }
    
    def action_open_sell_wizard(self):
        """Abre el wizard para vender divisa"""
        return {
            'name': _('Vender Divisa'),
            'type': 'ir.actions.act_window',
            'res_model': 'divisas.exchange.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_operation_type': 'sell'}
        }
    
    def action_update_exchange_rate(self):
        """Abre el wizard para actualizar tipos de cambio"""
        return {
            'name': _('Actualizar Tipo de Cambio'),
            'type': 'ir.actions.act_window',
            'res_model': 'divisas.exchange.rate.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_view_open_positions(self):
        """NUEVO: Abre la vista de posiciones abiertas"""
        return {
            'name': _('Posiciones Abiertas'),
            'type': 'ir.actions.act_window',
            'res_model': 'divisas.open.position',
            'view_mode': 'tree,form',
            'domain': [('state', 'in', ['open', 'partial'])],
            'context': {'search_default_open': 1}
        }