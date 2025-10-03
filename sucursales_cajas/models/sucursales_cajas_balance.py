# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json


class SucursalesCajasBalance(models.Model):
    _name = 'sucursales_cajas.balance'
    _description = 'Balance de Apertura/Cierre de Caja'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    
    # Campos básicos
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True
    )
    
    # Relación con sesión
    session_id = fields.Many2one(
        'sucursales_cajas.session',
        string='Sesión',
        required=True,
        ondelete='cascade'
    )
    
    # Tipo de balance
    balance_type = fields.Selection([
        ('opening', 'Apertura'),
        ('closing', 'Cierre')
    ], string='Tipo de Balance', required=True)
    
    # Relación con línea de caja
    cashbox_line_id = fields.Many2one(
        'sucursales_cajas.cashbox_line',
        string='Subcaja',
        required=True,
        domain="[('cashbox_id', '=', cashbox_id)]"
    )
    
    # Campos relacionados para facilitar
    cashbox_id = fields.Many2one(
        related='session_id.cashbox_id',
        string='Caja',
        store=True
    )
    
    currency_type = fields.Selection(
        related='cashbox_line_id.currency_type',
        string='Moneda',
        store=True
    )
    
    line_type = fields.Selection(
        related='cashbox_line_id.line_type',
        string='Tipo de Subcaja',
        store=True
    )
    
    is_cash = fields.Boolean(
        related='cashbox_line_id.is_cash',
        string='Es Efectivo',
        store=True
    )
    
    user_id = fields.Many2one(
        related='session_id.user_id',
        string='Usuario',
        store=True
    )
    
    # Montos
    system_balance = fields.Float(
        string='Saldo del Sistema',
        help="Saldo según el sistema al momento del balance",
        readonly=True
    )
    
    declared_amount = fields.Float(
        string='Monto Declarado',
        help="Monto declarado por el usuario"
    )
    
    counted_amount = fields.Float(
        string='Monto Contado',
        help="Monto contado físicamente (para efectivo)"
    )
    
    difference = fields.Float(
        string='Diferencia',
        compute='_compute_difference',
        store=True,
        help="Diferencia entre lo declarado/contado y el sistema"
    )
    
    # Detalle de billetes (para efectivo)
    bill_details = fields.Text(
        string='Detalle de Billetes',
        help="JSON con el detalle de billetes por denominación"
    )
    
    bill_details_display = fields.Html(
        string='Detalle de Billetes',
        compute='_compute_bill_details_display'
    )
    
    # Para cuentas bancarias/crypto
    account_id = fields.Many2one(
        'sucursales_cajas.account',
        string='Cuenta',
        domain="[('cashbox_line_id', '=', cashbox_line_id)]"
    )
    
    # Observaciones
    notes = fields.Text(
        string='Observaciones'
    )
    
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado')
    ], string='Estado', default='draft')
    
    # Auditoría
    confirmed_date = fields.Datetime(
        string='Fecha de Confirmación',
        readonly=True
    )
    
    confirmed_user_id = fields.Many2one(
        'res.users',
        string='Confirmado por',
        readonly=True
    )
    
    @api.depends('session_id', 'balance_type', 'cashbox_line_id')
    def _compute_display_name(self):
        """Genera el nombre para mostrar"""
        type_names = {
            'opening': 'Apertura',
            'closing': 'Cierre'
        }
        
        for balance in self:
            parts = []
            if balance.balance_type:
                parts.append(type_names.get(balance.balance_type, ''))
            if balance.cashbox_line_id:
                parts.append(balance.cashbox_line_id.display_name)
            if balance.session_id:
                parts.append(balance.session_id.name)
            
            balance.display_name = ' - '.join(filter(None, parts))
    
    @api.depends('declared_amount', 'counted_amount', 'system_balance', 'balance_type')
    def _compute_difference(self):
        """Calcula la diferencia entre lo declarado/contado y el sistema"""
        for balance in self:
            if balance.is_cash and balance.counted_amount:
                # Para efectivo, usar el monto contado
                balance.difference = balance.counted_amount - balance.system_balance
            else:
                # Para otros tipos, usar el monto declarado
                balance.difference = balance.declared_amount - balance.system_balance
    
    def _compute_bill_details_display(self):
        """Genera HTML para mostrar el detalle de billetes"""
        for balance in self:
            if not balance.bill_details:
                balance.bill_details_display = False
                continue
            
            try:
                details = json.loads(balance.bill_details)
                
                # Generar tabla HTML
                html = '<table class="table table-sm">'
                html += '<thead><tr><th>Denominación</th><th>Cantidad</th><th>Subtotal</th></tr></thead>'
                html += '<tbody>'
                
                total = 0
                for denom, qty in sorted(details.items(), key=lambda x: float(x[0]), reverse=True):
                    if qty > 0:
                        subtotal = float(denom) * qty
                        total += subtotal
                        html += f'<tr><td>${denom}</td><td>{qty}</td><td>${subtotal:,.2f}</td></tr>'
                
                html += f'<tr class="font-weight-bold"><td colspan="2">Total</td><td>${total:,.2f}</td></tr>'
                html += '</tbody></table>'
                
                balance.bill_details_display = html
            except:
                balance.bill_details_display = '<p>Error al mostrar detalle</p>'
    
    @api.model
    def create(self, vals):
        """Override create para establecer saldo del sistema"""
        # Obtener el saldo del sistema al momento de crear
        if vals.get('cashbox_line_id') and vals.get('balance_type'):
            line = self.env['sucursales_cajas.cashbox_line'].browse(vals['cashbox_line_id'])
            
            if vals['balance_type'] == 'opening':
                # Para apertura, usar el saldo actual de la línea
                vals['system_balance'] = line.current_balance
            else:
                # Para cierre, calcular basado en la sesión
                # TODO: Implementar cuando tengamos operaciones
                vals['system_balance'] = line.session_current_balance
        
        return super(SucursalesCajasBalance, self).create(vals)
    
    @api.constrains('session_id', 'balance_type', 'cashbox_line_id')
    def _check_unique_balance(self):
        """Verifica que no haya balances duplicados"""
        for balance in self:
            # No puede haber dos balances del mismo tipo para la misma línea en la misma sesión
            duplicate = self.search([
                ('session_id', '=', balance.session_id.id),
                ('balance_type', '=', balance.balance_type),
                ('cashbox_line_id', '=', balance.cashbox_line_id.id),
                ('id', '!=', balance.id)
            ], limit=1)
            
            if duplicate:
                raise ValidationError(
                    _('Ya existe un balance de %s para la subcaja "%s" en esta sesión.') 
                    % ('apertura' if balance.balance_type == 'opening' else 'cierre',
                       balance.cashbox_line_id.display_name)
                )
    
    def action_confirm(self):
        """Confirma el balance"""
        self.ensure_one()
        
        if self.state == 'confirmed':
            raise UserError(_('Este balance ya está confirmado.'))
        
        # Validar que se haya ingresado un monto
        if self.is_cash:
            if not self.counted_amount and self.counted_amount != 0:
                raise UserError(_('Debe contar el efectivo antes de confirmar.'))
        else:
            if not self.declared_amount and self.declared_amount != 0:
                raise UserError(_('Debe declarar el monto antes de confirmar.'))
        
        # Actualizar campos
        self.write({
            'state': 'confirmed',
            'confirmed_date': fields.Datetime.now(),
            'confirmed_user_id': self.env.user.id
        })
        
        # Si es balance de apertura, actualizar el saldo inicial de la sesión
        if self.balance_type == 'opening':
            # El saldo declarado/contado se convierte en el saldo inicial
            amount = self.counted_amount if self.is_cash else self.declared_amount
            
            # Actualizar el balance de la línea de caja si hay diferencia
            if self.difference != 0:
                # TODO: Crear operación de ajuste
                pass
        
        return True
    
    def action_recount(self):
        """Permite recontar (solo para efectivo)"""
        self.ensure_one()
        
        if not self.is_cash:
            raise UserError(_('El reconteo solo aplica para subcajas de efectivo.'))
        
        if self.state == 'confirmed':
            raise UserError(_('No se puede recontar un balance confirmado.'))
        
        # Abrir wizard de conteo
        return {
            'name': _('Contar Efectivo'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.cash_count_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_balance_id': self.id,
                'default_currency_type': self.currency_type,
                'default_current_amount': self.counted_amount or 0.0,
            }
        }
    
    def action_view_difference_details(self):
        """Ver detalles de la diferencia"""
        self.ensure_one()
        
        # TODO: Implementar vista de análisis de diferencias
        raise UserError(_('Función en desarrollo.'))
    
    @api.onchange('cashbox_line_id')
    def _onchange_cashbox_line_id(self):
        """Limpiar campos cuando cambia la línea"""
        self.account_id = False
        self.declared_amount = 0.0
        self.counted_amount = 0.0
        self.bill_details = False
        
        # Si la línea tiene una sola cuenta, seleccionarla automáticamente
        if self.cashbox_line_id and not self.is_cash:
            accounts = self.cashbox_line_id.account_ids
            if len(accounts) == 1:
                self.account_id = accounts[0]
    
    def unlink(self):
        """Validaciones antes de eliminar"""
        for balance in self:
            if balance.state == 'confirmed':
                raise UserError(
                    _('No se puede eliminar un balance confirmado.')
                )
            
            # No permitir eliminar balances de apertura si la sesión está abierta
            if balance.balance_type == 'opening' and balance.session_id.state == 'open':
                raise UserError(
                    _('No se puede eliminar un balance de apertura mientras la sesión está abierta.')
                )
        
        return super(SucursalesCajasBalance, self).unlink()