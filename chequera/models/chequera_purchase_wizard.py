from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ChequeraPurchaseWizard(models.Model):
    _name = 'chequera.purchase.wizard'
    _description = 'Wizard para compra múltiple de cheques'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Referencia', default='Nueva Compra', readonly=True)
    tipo_operacion = fields.Selection([
        ('compra', 'Compra'),
        ('venta', 'Venta')
    ], string='Tipo', default='compra', readonly=True)
    
    proveedor_id = fields.Many2one('res.partner', string='Proveedor', required=True, tracking=True)
    fecha_operacion = fields.Date(string='Fecha de operación', default=fields.Date.today, required=True)
    
    # Valores para actualización masiva
    tasa_pesificacion_masiva = fields.Float(string='Tasa de pesificación (%) para todos', default=0.0)
    interes_mensual_masivo = fields.Float(string='Interés mensual (%) para todos', default=0.0)
    vendedor_id_masivo = fields.Many2one('res.users', string='Operador para todos')
    
    # Relación con los cheques
    check_ids = fields.Many2many('chequera.check', 'chequera_purchase_wizard_check_rel', 
                                'wizard_id', 'check_id', string='Cheques a comprar', 
                                domain=[('state', '=', 'borrador')])
    
    confirmed_check_ids = fields.One2many(
        'chequera.check', 
        'operation_id',
        string='Cheques de esta operación',
        readonly=True
    )
    
    # Campos computados para totales
    cantidad_cheques = fields.Integer(string='Cantidad de cheques', compute='_compute_totales', store=True)
    monto_total = fields.Float(string='Monto total', compute='_compute_totales', store=True)
    precio_total = fields.Float(string='Precio total de compra', compute='_compute_totales', store=True)
    
    # Campos para valores confirmados
    cantidad_cheques_confirmado = fields.Integer(string='Cantidad confirmada', readonly=True)
    precio_total_confirmado = fields.Float(string='Precio total confirmado', readonly=True)
    
    # NUEVO: Campos para historial de modificaciones
    modificacion_count = fields.Integer(string='Número de modificaciones', default=0, readonly=True)
    ultimo_usuario_modificacion = fields.Many2one('res.users', string='Último usuario que modificó', readonly=True)
    ultima_fecha_modificacion = fields.Datetime(string='Última fecha de modificación', readonly=True)
    precio_total_original = fields.Float(string='Precio total original', readonly=True)
    cantidad_cheques_original = fields.Integer(string='Cantidad cheques original', readonly=True)
    proveedor_original_id = fields.Many2one('res.partner', string='Proveedor original', readonly=True)
    
    # Estado
    state = fields.Selection([
        ('borrador', 'Borrador'),
        ('confirmado', 'Confirmado'),
        ('revertido', 'Revertido')
    ], default='borrador', string='Estado', tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva Compra') == 'Nueva Compra':
                vals['name'] = self.env['ir.sequence'].next_by_code('chequera.purchase.sequence') or 'OPC#000'
        return super(ChequeraPurchaseWizard, self).create(vals_list)
    
    @api.depends('check_ids', 'confirmed_check_ids', 'check_ids.monto', 'check_ids.precio_compra', 
             'confirmed_check_ids.monto', 'confirmed_check_ids.precio_compra', 'state')
    def _compute_totales(self):
        for wizard in self:
            if wizard.state == 'borrador':
                wizard.cantidad_cheques = len(wizard.check_ids)
                wizard.monto_total = sum(wizard.check_ids.mapped('monto'))
                wizard.precio_total = sum(wizard.check_ids.mapped('precio_compra'))
            else:  # confirmado o revertido
                wizard.cantidad_cheques = len(wizard.confirmed_check_ids)
                wizard.monto_total = sum(wizard.confirmed_check_ids.mapped('monto'))
                wizard.precio_total = sum(wizard.confirmed_check_ids.mapped('precio_compra'))
    
    @api.onchange('proveedor_id')
    def _onchange_proveedor_id(self):
        """Al cambiar el proveedor, actualizar los valores de las tasas masivas"""
        if self.proveedor_id:
            self.tasa_pesificacion_masiva = self.proveedor_id.tasa_pesificacion_compra
            self.interes_mensual_masivo = self.proveedor_id.interes_mensual_compra
            self.vendedor_id_masivo = self.proveedor_id.assigned_seller_id
            self._aplicar_tasas_a_cheques()
    
    @api.onchange('check_ids')
    def _onchange_check_ids(self):
        """Al agregar cheques, actualizar sus tasas automáticamente"""
        self._aplicar_tasas_a_cheques()
    
    def _aplicar_tasas_a_cheques(self):
        """Método auxiliar para aplicar tasas a todos los cheques"""
        if self.proveedor_id and self.check_ids:
            for cheque in self.check_ids:
                update_vals = {
                    'is_in_purchase_wizard': True,
                    'proveedor_id': self.proveedor_id.id,
                    'tasa_pesificacion_compra': self.tasa_pesificacion_masiva,
                    'interes_mensual_compra': self.interes_mensual_masivo,
                }
                if self.vendedor_id_masivo:
                    update_vals['vendedor_id_compra'] = self.vendedor_id_masivo.id
                
                cheque.write(update_vals)
    
    def action_add_cheque(self):
        """Acción para agregar un nuevo cheque para la compra"""
        self.ensure_one()
        
        if not self.id:
            self = self.create({
                'proveedor_id': self.proveedor_id.id,
                'fecha_operacion': self.fecha_operacion,
                'tasa_pesificacion_masiva': self.tasa_pesificacion_masiva,
                'interes_mensual_masivo': self.interes_mensual_masivo,
                'vendedor_id_masivo': self.vendedor_id_masivo.id if self.vendedor_id_masivo else False,
            })
        
        return {
            'name': _('Nuevo Cheque'),
            'view_mode': 'form',
            'res_model': 'chequera.check',
            'view_id': self.env.ref('chequera.view_chequera_check_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'default_is_in_purchase_wizard': True,
                'default_proveedor_id': self.proveedor_id.id,
                'default_tasa_pesificacion_compra': self.tasa_pesificacion_masiva,
                'default_interes_mensual_compra': self.interes_mensual_masivo,
                'default_vendedor_id_compra': self.vendedor_id_masivo.id if self.vendedor_id_masivo else False,
                'default_state': 'borrador',
                'form_view_initial_mode': 'edit',
                'wizard_id': self.id,
            },
            'target': 'new',
            'flags': {'mode': 'edit'},
        }
    
    def action_edit_cheque(self):
        """Acción para editar un cheque existente"""
        self.ensure_one()
        cheque_id = self._context.get('cheque_id')
        wizard_id = self._context.get('wizard_id', self.id)
        
        if not cheque_id:
            return {'type': 'ir.actions.act_window_close'}
        
        cheque = self.env['chequera.check'].browse(cheque_id)
        if cheque.exists() and not cheque.is_in_purchase_wizard:
            cheque.write({'is_in_purchase_wizard': True})
        
        return {
            'name': _('Editar Cheque'),
            'view_mode': 'form',
            'res_model': 'chequera.check',
            'res_id': cheque_id,
            'view_id': self.env.ref('chequera.view_chequera_check_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_is_in_purchase_wizard': True,
                'wizard_id': wizard_id,
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
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chequera.purchase.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
            'flags': {'mode': 'edit'},
        }
    
    @api.model
    def default_get(self, fields_list):
        """Obtener valores predeterminados"""
        res = super(ChequeraPurchaseWizard, self).default_get(fields_list)
        
        active_model = self._context.get('active_model')
        active_id = self._context.get('active_id')
        
        if active_model == 'chequera.check' and active_id:
            cheque = self.env['chequera.check'].browse(active_id)
            if cheque.state == 'borrador':
                res['check_ids'] = [(4, active_id)]
                
                if cheque.proveedor_id:
                    res['proveedor_id'] = cheque.proveedor_id.id
                    res['tasa_pesificacion_masiva'] = cheque.proveedor_id.tasa_pesificacion_compra
                    res['interes_mensual_masivo'] = cheque.proveedor_id.interes_mensual_compra
                    if cheque.proveedor_id.assigned_seller_id:
                        res['vendedor_id_masivo'] = cheque.proveedor_id.assigned_seller_id.id
        
        return res
    
    def action_confirmar_compra(self):
        """Confirmar la compra de todos los cheques seleccionados"""
        cheques = self.check_ids
        
        if not cheques:
            raise ValidationError(_('Debe agregar al menos un cheque para realizar la compra.'))
        
        if not self.proveedor_id:
            raise ValidationError(_('Debe seleccionar un proveedor para la compra.'))
        
        cheques_sin_checklist = cheques.filtered(
            lambda c: not (c.checklist_emisor and c.checklist_irregularidades and c.checklist_firma)
        )
        if cheques_sin_checklist:
            raise ValidationError(_('Todos los cheques deben tener el checklist completo antes de confirmar la compra.'))
        
        cheque_ids = cheques.ids[:]
        cantidad_cheques = len(cheque_ids)
        monto_total = sum(cheques.mapped('monto'))
        precio_total = sum(cheques.mapped('precio_compra'))
        
        self.write({
            'cantidad_cheques_confirmado': cantidad_cheques,
            'precio_total_confirmado': precio_total,
            'state': 'confirmado'
        })
        
        self.env['chequera.check'].browse(cheque_ids).write({
            'state': 'disponible',
            'proveedor_id': self.proveedor_id.id,
            'is_in_purchase_wizard': False,
            'operation_id': self.id
        })
        
        movement = self.env['chequera.wallet.movement'].create({
            'partner_id': self.proveedor_id.id,
            'tipo': 'compra',
            'monto': precio_total,
            'fecha': self.fecha_operacion,
            'multiple_checks': True,
            'check_ids': [(6, 0, cheque_ids)],
            'notes': f'Compra múltiple: {cantidad_cheques} cheques por un total de {monto_total}'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chequera.purchase.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'},
        }
    
    # NUEVO: Método para modificar operación
    def action_modificar_operacion(self):
        """Permite modificar una operación confirmada"""
        self.ensure_one()
        
        if self.state != 'confirmado':
            raise ValidationError(_('Solo se pueden modificar operaciones confirmadas.'))
        
        if not self.env.user.has_group('chequera.group_chequera_supervisor'):
            raise ValidationError(_('Solo los supervisores pueden modificar operaciones confirmadas.'))
        
        cheques_operacion = self.env['chequera.check'].search([
            ('operation_id', '=', self.id)
        ])
        
        cheques_vendidos = cheques_operacion.filtered(lambda c: c.state == 'vendido')
        cheques_modificables = cheques_operacion.filtered(lambda c: c.state != 'vendido')
        
        if not cheques_modificables:
            raise ValidationError(_('No hay cheques modificables en esta operación. Todos han sido vendidos.'))
        
        if self.modificacion_count == 0:
            self.write({
                'precio_total_original': self.precio_total_confirmado,
                'cantidad_cheques_original': self.cantidad_cheques_confirmado,
                'proveedor_original_id': self.proveedor_id.id,
            })
        
        if cheques_modificables:
            movement = self.env['chequera.wallet.movement'].search([
                ('partner_id', '=', self.proveedor_id.id),
                ('check_ids', 'in', cheques_operacion.ids),
                ('tipo', '=', 'compra'),
                ('state', '=', 'confirmado')
            ], limit=1)
            
            if movement:
                if cheques_vendidos:
                    precio_vendidos = sum(cheques_vendidos.mapped('precio_compra'))
                    movement.write({
                        'check_ids': [(6, 0, cheques_vendidos.ids)],
                        'monto': precio_vendidos,
                        'notes': f'Movimiento ajustado por modificación de operación {self.name}. Cheques vendidos mantenidos.'
                    })
                else:
                    movement.unlink()
        
        cheques_modificables.write({
            'state': 'borrador',
            'proveedor_id': False
        })
        
        # Agregar mensajes al chatter de cada cheque modificado
        for cheque in cheques_modificables:
            cheque.message_post(
                body=f"""Cheque modificado por operación {self.name}
                Usuario: {self.env.user.name}
                Fecha: {fields.Datetime.now()}
                Modificación número: {self.modificacion_count + 1}
                Proveedor anterior: {self.proveedor_id.name}""",
                subject="Modificación desde operación de compra"
            )

         # Registrar en chatter con formato mejorado
        mensaje = f"""
        <div style="margin: 10px 0;">
            <strong>🔄 Operación Modificada</strong><br/>
            <ul style="margin: 5px 0;">
                <li><strong>Usuario:</strong> {self.env.user.name}</li>
                <li><strong>Fecha:</strong> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</li>
                <li><strong>Modificación N°:</strong> {self.modificacion_count + 1}</li>
                <li><strong>Cheques modificables:</strong> {len(cheques_modificables)}</li>
                <li><strong>Cheques vendidos (no modificables):</strong> {len(cheques_vendidos)}</li>
            </ul>
        </div>
        """
        
        if cheques_vendidos:
            mensaje += f"<p><em>Cheques vendidos mantenidos: {', '.join(cheques_vendidos.mapped('numero_cheque'))}</em></p>"
        
        self.message_post(
            body=mensaje,
            subject="Modificación de operación",
            message_type='notification'
        )
        
        # Actualizar el wizard con SOLO los cheques modificables
        self.write({
            'state': 'borrador',
            'check_ids': [(6, 0, cheques_modificables.ids)],
            'confirmed_check_ids': [(5, 0, 0)],  # Limpiar la relación anterior
            'modificacion_count': self.modificacion_count + 1,
            'ultimo_usuario_modificacion': self.env.user.id,
            'ultima_fecha_modificacion': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'chequera.purchase.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }
    
    def action_revertir_operacion(self):
        """Revertir una operación confirmada con validación de estados"""
        self.ensure_one()
        
        if self.state != 'confirmado':
            raise ValidationError(_('Solo se pueden revertir operaciones confirmadas.'))
        
        cheques_operacion = self.env['chequera.check'].search([
            ('operation_id', '=', self.id)
        ])
        
        if not cheques_operacion:
            raise ValidationError(_('No se encontraron cheques asociados a esta operación.'))
        
        cheques_vendidos = cheques_operacion.filtered(lambda c: c.state == 'vendido')
        
        if cheques_vendidos:
            ventas_relacionadas = self.env['chequera.sale.wizard'].search([
                ('confirmed_check_ids', 'in', cheques_vendidos.ids),
                ('state', '=', 'confirmado')
            ])
            
            wizard = self.env['chequera.reversion.confirmation'].create({
                'operation_type': 'purchase',
                'purchase_operation_id': self.id,
                'conflicted_check_ids': [(6, 0, cheques_vendidos.ids)],
                'related_sale_ids': [(6, 0, ventas_relacionadas.ids)],
            })
            
            return {
                'name': _('Confirmar Reversión'),
                'type': 'ir.actions.act_window',
                'res_model': 'chequera.reversion.confirmation',
                'res_id': wizard.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context,
            }
        
        movement = self.env['chequera.wallet.movement'].search([
            ('partner_id', '=', self.proveedor_id.id),
            ('check_ids', 'in', cheques_operacion.ids),
            ('tipo', '=', 'compra'),
            ('state', '=', 'confirmado')
        ], limit=1)
        
        if movement:
            movement.unlink()
        
        cheques_operacion.write({
            'state': 'borrador',        
            'proveedor_id': False
        })
        
        self.write({'state': 'revertido'})
        
        self.message_post(
            body=f"Operación revertida directamente por {self.env.user.name} (sin conflictos)",
            subject="Reversión de operación"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Operación Revertida'),
                'message': _('La operación de compra ha sido revertida exitosamente.'),
                'type': 'success',
                'sticky': False,
            }
        }