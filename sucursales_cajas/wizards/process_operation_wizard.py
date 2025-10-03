# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json


class ProcessOperationWizard(models.TransientModel):
    _name = 'sucursales_cajas.process_operation_wizard'
    _description = 'Wizard para Procesar Operación'
    
    # Operación
    operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación',
        required=True,
        readonly=True
    )
    
    # Campos relacionados de la operación
    operation_type = fields.Selection(
        related='operation_id.operation_type',
        string='Tipo de Operación'
    )
    
    partner_id = fields.Many2one(
        related='operation_id.partner_id',
        string='Cliente'
    )
    
    currency_type = fields.Selection(
        related='operation_id.currency_type',
        string='Moneda'
    )
    
    amount = fields.Float(
        related='operation_id.amount',
        string='Monto'
    )
    
    # Información de beneficiario
    is_third_party = fields.Boolean(
        related='operation_id.is_third_party',
        string='Es para Tercero'
    )
    
    beneficiary_info = fields.Html(
        string='Información del Beneficiario',
        compute='_compute_beneficiary_info'
    )
    
    # Verificación de identidad
    identity_verified = fields.Boolean(
        string='Identidad Verificada',
        help="Marcar después de verificar el DNI"
    )
    
    verification_notes = fields.Text(
        string='Observaciones de Verificación'
    )
    
    # Selección de subcaja/cuenta
    cashbox_line_id = fields.Many2one(
        'sucursales_cajas.cashbox_line',
        string='Subcaja',
        required=True,
        domain="[('cashbox_id', '=', cashbox_id), ('currency_type', '=', currency_type), ('active', '=', True)]"
    )
    
    account_id = fields.Many2one(
        'sucursales_cajas.account',
        string='Cuenta',
        domain="[('cashbox_line_id', '=', cashbox_line_id), ('active', '=', True)]"
    )
    
    # Campos relacionados para validaciones
    cashbox_id = fields.Many2one(
        related='operation_id.cashbox_id',
        string='Caja'
    )
    
    is_cash = fields.Boolean(
        related='cashbox_line_id.is_cash',
        string='Es Efectivo'
    )
    
    # Saldos
    current_balance = fields.Float(
        string='Saldo Disponible',
        compute='_compute_current_balance'
    )
    
    balance_after = fields.Float(
        string='Saldo Después',
        compute='_compute_balance_after'
    )
    
    has_sufficient_balance = fields.Boolean(
        string='Tiene Saldo Suficiente',
        compute='_compute_has_sufficient_balance'
    )
    
    # Para operaciones con transferencia
    transfer_completed = fields.Boolean(
        string='Transferencia Completada',
        help="Marcar cuando la transferencia haya sido realizada"
    )
    
    transfer_reference = fields.Char(
        string='Referencia/Comprobante'
    )
    
    transfer_info = fields.Html(
        string='Información de Transferencia',
        compute='_compute_transfer_info'
    )
    
    # Resumen
    operation_summary = fields.Html(
        string='Resumen de la Operación',
        compute='_compute_operation_summary'
    )
    
    # Opciones de procesamiento
    print_receipt = fields.Boolean(
        string='Imprimir Comprobante',
        default=True
    )
    
    send_notification = fields.Boolean(
        string='Enviar Notificación',
        default=False,
        help="Enviar notificación al cliente cuando se complete"
    )
    
    @api.depends('operation_id')
    def _compute_beneficiary_info(self):
        """Genera HTML con información del beneficiario"""
        for wizard in self:
            if not wizard.is_third_party:
                wizard.beneficiary_info = ''
                continue
            
            html = '<div class="alert alert-warning">'
            html += '<h6><i class="fa fa-user"></i> Operación para Tercero</h6>'
            html += '<table class="table table-sm mb-0">'
            html += f'<tr><td><strong>Nombre:</strong></td><td>{wizard.operation_id.beneficiary_name or "-"}</td></tr>'
            html += f'<tr><td><strong>DNI:</strong></td><td>{wizard.operation_id.beneficiary_dni or "-"}</td></tr>'
            
            if wizard.operation_id.beneficiary_phone:
                html += f'<tr><td><strong>Teléfono:</strong></td><td>{wizard.operation_id.beneficiary_phone}</td></tr>'
            
            html += '</table>'
            html += '<p class="mb-0 mt-2"><strong>⚠️ Verificar identidad con DNI físico</strong></p>'
            html += '</div>'
            
            wizard.beneficiary_info = html
    
    @api.depends('operation_id')
    def _compute_transfer_info(self):
        """Genera HTML con información de transferencia"""
        for wizard in self:
            if not wizard.operation_id.transfer_data:
                wizard.transfer_info = ''
                continue
            
            try:
                data = json.loads(wizard.operation_id.transfer_data)
                
                html = '<div class="alert alert-info">'
                html += '<h6><i class="fa fa-exchange"></i> Datos de Transferencia</h6>'
                html += '<table class="table table-sm mb-0">'
                
                if data.get('type') == 'bank_transfer':
                    html += f'<tr><td><strong>Banco:</strong></td><td>{data.get("bank_name", "-")}</td></tr>'
                    html += f'<tr><td><strong>Titular:</strong></td><td>{data.get("account_holder", "-")}</td></tr>'
                    
                    if data.get('cbu'):
                        html += f'<tr><td><strong>CBU:</strong></td><td>{data.get("cbu")}</td></tr>'
                    if data.get('alias'):
                        html += f'<tr><td><strong>Alias:</strong></td><td>{data.get("alias")}</td></tr>'
                    if data.get('account_number'):
                        html += f'<tr><td><strong>Cuenta:</strong></td><td>{data.get("account_number")}</td></tr>'
                
                elif data.get('type') == 'crypto':
                    html += f'<tr><td><strong>Red:</strong></td><td>{data.get("network", "-")}</td></tr>'
                    addr = data.get('address', '')
                    if len(addr) > 20:
                        addr_display = f"{addr[:10]}...{addr[-10:]}"
                    else:
                        addr_display = addr
                    html += f'<tr><td><strong>Dirección:</strong></td><td><code>{addr_display}</code></td></tr>'
                
                html += '</table></div>'
                
                wizard.transfer_info = html
                
            except:
                wizard.transfer_info = '<p class="text-danger">Error al leer datos de transferencia</p>'
    
    @api.depends('cashbox_line_id')
    def _compute_current_balance(self):
        """Calcula el saldo disponible de la subcaja"""
        for wizard in self:
            if wizard.cashbox_line_id:
                wizard.current_balance = wizard.cashbox_line_id.current_balance
            else:
                wizard.current_balance = 0.0
    
    @api.depends('current_balance', 'amount', 'operation_type')
    def _compute_balance_after(self):
        """Calcula el saldo después de la operación"""
        for wizard in self:
            if wizard.operation_type == 'deposit':
                wizard.balance_after = wizard.current_balance + wizard.amount
            elif wizard.operation_type == 'withdrawal':
                wizard.balance_after = wizard.current_balance - wizard.amount
            else:
                wizard.balance_after = wizard.current_balance
    
    @api.depends('current_balance', 'amount', 'operation_type')
    def _compute_has_sufficient_balance(self):
        """Verifica si hay saldo suficiente para retiros"""
        for wizard in self:
            if wizard.operation_type != 'withdrawal':
                wizard.has_sufficient_balance = True
            else:
                wizard.has_sufficient_balance = wizard.current_balance >= wizard.amount
    
    @api.depends('operation_id', 'cashbox_line_id', 'balance_after')
    def _compute_operation_summary(self):
        """Genera resumen HTML de la operación"""
        for wizard in self:
            op = wizard.operation_id
            
            html = '<div class="card">'
            html += '<div class="card-body">'
            
            # Tipo de operación
            op_type = dict(op._fields['operation_type'].selection).get(op.operation_type, '')
            html += f'<h5 class="card-title">{op_type} - {op.name}</h5>'
            
            # Detalles
            html += '<dl class="row">'
            html += f'<dt class="col-sm-4">Cliente:</dt><dd class="col-sm-8">{op.partner_id.name}</dd>'
            html += f'<dt class="col-sm-4">Monto:</dt><dd class="col-sm-8"><strong>{op.currency_type} {op.amount:,.2f}</strong></dd>'
            
            if wizard.cashbox_line_id:
                html += f'<dt class="col-sm-4">Subcaja:</dt><dd class="col-sm-8">{wizard.cashbox_line_id.display_name}</dd>'
                
                # Mostrar saldos
                if wizard.operation_type == 'withdrawal':
                    html += f'<dt class="col-sm-4">Saldo Actual:</dt><dd class="col-sm-8">{wizard.current_balance:,.2f}</dd>'
                    balance_class = 'text-success' if wizard.has_sufficient_balance else 'text-danger'
                    html += f'<dt class="col-sm-4">Saldo Después:</dt><dd class="col-sm-8 {balance_class}">{wizard.balance_after:,.2f}</dd>'
            
            html += '</dl>'
            html += '</div></div>'
            
            wizard.operation_summary = html
    
    @api.onchange('cashbox_line_id')
    def _onchange_cashbox_line_id(self):
        """Actualiza la cuenta cuando cambia la subcaja"""
        self.account_id = False
        
        if self.cashbox_line_id and not self.is_cash:
            # Si hay una sola cuenta, seleccionarla automáticamente
            accounts = self.cashbox_line_id.account_ids.filtered('active')
            if len(accounts) == 1:
                self.account_id = accounts[0]
    
    def _validate_withdrawal(self):
        """Validaciones específicas para retiros"""
        if not self.has_sufficient_balance:
            raise ValidationError(
                _('Saldo insuficiente. Disponible: %s %s') 
                % (self.currency_type, self.current_balance)
            )
        
        # Para retiros de terceros, verificar identidad
        if self.is_third_party and not self.identity_verified:
            raise ValidationError(
                _('Debe verificar la identidad del beneficiario antes de procesar el retiro.')
            )
        
        # Para transferencias, verificar que esté marcada como completada
        if self.operation_id.transfer_type and not self.is_cash:
            if not self.transfer_completed:
                raise ValidationError(
                    _('Debe marcar la transferencia como completada antes de procesar.')
                )
            if not self.transfer_reference:
                raise ValidationError(
                    _('Debe ingresar la referencia o comprobante de la transferencia.')
                )
    
    def _validate_deposit(self):
        """Validaciones específicas para depósitos"""
        # Para depósitos en efectivo de terceros, verificar identidad
        if self.is_third_party and self.is_cash and not self.identity_verified:
            raise ValidationError(
                _('Debe verificar la identidad de quien realiza el depósito.')
            )
    
    def action_process(self):
        """Procesa la operación"""
        self.ensure_one()
        
        # Validaciones generales
        if not self.cashbox_line_id:
            raise ValidationError(_('Debe seleccionar una subcaja.'))
        
        if not self.is_cash and not self.account_id:
            raise ValidationError(_('Debe seleccionar una cuenta para operaciones no efectivo.'))
        
        # Validaciones específicas por tipo
        if self.operation_type == 'withdrawal':
            self._validate_withdrawal()
        elif self.operation_type == 'deposit':
            self._validate_deposit()
        
        # Actualizar la operación
        update_vals = {
            'cashbox_line_id': self.cashbox_line_id.id,
            'account_id': self.account_id.id if self.account_id else False,
            'processed_by_user_id': self.env.user.id,
            'processing_date': fields.Datetime.now(),
        }
        
        if self.operation_id.transfer_type:
            update_vals['transfer_reference'] = self.transfer_reference
        
        if self.verification_notes:
            notes = self.operation_id.notes or ''
            if notes:
                notes += '\n\n'
            notes += f"[Verificación] {self.verification_notes}"
            update_vals['notes'] = notes
        
        self.operation_id.write(update_vals)
        
        # Completar la operación
        self.operation_id.action_complete()
        
        # Acciones post-procesamiento
        actions = []
        
        # Imprimir comprobante si está marcado
        if self.print_receipt:
            actions.append(self.operation_id.action_print_receipt())
        
        # Enviar notificación si está marcado
        if self.send_notification:
            # TODO: Implementar envío de notificación
            pass
        
        # Mostrar mensaje de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Operación Completada'),
                'message': _('La operación %s ha sido procesada exitosamente.') % self.operation_id.name,
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'sucursales_cajas.operation',
                    'res_id': self.operation_id.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            }
        }
    
    def action_reject(self):
        """Rechaza la operación"""
        self.ensure_one()
        
        # Solicitar motivo de rechazo
        return {
            'name': _('Rechazar Operación'),
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.reject_operation_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_operation_id': self.operation_id.id,
            }
        }


class RejectOperationWizard(models.TransientModel):
    _name = 'sucursales_cajas.reject_operation_wizard'
    _description = 'Wizard para Rechazar Operación'
    
    operation_id = fields.Many2one(
        'sucursales_cajas.operation',
        string='Operación',
        required=True,
        readonly=True
    )
    
    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        required=True
    )
    
    def action_confirm_reject(self):
        """Confirma el rechazo"""
        self.ensure_one()
        
        self.operation_id.write({
            'rejection_reason': self.rejection_reason,
            'processed_by_user_id': self.env.user.id,
            'processing_date': fields.Datetime.now(),
        })
        
        self.operation_id.action_cancel()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Operación Rechazada'),
                'message': _('La operación ha sido rechazada.'),
                'type': 'warning',
            }
        }