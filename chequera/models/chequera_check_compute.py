from odoo import models, fields, api
from datetime import date

class ChequeraCheckCompute(models.Model):
    _inherit = 'chequera.check'
    
    # Computos de fechas y valores
    @api.depends('fecha_vencimiento')
    def _compute_dias_para_vencimiento(self):
        today = date.today()
        for record in self:
            if record.fecha_vencimiento:
                dias = (record.fecha_vencimiento - today).days
                record.dias_para_vencimiento = dias
                
                # Determinar la alerta de vencimiento
                if dias < 0:
                    record.alerta_vencimiento = 'vencido'
                elif dias <= 7:
                    record.alerta_vencimiento = 'alerta_7'
                elif dias <= 15:
                    record.alerta_vencimiento = 'alerta_15'
                elif dias <= 30:
                    record.alerta_vencimiento = 'alerta_30'
                else:
                    record.alerta_vencimiento = 'normal'
            else:
                record.dias_para_vencimiento = 0
                record.alerta_vencimiento = 'normal'
    
    @api.depends('fecha_vencimiento')
    def _compute_meses_hasta_vencimiento(self):
        today = date.today()
        for record in self:
            if record.fecha_vencimiento:
                # Calcular meses hasta vencimiento
                dias = (record.fecha_vencimiento - today).days
                if dias >= 0:
                    # Convertir días a meses (aproximado)
                    record.meses_hasta_vencimiento = dias / 30.0
                else:
                    record.meses_hasta_vencimiento = 0
            else:
                record.meses_hasta_vencimiento = 0
    
    @api.depends('monto', 'fecha_pago', 'fecha_vencimiento', 'tasa_pesificacion_compra', 'interes_mensual_compra', 'meses_hasta_vencimiento')
    def _compute_valores_compra(self):
        for record in self:
            # Obtener fórmulas configuradas para cada cálculo
            formulas = self.env['chequera.formula_config'].search([
                ('context_type', '=', 'compra')
            ])
            
            # Por defecto, si no hay fórmulas personalizadas
            pesificacion_formula = "record.monto * record.tasa_pesificacion_compra / 100"
            interes_formula = "record.monto * record.interes_mensual_compra / 100 * record.meses_hasta_vencimiento"
            precio_formula = "record.monto - record.pesificacion_valor_compra - record.interes_valor_compra"
            
            # Buscar fórmulas personalizadas si existen
            for formula in formulas:
                if formula.field_name == 'pesificacion_valor_compra':
                    pesificacion_formula = formula.code
                elif formula.field_name == 'interes_valor_compra':
                    interes_formula = formula.code
                elif formula.field_name == 'precio_compra':
                    precio_formula = formula.code
            
            # Evaluar fórmulas (con seguridad)
            try:
                record.pesificacion_valor_compra = eval(pesificacion_formula)
            except Exception as e:
                record.pesificacion_valor_compra = 0
                
            try:
                record.interes_valor_compra = eval(interes_formula)
            except Exception as e:
                record.interes_valor_compra = 0
                
            try:
                # CAMBIO: Siempre recalcular, igual que en venta
                record.precio_compra = eval(precio_formula)
            except Exception as e:
                record.precio_compra = record.monto
    
    @api.depends('monto', 'fecha_pago', 'fecha_vencimiento', 'tasa_pesificacion_venta', 'interes_mensual_venta', 'meses_hasta_vencimiento')
    def _compute_valores_venta(self):
        for record in self:
            # Obtener fórmulas configuradas para cada cálculo
            formulas = self.env['chequera.formula_config'].search([
                ('context_type', '=', 'venta')
            ])
            
            # Por defecto, si no hay fórmulas personalizadas
            pesificacion_formula = "record.monto * record.tasa_pesificacion_venta / 100"
            interes_formula = "record.monto * record.interes_mensual_venta / 100 * record.meses_hasta_vencimiento"
            precio_formula = "record.monto - record.pesificacion_valor_venta - record.interes_valor_venta"
            
            # Buscar fórmulas personalizadas si existen
            for formula in formulas:
                if formula.field_name == 'pesificacion_valor_venta':
                    pesificacion_formula = formula.code
                elif formula.field_name == 'interes_valor_venta':
                    interes_formula = formula.code
                elif formula.field_name == 'precio_venta':
                    precio_formula = formula.code
            
            # Evaluar fórmulas (con seguridad)
            try:
                record.pesificacion_valor_venta = eval(pesificacion_formula)
            except Exception as e:
                record.pesificacion_valor_venta = 0
                
            try:
                record.interes_valor_venta = eval(interes_formula)
            except Exception as e:
                record.interes_valor_venta = 0
                
            try:
                record.precio_venta = eval(precio_formula)
            except Exception as e:
                record.precio_venta = record.monto
                
    # Cálculo de datos para el dashboard
    def _compute_dashboard_data(self):
        # Usamos el método estático para obtener los datos del dashboard
        dashboard_data = self.env['chequera.check']._compute_dashboard_data_static()
        
        for record in self:
            record.latest_purchases = dashboard_data['latest_purchases']
            record.available_checks = dashboard_data['available_checks']