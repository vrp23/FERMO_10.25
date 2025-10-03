# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import hashlib


class SessionLoginWizard(models.TransientModel):
    _name = 'sucursales_cajas.session_login_wizard'
    _description = 'Wizard para Iniciar Sesión de Caja'
    
    # Caja
    cashbox_id = fields.Many2one(
        'sucursales_cajas.cashbox',
        string='Caja',
        required=True,
        readonly=True
    )
    
    # Usuario
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        readonly=True,
        default=lambda self: self.env.user
    )
    
    # PIN
    pin = fields.Char(
        string='PIN de Sesión',
        size=6,
        help="Ingrese un PIN de 6 dígitos para esta sesión"
    )
    
    confirm_pin = fields.Char(
        string='Confirmar PIN',
        size=6,
        help="Vuelva a ingresar el PIN para confirmar"
    )
    
    # Información de la caja
    cashbox_info = fields.Html(
        string='Información de la Caja',
        compute='_compute_cashbox_info'
    )
    
    # Líneas para declarar saldos iniciales
    balance_line_ids = fields.One2many(
        'sucursales_cajas.session_login_wizard.line',
        'wizard_id',
        string='Saldos Iniciales'
    )
    
    # Opciones
    use_previous_balance = fields.Boolean(
        string='Usar Saldos Anteriores',
        default=True,
        help="Usar los saldos del cierre de la última sesión"
    )
    
    skip_opening_balance = fields.Boolean(
        string='Omitir Declaración de Saldos',
        help="Iniciar sesión sin declarar saldos de apertura (no recomendado)"
    )
    
    # Notas
    opening_notes = fields.Text(
        string='Observaciones de Apertura'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Carga valores por defecto"""
        res = super().default_get(fields_list)
        
        # Obtener caja del contexto
        cashbox_id = self.env.context.get('default_cashbox_id')
        if cashbox_id:
            cashbox = self.env['sucursales_cajas.cashbox'].browse(cashbox_id)
            
            # Crear líneas para cada subcaja
            lines = []
            for cashbox_line in cashbox.cashbox_line_ids.filtered('active'):
                # Asegurar que currency_type tenga un valor válido
                currency_type = cashbox_line.currency_type or 'ARS'
                
                line_vals = {
                    'cashbox_line_id': cashbox_line.id,
                    'currency_type': currency_type,
                    'system_balance': cashbox_line.current_balance,
                    'declared_balance': cashbox_line.current_balance,  # Por defecto igual al sistema
                    'is_cash': cashbox_line.is_cash,
                    'line_name': cashbox_line.display_name,
                }
                
                # Para líneas con cuentas, preseleccionar si hay una sola
                if not cashbox_line.is_cash and cashbox_line.account_ids:
                    if len(cashbox_line.account_ids) == 1:
                        line_vals['account_id'] = cashbox_line.account_ids[0].id
                
                lines.append((0, 0, line_vals))
            
            res['balance_line_ids'] = lines
        
        return res
    
    @api.depends('cashbox_id')
    def _compute_cashbox_info(self):
        """Genera información HTML de la caja"""
        for wizard in self:
            if not wizard.cashbox_id:
                wizard.cashbox_info = ''
                continue
            
            cashbox = wizard.cashbox_id
            html = '<div class="alert alert-info">'
            html += f'<h5>{cashbox.display_name}</h5>'
            html += '<table class="table table-sm mb-0">'
            
            # Información básica
            html += f'<tr><td><strong>Sucursal:</strong></td><td>{cashbox.branch_id.name}</td></tr>'
            html += f'<tr><td><strong>Responsable:</strong></td><td>{cashbox.responsible_user_id.name if cashbox.responsible_user_id else "No asignado"}</td></tr>'
            
            # Última sesión
            if cashbox.last_session_closing_date:
                html += f'<tr><td><strong>Último cierre:</strong></td>'
                html += f'<td>{cashbox.last_session_closing_date.strftime("%d/%m/%Y %H:%M")}'
                if cashbox.last_session_closing_user_id:
                    html += f' por {cashbox.last_session_closing_user_id.name}'
                html += '</td></tr>'
            
            # Subcajas
            html += f'<tr><td><strong>Subcajas activas:</strong></td><td>{len(cashbox.cashbox_line_ids.filtered("active"))}</td></tr>'
            
            html += '</table></div>'
            
            wizard.cashbox_info = html
    
    @api.constrains('pin', 'confirm_pin')
    def _check_pin(self):
        """Valida el PIN ingresado"""
        for wizard in self:
            if wizard.cashbox_id.require_pin and not wizard.pin:
                raise ValidationError(_('Debe ingresar un PIN para esta caja.'))
            
            if wizard.pin:
                # Validar formato
                if not wizard.pin.isdigit():
                    raise ValidationError(_('El PIN debe contener solo números.'))
                
                if len(wizard.pin) != 6:
                    raise ValidationError(_('El PIN debe tener exactamente 6 dígitos.'))
                
                # Validar confirmación
                if wizard.pin != wizard.confirm_pin:
                    raise ValidationError(_('El PIN y su confirmación no coinciden.'))
    
    @api.onchange('use_previous_balance')
    def _onchange_use_previous_balance(self):
        """Actualiza los saldos declarados según la opción"""
        if self.use_previous_balance:
            # Restaurar saldos del sistema
            for line in self.balance_line_ids:
                line.declared_balance = line.system_balance
        else:
            # Limpiar saldos declarados para entrada manual
            for line in self.balance_line_ids:
                if line.is_cash:
                    line.declared_balance = 0.0
    
    @api.onchange('skip_opening_balance')
    def _onchange_skip_opening_balance(self):
        """Muestra advertencia al omitir declaración de saldos"""
        if self.skip_opening_balance:
            return {
                'warning': {
                    'title': _('Advertencia'),
                    'message': _('No se recomienda omitir la declaración de saldos iniciales. '
                               'Esto puede afectar el control y arqueo de caja.')
                }
            }
    
    def _create_opening_balances(self, session):
        """Crea los balances de apertura para la sesión"""
        Balance = self.env['sucursales_cajas.balance']
        
        for line in self.balance_line_ids:
            # Asegurar que cashbox_line_id existe
            if not line.cashbox_line_id:
                raise ValidationError(_('Error al procesar subcaja. Por favor, cierre el wizard y vuelva a intentar.'))
                
            balance_vals = {
                'session_id': session.id,
                'balance_type': 'opening',
                'cashbox_line_id': line.cashbox_line_id.id,
                'system_balance': line.system_balance,
                'declared_amount': line.declared_balance,
                'account_id': line.account_id.id if line.account_id else False,
                'notes': line.notes,
            }
            
            # Para efectivo, si hay diferencia, podría requerir conteo
            if line.is_cash and line.declared_balance != line.system_balance:
                balance_vals['counted_amount'] = line.declared_balance
            
            balance = Balance.create(balance_vals)
            
            # Auto-confirmar el balance de apertura
            balance.action_confirm()
    
    def action_start_session(self):
        """Inicia la sesión de caja"""
        self.ensure_one()
        
        # Validaciones finales
        if self.cashbox_id.active_session_id:
            raise UserError(
                _('La caja ya tiene una sesión activa. Usuario: %s') 
                % self.cashbox_id.session_user_id.name
            )
        
        if self.user_id not in self.cashbox_id.allowed_user_ids:
            raise UserError(
                _('El usuario %s no está autorizado para operar esta caja.') 
                % self.user_id.name
            )
        
        # Crear la sesión
        session_vals = {
            'cashbox_id': self.cashbox_id.id,
            'user_id': self.user_id.id,
            'state': 'open',
        }
        
        # Agregar PIN hasheado si se requiere
        if self.cashbox_id.require_pin and self.pin:
            session_vals['pin_hash'] = hashlib.sha256(self.pin.encode()).hexdigest()
        
        # Capturar información del dispositivo si está disponible
        if self.env.context.get('device_info'):
            session_vals['device_info'] = self.env.context.get('device_info')
        if self.env.context.get('login_ip'):
            session_vals['login_ip'] = self.env.context.get('login_ip')
        
        # Crear sesión
        session = self.env['sucursales_cajas.session'].create(session_vals)
        
        # Crear balances de apertura si no se omiten
        if not self.skip_opening_balance:
            self._create_opening_balances(session)
        
        # Mostrar la sesión creada
        return {
            'name': _('Sesión Iniciada'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.session',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'show_success_message': _('Sesión iniciada exitosamente. ¡Buen trabajo!'),
            }
        }
    
    def action_quick_start(self):
        """Inicio rápido con valores por defecto"""
        self.ensure_one()
        
        # Establecer valores por defecto
        self.use_previous_balance = True
        self.skip_opening_balance = False
        
        # Si requiere PIN y no está establecido, generar uno
        if self.cashbox_id.require_pin and not self.pin:
            # Generar PIN aleatorio
            import random
            self.pin = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            self.confirm_pin = self.pin
            
            # Mostrar el PIN generado
            return {
                'warning': {
                    'title': _('PIN Generado'),
                    'message': _('Se ha generado el PIN: %s\n'
                               'Por favor, anótelo en un lugar seguro.') % self.pin
                }
            }
        
        # Iniciar sesión directamente
        return self.action_start_session()


class SessionLoginWizardLine(models.TransientModel):
    _name = 'sucursales_cajas.session_login_wizard.line'
    _description = 'Línea de Saldo Inicial'
    _order = 'sequence'
    
    wizard_id = fields.Many2one(
        'sucursales_cajas.session_login_wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    cashbox_line_id = fields.Many2one(
        'sucursales_cajas.cashbox_line',
        string='Subcaja',
        required=True
    )
    
    line_name = fields.Char(
        string='Nombre Subcaja'
    )
    
    currency_type = fields.Selection([
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('EUR', 'Euros'),
        ('USDT', 'Tether USDT'),
        ('USDC', 'USD Coin'),
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('other', 'Otra')
    ], string='Moneda', required=True, default='ARS')
    
    is_cash = fields.Boolean(
        string='Es Efectivo',
        default=False
    )
    
    system_balance = fields.Float(
        string='Saldo Sistema',
        readonly=True,
        help="Saldo actual según el sistema"
    )
    
    declared_balance = fields.Float(
        string='Saldo Declarado',
        help="Saldo inicial declarado para esta sesión"
    )
    
    difference = fields.Float(
        string='Diferencia',
        compute='_compute_difference'
    )
    
    # Para cuentas no efectivo
    account_id = fields.Many2one(
        'sucursales_cajas.account',
        string='Cuenta',
        domain="[('cashbox_line_id', '=', cashbox_line_id)]"
    )
    
    notes = fields.Text(
        string='Observaciones'
    )
    
    @api.depends('system_balance', 'declared_balance')
    def _compute_difference(self):
        """Calcula la diferencia entre lo declarado y el sistema"""
        for line in self:
            line.difference = line.declared_balance - line.system_balance
    
    @api.onchange('declared_balance')
    def _onchange_declared_balance(self):
        """Advierte si hay diferencia significativa"""
        if self.system_balance and self.declared_balance:
            diff_percent = abs(self.difference) / self.system_balance * 100 if self.system_balance != 0 else 0
            
            if diff_percent > 10:  # Más del 10% de diferencia
                return {
                    'warning': {
                        'title': _('Diferencia Significativa'),
                        'message': _('Hay una diferencia del %.1f%% entre el saldo declarado '
                                   'y el saldo del sistema. Por favor verifique.') % diff_percent
                    }
                }