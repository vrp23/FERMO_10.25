from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ChequeraReversionConfirmation(models.TransientModel):
    _name = 'chequera.reversion.confirmation'
    _description = 'Confirmación de Reversión de Operación'
    
    # Operación a revertir
    operation_type = fields.Selection([
        ('purchase', 'Compra'),
        ('sale', 'Venta')
    ], string='Tipo de Operación', required=True)
    
    purchase_operation_id = fields.Many2one('chequera.purchase.wizard', string='Operación de Compra')
    sale_operation_id = fields.Many2one('chequera.sale.wizard', string='Operación de Venta')
    
    # Información de la operación
    operation_name = fields.Char(string='Operación', compute='_compute_operation_info')
    partner_name = fields.Char(string='Contacto', compute='_compute_operation_info')
    total_amount = fields.Float(string='Monto Total', compute='_compute_operation_info')
    
    # Cheques con conflictos
    conflicted_check_ids = fields.Many2many(
        'chequera.check',
        'reversion_confirmation_check_rel',
        'wizard_id',
        'check_id',
        string='Cheques con Conflictos'
    )
    
    # Operaciones relacionadas que necesitan reversión
    related_sale_ids = fields.Many2many(
        'chequera.sale.wizard',
        'reversion_confirmation_sale_rel',
        'wizard_id',
        'sale_id',
        string='Ventas Relacionadas'
    )
    
    # Opciones de reversión
    reversion_mode = fields.Selection([
        ('cancel', 'Cancelar - No revertir nada'),
        ('cascade', 'Revertir en cascada - Revertir ventas primero'),
        ('force', 'Forzar reversión - Solo esta operación (no recomendado)')
    ], string='Modo de Reversión', default='cancel', required=True)
    
    # Mensaje de advertencia
    warning_message = fields.Text(string='Advertencia', compute='_compute_warning_message')
    
    @api.depends('purchase_operation_id', 'sale_operation_id', 'operation_type')
    def _compute_operation_info(self):
        for record in self:
            if record.operation_type == 'purchase' and record.purchase_operation_id:
                record.operation_name = record.purchase_operation_id.name
                record.partner_name = record.purchase_operation_id.proveedor_id.name
                record.total_amount = record.purchase_operation_id.precio_total_confirmado
            elif record.operation_type == 'sale' and record.sale_operation_id:
                record.operation_name = record.sale_operation_id.name
                record.partner_name = record.sale_operation_id.cliente_id.name
                record.total_amount = record.sale_operation_id.precio_total_confirmado
            else:
                record.operation_name = ''
                record.partner_name = ''
                record.total_amount = 0
    
    @api.depends('conflicted_check_ids', 'related_sale_ids', 'operation_type')
    def _compute_warning_message(self):
        for record in self:
            if record.operation_type == 'purchase' and record.conflicted_check_ids:
                cheques_vendidos = len(record.conflicted_check_ids)
                ventas_relacionadas = len(record.related_sale_ids)
                
                message = f"""
                ⚠️ ADVERTENCIA: No se puede revertir esta operación de compra directamente.
                
                Se encontraron {cheques_vendidos} cheque(s) que ya fueron vendidos:
                """
                
                for check in record.conflicted_check_ids[:5]:  # Mostrar máximo 5
                    message += f"\n  • {check.name} - {check.numero_cheque}"
                
                if cheques_vendidos > 5:
                    message += f"\n  ... y {cheques_vendidos - 5} más"
                
                message += f"""
                
                Estos cheques están en {ventas_relacionadas} operación(es) de venta:
                """
                
                for sale in record.related_sale_ids[:5]:  # Mostrar máximo 5
                    message += f"\n  • {sale.name} - Cliente: {sale.cliente_id.name}"
                
                if ventas_relacionadas > 5:
                    message += f"\n  ... y {ventas_relacionadas - 5} más"
                
                message += """
                
                Opciones disponibles:
                • CANCELAR: No realizar ninguna reversión
                • REVERTIR EN CASCADA: Revertir primero las ventas, luego la compra
                • FORZAR: Revertir solo la compra (NO RECOMENDADO - puede causar inconsistencias)
                """
                
                record.warning_message = message
            else:
                record.warning_message = "Esta operación puede ser revertida sin problemas."
    
    def action_confirm_reversion(self):
        """Ejecutar la reversión según el modo seleccionado"""
        self.ensure_one()
        
        if self.reversion_mode == 'cancel':
            # No hacer nada, solo cerrar
            return {'type': 'ir.actions.act_window_close'}
        
        elif self.reversion_mode == 'cascade':
            # Revertir en cascada: primero las ventas, luego la compra
            reversion_log = []
            
            # Revertir cada venta relacionada
            for sale_op in self.related_sale_ids:
                if sale_op.state == 'confirmado':
                    # Revertir la venta
                    self._revert_sale_operation(sale_op)
                    reversion_log.append(f"Revertida venta: {sale_op.name}")
            
            # Ahora revertir la compra original
            if self.purchase_operation_id:
                self._revert_purchase_operation(self.purchase_operation_id)
                reversion_log.append(f"Revertida compra: {self.purchase_operation_id.name}")
            
            # Mensaje de éxito
            message = "Reversión en cascada completada:\n" + "\n".join(reversion_log)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reversión Exitosa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        elif self.reversion_mode == 'force':
            # Forzar reversión (no recomendado)
            if self.purchase_operation_id:
                self._revert_purchase_operation(self.purchase_operation_id, force=True)
            elif self.sale_operation_id:
                self._revert_sale_operation(self.sale_operation_id, force=True)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reversión Forzada'),
                    'message': _('La operación ha sido revertida forzosamente. Verifique la consistencia de los datos.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }
    
    def _revert_purchase_operation(self, operation, force=False):
        """Revertir una operación de compra"""
        # Buscar cheques de la operación
        cheques_operacion = self.env['chequera.check'].search([
            ('operation_id', '=', operation.id)
        ])
        
        # Identificar cheques vendidos
        cheques_vendidos = cheques_operacion.filtered(lambda c: c.state == 'vendido')
        cheques_no_vendidos = cheques_operacion.filtered(lambda c: c.state != 'vendido')
        
        if not force and cheques_vendidos:
            raise ValidationError(_('No se puede revertir: hay cheques vendidos en esta operación.'))
        
        # Buscar y eliminar movimientos de wallet
        movement = self.env['chequera.wallet.movement'].search([
            ('partner_id', '=', operation.proveedor_id.id),
            ('check_ids', 'in', cheques_operacion.ids),
            ('tipo', '=', 'compra'),
            ('state', '=', 'confirmado')
        ], limit=1)
        
        if movement:
            movement.unlink()
        
        # Actualizar cheques según el caso
        if force:
            # IMPORTANTE: Actualizar solo los NO vendidos
            for cheque in cheques_no_vendidos:
                cheque.write({
                    'state': 'borrador',                    
                    'proveedor_id': False
                })
            
            # Para los vendidos, SOLO quitar la referencia a la operación
            for cheque in cheques_vendidos:

                 # Agregar mensaje al historial del cheque
                cheque.message_post(
                    body=f"Reversión FORZADA de compra (Operación {operation.name}) por {self.env.user.name}. El cheque permanece vendido.",
                    subject="Reversión forzada de compra"
                )
        else:
            # Reversión normal: todos a borrador
            cheques_operacion.write({
                'state': 'borrador',
                'operation_id': False,
                'proveedor_id': False
            })
        
        # Actualizar operación
        operation.write({'state': 'revertido'})
        
        # Log en chatter
        if force and cheques_vendidos:
            message = f"""Operación revertida FORZADAMENTE por {self.env.user.name}.
            ADVERTENCIA: {len(cheques_vendidos)} cheque(s) permanecen en estado vendido pero mantienen referencia a esta operación de compra revertida."""
        else:
            message = f"Operación revertida por {self.env.user.name}"
        
        operation.message_post(
            body=message,
            subject="Reversión de operación",
            message_type='notification'
        )
    
    def _revert_sale_operation(self, operation, force=False):
        """Revertir una operación de venta"""
        # Buscar cheques de la operación
        cheques_operacion = self.env['chequera.check'].search([
            ('sale_operation_id', '=', operation.id)
        ])
        
        # Buscar y eliminar movimientos de wallet
        movement = self.env['chequera.wallet.movement'].search([
            ('partner_id', '=', operation.cliente_id.id),
            ('check_ids', 'in', cheques_operacion.ids),
            ('tipo', '=', 'venta'),
            ('state', '=', 'confirmado')
        ], limit=1)
        
        if movement:
            movement.unlink()
        
        # Actualizar cheques
        cheques_operacion.write({
            'state': 'disponible',
            'sale_operation_id': False,
            'cliente_id': False
        })
        
        # Actualizar operación
        operation.write({'state': 'revertido'})
        
        # Log en chatter
        operation.message_post(
            body=f"Operación revertida por {self.env.user.name}",
            subject="Reversión de operación"
        )