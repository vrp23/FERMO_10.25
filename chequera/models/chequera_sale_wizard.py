from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ChequeraSaleWizard(models.Model):
    _name = 'chequera.sale.wizard'
    _description = 'Wizard para venta múltiple de cheques'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Referencia', default='Nueva Venta', readonly=True)
    tipo_operacion = fields.Selection([
        ('compra', 'Compra'),
        ('venta', 'Venta')
    ], string='Tipo', default='venta', readonly=True)
    
    cliente_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True)
    fecha_operacion = fields.Date(string='Fecha de operación', default=fields.Date.today, required=True)
    
    # Valores para actualización masiva
    tasa_pesificacion_masiva = fields.Float(string='Tasa de pesificación (%) para todos', default=0.0)
    interes_mensual_masivo = fields.Float(string='Interés mensual (%) para todos', default=0.0)
    vendedor_id_masivo = fields.Many2one('res.users', string='Operador para todos')
    
    # Relación con los cheques
    check_ids = fields.Many2many('chequera.check', 'chequera_sale_wizard_check_rel',
                                'wizard_id', 'check_id', string='Cheques a vender', 
                                domain=[('state', '=', 'disponible')])
    
    confirmed_check_ids = fields.One2many(
        'chequera.check', 
        'sale_operation_id',
        string='Cheques de esta operación',
        readonly=True
    )
    
    # Campos computados para totales
    cantidad_cheques = fields.Integer(string='Cantidad de cheques', compute='_compute_totales', store=True)
    monto_total = fields.Float(string='Monto total', compute='_compute_totales', store=True)
    precio_total = fields.Float(string='Precio total de venta', compute='_compute_totales', store=True)
    
    # Campos para valores confirmados
    cantidad_cheques_confirmado = fields.Integer(string='Cantidad confirmada', readonly=True)
    precio_total_confirmado = fields.Float(string='Precio total confirmado', readonly=True)
    
    # NUEVO: Campos para historial de modificaciones
    modificacion_count = fields.Integer(string='Número de modificaciones', default=0, readonly=True)
    ultimo_usuario_modificacion = fields.Many2one('res.users', string='Último usuario que modificó', readonly=True)
    ultima_fecha_modificacion = fields.Datetime(string='Última fecha de modificación', readonly=True)
    precio_total_original = fields.Float(string='Precio total original', readonly=True)
    cantidad_cheques_original = fields.Integer(string='Cantidad cheques original', readonly=True)
    cliente_original_id = fields.Many2one('res.partner', string='Cliente original', readonly=True)
    
    # Estado
    state = fields.Selection([
        ('borrador', 'Borrador'),
        ('confirmado', 'Confirmado'),
        ('revertido', 'Revertido')
    ], default='borrador', string='Estado', tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva Venta') == 'Nueva Venta':
                vals['name'] = self.env['ir.sequence'].next_by_code('chequera.sale.sequence') or 'OPV#000'
        return super(ChequeraSaleWizard, self).create(vals_list)
    
    @api.depends('check_ids', 'check_ids.monto', 'check_ids.precio_venta')
    def _compute_totales(self):
        for wizard in self:
            if wizard.state != 'confirmado':
                wizard.cantidad_cheques = len(wizard.check_ids)
                wizard.monto_total = sum(wizard.check_ids.mapped('monto'))
                wizard.precio_total = sum(wizard.check_ids.mapped('precio_venta'))
    
    @api.onchange('cliente_id')
    def _onchange_cliente_id(self):
        """Al cambiar el cliente, actualizar los valores de las tasas masivas"""
        if self.cliente_id:
            self.tasa_pesificacion_masiva = self.cliente_id.tasa_pesificacion_venta
            self.interes_mensual_masivo = self.cliente_id.interes_mensual_venta
            self.vendedor_id_masivo = self.cliente_id.assigned_seller_id
            self._aplicar_tasas_a_cheques()
    
    @api.onchange('check_ids')
    def _onchange_check_ids(self):
        """Al agregar cheques, actualizar sus tasas automáticamente"""
        self._aplicar_tasas_a_cheques()
    
    def _aplicar_tasas_a_cheques(self):
        """Método auxiliar para aplicar tasas a todos los cheques"""
        if self.cliente_id and self.check_ids:
            for cheque in self.check_ids:
                update_vals = {
                    'cliente_id': self.cliente_id.id,
                    'tasa_pesificacion_venta': self.tasa_pesificacion_masiva,
                    'interes_mensual_venta': self.interes_mensual_masivo,
                    'is_in_sale_wizard': True,
                }
                
                if self.vendedor_id_masivo:
                    update_vals['vendedor_id_venta'] = self.vendedor_id_masivo.id
                
                cheque.write(update_vals)
                cheque._compute_valores_venta()
    
    def action_edit_cheque(self):
        """Acción para editar un cheque existente en venta"""
        self.ensure_one()
        cheque_id = self._context.get('cheque_id')
        if not cheque_id:
            return {'type': 'ir.actions.act_window_close'}
        
        if not self.id:
            self.ensure_one()
        
        cheque = self.env['chequera.check'].browse(cheque_id)
        if cheque.exists():
            cheque.write({
                'is_in_sale_wizard': True,
                'cliente_id': self.cliente_id.id,
            })
            
        return {
            'name': _('Editar Cheque'),
            'view_mode': 'form',
            'res_model': 'chequera.check',
            'res_id': cheque_id,
            'view_id': self.env.ref('chequera.view_chequera_check_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_initial_mode': 'edit',
                'sale_wizard_id': self.id,
                'is_in_sale_wizard': True,
                'default_cliente_id': self.cliente_id.id,
                'no_create': True,
            },
            'target': 'new',
        }
    
    def action_update_tasas_masivas(self):
        """Actualiza las tasas de todos los cheques seleccionados"""
        self.ensure_one()
        if not self.check_ids:
            return
        
        self._aplicar_tasas_a_cheques()
        self._compute_totales()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chequera.sale.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
            'flags': {'mode': 'edit'},
        }
    
    def action_confirmar_venta(self):
        """Confirmar la venta de todos los cheques seleccionados"""
        cheques = self.check_ids
        
        if not cheques:
            raise ValidationError(_('Debe seleccionar al menos un cheque para realizar la venta.'))
        
        if not self.cliente_id:
            raise ValidationError(_('Debe seleccionar un cliente para la venta.'))
        
        cheque_ids = cheques.ids[:]
        cantidad_cheques = len(cheque_ids)
        monto_total = sum(cheques.mapped('monto'))
        precio_total = sum(cheques.mapped('precio_venta'))
        
        self.write({
            'cantidad_cheques_confirmado': cantidad_cheques,
            'precio_total_confirmado': precio_total,
            'state': 'confirmado'
        })
        
        self.env['chequera.check'].browse(cheque_ids).write({
            'state': 'vendido',
            'cliente_id': self.cliente_id.id,
            'is_in_sale_wizard': False,
            'sale_operation_id': self.id
        })
        
        movement = self.env['chequera.wallet.movement'].create({
            'partner_id': self.cliente_id.id,
            'tipo': 'venta',
            'monto': precio_total,
            'fecha': self.fecha_operacion,
            'multiple_checks': True,
            'check_ids': [(6, 0, cheque_ids)],
            'notes': f'Venta múltiple: {cantidad_cheques} cheques por un total de {monto_total}'
        })
        
        movement.action_confirm()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chequera.sale.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'},
        }
    
    def action_modificar_operacion(self):
        """Permite modificar una operación de venta confirmada"""
        self.ensure_one()
        
        if self.state != 'confirmado':
            raise ValidationError(_('Solo se pueden modificar operaciones confirmadas.'))
        
        if not self.env.user.has_group('chequera.group_chequera_supervisor'):
            raise ValidationError(_('Solo los supervisores pueden modificar operaciones confirmadas.'))
        
        cheques_operacion = self.env['chequera.check'].search([
            ('sale_operation_id', '=', self.id)
        ])
        
        if not cheques_operacion:
            raise ValidationError(_('No se encontraron cheques en esta operación.'))
        
        if self.modificacion_count == 0:
            self.write({
                'precio_total_original': self.precio_total_confirmado,
                'cantidad_cheques_original': self.cantidad_cheques_confirmado,
                'cliente_original_id': self.cliente_id.id,
            })
        
        movement = self.env['chequera.wallet.movement'].search([
            ('partner_id', '=', self.cliente_id.id),
            ('check_ids', 'in', cheques_operacion.ids),
            ('tipo', '=', 'venta'),
            ('state', '=', 'confirmado')
        ], limit=1)
        
        if movement:
            movement.unlink()
        
        cheques_operacion.write({
            'state': 'disponible',
            'cliente_id': False
        })
        
        # Agregar mensajes al chatter de cada cheque modificado
        for cheque in cheques_operacion:
            cheque.message_post(
                body=f"""Cheque modificado por operación {self.name}
                Usuario: {self.env.user.name}
                Fecha: {fields.Datetime.now()}
                Modificación número: {self.modificacion_count + 1}
                Cliente anterior: {self.cliente_id.name}""",
                subject="Modificación desde operación de venta"
            )
        
        # Registrar en chatter con formato mejorado
        mensaje = f"""
        <div style="margin: 10px 0;">
            <strong>🔄 Operación Modificada</strong><br/>
            <ul style="margin: 5px 0;">
                <li><strong>Usuario:</strong> {self.env.user.name}</li>
                <li><strong>Fecha:</strong> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</li>
                <li><strong>Modificación N°:</strong> {self.modificacion_count + 1}</li>
                <li><strong>Cheques modificados:</strong> {len(cheques_operacion)}</li>
            </ul>
        </div>
        """
        
        self.message_post(
            body=mensaje,
            subject="Modificación de operación",
            message_type='notification'
        )
        
        # Actualizar el wizard con los cheques
        self.write({
            'state': 'borrador',
            'check_ids': [(6, 0, cheques_operacion.ids)],
            'confirmed_check_ids': [(5, 0, 0)],  # Limpiar la relación anterior
            'modificacion_count': self.modificacion_count + 1,
            'ultimo_usuario_modificacion': self.env.user.id,
            'ultima_fecha_modificacion': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chequera.sale.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }
    
    def action_revertir_operacion(self):
        """Revertir una operación confirmada"""
        self.ensure_one()
        
        if self.state != 'confirmado':
            raise ValidationError(_('Solo se pueden revertir operaciones confirmadas.'))
        
        cheques_operacion = self.env['chequera.check'].search([
            ('sale_operation_id', '=', self.id)
        ])
        
        if not cheques_operacion:
            raise ValidationError(_('No se encontraron cheques asociados a esta operación.'))
        
        movement = self.env['chequera.wallet.movement'].search([
            ('partner_id', '=', self.cliente_id.id),
            ('check_ids', 'in', cheques_operacion.ids),
            ('tipo', '=', 'venta'),
            ('state', '=', 'confirmado')
        ], limit=1)
        
        if movement:
            movement.unlink()
        else:
            cheques_operacion.write({
                'state': 'disponible',
                'sale_operation_id': False,
                'cliente_id': False
            })
        
        self.write({'state': 'revertido'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Operación Revertida'),
                'message': _('La operación de venta ha sido revertida exitosamente.'),
                'sticky': False,
            }
        }