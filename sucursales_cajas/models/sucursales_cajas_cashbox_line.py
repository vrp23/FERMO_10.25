# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SucursalesCajasCashboxLine(models.Model):
    _name = 'sucursales_cajas.cashbox_line'
    _description = 'Línea de Caja (Subcaja)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, line_type'
    _rec_name = 'display_name'
    
    # Campos básicos
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
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
    
    # Relación con caja principal
    cashbox_id = fields.Many2one(
        'sucursales_cajas.cashbox',
        string='Caja',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    # Tipo de línea/subcaja
    line_type = fields.Selection([
        ('cash_ars', 'Efectivo ARS'),
        ('cash_usd', 'Efectivo USD'),
        ('cash_eur', 'Efectivo EUR'),
        ('bank_account', 'Cuenta Bancaria'),
        ('crypto', 'Criptomoneda'),
        ('mercadopago', 'Mercado Pago'),
        ('other', 'Otro')
    ], string='Tipo de Subcaja', required=True, tracking=True)
    
    # Moneda (para efectivo directo)
    currency_type = fields.Selection([
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('EUR', 'Euros'),
        ('USDT', 'Tether USDT'),
        ('USDC', 'USD Coin'),
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('other', 'Otra')
    ], string='Moneda', 
       compute='_compute_currency_type',
       store=True,
       readonly=False,
       tracking=True)
    
    # Cuentas asociadas (para tipos no efectivo)
    account_ids = fields.One2many(
        'sucursales_cajas.account',
        'cashbox_line_id',
        string='Cuentas',
        help="Cuentas bancarias o wallets asociadas"
    )
    
    account_count = fields.Integer(
        string='Cantidad de Cuentas',
        compute='_compute_account_count',
        store=True
    )
    
    # Balance actual
    current_balance = fields.Float(
        string='Saldo Actual',
        tracking=True,
        help="Saldo actual en esta subcaja",
        default=0.0
    )
    
    # Balance en sesión
    session_opening_balance = fields.Float(
        string='Saldo Apertura Sesión',
        compute='_compute_session_balances',
        help="Saldo al inicio de la sesión actual"
    )
    
    session_current_balance = fields.Float(
        string='Saldo Actual en Sesión',
        compute='_compute_session_balances',
        help="Saldo actual considerando movimientos de la sesión"
    )
    
    # Estado
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )
    
    is_cash = fields.Boolean(
        string='Es Efectivo',
        compute='_compute_is_cash',
        store=True
    )
    
    # Límites operacionales
    min_balance = fields.Float(
        string='Saldo Mínimo',
        default=0.0,
        help="Saldo mínimo permitido"
    )
    
    max_balance = fields.Float(
        string='Saldo Máximo',
        default=0.0,
        help="Saldo máximo permitido (0 = sin límite)"
    )
    
    # Notas
    notes = fields.Text(
        string='Notas'
    )
    
    # Campos relacionados para facilitar búsquedas
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
    
    @api.depends('line_type')
    def _compute_name(self):
        """Genera nombre basado en el tipo"""
        type_names = {
            'cash_ars': 'Efectivo ARS',
            'cash_usd': 'Efectivo USD',
            'cash_eur': 'Efectivo EUR',
            'bank_account': 'Cuenta Bancaria',
            'crypto': 'Criptomoneda',
            'mercadopago': 'Mercado Pago',
            'other': 'Otro'
        }
        
        for line in self:
            line.name = type_names.get(line.line_type, 'Subcaja')
    
    @api.depends('name', 'currency_type', 'account_ids')
    def _compute_display_name(self):
        """Genera nombre completo para mostrar"""
        for line in self:
            parts = [line.name or '']
            
            if line.line_type in ['bank_account', 'crypto'] and line.account_ids:
                # Mostrar resumen de cuentas
                account_count = len(line.account_ids)
                if account_count == 1:
                    parts.append(f"- {line.account_ids[0].display_name}")
                else:
                    parts.append(f"- {account_count} cuentas")
            elif line.currency_type and line.line_type not in ['cash_ars', 'cash_usd', 'cash_eur']:
                parts.append(f"({line.currency_type})")
            
            line.display_name = ' '.join(filter(None, parts))
    
    @api.depends('line_type')
    def _compute_currency_type(self):
        """Auto-determina la moneda según el tipo"""
        for line in self:
            if line.line_type == 'cash_ars':
                line.currency_type = 'ARS'
            elif line.line_type == 'cash_usd':
                line.currency_type = 'USD'
            elif line.line_type == 'cash_eur':
                line.currency_type = 'EUR'
            elif line.line_type == 'mercadopago':
                line.currency_type = 'ARS'
            # Para otros tipos, se mantiene el valor actual o se deja en blanco
    
    @api.depends('line_type')
    def _compute_is_cash(self):
        """Determina si es una línea de efectivo"""
        for line in self:
            line.is_cash = line.line_type in ['cash_ars', 'cash_usd', 'cash_eur']
    
    @api.depends('account_ids')
    def _compute_account_count(self):
        """Cuenta las cuentas asociadas"""
        for line in self:
            line.account_count = len(line.account_ids)
    
    def _compute_session_balances(self):
        """Calcula saldos relacionados con la sesión actual"""
        for line in self:
            # Obtener sesión activa de la caja
            session = line.cashbox_id.active_session_id
            
            if session and session.state == 'open':
                # Buscar balance de apertura
                opening_balance = self.env['sucursales_cajas.balance'].search([
                    ('session_id', '=', session.id),
                    ('cashbox_line_id', '=', line.id),
                    ('balance_type', '=', 'opening')
                ], limit=1)
                
                line.session_opening_balance = opening_balance.declared_amount if opening_balance else line.current_balance
                
                # Calcular balance actual en sesión
                # (se implementará cuando tengamos el modelo de operaciones)
                operations_amount = 0.0  # TODO: Sumar operaciones de la sesión
                
                line.session_current_balance = line.session_opening_balance + operations_amount
            else:
                line.session_opening_balance = 0.0
                line.session_current_balance = 0.0
    
    @api.constrains('line_type', 'cashbox_id')
    def _check_unique_line_type(self):
        """Verifica que no haya tipos duplicados en la misma caja para efectivo"""
        for line in self:
            if line.is_cash:
                # Para efectivo, no puede haber duplicados del mismo tipo
                duplicate = self.search([
                    ('cashbox_id', '=', line.cashbox_id.id),
                    ('line_type', '=', line.line_type),
                    ('id', '!=', line.id)
                ], limit=1)
                
                if duplicate:
                    raise ValidationError(
                        _('Ya existe una subcaja de tipo "%s" en esta caja. '
                          'Solo puede haber una subcaja de cada tipo de efectivo.') 
                        % line.name
                    )
    
    @api.constrains('current_balance', 'min_balance', 'max_balance')
    def _check_balance_limits(self):
        """Verifica que el saldo esté dentro de los límites"""
        for line in self:
            if line.current_balance < line.min_balance:
                raise ValidationError(
                    _('El saldo actual (%.2f) está por debajo del mínimo permitido (%.2f) '
                      'para la subcaja "%s".') 
                    % (line.current_balance, line.min_balance, line.display_name)
                )
            
            if line.max_balance > 0 and line.current_balance > line.max_balance:
                raise ValidationError(
                    _('El saldo actual (%.2f) supera el máximo permitido (%.2f) '
                      'para la subcaja "%s".') 
                    % (line.current_balance, line.max_balance, line.display_name)
                )
    
    @api.constrains('min_balance', 'max_balance')
    def _check_limit_values(self):
        """Verifica que los límites sean coherentes"""
        for line in self:
            if line.max_balance > 0 and line.min_balance > line.max_balance:
                raise ValidationError(
                    _('El saldo mínimo no puede ser mayor que el saldo máximo.')
                )
    
    @api.onchange('line_type')
    def _onchange_line_type(self):
        """Ajusta valores según el tipo seleccionado"""
        if self.line_type in ['cash_ars', 'cash_usd', 'cash_eur']:
            # Para efectivo, limpiar cuentas asociadas
            self.account_ids = [(5, 0, 0)]
    
    def action_add_account(self):
        """Abre formulario para agregar una cuenta"""
        self.ensure_one()
        
        if self.is_cash:
            raise UserError(
                _('No se pueden agregar cuentas a subcajas de efectivo.')
            )
        
        # Determinar tipo de cuenta por defecto según el tipo de línea
        default_account_type = 'bank_arg'
        if self.line_type == 'crypto':
            default_account_type = 'crypto'
        elif self.line_type == 'mercadopago':
            default_account_type = 'mercadopago'
        
        return {
            'name': _('Nueva Cuenta'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.account',
            'view_mode': 'form',
            'context': {
                'default_cashbox_line_id': self.id,
                'default_account_type': default_account_type,
                'default_currency_type': self.currency_type or 'ARS',
            },
            'target': 'new',
        }
    
    def action_view_accounts(self):
        """Ver todas las cuentas de esta línea"""
        self.ensure_one()
        return {
            'name': _('Cuentas - %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.account',
            'view_mode': 'tree,form',
            'domain': [('cashbox_line_id', '=', self.id)],
            'context': {
                'default_cashbox_line_id': self.id,
                'search_default_active': 1,
            }
        }
    
    def action_adjust_balance(self):
        """Permite ajustar manualmente el saldo"""
        self.ensure_one()
        
        # Verificar que haya una sesión activa
        if not self.cashbox_id.active_session_id:
            raise UserError(
                _('Debe haber una sesión activa en la caja para ajustar saldos.')
            )
        
        # TODO: Implementar wizard de ajuste cuando tengamos el modelo de operaciones
        raise UserError(_('Función de ajuste en desarrollo.'))
    
    @api.model
    def create(self, vals):
        """Override create para validaciones adicionales"""
        # Si es una línea de efectivo, asegurar que la moneda esté correcta
        if vals.get('line_type') in ['cash_ars', 'cash_usd', 'cash_eur']:
            currency_map = {
                'cash_ars': 'ARS',
                'cash_usd': 'USD',
                'cash_eur': 'EUR'
            }
            vals['currency_type'] = currency_map[vals['line_type']]
        
        return super(SucursalesCajasCashboxLine, self).create(vals)
    
    def unlink(self):
        """Validaciones antes de eliminar"""
        for line in self:
            # Verificar si hay operaciones asociadas
            operations = self.env['sucursales_cajas.operation'].search([
                ('cashbox_line_id', '=', line.id)
            ], limit=1)
            
            if operations:
                raise UserError(
                    _('No se puede eliminar la subcaja "%s" porque tiene operaciones registradas.')
                    % line.display_name
                )
            
            # Verificar saldo
            if line.current_balance != 0:
                raise UserError(
                    _('No se puede eliminar la subcaja "%s" porque tiene saldo (%.2f). '
                      'Primero debe transferir o ajustar el saldo a cero.')
                    % (line.display_name, line.current_balance)
                )
        
        return super(SucursalesCajasCashboxLine, self).unlink()
    
    def name_get(self):
        """Usa display_name para mostrar"""
        return [(line.id, line.display_name) for line in self]
    
    @api.model
    def get_cashbox_lines_for_operation(self, cashbox_id, currency_type, operation_type):
        """
        Obtiene las líneas de caja disponibles para una operación
        según la moneda y el tipo de operación
        """
        domain = [
            ('cashbox_id', '=', cashbox_id),
            ('active', '=', True),
            ('currency_type', '=', currency_type)
        ]
        
        # Para retiros, verificar que haya saldo suficiente
        lines = self.search(domain)
        
        if operation_type == 'withdrawal':
            # Filtrar líneas con saldo suficiente (se refinará cuando se implemente)
            lines = lines.filtered(lambda l: l.current_balance > 0)
        
        return lines