# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Relación con operaciones de caja
    cashbox_operation_ids = fields.One2many(
        'sucursales_cajas.operation',
        'partner_id',
        string='Operaciones de Caja'
    )
    
    # Contadores
    cashbox_operation_count = fields.Integer(
        string='Operaciones de Caja',
        compute='_compute_cashbox_operation_count'
    )
    
    pending_cashbox_operation_count = fields.Integer(
        string='Operaciones Pendientes',
        compute='_compute_cashbox_operation_count'
    )
    
    # Campos para facilitar el envío a caja
    has_pending_cashbox_operations = fields.Boolean(
        string='Tiene Operaciones Pendientes',
        compute='_compute_cashbox_operation_count'
    )
    
    @api.depends('cashbox_operation_ids', 'cashbox_operation_ids.state')
    def _compute_cashbox_operation_count(self):
        """Calcula contadores de operaciones de caja"""
        for partner in self:
            operations = partner.cashbox_operation_ids
            partner.cashbox_operation_count = len(operations)
            
            pending_ops = operations.filtered(lambda o: o.state == 'pending')
            partner.pending_cashbox_operation_count = len(pending_ops)
            partner.has_pending_cashbox_operations = bool(pending_ops)
    
    def action_send_to_cashbox(self):
        """Abre el wizard para enviar dinero a caja"""
        self.ensure_one()
        
        # Verificar que el partner tenga algún saldo
        has_balance = False
        balances = []
        
        # Verificar saldo ARS (del módulo chequera)
        if hasattr(self, 'wallet_balance') and self.wallet_balance != 0:
            has_balance = True
            balances.append(f'ARS: ${self.wallet_balance:,.2f}')
        
        # Verificar saldo USD (del módulo divisas)
        if hasattr(self, 'wallet_usd_balance') and self.wallet_usd_balance != 0:
            has_balance = True
            balances.append(f'USD: ${self.wallet_usd_balance:,.2f}')
        
        # Verificar saldo USDT (del módulo divisas)
        if hasattr(self, 'wallet_usdt_balance') and self.wallet_usdt_balance != 0:
            has_balance = True
            balances.append(f'USDT: ${self.wallet_usdt_balance:,.2f}')
        
        if not has_balance:
            raise UserError(
                _('El contacto %s no tiene saldo disponible en ninguna wallet.') 
                % self.name
            )
        
        # Preparar contexto con información de saldos
        context = {
            'default_partner_id': self.id,
            'default_operation_type': 'withdrawal',  # Por defecto retiro
            'partner_balances': ', '.join(balances),
            'partner_wallet_ars': getattr(self, 'wallet_balance', 0.0),
            'partner_wallet_usd': getattr(self, 'wallet_usd_balance', 0.0),
            'partner_wallet_usdt': getattr(self, 'wallet_usdt_balance', 0.0),
        }
        
        return {
            'name': _('Enviar a Caja - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.send_to_cashbox_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }
    
    def action_receive_from_cashbox(self):
        """Abre el wizard para recibir dinero de caja (depósito)"""
        self.ensure_one()
        
        context = {
            'default_partner_id': self.id,
            'default_operation_type': 'deposit',
        }
        
        return {
            'name': _('Recibir de Caja - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.send_to_cashbox_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }
    
    def action_view_cashbox_operations(self):
        """Ver todas las operaciones de caja del partner"""
        self.ensure_one()
        
        return {
            'name': _('Operaciones de Caja - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.operation',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
                'search_default_group_by_state': 1,
            }
        }
    
    def action_view_pending_cashbox_operations(self):
        """Ver operaciones pendientes de caja"""
        self.ensure_one()
        
        return {
            'name': _('Operaciones Pendientes - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.operation',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('state', '=', 'pending')
            ],
            'context': {
                'default_partner_id': self.id,
            }
        }
    
    def get_wallet_balance_by_currency(self, currency_type):
        """
        Obtiene el saldo de wallet para una moneda específica
        Útil para validaciones en wizards y operaciones
        """
        self.ensure_one()
        
        if currency_type == 'ARS':
            return getattr(self, 'wallet_balance', 0.0)
        elif currency_type == 'USD':
            return getattr(self, 'wallet_usd_balance', 0.0)
        elif currency_type == 'USDT':
            return getattr(self, 'wallet_usdt_balance', 0.0)
        else:
            return 0.0
    
    def update_wallet_balance(self, currency_type, amount, operation_type='adjustment'):
        """
        Actualiza el saldo de wallet para una moneda específica
        
        :param currency_type: Tipo de moneda (ARS, USD, USDT)
        :param amount: Monto a sumar (positivo) o restar (negativo)
        :param operation_type: Tipo de operación para el registro
        :return: True si se actualizó correctamente
        """
        self.ensure_one()
        
        if currency_type == 'ARS':
            # Usar el sistema de wallet del módulo chequera
            self.env['chequera.wallet.movement'].create({
                'partner_id': self.id,
                'tipo': operation_type,
                'monto': amount,
                'fecha': fields.Date.today(),
                'notes': f'Operación de caja'
            })
            
        elif currency_type in ['USD', 'USDT']:
            # Usar el sistema de wallet del módulo divisas
            self.env['divisas.wallet.movement'].create({
                'partner_id': self.id,
                'operation_type': 'adjustment',
                'currency_type': currency_type,
                'payment_currency_type': currency_type,
                'amount': amount,
                'payment_amount': amount,
                'date': fields.Date.today(),
                'notes': f'Operación de caja'
            })
        else:
            raise UserError(
                _('Moneda %s no soportada para operaciones de wallet.') % currency_type
            )
        
        return True
    
    @api.model
    def create_cashbox_operation_from_partner(self, partner_id, operation_data):
        """
        Método helper para crear operaciones desde el contexto del partner
        Usado por wizards y otras interfaces
        
        :param partner_id: ID del partner
        :param operation_data: Diccionario con datos de la operación
        :return: Operación creada
        """
        partner = self.browse(partner_id)
        if not partner.exists():
            raise UserError(_('Partner no encontrado.'))
        
        # Validar datos mínimos
        required_fields = ['operation_type', 'amount', 'currency_type', 'cashbox_id']
        missing_fields = [f for f in required_fields if not operation_data.get(f)]
        
        if missing_fields:
            raise ValidationError(
                _('Faltan campos requeridos: %s') % ', '.join(missing_fields)
            )
        
        # Validar saldo para retiros
        if operation_data['operation_type'] == 'withdrawal':
            balance = partner.get_wallet_balance_by_currency(operation_data['currency_type'])
            if balance < operation_data['amount']:
                raise ValidationError(
                    _('Saldo insuficiente. Saldo disponible: %s %s') 
                    % (operation_data['currency_type'], balance)
                )
        
        # Crear operación
        operation_data['partner_id'] = partner_id
        operation_data['origin'] = 'partner'
        operation_data['state'] = 'pending'
        
        return self.env['sucursales_cajas.operation'].create(operation_data)


class ChequeraWalletMovement(models.Model):
    """Extender el modelo de movimientos de wallet de chequera"""
    _inherit = 'chequera.wallet.movement'
    
    # Relación con operación de caja
    cashbox_operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación de Caja',
        readonly=True
    )


class DivisasWalletMovement(models.Model):
    """Extender el modelo de movimientos de wallet de divisas"""
    _inherit = 'divisas.wallet.movement'
    
    # Relación con operación de caja
    cashbox_operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación de Caja',
        readonly=True
    )