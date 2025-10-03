# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json


class SendToCashboxWizard(models.TransientModel):
    _name = 'sucursales_cajas.send_to_cashbox_wizard'
    _description = 'Wizard para Enviar a Caja'
    
    # Partner
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente/Contacto',
        required=True,
        readonly=True
    )
    
    # Tipo de operación
    operation_type = fields.Selection([
        ('deposit', 'Depósito (Entregar a Caja)'),
        ('withdrawal', 'Retiro (Recibir de Caja)')
    ], string='Tipo de Operación', required=True, default='withdrawal')
    
    # Moneda y monto
    currency_type = fields.Selection([
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('USDT', 'Tether USDT')
    ], string='Moneda', required=True, default='ARS')
    
    amount = fields.Float(
        string='Monto',
        required=True
    )
    
    # Saldos disponibles (solo lectura)
    wallet_balance_ars = fields.Float(
        string='Saldo Disponible ARS',
        compute='_compute_wallet_balances',
        readonly=True
    )
    
    wallet_balance_usd = fields.Float(
        string='Saldo Disponible USD',
        compute='_compute_wallet_balances',
        readonly=True
    )
    
    wallet_balance_usdt = fields.Float(
        string='Saldo Disponible USDT',
        compute='_compute_wallet_balances',
        readonly=True
    )
    
    current_balance = fields.Float(
        string='Saldo Actual',
        compute='_compute_current_balance',
        readonly=True
    )
    
    # Sucursal y caja
    branch_id = fields.Many2one(
        'sucursales_cajas.branch',
        string='Sucursal',
        required=True,
        domain="[('active', '=', True)]"
    )
    
    cashbox_id = fields.Many2one(
        'sucursales_cajas.cashbox',
        string='Caja',
        required=True,
        domain="[('branch_id', '=', branch_id), ('active', '=', True)]"
    )
    
    # Para terceros
    is_third_party = fields.Boolean(
        string='Es para un Tercero'
    )
    
    beneficiary_name = fields.Char(
        string='Nombre del Beneficiario'
    )
    
    beneficiary_dni = fields.Char(
        string='DNI del Beneficiario'
    )
    
    beneficiary_phone = fields.Char(
        string='Teléfono del Beneficiario'
    )
    
    # Forma de entrega/recepción
    delivery_method = fields.Selection([
        ('cash', 'Efectivo'),
        ('transfer', 'Transferencia')
    ], string='Forma de Entrega/Recepción', required=True, default='cash')
    
    # Para transferencias
    transfer_type = fields.Selection([
        ('bank_transfer', 'Transferencia Bancaria'),
        ('crypto', 'Criptomoneda'),
        ('mercadopago', 'Mercado Pago')
    ], string='Tipo de Transferencia')
    
    # Datos de cuenta destino (para transferencias en retiros)
    destination_bank = fields.Char(string='Banco')
    destination_account_number = fields.Char(string='Número de Cuenta')
    destination_cbu = fields.Char(string='CBU')
    destination_alias = fields.Char(string='Alias')
    destination_account_holder = fields.Char(string='Titular de la Cuenta')
    
    # Para crypto
    destination_network = fields.Selection([
        ('trc20', 'TRC-20 (Tron)'),
        ('erc20', 'ERC-20 (Ethereum)'),
        ('bep20', 'BEP-20 (BSC)'),
        ('polygon', 'Polygon'),
        ('other', 'Otra')
    ], string='Red')
    
    destination_wallet = fields.Char(string='Dirección de Wallet')
    
    # Observaciones
    notes = fields.Text(
        string='Observaciones'
    )
    
    # Validación de monto máximo para retiros
    @api.constrains('amount', 'currency_type', 'operation_type')
    def _check_withdrawal_amount(self):
        """Valida que el monto no exceda el saldo disponible"""
        for wizard in self:
            if wizard.operation_type == 'withdrawal':
                balance = wizard.partner_id.get_wallet_balance_by_currency(wizard.currency_type)
                if wizard.amount > balance:
                    raise ValidationError(
                        _('El monto a retirar (%(amount)s) excede el saldo disponible (%(balance)s) en %(currency)s.') % {
                            'amount': wizard.amount,
                            'balance': balance,
                            'currency': wizard.currency_type
                        }
                    )
    
    @api.depends('partner_id')
    def _compute_wallet_balances(self):
        """Calcula los saldos disponibles del partner"""
        for wizard in self:
            if wizard.partner_id:
                wizard.wallet_balance_ars = wizard.partner_id.get_wallet_balance_by_currency('ARS')
                wizard.wallet_balance_usd = wizard.partner_id.get_wallet_balance_by_currency('USD')
                wizard.wallet_balance_usdt = wizard.partner_id.get_wallet_balance_by_currency('USDT')
            else:
                wizard.wallet_balance_ars = 0.0
                wizard.wallet_balance_usd = 0.0
                wizard.wallet_balance_usdt = 0.0
    
    @api.depends('currency_type', 'wallet_balance_ars', 'wallet_balance_usd', 'wallet_balance_usdt')
    def _compute_current_balance(self):
        """Muestra el saldo de la moneda seleccionada"""
        for wizard in self:
            if wizard.currency_type == 'ARS':
                wizard.current_balance = wizard.wallet_balance_ars
            elif wizard.currency_type == 'USD':
                wizard.current_balance = wizard.wallet_balance_usd
            elif wizard.currency_type == 'USDT':
                wizard.current_balance = wizard.wallet_balance_usdt
            else:
                wizard.current_balance = 0.0
    
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        """Limpia la caja al cambiar de sucursal"""
        self.cashbox_id = False
        
        # Filtrar solo cajas con sesión activa
        if self.branch_id:
            return {
                'domain': {
                    'cashbox_id': [
                        ('branch_id', '=', self.branch_id.id),
                        ('active', '=', True),
                    ]
                }
            }
    
    @api.onchange('delivery_method')
    def _onchange_delivery_method(self):
        """Ajusta campos según el método de entrega"""
        if self.delivery_method == 'cash':
            # Limpiar campos de transferencia
            self.transfer_type = False
            self.destination_bank = False
            self.destination_account_number = False
            self.destination_cbu = False
            self.destination_alias = False
            self.destination_account_holder = False
            self.destination_network = False
            self.destination_wallet = False
        else:
            # Establecer tipo de transferencia por defecto
            if self.currency_type in ['USDT']:
                self.transfer_type = 'crypto'
            else:
                self.transfer_type = 'bank_transfer'
    
    @api.onchange('transfer_type')
    def _onchange_transfer_type(self):
        """Limpia campos según el tipo de transferencia"""
        if self.transfer_type != 'bank_transfer':
            self.destination_bank = False
            self.destination_account_number = False
            self.destination_cbu = False
            self.destination_alias = False
            
        if self.transfer_type != 'crypto':
            self.destination_network = False
            self.destination_wallet = False
    
    @api.onchange('currency_type')
    def _onchange_currency_type(self):
        """Ajusta opciones según la moneda"""
        # Si es crypto, sugerir transferencia crypto
        if self.currency_type in ['USDT'] and self.delivery_method == 'transfer':
            self.transfer_type = 'crypto'
            if not self.destination_network:
                self.destination_network = 'trc20'  # Red por defecto para USDT
    
    @api.onchange('is_third_party')
    def _onchange_is_third_party(self):
        """Limpia campos de beneficiario si no es para tercero"""
        if not self.is_third_party:
            self.beneficiary_name = False
            self.beneficiary_dni = False
            self.beneficiary_phone = False
        elif self.operation_type == 'deposit':
            # Para depósitos de terceros, copiar el nombre del partner como sugerencia
            if not self.beneficiary_name and self.partner_id:
                self.beneficiary_name = self.partner_id.name
    
    def _prepare_transfer_data(self):
        """Prepara los datos de transferencia en formato JSON"""
        transfer_data = {}
        
        if self.transfer_type == 'bank_transfer':
            transfer_data = {
                'type': 'bank_transfer',
                'bank_name': self.destination_bank or '',
                'account_number': self.destination_account_number or '',
                'cbu': self.destination_cbu or '',
                'alias': self.destination_alias or '',
                'account_holder': self.destination_account_holder or '',
            }
        elif self.transfer_type == 'crypto':
            transfer_data = {
                'type': 'crypto',
                'network': self.destination_network or '',
                'address': self.destination_wallet or '',
            }
        elif self.transfer_type == 'mercadopago':
            transfer_data = {
                'type': 'mercadopago',
                'alias': self.destination_alias or '',
            }
        
        return json.dumps(transfer_data)
    
    def _validate_transfer_data(self):
        """Valida que se hayan ingresado los datos necesarios para transferencia"""
        if self.delivery_method != 'transfer':
            return True
        
        errors = []
        
        if self.transfer_type == 'bank_transfer':
            if self.currency_type == 'ARS':
                # Para ARS, requerir CBU o alias
                if not self.destination_cbu and not self.destination_alias:
                    errors.append(_('Debe especificar CBU o Alias para transferencias en ARS.'))
            else:
                # Para otras monedas, requerir número de cuenta
                if not self.destination_account_number:
                    errors.append(_('Debe especificar el número de cuenta.'))
            
            if not self.destination_bank:
                errors.append(_('Debe especificar el banco.'))
            
            if not self.destination_account_holder:
                errors.append(_('Debe especificar el titular de la cuenta.'))
                
        elif self.transfer_type == 'crypto':
            if not self.destination_wallet:
                errors.append(_('Debe especificar la dirección de wallet.'))
            if not self.destination_network:
                errors.append(_('Debe especificar la red.'))
        
        if errors:
            raise ValidationError('\n'.join(errors))
        
        return True
    
    def action_confirm(self):
        """Confirma y crea la operación de caja"""
        self.ensure_one()
        
        # Validaciones
        if self.amount <= 0:
            raise ValidationError(_('El monto debe ser mayor a cero.'))
        
        if self.is_third_party:
            if not self.beneficiary_name:
                raise ValidationError(_('Debe especificar el nombre del beneficiario.'))
            if not self.beneficiary_dni:
                raise ValidationError(_('Debe especificar el DNI del beneficiario.'))
        
        # Validar datos de transferencia si aplica
        self._validate_transfer_data()
        
        # Verificar que la caja tenga sesión activa
        if not self.cashbox_id.active_session_id:
            raise UserError(
                _('La caja %s no tiene una sesión activa. Por favor seleccione otra caja.') 
                % self.cashbox_id.display_name
            )
        
        # Preparar valores para la operación
        operation_vals = {
            'partner_id': self.partner_id.id,
            'operation_type': self.operation_type,
            'currency_type': self.currency_type,
            'amount': self.amount,
            'cashbox_id': self.cashbox_id.id,
            'is_third_party': self.is_third_party,
            'beneficiary_name': self.beneficiary_name,
            'beneficiary_dni': self.beneficiary_dni,
            'beneficiary_phone': self.beneficiary_phone,
            'notes': self.notes,
            'origin': 'partner',
            'state': 'pending',
        }
        
        # Agregar datos de transferencia si aplica
        if self.delivery_method == 'transfer':
            operation_vals.update({
                'transfer_type': self.transfer_type,
                'transfer_data': self._prepare_transfer_data(),
            })
        
        # Crear la operación
        operation = self.env['sucursales_cajas.operation'].create(operation_vals)
        
        # Mostrar mensaje de éxito
        message = _('Se ha creado la operación %s exitosamente.\n\n') % operation.name
        
        if self.is_third_party:
            message += _('Beneficiario: %s (DNI: %s)\n') % (self.beneficiary_name, self.beneficiary_dni)
        
        message += _('Debe presentarse en %s - %s para completar la operación.') % (
            self.branch_id.name,
            self.cashbox_id.name
        )
        
        # Retornar acción para mostrar la operación creada
        return {
            'name': _('Operación Creada'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.operation',
            'res_id': operation.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'show_success_message': message,
            }
        }
    
    def action_confirm_and_print(self):
        """Confirma y abre el comprobante para imprimir"""
        # Primero confirmar
        result = self.action_confirm()
        
        # Obtener la operación creada
        if result.get('res_id'):
            operation = self.env['sucursales_cajas.operation'].browse(result['res_id'])
            
            # Agregar acción de impresión al contexto
            result['context']['print_voucher'] = True
            
        return result