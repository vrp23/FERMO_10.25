from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ChequeraRejectionWizard(models.TransientModel):
    _name = 'chequera.rejection.wizard'
    _description = 'Wizard para rechazar cheques'
    
    cheque_id = fields.Many2one('chequera.check', string='Cheque', required=True, readonly=True)
    
    # Información del cheque
    numero_cheque = fields.Char(related='cheque_id.numero_cheque', readonly=True)
    banco_id = fields.Many2one(related='cheque_id.banco_id', readonly=True)
    monto = fields.Float(related='cheque_id.monto', readonly=True)
    state = fields.Selection(related='cheque_id.state', readonly=True)
    
    # Información de la operación de compra
    proveedor_id = fields.Many2one(related='cheque_id.proveedor_id', readonly=True)
    precio_compra = fields.Float(related='cheque_id.precio_compra', readonly=True)
    
    # Información de la operación de venta
    cliente_id = fields.Many2one(related='cheque_id.cliente_id', readonly=True)
    precio_venta = fields.Float(related='cheque_id.precio_venta', readonly=True)
    
    # Campos para el rechazo
    motivo_rechazo = fields.Text(string='Motivo del rechazo', required=True)
    revertir_compra = fields.Boolean(string='Revertir operación de compra', default=True)
    monto_reversion_compra = fields.Float(string='Monto a revertir (compra)', 
                                         help='Por defecto es el monto original, puede modificarse para añadir costos')
    
    revertir_venta = fields.Boolean(string='Revertir operación de venta', default=True)
    monto_reversion_venta = fields.Float(string='Monto a revertir (venta)', 
                                        help='Por defecto es el monto original, puede modificarse para añadir costos')
    
    @api.model
    def default_get(self, fields_list):
        """Obtener valores predeterminados"""
        res = super(ChequeraRejectionWizard, self).default_get(fields_list)
        
        # Obtener el cheque activo
        active_id = self.env.context.get('active_id')
        if active_id:
            cheque = self.env['chequera.check'].browse(active_id)
            
            # VALIDACIÓN: No permitir rechazar un cheque ya rechazado
            if cheque.state == 'rechazado':
                raise ValidationError(_('Este cheque ya ha sido rechazado.'))
            
            res['cheque_id'] = cheque.id
            
            # Inicializar montos de reversión con los valores originales
            res['monto_reversion_compra'] = cheque.precio_compra
            res['monto_reversion_venta'] = cheque.precio_venta
            
            # Si el cheque no está vendido, no se puede revertir la venta
            if cheque.state != 'vendido':
                res['revertir_venta'] = False
        
        return res
    
    def action_rechazar_cheque(self):
        """Procesar el rechazo del cheque"""
        self.ensure_one()
        cheque = self.cheque_id
        
        # DOBLE VALIDACIÓN: Por si acaso llegamos aquí con un cheque ya rechazado
        if cheque.state == 'rechazado':
            raise ValidationError(_('Este cheque ya ha sido rechazado.'))
        
        # Crear movimientos de compensación si se solicita
        if self.revertir_compra and cheque.proveedor_id:
            # Buscar el movimiento original de compra
            compra_original = self.env['chequera.wallet.movement'].search([
                ('partner_id', '=', cheque.proveedor_id.id),
                ('tipo', '=', 'compra'),
                '|',
                ('cheque_id', '=', cheque.id),
                ('check_ids', 'in', cheque.id),
                ('es_compensacion', '=', False),
                ('state', '=', 'confirmado')
            ], limit=1)
            
            if compra_original:
                # Crear movimiento de compensación
                compensacion_compra = self.env['chequera.wallet.movement'].create({
                    'partner_id': cheque.proveedor_id.id,
                    'cheque_id': cheque.id,
                    'tipo': 'anulacion',
                    'monto': -self.monto_reversion_compra,  # Negativo para compensar
                    'fecha': fields.Date.today(),
                    'notes': f'Compensación por cheque rechazado: {self.motivo_rechazo}',
                    'movement_origin_id': compra_original.id,
                    'es_compensacion': True,
                    'state': 'confirmado'
                })
        
        if self.revertir_venta and cheque.cliente_id and cheque.state == 'vendido':
            # Buscar el movimiento original de venta
            venta_original = self.env['chequera.wallet.movement'].search([
                ('partner_id', '=', cheque.cliente_id.id),
                ('tipo', '=', 'venta'),
                '|',
                ('cheque_id', '=', cheque.id),
                ('check_ids', 'in', cheque.id),
                ('es_compensacion', '=', False),
                ('state', '=', 'confirmado')
            ], limit=1)
            
            if venta_original:
                # Crear movimiento de compensación
                compensacion_venta = self.env['chequera.wallet.movement'].create({
                    'partner_id': cheque.cliente_id.id,
                    'cheque_id': cheque.id,
                    'tipo': 'anulacion',
                    'monto': self.monto_reversion_venta,  # Positivo para compensar la venta
                    'fecha': fields.Date.today(),
                    'notes': f'Compensación por cheque rechazado: {self.motivo_rechazo}',
                    'movement_origin_id': venta_original.id,
                    'es_compensacion': True,
                    'state': 'confirmado'
                })
        
        # Cambiar el estado del cheque a rechazado
        cheque.write({
            'state': 'rechazado',
            'motivo_rechazo': self.motivo_rechazo,
            'fecha_rechazo': fields.Date.today()
        })
        
        # Cerrar el wizard y mostrar notificación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cheque Rechazado'),
                'message': _('El cheque ha sido marcado como rechazado y se han creado los movimientos de compensación correspondientes.'),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }