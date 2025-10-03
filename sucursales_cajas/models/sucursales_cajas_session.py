# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import hashlib
import random
import string


class SucursalesCajasSession(models.Model):
    _name = 'sucursales_cajas.session'
    _description = 'Sesión de Caja'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'
    _rec_name = 'name'
    
    # Identificación
    name = fields.Char(
        string='Número de Sesión',
        required=True,
        readonly=True,
        default='Nueva',
        copy=False,
        tracking=True
    )
    
    # Relaciones principales
    cashbox_id = fields.Many2one(
        'sucursales_cajas.cashbox',
        string='Caja',
        required=True,
        readonly=True,
        ondelete='restrict',
        tracking=True
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        readonly=True,
        tracking=True
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
    
    # Fechas y tiempos
    start_datetime = fields.Datetime(
        string='Fecha/Hora Inicio',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    end_datetime = fields.Datetime(
        string='Fecha/Hora Cierre',
        readonly=True,
        tracking=True
    )
    
    duration = fields.Float(
        string='Duración (horas)',
        compute='_compute_duration',
        store=True
    )
    
    # PIN de sesión (encriptado)
    pin_hash = fields.Char(
        string='PIN Hash',
        readonly=True,
        copy=False
    )
    
    # Estado
    state = fields.Selection([
        ('open', 'Abierta'),
        ('closing', 'En Cierre'),
        ('closed', 'Cerrada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='open', tracking=True, required=True)
    
    # Balances
    opening_balance_ids = fields.One2many(
        'sucursales_cajas.balance',
        'session_id',
        string='Balances de Apertura',
        domain=[('balance_type', '=', 'opening')]
    )
    
    closing_balance_ids = fields.One2many(
        'sucursales_cajas.balance',
        'session_id',
        string='Balances de Cierre',
        domain=[('balance_type', '=', 'closing')]
    )
    
    # Operaciones
    operation_ids = fields.One2many(
        'sucursales_cajas.operation',
        'session_id',
        string='Operaciones'
    )
    
    # Contadores
    operation_count = fields.Integer(
        string='Cantidad de Operaciones',
        compute='_compute_counts',
        store=True
    )
    
    pending_operation_count = fields.Integer(
        string='Operaciones Pendientes',
        compute='_compute_counts',
        store=True
    )
    
    deposit_count = fields.Integer(
        string='Depósitos',
        compute='_compute_counts',
        store=True
    )
    
    withdrawal_count = fields.Integer(
        string='Retiros',
        compute='_compute_counts',
        store=True
    )
    
    # Totales por moneda
    total_deposits_ars = fields.Float(
        string='Total Depósitos ARS',
        compute='_compute_totals',
        store=True
    )
    
    total_withdrawals_ars = fields.Float(
        string='Total Retiros ARS',
        compute='_compute_totals',
        store=True
    )
    
    total_deposits_usd = fields.Float(
        string='Total Depósitos USD',
        compute='_compute_totals',
        store=True
    )
    
    total_withdrawals_usd = fields.Float(
        string='Total Retiros USD',
        compute='_compute_totals',
        store=True
    )
    
    # Control de cierre
    has_pending_operations = fields.Boolean(
        string='Tiene Operaciones Pendientes',
        compute='_compute_has_pending'
    )
    
    closing_notes = fields.Text(
        string='Observaciones de Cierre'
    )
    
    # IP y dispositivo
    login_ip = fields.Char(
        string='IP de Conexión',
        readonly=True
    )
    
    device_info = fields.Text(
        string='Información del Dispositivo',
        readonly=True
    )
    
    # Campos para manejo de errores/excepciones
    has_discrepancies = fields.Boolean(
        string='Tiene Discrepancias',
        compute='_compute_has_discrepancies',
        store=True
    )
    
    total_discrepancy_amount = fields.Float(
        string='Monto Total Discrepancias',
        compute='_compute_has_discrepancies',
        store=True
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para generar número de sesión"""
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                vals['name'] = self.env['ir.sequence'].next_by_code('sucursales_cajas.session') or 'SES/001'
            
            # Capturar información del contexto
            if self.env.context.get('login_ip'):
                vals['login_ip'] = self.env.context.get('login_ip')
            if self.env.context.get('device_info'):
                vals['device_info'] = self.env.context.get('device_info')
        
        sessions = super(SucursalesCajasSession, self).create(vals_list)
        
        # Actualizar el estado de la caja
        for session in sessions:
            session.cashbox_id.write({
                'active_session_id': session.id,
                'state': 'in_session'
            })
        
        return sessions
    
    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        """Calcula la duración de la sesión"""
        for session in self:
            if session.start_datetime and session.end_datetime:
                delta = session.end_datetime - session.start_datetime
                session.duration = delta.total_seconds() / 3600.0
            else:
                session.duration = 0.0
    
    @api.depends('operation_ids', 'operation_ids.state', 'operation_ids.operation_type')
    def _compute_counts(self):
        """Calcula contadores de operaciones"""
        for session in self:
            operations = session.operation_ids
            session.operation_count = len(operations)
            session.pending_operation_count = len(operations.filtered(lambda o: o.state == 'pending'))
            session.deposit_count = len(operations.filtered(
                lambda o: o.operation_type == 'deposit' and o.state == 'done'
            ))
            session.withdrawal_count = len(operations.filtered(
                lambda o: o.operation_type == 'withdrawal' and o.state == 'done'
            ))
    
    @api.depends('operation_ids', 'operation_ids.amount', 'operation_ids.currency_type', 
                 'operation_ids.operation_type', 'operation_ids.state')
    def _compute_totals(self):
        """Calcula totales por moneda"""
        for session in self:
            # Filtrar solo operaciones completadas
            done_operations = session.operation_ids.filtered(lambda o: o.state == 'done')
            
            # Depósitos
            deposits_ars = done_operations.filtered(
                lambda o: o.operation_type == 'deposit' and o.currency_type == 'ARS'
            )
            deposits_usd = done_operations.filtered(
                lambda o: o.operation_type == 'deposit' and o.currency_type == 'USD'
            )
            
            # Retiros
            withdrawals_ars = done_operations.filtered(
                lambda o: o.operation_type == 'withdrawal' and o.currency_type == 'ARS'
            )
            withdrawals_usd = done_operations.filtered(
                lambda o: o.operation_type == 'withdrawal' and o.currency_type == 'USD'
            )
            
            # Sumar
            session.total_deposits_ars = sum(deposits_ars.mapped('amount'))
            session.total_deposits_usd = sum(deposits_usd.mapped('amount'))
            session.total_withdrawals_ars = sum(withdrawals_ars.mapped('amount'))
            session.total_withdrawals_usd = sum(withdrawals_usd.mapped('amount'))
    
    def _compute_has_pending(self):
        """Verifica si hay operaciones pendientes"""
        for session in self:
            session.has_pending_operations = any(
                op.state == 'pending' for op in session.operation_ids
            )
    
    @api.depends('closing_balance_ids', 'closing_balance_ids.difference')
    def _compute_has_discrepancies(self):
        """Calcula si hay discrepancias en los balances"""
        for session in self:
            closing_balances = session.closing_balance_ids.filtered(
                lambda b: b.state == 'confirmed'
            )
            
            if closing_balances:
                differences = closing_balances.mapped('difference')
                session.has_discrepancies = any(diff != 0 for diff in differences)
                session.total_discrepancy_amount = sum(abs(diff) for diff in differences)
            else:
                session.has_discrepancies = False
                session.total_discrepancy_amount = 0.0
    
    @api.model
    def generate_pin(self, length=6):
        """Genera un PIN aleatorio"""
        return ''.join(random.choices(string.digits, k=length))
    
    @api.model
    def hash_pin(self, pin):
        """Hashea un PIN para almacenamiento seguro"""
        if not pin:
            return False
        return hashlib.sha256(pin.encode()).hexdigest()
    
    def verify_pin(self, pin):
        """Verifica un PIN contra el hash almacenado"""
        self.ensure_one()
        if not self.pin_hash or not pin:
            return False
        return self.pin_hash == self.hash_pin(pin)
    
    def action_start_closing(self):
        """Inicia el proceso de cierre"""
        self.ensure_one()
        
        if self.state != 'open':
            raise UserError(_('La sesión debe estar abierta para iniciar el cierre.'))
        
        if self.has_pending_operations:
            raise UserError(
                _('No se puede cerrar la sesión con operaciones pendientes. '
                  'Debe procesar o cancelar las operaciones pendientes primero.')
            )
        
        # Cambiar estado
        self.state = 'closing'
        
        # Crear balances de cierre para cada línea de caja
        Balance = self.env['sucursales_cajas.balance']
        for line in self.cashbox_id.cashbox_line_ids:
            # Verificar si ya existe balance de cierre
            existing = Balance.search([
                ('session_id', '=', self.id),
                ('cashbox_line_id', '=', line.id),
                ('balance_type', '=', 'closing')
            ])
            
            if not existing:
                Balance.create({
                    'session_id': self.id,
                    'cashbox_line_id': line.id,
                    'balance_type': 'closing',
                    'system_balance': line.session_current_balance,
                })
        
        # Abrir wizard de cierre
        return {
            'name': _('Cerrar Sesión de Caja'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.close_session_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_session_id': self.id,
            }
        }
    
    def action_close_session(self):
        """Cierra definitivamente la sesión"""
        self.ensure_one()
        
        if self.state != 'closing':
            raise UserError(_('La sesión debe estar en proceso de cierre.'))
        
        # Verificar que todos los balances estén confirmados
        unconfirmed_balances = self.closing_balance_ids.filtered(
            lambda b: b.state != 'confirmed'
        )
        
        if unconfirmed_balances:
            raise UserError(
                _('Debe confirmar todos los balances de cierre antes de cerrar la sesión.')
            )
        
        # Actualizar campos
        self.write({
            'state': 'closed',
            'end_datetime': fields.Datetime.now(),
        })
        
        # Actualizar caja
        self.cashbox_id.write({
            'active_session_id': False,
            'state': 'ready',
            'last_session_closing_date': self.end_datetime,
            'last_session_closing_user_id': self.env.user.id,
        })
        
        # TODO: Generar asientos contables si corresponde
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sesión Cerrada'),
                'message': _('La sesión %s ha sido cerrada exitosamente.') % self.name,
                'sticky': False,
                'type': 'success',
            }
        }
    
    def action_cancel_session(self):
        """Cancela la sesión (solo si no hay operaciones)"""
        self.ensure_one()
        
        if self.state not in ['open', 'closing']:
            raise UserError(_('Solo se pueden cancelar sesiones abiertas o en cierre.'))
        
        if self.operation_ids:
            raise UserError(
                _('No se puede cancelar una sesión que tiene operaciones registradas.')
            )
        
        # Cambiar estado
        self.write({
            'state': 'cancelled',
            'end_datetime': fields.Datetime.now(),
        })
        
        # Actualizar caja
        self.cashbox_id.write({
            'active_session_id': False,
            'state': 'ready',
        })
        
        return True
    
    def action_view_operations(self):
        """Ver todas las operaciones de la sesión"""
        self.ensure_one()
        return {
            'name': _('Operaciones - Sesión %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.operation',
            'view_mode': 'tree,form',
            'domain': [('session_id', '=', self.id)],
            'context': {
                'default_session_id': self.id,
                'search_default_group_by_state': 1,
            }
        }
    
    def action_view_cash_details(self):
        """Ver detalles de efectivo"""
        self.ensure_one()
        # TODO: Implementar vista de resumen de efectivo
        raise UserError(_('Función en desarrollo.'))
    
    def action_print_session_report(self):
        """Imprime reporte de sesión"""
        self.ensure_one()
        # TODO: Implementar reporte
        raise UserError(_('Función en desarrollo.'))
    
    @api.constrains('cashbox_id', 'user_id')
    def _check_user_allowed(self):
        """Verifica que el usuario esté permitido en la caja"""
        for session in self:
            if session.user_id not in session.cashbox_id.allowed_user_ids:
                raise ValidationError(
                    _('El usuario %s no está autorizado para operar la caja %s.')
                    % (session.user_id.name, session.cashbox_id.display_name)
                )
    
    @api.constrains('cashbox_id', 'state')
    def _check_one_open_session(self):
        """Verifica que solo haya una sesión abierta por caja"""
        for session in self:
            if session.state in ['open', 'closing']:
                other_sessions = self.search([
                    ('cashbox_id', '=', session.cashbox_id.id),
                    ('state', 'in', ['open', 'closing']),
                    ('id', '!=', session.id)
                ])
                
                if other_sessions:
                    raise ValidationError(
                        _('Ya existe una sesión abierta para la caja %s.')
                        % session.cashbox_id.display_name
                    )
    
    def unlink(self):
        """Validaciones antes de eliminar"""
        for session in self:
            if session.state != 'cancelled':
                raise UserError(
                    _('Solo se pueden eliminar sesiones canceladas.')
                )
        
        return super(SucursalesCajasSession, self).unlink()
    
    @api.model
    def check_session_timeout(self):
        """
        Método para verificar sesiones que llevan mucho tiempo abiertas
        Puede ser llamado por un cron
        """
        timeout_hours = 24  # Configurar según necesidad
        
        timeout_date = fields.Datetime.now() - timedelta(hours=timeout_hours)
        
        old_sessions = self.search([
            ('state', '=', 'open'),
            ('start_datetime', '<', timeout_date)
        ])
        
        for session in old_sessions:
            # Notificar al usuario y/o cerrar automáticamente
            session.message_post(
                body=_('Esta sesión lleva más de %d horas abierta. '
                      'Por favor, proceda a cerrarla.') % timeout_hours,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )