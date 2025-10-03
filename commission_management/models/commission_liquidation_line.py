from odoo import models, fields, api

class CommissionLiquidationLine(models.Model):
    _name = 'commission.liquidation.line'
    _description = 'Línea de Liquidación de Comisiones'
    _order = 'sequence, id'
    
    # Relación con liquidación
    liquidation_id = fields.Many2one('commission.liquidation', string='Liquidación', 
                                     required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia', default=10)
    
    # Descripción
    description = fields.Text(string='Descripción', required=True)
    
    # Origen
    source_model = fields.Char(string='Modelo Origen')
    source_reference = fields.Char(string='Referencia Origen')
    
    # Datos de la operación
    operation_date = fields.Date(string='Fecha Operación')
    partner_id = fields.Many2one('res.partner', string='Cliente/Proveedor')
    
    # Montos
    base_amount = fields.Float(string='Monto Base', required=True)
    commission_rate = fields.Float(string='Tasa Comisión (%)', required=True)
    commission_amount = fields.Float(string='Monto Comisión', required=True)
    
    # Referencias específicas según el tipo
    check_id = fields.Many2one('chequera.check', string='Cheque', ondelete='set null')
    currency_operation_id = fields.Many2one('divisas.currency', string='Operación Divisa', ondelete='set null')
    cashbox_operation_id = fields.Many2one('sucursales_cajas.operation', string='Operación Caja', ondelete='set null')
    
    # Datos adicionales para cheques
    purchase_price = fields.Float(string='Precio Compra')
    sale_price = fields.Float(string='Precio Venta')
    
    # Datos adicionales para divisas
    operation_type = fields.Selection([
        ('buy', 'Compra'),
        ('sell', 'Venta')
    ], string='Tipo Operación')
    
    # Campo para moneda de ganancia (divisas)
    profit_currency = fields.Selection([
        ('ARS', 'ARS'),
        ('USD', 'USD')
    ], string='Moneda de Ganancia')
    
    def action_view_source(self):
        """Abre el documento origen"""
        self.ensure_one()
        
        if self.source_model == 'chequera.check' and self.check_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'chequera.check',
                'res_id': self.check_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.source_model == 'divisas.currency' and self.currency_operation_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'divisas.currency',
                'res_id': self.currency_operation_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.source_model == 'sucursales_cajas.operation' and self.cashbox_operation_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sucursales_cajas.operation',
                'res_id': self.cashbox_operation_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        return {'type': 'ir.actions.act_window_close'}