# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date, timedelta


class SucursalesCajasCashbox(models.Model):
    _name = 'sucursales_cajas.cashbox'
    _description = 'Caja'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'branch_id, sequence, name'
    _rec_name = 'display_name'
    
    # Campos básicos
    name = fields.Char(
        string='Nombre de la Caja',
        required=True,
        tracking=True,
        help="Nombre identificativo de la caja"
    )
    
    code = fields.Char(
        string='Código',
        help="Código único de la caja",
        tracking=True
    )
    
    display_name = fields.Char(
        string='Nombre Completo',
        compute='_compute_display_name',
        store=True
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help="Orden de visualización"
    )
    
    # Relación con sucursal
    branch_id = fields.Many2one(
        'sucursales_cajas.branch',
        string='Sucursal',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('active', '=', True)]"
    )
    
    # Relación con empresa (heredada de sucursal)
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        related='branch_id.company_id',
        store=True,
        readonly=True
    )
    
    # Usuarios permitidos
    allowed_user_ids = fields.Many2many(
        'res.users',
        'sucursales_cajas_cashbox_users_rel',
        'cashbox_id',
        'user_id',
        string='Usuarios Permitidos',
        help="Usuarios que pueden operar esta caja",
        tracking=True
    )
    
    # Responsable de la caja
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        tracking=True,
        help="Usuario responsable principal de esta caja"
    )
    
    # Líneas de caja (subcajas)
    cashbox_line_ids = fields.One2many(
        'sucursales_cajas.cashbox_line',
        'cashbox_id',
        string='Subcajas',
        help="Tipos de activos manejados por esta caja"
    )
    
    # Contadores
    line_count = fields.Integer(
        string='Cantidad de Subcajas',
        compute='_compute_counts',
        store=True
    )
    
    pending_operations_count = fields.Integer(
        string='Operaciones Pendientes',
        compute='_compute_counts',
        store=True
    )
    
    # Sesión activa
    active_session_id = fields.Many2one(
        'sucursales_cajas.session',
        string='Sesión Activa',
        readonly=True,
        tracking=True,
        help="Sesión actualmente abierta en esta caja"
    )
    
    session_state = fields.Selection(
        related='active_session_id.state',
        string='Estado de Sesión',
        readonly=True
    )
    
    session_user_id = fields.Many2one(
        related='active_session_id.user_id',
        string='Usuario en Sesión',
        readonly=True
    )
    
    # Balance total
    total_balance_ars = fields.Float(
        string='Balance Total (ARS)',
        compute='_compute_total_balances',
        help="Balance total convertido a ARS"
    )
    
    total_balance_usd = fields.Float(
        string='Balance Total (USD)',
        compute='_compute_total_balances',
        help="Balance total convertido a USD"
    )
    
    # Estado
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('ready', 'Lista'),
        ('in_session', 'En Sesión'),
        ('closed', 'Cerrada Temporalmente')
    ], string='Estado', default='draft', tracking=True)
    
    # Configuración operacional
    require_pin = fields.Boolean(
        string='Requiere PIN',
        default=True,
        help="Si se requiere PIN adicional para iniciar sesión"
    )
    
    allow_negative_balance = fields.Boolean(
        string='Permitir Saldo Negativo',
        default=False,
        help="Permitir operaciones que resulten en saldo negativo"
    )
    
    max_cash_amount = fields.Float(
        string='Monto Máximo en Efectivo',
        default=0.0,
        help="Monto máximo permitido en efectivo (0 = sin límite)"
    )
    
    # Horarios de operación
    operating_hours = fields.Text(
        string='Horarios de Operación',
        help="Horarios de atención de la caja"
    )
    
    # Notas
    notes = fields.Text(
        string='Notas',
        help="Información adicional sobre la caja"
    )
    
    # Campos de auditoría
    last_session_closing_date = fields.Datetime(
        string='Último Cierre de Sesión',
        readonly=True
    )
    
    last_session_closing_user_id = fields.Many2one(
        'res.users',
        string='Usuario Último Cierre',
        readonly=True
    )
    
    # Campos para Dashboard
    operation_count_today = fields.Integer(
        string='Operaciones Hoy',
        compute='_compute_dashboard_stats'
    )
    
    deposit_count_today = fields.Integer(
        string='Depósitos Hoy',
        compute='_compute_dashboard_stats'
    )
    
    withdrawal_count_today = fields.Integer(
        string='Retiros Hoy',
        compute='_compute_dashboard_stats'
    )
    
    pending_count_today = fields.Integer(
        string='Pendientes Hoy',
        compute='_compute_dashboard_stats'
    )
    
    branch_summary_ids = fields.One2many(
        'sucursales_cajas.branch',
        compute='_compute_dashboard_data',
        string='Resumen de Sucursales'
    )
    
    active_cashbox_ids = fields.Many2many(
        'sucursales_cajas.cashbox',
        compute='_compute_dashboard_data',
        string='Cajas Activas'
    )
    
    recent_operation_ids = fields.One2many(
        'sucursales_cajas.operation',
        compute='_compute_dashboard_data',
        string='Operaciones Recientes'
    )
    
    # Tiempo de sesión activa
    session_start_time = fields.Datetime(
        related='active_session_id.start_datetime',
        string='Inicio de Sesión'
    )
    
    @api.depends('name', 'code', 'branch_id')
    def _compute_display_name(self):
        """Genera el nombre completo para mostrar"""
        for cashbox in self:
            parts = []
            if cashbox.branch_id:
                parts.append(cashbox.branch_id.name)
            if cashbox.code:
                parts.append(f'[{cashbox.code}]')
            parts.append(cashbox.name or '')
            
            cashbox.display_name = ' - '.join(filter(None, parts))
    
    @api.depends('cashbox_line_ids')
    def _compute_counts(self):
        """Calcula contadores varios"""
        Operation = self.env['sucursales_cajas.operation']
        
        for cashbox in self:
            # Contar líneas
            cashbox.line_count = len(cashbox.cashbox_line_ids)
            
            # Contar operaciones pendientes
            cashbox.pending_operations_count = Operation.search_count([
                ('cashbox_id', '=', cashbox.id),
                ('state', '=', 'pending')
            ])
    
    def _compute_total_balances(self):
        """Calcula los balances totales en diferentes monedas"""
        for cashbox in self:
            total_ars = 0.0
            total_usd = 0.0
            
            # Por ahora, sumamos directamente sin conversión
            # TODO: Implementar conversión de monedas cuando se integre con el módulo de divisas
            for line in cashbox.cashbox_line_ids:
                if line.currency_type == 'ARS':
                    total_ars += line.current_balance
                elif line.currency_type == 'USD':
                    total_usd += line.current_balance
                # Otras monedas se convertirán más adelante
            
            cashbox.total_balance_ars = total_ars
            cashbox.total_balance_usd = total_usd
    
    def _compute_dashboard_stats(self):
        """Calcula estadísticas del día para el dashboard"""
        Operation = self.env['sucursales_cajas.operation']
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        for cashbox in self:
            domain_base = [
                ('cashbox_id', '=', cashbox.id),
                ('create_date', '>=', today_start),
                ('create_date', '<=', today_end)
            ]
            
            # Total de operaciones del día
            cashbox.operation_count_today = Operation.search_count(domain_base)
            
            # Depósitos del día
            cashbox.deposit_count_today = Operation.search_count(
                domain_base + [('operation_type', '=', 'deposit')]
            )
            
            # Retiros del día
            cashbox.withdrawal_count_today = Operation.search_count(
                domain_base + [('operation_type', '=', 'withdrawal')]
            )
            
            # Pendientes del día
            cashbox.pending_count_today = Operation.search_count(
                domain_base + [('state', '=', 'pending')]
            )
    
    def _compute_dashboard_data(self):
        """Calcula datos complejos para el dashboard"""
        # Este método es llamado desde el dashboard para un registro dummy
        # Solo calculamos si es el primer registro o uno específico
        for cashbox in self:
            # Resumen de sucursales
            branches = self.env['sucursales_cajas.branch'].search([
                ('active', '=', True)
            ])
            cashbox.branch_summary_ids = branches
            
            # Cajas activas
            active_cashboxes = self.search([
                ('state', '=', 'in_session')
            ], limit=10)
            cashbox.active_cashbox_ids = active_cashboxes
            
            # Operaciones recientes
            recent_ops = self.env['sucursales_cajas.operation'].search([
                ('state', '!=', 'cancelled')
            ], order='create_date desc', limit=10)
            cashbox.recent_operation_ids = recent_ops
    
    @api.model
    def _compute_dashboard_data(self):
        """Método estático para actualizar datos del dashboard (llamado por cron)"""
        # Este método puede usarse para pre-calcular datos si es necesario
        # Por ahora no hacemos nada ya que los cálculos son en tiempo real
        return True
    
    @api.constrains('allowed_user_ids', 'responsible_user_id')
    def _check_responsible_in_allowed_users(self):
        """Verifica que el responsable esté en los usuarios permitidos"""
        for cashbox in self:
            if cashbox.responsible_user_id and cashbox.responsible_user_id not in cashbox.allowed_user_ids:
                raise ValidationError(
                    _('El responsable debe estar incluido en los usuarios permitidos de la caja.')
                )
    
    @api.constrains('branch_id', 'name')
    def _check_unique_name_per_branch(self):
        """Verifica que no haya nombres duplicados en la misma sucursal"""
        for cashbox in self:
            duplicate = self.search([
                ('branch_id', '=', cashbox.branch_id.id),
                ('name', '=', cashbox.name),
                ('id', '!=', cashbox.id)
            ], limit=1)
            
            if duplicate:
                raise ValidationError(
                    _('Ya existe una caja con el nombre "%s" en la sucursal "%s".')
                    % (cashbox.name, cashbox.branch_id.name)
                )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para configuración inicial"""
        for vals in vals_list:
            # Auto-generar código si no se proporciona
            if not vals.get('code'):
                branch_id = vals.get('branch_id')
                if branch_id:
                    branch = self.env['sucursales_cajas.branch'].browse(branch_id)
                    sequence = self.search_count([('branch_id', '=', branch_id)]) + 1
                    vals['code'] = f'{branch.code}-C{sequence:02d}'
                else:
                    vals['code'] = f'CAJA{self.search_count([]) + 1:03d}'
            
            # Si hay un responsable, agregarlo a usuarios permitidos
            if vals.get('responsible_user_id'):
                user_ids = []
                if vals.get('allowed_user_ids'):
                    # Extraer IDs existentes
                    for item in vals['allowed_user_ids']:
                        if item[0] == 6:  # set
                            user_ids = list(item[2])
                        elif item[0] == 4:  # add
                            user_ids.append(item[1])
                
                if vals['responsible_user_id'] not in user_ids:
                    user_ids.append(vals['responsible_user_id'])
                    vals['allowed_user_ids'] = [(6, 0, user_ids)]
        
        cashboxes = super(SucursalesCajasCashbox, self).create(vals_list)
        
        # Crear líneas de caja por defecto para efectivo
        for cashbox in cashboxes:
            if not cashbox.cashbox_line_ids:
                # Crear líneas básicas de efectivo
                default_lines = [
                    {'line_type': 'cash_ars', 'sequence': 10},
                    {'line_type': 'cash_usd', 'sequence': 20},
                ]
                
                for line_vals in default_lines:
                    line_vals['cashbox_id'] = cashbox.id
                    self.env['sucursales_cajas.cashbox_line'].create(line_vals)
            
            # Cambiar estado a ready si tiene líneas
            if cashbox.cashbox_line_ids:
                cashbox.state = 'ready'
        
        return cashboxes
    
    def write(self, vals):
        """Override write para validaciones"""
        # Si se actualiza el responsable, agregarlo a usuarios permitidos
        if vals.get('responsible_user_id'):
            for cashbox in self:
                current_users = cashbox.allowed_user_ids.ids
                if vals['responsible_user_id'] not in current_users:
                    current_users.append(vals['responsible_user_id'])
                    vals['allowed_user_ids'] = [(6, 0, current_users)]
        
        # Validar cambios de estado
        if vals.get('state'):
            for cashbox in self:
                if cashbox.state == 'in_session' and vals['state'] != 'in_session':
                    if cashbox.active_session_id and cashbox.active_session_id.state == 'open':
                        raise UserError(
                            _('No se puede cambiar el estado de la caja mientras hay una sesión activa.')
                        )
        
        return super(SucursalesCajasCashbox, self).write(vals)
    
    @api.onchange('responsible_user_id')
    def _onchange_responsible_user_id(self):
        """Al cambiar el responsable, sugerir agregarlo a usuarios permitidos"""
        if self.responsible_user_id and self.responsible_user_id not in self.allowed_user_ids:
            self.allowed_user_ids = [(4, self.responsible_user_id.id)]
    
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        """Al cambiar la sucursal, filtrar usuarios permitidos"""
        if self.branch_id:
            # Sugerir usuarios de la sucursal
            return {
                'domain': {
                    'allowed_user_ids': [('id', 'in', self.branch_id.allowed_user_ids.ids)],
                    'responsible_user_id': [('id', 'in', self.branch_id.allowed_user_ids.ids)]
                }
            }
    
    def action_open_session(self):
        """Abre el wizard para iniciar sesión"""
        self.ensure_one()
        
        if self.state != 'ready':
            raise UserError(
                _('La caja debe estar en estado "Lista" para iniciar sesión.')
            )
        
        if self.active_session_id:
            raise UserError(
                _('Ya hay una sesión activa en esta caja. Usuario: %s') 
                % self.session_user_id.name
            )
        
        # Verificar que el usuario actual esté permitido
        if self.env.user not in self.allowed_user_ids:
            raise UserError(
                _('No tiene permisos para operar esta caja.')
            )
        
        return {
            'name': _('Iniciar Sesión de Caja'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.session_login_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_cashbox_id': self.id,
                'default_user_id': self.env.user.id,
            }
        }
    
    def action_view_active_session(self):
        """Ver la sesión activa"""
        self.ensure_one()
        
        if not self.active_session_id:
            raise UserError(_('No hay sesión activa en esta caja.'))
        
        return {
            'name': _('Sesión Activa'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.session',
            'res_id': self.active_session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_pending_operations(self):
        """Ver operaciones pendientes de la caja"""
        self.ensure_one()
        return {
            'name': _('Operaciones Pendientes - %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.operation',
            'view_mode': 'tree,form',
            'domain': [
                ('cashbox_id', '=', self.id),
                ('state', '=', 'pending')
            ],
            'context': {
                'default_cashbox_id': self.id,
                'search_default_pending': 1,
            }
        }
    
    def action_view_cashbox_lines(self):
        """Ver las líneas/subcajas"""
        self.ensure_one()
        return {
            'name': _('Subcajas - %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.cashbox_line',
            'view_mode': 'tree,form',
            'domain': [('cashbox_id', '=', self.id)],
            'context': {
                'default_cashbox_id': self.id,
                'search_default_active': 1,
            }
        }
    
    def action_add_cashbox_line(self):
        """Agregar una nueva línea/subcaja"""
        self.ensure_one()
        
        return {
            'name': _('Nueva Subcaja'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.cashbox_line',
            'view_mode': 'form',
            'context': {
                'default_cashbox_id': self.id,
            },
            'target': 'new',
        }
    
    def name_get(self):
        """Usa display_name para mostrar"""
        return [(cashbox.id, cashbox.display_name) for cashbox in self]
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, order=None):
        """Permite buscar por código o nombre"""
        if name:
            args = args or []
            domain = ['|', ('code', operator, name), ('name', operator, name)]
            return self.search(domain + args, limit=limit, order=order).ids
        return super()._name_search(name, args, operator, limit, order)
    
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """Override copy para manejar duplicación"""
        default = dict(default or {})
        default.update({
            'name': _("%s (Copia)") % self.name,
            'code': False,
            'state': 'draft',
            'active_session_id': False,
        })
        return super(SucursalesCajasCashbox, self).copy(default)
    
    def unlink(self):
        """Validaciones antes de eliminar"""
        for cashbox in self:
            if cashbox.state == 'in_session':
                raise UserError(
                    _('No se puede eliminar la caja "%s" porque tiene una sesión activa.')
                    % cashbox.name
                )
            
            # Verificar si hay operaciones
            operations = self.env['sucursales_cajas.operation'].search([
                ('cashbox_id', '=', cashbox.id)
            ], limit=1)
            
            if operations:
                raise UserError(
                    _('No se puede eliminar la caja "%s" porque tiene operaciones registradas.')
                    % cashbox.name
                )
        
        return super(SucursalesCajasCashbox, self).unlink()