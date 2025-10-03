from odoo import http
from odoo.http import request

class ChequeraDashboard(http.Controller):
    @http.route('/chequera/dashboard', type='json', auth='user')
    def get_dashboard_data(self):
        """Obtener datos para el dashboard de Chequera"""
        # Obtener los cheques disponibles
        available_checks = request.env['chequera.check'].search([
            ('state', '=', 'disponible')
        ], limit=10, order='fecha')

        # Obtener las últimas compras
        last_purchases = request.env['chequera.check'].search([
            ('state', 'in', ['disponible', 'vendido', 'rechazado'])
        ], limit=10, order='create_date desc')

        # Obtener las últimas ventas
        last_sales = request.env['chequera.check'].search([
            ('state', '=', 'vendido')
        ], limit=10, order='write_date desc')
        
        # Obtener los últimos cheques rechazados
        last_rejected = request.env['chequera.check'].search([
            ('state', '=', 'rechazado')
        ], limit=10, order='fecha_rechazo desc, write_date desc')

        # Totales
        total_checks = request.env['chequera.check'].search_count([])
        total_available = request.env['chequera.check'].search_count([('state', '=', 'disponible')])
        total_sold = request.env['chequera.check'].search_count([('state', '=', 'vendido')])
        total_rejected = request.env['chequera.check'].search_count([('state', '=', 'rechazado')])
        
        # Calcular totales de montos
        available_amount = sum(request.env['chequera.check'].search([
            ('state', '=', 'disponible')
        ]).mapped('monto'))
        
        rejected_amount = sum(request.env['chequera.check'].search([
            ('state', '=', 'rechazado')
        ]).mapped('monto'))
        
        # Cheques próximos a estar disponibles
        soon_available_checks = request.env['chequera.check'].search([
            ('state', '=', 'disponible'),
            ('dias_para_disponibilidad', '>', 0),
            ('dias_para_disponibilidad', '<=', 7)
        ], limit=5, order='fecha_pago')
        
        # Retornar los datos
        return {
            'available_checks': [{'id': c.id, 'name': c.name, 'monto': c.monto, 'fecha': c.fecha_pago,
                                'dias_disponibilidad': c.dias_para_disponibilidad,
                                'dias_vencimiento': c.dias_para_vencimiento} 
                                for c in available_checks],
            'last_purchases': [{'id': c.id, 'name': c.name, 'monto': c.monto, 'proveedor': c.proveedor_id.name, 
                               'state': c.state} 
                               for c in last_purchases],
            'last_sales': [{'id': c.id, 'name': c.name, 'monto': c.monto, 'cliente': c.cliente_id.name} 
                           for c in last_sales],
            'last_rejected': [{'id': c.id, 'name': c.name, 'monto': c.monto, 
                              'fecha_rechazo': c.fecha_rechazo,
                              'motivo': c.motivo_rechazo,
                              'cliente': c.cliente_id.name if c.cliente_id else None,
                              'proveedor': c.proveedor_id.name if c.proveedor_id else None} 
                              for c in last_rejected],
            'soon_available_checks': [{'id': c.id, 'name': c.name, 'monto': c.monto, 
                                      'fecha_pago': c.fecha_pago, 
                                      'dias_disponibilidad': c.dias_para_disponibilidad} 
                                      for c in soon_available_checks],
            'total_checks': total_checks,
            'total_available': total_available,
            'total_sold': total_sold,
            'total_rejected': total_rejected,
            'available_amount': available_amount,
            'rejected_amount': rejected_amount,
        }