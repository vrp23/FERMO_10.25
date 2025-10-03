# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SucursalesCajasAccount(models.Model):
    _name = 'sucursales_cajas.account'
    _description = 'Cuenta Bancaria o Crypto'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _rec_name = 'display_name'
    
    # Campos básicos
    name = fields.Char(
        string='Nombre de la Cuenta',
        compute='_compute_name',
        store=True,
        readonly=False,
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
    
    # Relación con línea de caja
    cashbox_line_id = fields.Many2one(
        'sucursales_cajas.cashbox_line',
        string='Línea de Caja',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    # Tipo de cuenta
    account_type = fields.Selection([
        ('bank_arg', 'Banco Argentino'),
        ('bank_foreign', 'Banco Extranjero'),
        ('crypto', 'Billetera Crypto'),
        ('mercadopago', 'Mercado Pago'),
        ('other', 'Otro')
    ], string='Tipo de Cuenta', required=True, tracking=True)
    
    # Datos bancarios
    bank_name = fields.Char(
        string='Nombre del Banco',
        tracking=True
    )
    
    bank_country_id = fields.Many2one(
        'res.country',
        string='País del Banco',
        tracking=True
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
    ], string='Moneda', required=True, tracking=True)
    
    account_number = fields.Char(
        string='Número de Cuenta',
        tracking=True
    )
    
    # Datos específicos Argentina
    cbu = fields.Char(
        string='CBU',
        size=22,
        tracking=True,
        help="Clave Bancaria Uniforme (22 dígitos)"
    )
    
    alias_cbu = fields.Char(
        string='Alias CBU',
        tracking=True,
        help="Alias para transferencias"
    )
    
    cuit_holder = fields.Char(
        string='CUIT del Titular',
        size=11,
        tracking=True
    )
    
    # Datos internacionales
    iban = fields.Char(
        string='IBAN',
        tracking=True,
        help="International Bank Account Number"
    )
    
    swift_code = fields.Char(
        string='Código SWIFT/BIC',
        tracking=True,
        help="Código SWIFT para transferencias internacionales"
    )
    
    routing_number = fields.Char(
        string='Routing Number (ABA)',
        tracking=True,
        help="Para bancos de Estados Unidos"
    )
    
    # Datos crypto
    wallet_address = fields.Char(
        string='Dirección de Wallet',
        tracking=True
    )
    
    network_type = fields.Selection([
        ('erc20', 'Ethereum (ERC-20)'),
        ('trc20', 'Tron (TRC-20)'),
        ('bep20', 'Binance Smart Chain (BEP-20)'),
        ('polygon', 'Polygon'),
        ('arbitrum', 'Arbitrum'),
        ('optimism', 'Optimism'),
        ('bitcoin', 'Bitcoin'),
        ('lightning', 'Lightning Network'),
        ('other', 'Otra')
    ], string='Red/Network', tracking=True)
    
    exchange_platform = fields.Char(
        string='Plataforma/Exchange',
        tracking=True,
        help="Ej: Binance, Coinbase, etc."
    )
    
    # Titular de la cuenta
    account_holder_name = fields.Char(
        string='Nombre del Titular',
        required=True,
        tracking=True
    )
    
    account_holder_id = fields.Char(
        string='DNI/ID del Titular',
        tracking=True
    )
    
    # Estado y balance
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )
    
    current_balance = fields.Float(
        string='Saldo Actual',
        compute='_compute_current_balance',
        store=True,
        help="Saldo actual en esta cuenta"
    )
    
    # Notas
    notes = fields.Text(
        string='Notas',
        help="Información adicional sobre la cuenta"
    )
    
    # Campos de auditoría
    last_operation_date = fields.Datetime(
        string='Última Operación',
        readonly=True
    )
    
    last_operation_user_id = fields.Many2one(
        'res.users',
        string='Usuario Última Operación',
        readonly=True
    )
    
    @api.depends('account_type', 'bank_name', 'currency_type', 'exchange_platform')
    def _compute_name(self):
        """Genera un nombre automático basado en el tipo de cuenta"""
        for account in self:
            if not account.name:  # Solo calcular si no hay nombre manual
                parts = []
                
                if account.account_type in ['bank_arg', 'bank_foreign']:
                    if account.bank_name:
                        parts.append(account.bank_name)
                elif account.account_type == 'crypto':
                    if account.exchange_platform:
                        parts.append(account.exchange_platform)
                    else:
                        parts.append('Crypto')
                elif account.account_type == 'mercadopago':
                    parts.append('Mercado Pago')
                else:
                    parts.append('Cuenta')
                
                if account.currency_type:
                    parts.append(f"({account.currency_type})")
                
                account.name = ' '.join(parts) if parts else 'Nueva Cuenta'
    
    @api.depends('name', 'account_number', 'cbu', 'alias_cbu', 'wallet_address')
    def _compute_display_name(self):
        """Genera el nombre completo para mostrar"""
        for account in self:
            parts = [account.name or '']
            
            # Agregar identificador según el tipo
            if account.account_type in ['bank_arg', 'bank_foreign']:
                if account.account_number:
                    parts.append(f"[{account.account_number[-4:]}]")
                elif account.cbu:
                    parts.append(f"[...{account.cbu[-4:]}]")
            elif account.account_type == 'crypto' and account.wallet_address:
                # Mostrar primeros y últimos caracteres de la wallet
                addr = account.wallet_address
                if len(addr) > 10:
                    parts.append(f"[{addr[:6]}...{addr[-4:]}]")
                else:
                    parts.append(f"[{addr}]")
            
            account.display_name = ' '.join(filter(None, parts))
    
    def _compute_current_balance(self):
        """Calcula el saldo actual basado en las operaciones"""
        for account in self:
            # Por ahora, solo retornamos el balance de la línea de caja
            # Esto se actualizará cuando implementemos las operaciones
            account.current_balance = 0.0
    
    @api.constrains('cbu')
    def _check_cbu(self):
        """Valida el formato del CBU"""
        for account in self:
            if account.cbu:
                # Remover espacios y guiones
                cbu_clean = account.cbu.replace(' ', '').replace('-', '')
                
                # Verificar longitud
                if len(cbu_clean) != 22:
                    raise ValidationError(
                        _('El CBU debe tener exactamente 22 dígitos. CBU ingresado: %s (%d dígitos)') 
                        % (account.cbu, len(cbu_clean))
                    )
                
                # Verificar que sean solo números
                if not cbu_clean.isdigit():
                    raise ValidationError(
                        _('El CBU debe contener solo números.')
                    )
                
                # Actualizar con formato limpio
                account.cbu = cbu_clean
    
    @api.constrains('cuit_holder')
    def _check_cuit(self):
        """Valida el formato del CUIT"""
        for account in self:
            if account.cuit_holder:
                # Remover espacios y guiones
                cuit_clean = account.cuit_holder.replace(' ', '').replace('-', '')
                
                # Verificar longitud
                if len(cuit_clean) != 11:
                    raise ValidationError(
                        _('El CUIT debe tener exactamente 11 dígitos.')
                    )
                
                # Verificar que sean solo números
                if not cuit_clean.isdigit():
                    raise ValidationError(
                        _('El CUIT debe contener solo números.')
                    )
                
                # Actualizar con formato limpio
                account.cuit_holder = cuit_clean
    
    @api.constrains('account_type', 'bank_name', 'wallet_address', 'exchange_platform')
    def _check_required_fields(self):
        """Valida campos requeridos según el tipo de cuenta"""
        for account in self:
            if account.account_type in ['bank_arg', 'bank_foreign']:
                if not account.bank_name:
                    raise ValidationError(
                        _('Debe especificar el nombre del banco para cuentas bancarias.')
                    )
                
                # Para bancos argentinos, CBU o alias es obligatorio
                if account.account_type == 'bank_arg':
                    if not account.cbu and not account.alias_cbu:
                        raise ValidationError(
                            _('Debe especificar CBU o Alias para cuentas bancarias argentinas.')
                        )
                
            elif account.account_type == 'crypto':
                if not account.wallet_address:
                    raise ValidationError(
                        _('Debe especificar la dirección de wallet para cuentas crypto.')
                    )
                if not account.network_type:
                    raise ValidationError(
                        _('Debe especificar la red/network para cuentas crypto.')
                    )
    
    @api.onchange('account_type')
    def _onchange_account_type(self):
        """Ajusta campos según el tipo de cuenta seleccionado"""
        if self.account_type == 'bank_arg':
            self.bank_country_id = self.env.ref('base.ar', False)
            if self.currency_type not in ['ARS', 'USD']:
                self.currency_type = 'ARS'
        elif self.account_type == 'crypto':
            if self.currency_type not in ['USDT', 'USDC', 'BTC', 'ETH']:
                self.currency_type = 'USDT'
        elif self.account_type == 'mercadopago':
            self.currency_type = 'ARS'
            self.bank_name = 'Mercado Pago'
    
    @api.onchange('currency_type')
    def _onchange_currency_type(self):
        """Ajusta la red según la moneda crypto seleccionada"""
        if self.currency_type in ['USDT', 'USDC'] and not self.network_type:
            self.network_type = 'trc20'  # Red por defecto para stablecoins
        elif self.currency_type == 'BTC':
            self.network_type = 'bitcoin'
        elif self.currency_type == 'ETH':
            self.network_type = 'erc20'
    
    def name_get(self):
        """Usa display_name para mostrar"""
        return [(account.id, account.display_name) for account in self]
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100):
        """Permite buscar por varios campos"""
        if name:
            args = args or []
            domain = ['|', '|', '|', '|',
                ('name', operator, name),
                ('account_number', operator, name),
                ('cbu', operator, name),
                ('alias_cbu', operator, name),
                ('wallet_address', operator, name)
            ]
            return self.search(domain + args, limit=limit).ids
        return super()._name_search(name, args, operator, limit)
    
    def action_view_operations(self):
        """Ver operaciones realizadas con esta cuenta"""
        self.ensure_one()
        return {
            'name': _('Operaciones - %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.operation',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.id)],
            'context': {
                'search_default_done': 1,
                'search_default_group_by_date': 1,
            }
        }
    
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """Override copy para limpiar datos sensibles"""
        default = dict(default or {})
        default.update({
            'name': _("%s (Copia)") % self.name,
            'account_number': False,
            'cbu': False,
            'wallet_address': False,
            'active': False,  # Desactivada por defecto
        })
        return super(SucursalesCajasAccount, self).copy(default)