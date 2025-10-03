from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)  # Faltaba definir _logger

class ChequeraCheckOperations(models.Model):
    _inherit = 'chequera.check'
    
    # Métodos de acciones para botones
    def action_comprar(self):
        """En lugar de comprar directamente, abre el wizard para más flexibilidad"""
        return {
            'name': _('Compra de Cheques'),
            'view_mode': 'form',
            'res_model': 'chequera.purchase.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'active_model': 'chequera.check',
                'active_id': self.id,
            }
        }
    
    def action_edit_cheque(self):
        """Método para editar un cheque desde el wizard de compra"""
        # Obtener el ID del cheque del contexto
        cheque_id = self._context.get('cheque_id', self.id)
        wizard_id = self._context.get('wizard_id')
        
        return {
            'name': _('Editar Cheque'),
            'view_mode': 'form',
            'res_model': 'chequera.check',
            'res_id': cheque_id,
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_is_in_purchase_wizard': True,
                'wizard_id': wizard_id,
            },
            'target': 'new',
            'flags': {'mode': 'edit'},
        }
    
    def action_save_and_return(self):
        """Guarda el cheque y vuelve al wizard"""
        self.ensure_one()
        _logger.info("Ejecutando action_save_and_return para cheque %s", self.id)
        
        # Buscar el wizard padre basándose en el flag
        if self.is_in_purchase_wizard:
            wizard = self.env['chequera.purchase.wizard'].search([
                ('check_ids', 'in', self.id),
                ('state', '=', 'borrador')
            ], limit=1)
            
            if wizard:
                _logger.info("Wizard encontrado: %s", wizard.id)
                # Retornar la acción que reabre el wizard
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'chequera.purchase.wizard',
                    'res_id': wizard.id,
                    'view_mode': 'form',
                    'view_id': self.env.ref('chequera.view_chequera_purchase_wizard_form').id,
                    'target': 'current',
                    'context': {
                        'form_view_initial_mode': 'edit',
                    },
                }
        
        elif self.is_in_sale_wizard:
            wizard = self.env['chequera.sale.wizard'].search([
                ('check_ids', 'in', self.id),
                ('state', '=', 'borrador')
            ], limit=1)
            
            if wizard:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'chequera.sale.wizard',
                    'res_id': wizard.id,
                    'view_mode': 'form',
                    'view_id': self.env.ref('chequera.view_chequera_sale_wizard_form').id,
                    'target': 'current',
                    'context': {
                        'form_view_initial_mode': 'edit',
                    },
                }
        
        # Si no encuentra wizard, intentar cerrar de todas formas
        _logger.warning("No se encontró wizard asociado")
        return {'type': 'ir.actions.act_window_close'}
    
    def action_vender(self):
        """Acción para vender el cheque - ahora abre el wizard de venta múltiple"""
        return {
            'name': _('Venta de Cheques'),
            'view_mode': 'form',
            'res_model': 'chequera.sale.wizard',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_check_ids': [(6, 0, [self.id])],
            }
        }
    
    @api.onchange('proveedor_id')
    def _onchange_proveedor_id(self):
        """Al cambiar el proveedor, cargar valores predeterminados"""
        if self.proveedor_id:
            self.tasa_pesificacion_compra = self.proveedor_id.tasa_pesificacion_compra
            self.interes_mensual_compra = self.proveedor_id.interes_mensual_compra
            self.vendedor_id_compra = self.proveedor_id.assigned_seller_id
    
    @api.onchange('cliente_id')
    def _onchange_cliente_id(self):
        """Al cambiar el cliente, cargar valores predeterminados"""
        if self.cliente_id:
            self.tasa_pesificacion_venta = self.cliente_id.tasa_pesificacion_venta
            self.interes_mensual_venta = self.cliente_id.interes_mensual_venta
            self.vendedor_id_venta = self.cliente_id.assigned_seller_id
    
    @api.onchange('check_ids')
    def _onchange_check_ids(self):
        """Al agregar cheques al wizard, actualizar sus tasas"""
        # Este método será heredado por los wizards
        pass
            
    def action_open_check_purchase(self):
        """Acción para abrir el wizard de compra desde el dashboard"""
        return {
            'name': _('Compra de Cheques'),
            'view_mode': 'form',
            'res_model': 'chequera.purchase.wizard',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
    
    def action_open_check_sale(self):
        """Acción para abrir el wizard de venta múltiple desde el dashboard"""
        return {
            'name': _('Venta de Cheques'),
            'view_mode': 'form',
            'res_model': 'chequera.sale.wizard',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
        
    # Mejorar el cálculo de datos del dashboard para asegurar que se muestren los registros
    @api.model
    def _compute_dashboard_data_static(self):
        """Método estático para obtener datos del dashboard"""
        # Últimas compras (5 más recientes)
        latest_purchases = self.env['chequera.check'].search([
            ('state', 'in', ['disponible', 'vendido', 'rechazado'])
        ], limit=5, order='create_date desc')
        
        # Cheques disponibles
        available_checks = self.env['chequera.check'].search([
            ('state', '=', 'disponible')
        ], limit=5, order='fecha_pago')
        
        return {
            'latest_purchases': latest_purchases,
            'available_checks': available_checks
        }