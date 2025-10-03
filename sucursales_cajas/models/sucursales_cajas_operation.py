# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json


class SucursalesCajasOperation(models.Model):
    _name = 'sucursales_cajas.operation'
    _description = 'Operación de Caja'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'
    
    # Identificación
    name = fields.Char(
        string='Número de Operación',
        required=True,
        readonly=True,
        default='Nueva',
        copy=False,
        tracking=True
    )
    
    # Tipo de operación
    operation_type = fields.Selection([
        ('deposit', 'Depósito'),
        ('withdrawal', 'Retiro'),
        ('transfer_in', 'Transferencia Entrada'),
        ('transfer_out', 'Transferencia Salida'),
        ('adjustment', 'Ajuste')
    ], string='Tipo de Operación', required=True, tracking=True)
    
    # Partner (titular)
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente/Contacto',
        required=True,
        tracking=True,
        domain="[('is_company', '=', True), '|', ('is_company', '=', False), ('parent_id', '=', False)]"
    )
    
    # Beneficiario (para operaciones de terceros)
    is_third_party = fields.Boolean(
        string='Es para Tercero',
        tracking=True
    )
    
    beneficiary_name = fields.Char(
        string='Nombre del Beneficiario',
        tracking=True
    )
    
    beneficiary_dni = fields.Char(
        string='DNI del Beneficiario',
        tracking=True
    )
    
    beneficiary_phone = fields.Char(
        string='Teléfono del Beneficiario'
    )
    
    # Caja y sesión
    cashbox_id = fields.Many2one(
        'sucursales_cajas.cashbox',
        string='Caja',
        required=True,
        tracking=True,
        domain="[('state', '=', 'in_session')]"
    )
    
    session_id = fields.Many2one(
        'sucursales_cajas.session',
        string='Sesión',
        tracking=True
    )
    
    cashbox_line_id = fields.Many2one(
        'sucursales_cajas.cashbox_line',
        string='Subcaja',
        tracking=True,
        domain="[('cashbox_id', '=', cashbox_id), ('active', '=', True)]"
    )
    
    account_id = fields.Many2one(
        'sucursales_cajas.account',
        string='Cuenta',
        tracking=True,
        domain="[('cashbox_line_id', '=', cashbox_line_id), ('active', '=', True)]"
    )
    
    # Campos relacionados
    branch_id = fields.Many2one(
        related='cashbox_id.branch_id',
        string='Sucursal',
        store=True
    )
    
    company_id = fields.Many2one(
        related='cashbox_id.company_id',
        string='Empresa',
        store=True
    )
    
    # Moneda y montos
    currency_type = fields.Selection([
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('EUR', 'Euros'),
        ('USDT', 'Tether USDT'),
        ('USDC', 'USD Coin'),
        ('other', 'Otra')
    ], string='Moneda', required=True, tracking=True)
    
    amount = fields.Float(
        string='Monto',
        required=True,
        tracking=True
    )
    
    # Para transferencias
    is_cash = fields.Boolean(
        string='Es Efectivo',
        compute='_compute_is_cash',
        store=True
    )
    
    transfer_type = fields.Selection([
        ('cash', 'Efectivo'),
        ('bank_transfer', 'Transferencia Bancaria'),
        ('crypto', 'Criptomoneda'),
        ('mercadopago', 'Mercado Pago'),
        ('other', 'Otro')
    ], string='Tipo de Transferencia', tracking=True)
    
    # Datos de transferencia (JSON)
    transfer_data = fields.Text(
        string='Datos de Transferencia',
        help="Información de la cuenta destino en formato JSON"
    )
    
    transfer_reference = fields.Char(
        string='Referencia/Comprobante',
        tracking=True
    )
    
    # Cuenta destino (para mostrar)
    destination_account_display = fields.Text(
        string='Cuenta Destino',
        compute='_compute_destination_display'
    )
    
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('processing', 'En Proceso'),
        ('done', 'Realizada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True, required=True)
    
    # Fechas
    request_date = fields.Datetime(
        string='Fecha de Solicitud',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    
    processing_date = fields.Datetime(
        string='Fecha de Procesamiento',
        tracking=True
    )
    
    completion_date = fields.Datetime(
        string='Fecha de Completado',
        tracking=True
    )
    
    # Usuario que procesa
    processed_by_user_id = fields.Many2one(
        'res.users',
        string='Procesado por',
        tracking=True
    )
    
    # Observaciones
    notes = fields.Text(
        string='Observaciones'
    )
    
    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        tracking=True
    )
    
    # Origen de la operación
    origin = fields.Selection([
        ('cashbox', 'Desde Caja'),
        ('partner', 'Desde Cliente'),
        ('manual', 'Manual')
    ], string='Origen', default='manual', tracking=True)
    
    # Referencia a movimientos de wallet
    wallet_movement_ids = fields.One2many(
        'chequera.wallet.movement',
        'cashbox_operation_id',
        string='Movimientos de Wallet Cheques'
    )
    
    divisas_movement_ids = fields.One2many(
        'divisas.wallet.movement', 
        'cashbox_operation_id',
        string='Movimientos de Wallet Divisas'
    )
    
    # Campos computados
    can_process = fields.Boolean(
        string='Puede Procesar',
        compute='_compute_can_process'
    )
    
    has_sufficient_balance = fields.Boolean(
        string='Tiene Saldo Suficiente',
        compute='_compute_has_sufficient_balance'
    )
    
    # Para impresión
    print_count = fields.Integer(
        string='Veces Impreso',
        default=0
    )
    
    last_print_date = fields.Datetime(
        string='Última Impresión'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para generar número"""
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                vals['name'] = self.env['ir.sequence'].next_by_code('sucursales_cajas.operation') or 'OP/001'
            
            # Si viene desde partner, marcar como pendiente
            if vals.get('origin') == 'partner' and vals.get('state') == 'draft':
                vals['state'] = 'pending'
        
        return super(SucursalesCajasOperation, self).create(vals_list)
    
    @api.depends('cashbox_line_id', 'operation_type')
    def _compute_is_cash(self):
        """Determina si es una operación en efectivo"""
        for operation in self:
            if operation.cashbox_line_id:
                operation.is_cash = operation.cashbox_line_id.is_cash
            else:
                operation.is_cash = operation.transfer_type == 'cash'
    
    def _compute_destination_display(self):
        """Genera texto descriptivo de la cuenta destino"""
        for operation in self:
            if not operation.transfer_data:
                operation.destination_account_display = ''
                continue
            
            try:
                data = json.loads(operation.transfer_data)
                parts = []
                
                # Construir descripción según el tipo
                if operation.transfer_type == 'bank_transfer':
                    if data.get('bank_name'):
                        parts.append(data['bank_name'])
                    if data.get('account_number'):
                        parts.append(f"Cuenta: {data['account_number']}")
                    if data.get('cbu'):
                        parts.append(f"CBU: {data['cbu']}")
                    if data.get('alias'):
                        parts.append(f"Alias: {data['alias']}")
                
                elif operation.transfer_type == 'crypto':
                    if data.get('network'):
                        parts.append(f"Red: {data['network']}")
                    if data.get('address'):
                        addr = data['address']
                        if len(addr) > 20:
                            addr = f"{addr[:10]}...{addr[-10:]}"
                        parts.append(f"Dirección: {addr}")
                
                operation.destination_account_display = '\n'.join(parts)
                
            except:
                operation.destination_account_display = 'Error al leer datos'
    
    def _compute_can_process(self):
        """Determina si la operación puede ser procesada"""
        for operation in self:
            can_process = True
            
            # Debe estar pendiente
            if operation.state != 'pending':
                can_process = False
            
            # Debe tener caja con sesión activa
            elif not operation.cashbox_id.active_session_id:
                can_process = False
            
            # El usuario debe tener permisos
            elif operation.env.user not in operation.cashbox_id.allowed_user_ids:
                can_process = False
            
            # Para retiros, verificar saldo
            elif operation.operation_type == 'withdrawal' and not operation.has_sufficient_balance:
                can_process = False
            
            operation.can_process = can_process
    
    def _compute_has_sufficient_balance(self):
        """Verifica si hay saldo suficiente para la operación"""
        for operation in self:
            if operation.operation_type != 'withdrawal' or not operation.cashbox_line_id:
                operation.has_sufficient_balance = True
                continue
            
            # Verificar saldo de la línea
            available = operation.cashbox_line_id.current_balance
            operation.has_sufficient_balance = available >= operation.amount
    
    @api.constrains('operation_type', 'amount')
    def _check_amount(self):
        """Valida montos según el tipo de operación"""
        for operation in self:
            if operation.amount <= 0:
                raise ValidationError(_('El monto debe ser mayor a cero.'))
    
    @api.constrains('is_third_party', 'beneficiary_name', 'beneficiary_dni')
    def _check_beneficiary(self):
        """Valida datos del beneficiario"""
        for operation in self:
            if operation.is_third_party:
                if not operation.beneficiary_name:
                    raise ValidationError(_('Debe especificar el nombre del beneficiario.'))
                if not operation.beneficiary_dni:
                    raise ValidationError(_('Debe especificar el DNI del beneficiario.'))
    
    @api.onchange('operation_type')
    def _onchange_operation_type(self):
        """Ajusta campos según el tipo de operación"""
        if self.operation_type in ['transfer_in', 'transfer_out']:
            self.transfer_type = 'bank_transfer'
        else:
            self.transfer_type = False
    
    @api.onchange('is_third_party')
    def _onchange_is_third_party(self):
        """Limpia campos de beneficiario si no es para tercero"""
        if not self.is_third_party:
            self.beneficiary_name = False
            self.beneficiary_dni = False
            self.beneficiary_phone = False
    
    @api.onchange('currency_type', 'cashbox_id')
    def _onchange_currency_cashbox(self):
        """Filtra líneas de caja según la moneda"""
        if self.currency_type and self.cashbox_id:
            # Buscar líneas compatibles
            compatible_lines = self.env['sucursales_cajas.cashbox_line'].search([
                ('cashbox_id', '=', self.cashbox_id.id),
                ('currency_type', '=', self.currency_type),
                ('active', '=', True)
            ])
            
            if compatible_lines:
                # Si hay una sola línea, seleccionarla automáticamente
                if len(compatible_lines) == 1:
                    self.cashbox_line_id = compatible_lines[0]
                
                # Establecer dominio
                return {
                    'domain': {
                        'cashbox_line_id': [('id', 'in', compatible_lines.ids)]
                    }
                }
    
    def action_send_to_cashbox(self):
        """Envía la operación a caja (marca como pendiente)"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Solo se pueden enviar a caja operaciones en borrador.'))
        
        self.write({
            'state': 'pending',
            'origin': 'partner' if self.origin == 'manual' else self.origin
        })
        
        # Notificar a la caja
        self.cashbox_id.message_post(
            body=_('Nueva operación pendiente: %s de %s por %s %s') % (
                dict(self._fields['operation_type'].selection).get(self.operation_type),
                self.partner_id.name,
                self.currency_type,
                self.amount
            ),
            message_type='notification'
        )
        
        return True
    
    def action_start_processing(self):
        """Inicia el procesamiento de la operación"""
        self.ensure_one()
        
        if not self.can_process:
            raise UserError(_('Esta operación no puede ser procesada en este momento.'))
        
        # Asignar sesión actual
        session = self.cashbox_id.active_session_id
        if not session:
            raise UserError(_('No hay sesión activa en la caja.'))
        
        self.write({
            'state': 'processing',
            'session_id': session.id,
            'processing_date': fields.Datetime.now(),
            'processed_by_user_id': self.env.user.id,
        })
        
        # Abrir wizard de procesamiento
        return {
            'name': _('Procesar Operación'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.process_operation_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_operation_id': self.id,
            }
        }
    
    def action_complete(self):
        """Completa la operación y actualiza saldos"""
        self.ensure_one()
        
        if self.state != 'processing':
            raise UserError(_('La operación debe estar en procesamiento para completarla.'))
        
        # Validar datos según el tipo
        if not self.cashbox_line_id:
            raise UserError(_('Debe seleccionar la subcaja para completar la operación.'))
        
        if not self.is_cash and not self.account_id:
            raise UserError(_('Debe seleccionar la cuenta para operaciones no efectivo.'))
        
        # Actualizar saldos
        if self.operation_type == 'deposit':
            self.cashbox_line_id.current_balance += self.amount
            # Actualizar wallet del partner
            self._update_partner_wallet(self.amount)
            
        elif self.operation_type == 'withdrawal':
            self.cashbox_line_id.current_balance -= self.amount
            # Actualizar wallet del partner
            self._update_partner_wallet(-self.amount)
        
        # Marcar como completada
        self.write({
            'state': 'done',
            'completion_date': fields.Datetime.now(),
        })
        
        # Registrar en la cuenta si aplica
        if self.account_id:
            self.account_id.write({
                'last_operation_date': fields.Datetime.now(),
                'last_operation_user_id': self.env.user.id,
            })
        
        return True
    
    def _update_partner_wallet(self, amount):
        """Actualiza el wallet del partner según la moneda"""
        self.ensure_one()
        
        # Determinar qué wallet actualizar
        if self.currency_type == 'ARS':
            # Crear movimiento en wallet de chequera
            self.env['chequera.wallet.movement'].create({
                'partner_id': self.partner_id.id,
                'tipo': 'cashbox_operation',
                'monto': amount,
                'fecha': fields.Date.today(),
                'cashbox_operation_id': self.id,
                'notes': f'Operación de caja: {self.name}'
            })
            
        elif self.currency_type in ['USD', 'USDT']:
            # Crear movimiento en wallet de divisas
            self.env['divisas.wallet.movement'].create({
                'partner_id': self.partner_id.id,
                'operation_type': 'adjustment',
                'currency_type': self.currency_type,
                'payment_currency_type': self.currency_type,
                'amount': amount,
                'payment_amount': amount,
                'date': fields.Date.today(),
                'cashbox_operation_id': self.id,
                'notes': f'Operación de caja: {self.name}'
            })
    
    def action_cancel(self):
        """Cancela la operación"""
        self.ensure_one()
        
        if self.state == 'done':
            raise UserError(_('No se pueden cancelar operaciones completadas.'))
        
        # Si estaba en proceso, revertir cualquier cambio parcial
        if self.state == 'processing':
            # TODO: Implementar reversión si es necesario
            pass
        
        self.write({
            'state': 'cancelled',
            'processing_date': fields.Datetime.now() if not self.processing_date else self.processing_date,
            'processed_by_user_id': self.env.user.id if not self.processed_by_user_id else self.processed_by_user_id.id,
        })
        
        return True
    
    def action_print_receipt(self):
        """Imprime el comprobante de la operación"""
        self.ensure_one()
        
        # Actualizar contador de impresión
        self.write({
            'print_count': self.print_count + 1,
            'last_print_date': fields.Datetime.now()
        })
        
        # TODO: Retornar acción de reporte
        return self.env.ref('sucursales_cajas.action_report_operation_receipt').report_action(self)
    
    def action_print_voucher(self):
        """Imprime el comprobante para presentar en caja"""
        self.ensure_one()
        
        if self.state not in ['pending', 'processing', 'done']:
            raise UserError(_('Solo se pueden imprimir comprobantes de operaciones válidas.'))
        
        # TODO: Retornar acción de reporte
        return self.env.ref('sucursales_cajas.action_report_operation_voucher').report_action(self)
    
    @api.model
    def get_pending_operations_for_cashbox(self, cashbox_id):
        """Obtiene operaciones pendientes para una caja específica"""
        return self.search([
            ('cashbox_id', '=', cashbox_id),
            ('state', '=', 'pending')
        ], order='request_date')
    
    def name_get(self):
        """Personaliza el display name"""
        result = []
        type_names = dict(self._fields['operation_type'].selection)
        
        for operation in self:
            name_parts = [operation.name]
            if operation.operation_type:
                name_parts.append(f"[{type_names.get(operation.operation_type, '')}]")
            if operation.partner_id:
                name_parts.append(operation.partner_id.name)
            
            result.append((operation.id, ' - '.join(name_parts)))
        
        return result