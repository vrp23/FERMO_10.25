# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
from datetime import datetime


class CloseSessionWizard(models.TransientModel):
    _name = 'sucursales_cajas.close_session_wizard'
    _description = 'Wizard para Cerrar Sesión de Caja'
    
    # Sesión
    session_id = fields.Many2one(
        'sucursales_cajas.session',
        string='Sesión',
        required=True,
        readonly=True
    )
    
    # Información de la sesión
    session_info = fields.Html(
        string='Información de la Sesión',
        compute='_compute_session_info'
    )
    
    # Líneas de balance
    balance_line_ids = fields.One2many(
        'sucursales_cajas.close_session_wizard.line',
        'wizard_id',
        string='Balances de Cierre'
    )
    
    # Resumen de operaciones
    operations_summary = fields.Html(
        string='Resumen de Operaciones',
        compute='_compute_operations_summary'
    )
    
    # Totales
    total_deposits_count = fields.Integer(
        string='Total Depósitos',
        compute='_compute_totals'
    )
    
    total_withdrawals_count = fields.Integer(
        string='Total Retiros',
        compute='_compute_totals'
    )
    
    total_operations_count = fields.Integer(
        string='Total Operaciones',
        compute='_compute_totals'
    )
    
    # Discrepancias
    has_discrepancies = fields.Boolean(
        string='Tiene Discrepancias',
        compute='_compute_has_discrepancies'
    )
    
    total_discrepancy = fields.Float(
        string='Discrepancia Total',
        compute='_compute_has_discrepancies'
    )
    
    discrepancy_notes = fields.Text(
        string='Justificación de Discrepancias',
        help="Explique las razones de las diferencias encontradas"
    )
    
    # Observaciones generales
    closing_notes = fields.Text(
        string='Observaciones de Cierre'
    )
    
    # Opciones
    force_close = fields.Boolean(
        string='Forzar Cierre',
        help="Cerrar sesión aunque haya discrepancias sin resolver"
    )
    
    print_report = fields.Boolean(
        string='Imprimir Reporte de Cierre',
        default=True
    )
    
    # PIN de confirmación
    confirm_pin = fields.Char(
        string='PIN de Confirmación',
        size=6,
        help="Ingrese su PIN de sesión para confirmar el cierre"
    )
    
    @api.model
    def default_get(self, fields_list):
        """Carga valores por defecto"""
        res = super().default_get(fields_list)
        
        session_id = self.env.context.get('default_session_id')
        if session_id:
            session = self.env['sucursales_cajas.session'].browse(session_id)
            
            # Obtener o crear balances de cierre
            lines = []
            for cashbox_line in session.cashbox_id.cashbox_line_ids.filtered('active'):
                # Buscar balance existente
                balance = session.closing_balance_ids.filtered(
                    lambda b: b.cashbox_line_id == cashbox_line
                )
                
                if balance:
                    balance = balance[0]
                    declared = balance.declared_amount
                    counted = balance.counted_amount
                else:
                    declared = cashbox_line.session_current_balance
                    counted = 0.0
                
                line_vals = {
                    'cashbox_line_id': cashbox_line.id,
                    'balance_id': balance.id if balance else False,
                    'system_balance': cashbox_line.session_current_balance,
                    'declared_balance': declared,
                    'counted_balance': counted,
                }
                
                lines.append((0, 0, line_vals))
            
            res['balance_line_ids'] = lines
        
        return res
    
    @api.depends('session_id')
    def _compute_session_info(self):
        """Genera información HTML de la sesión"""
        for wizard in self:
            if not wizard.session_id:
                wizard.session_info = ''
                continue
            
            session = wizard.session_id
            
            html = '<div class="row">'
            
            # Información básica
            html += '<div class="col-md-6">'
            html += '<table class="table table-sm">'
            html += f'<tr><td><strong>Sesión:</strong></td><td>{session.name}</td></tr>'
            html += f'<tr><td><strong>Caja:</strong></td><td>{session.cashbox_id.display_name}</td></tr>'
            html += f'<tr><td><strong>Usuario:</strong></td><td>{session.user_id.name}</td></tr>'
            html += f'<tr><td><strong>Inicio:</strong></td><td>{session.start_datetime.strftime("%d/%m/%Y %H:%M")}</td></tr>'
            
            # Duración
            duration = fields.Datetime.now() - session.start_datetime
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            html += f'<tr><td><strong>Duración:</strong></td><td>{hours}h {minutes}m</td></tr>'
            
            html += '</table>'
            html += '</div>'
            
            # Estadísticas
            html += '<div class="col-md-6">'
            html += '<table class="table table-sm">'
            html += f'<tr><td><strong>Operaciones:</strong></td><td>{session.operation_count}</td></tr>'
            html += f'<tr><td><strong>Depósitos:</strong></td><td>{session.deposit_count}</td></tr>'
            html += f'<tr><td><strong>Retiros:</strong></td><td>{session.withdrawal_count}</td></tr>'
            
            if session.pending_operation_count > 0:
                html += f'<tr class="text-danger"><td><strong>Pendientes:</strong></td><td>{session.pending_operation_count}</td></tr>'
            
            html += '</table>'
            html += '</div>'
            
            html += '</div>'
            
            wizard.session_info = html
    
    @api.depends('session_id')
    def _compute_operations_summary(self):
        """Genera resumen de operaciones por moneda"""
        for wizard in self:
            if not wizard.session_id:
                wizard.operations_summary = ''
                continue
            
            # Agrupar operaciones por moneda y tipo
            operations = wizard.session_id.operation_ids.filtered(lambda o: o.state == 'done')
            
            if not operations:
                wizard.operations_summary = '<p class="text-muted">No se realizaron operaciones en esta sesión.</p>'
                continue
            
            # Diccionario para acumular por moneda
            summary_by_currency = {}
            
            for op in operations:
                currency = op.currency_type
                if currency not in summary_by_currency:
                    summary_by_currency[currency] = {
                        'deposits': 0.0,
                        'withdrawals': 0.0,
                        'deposit_count': 0,
                        'withdrawal_count': 0,
                    }
                
                if op.operation_type == 'deposit':
                    summary_by_currency[currency]['deposits'] += op.amount
                    summary_by_currency[currency]['deposit_count'] += 1
                elif op.operation_type == 'withdrawal':
                    summary_by_currency[currency]['withdrawals'] += op.amount
                    summary_by_currency[currency]['withdrawal_count'] += 1
            
            # Generar HTML
            html = '<table class="table table-sm table-bordered">'
            html += '<thead><tr>'
            html += '<th>Moneda</th>'
            html += '<th class="text-center">Depósitos</th>'
            html += '<th class="text-center">Retiros</th>'
            html += '<th class="text-center">Neto</th>'
            html += '</tr></thead><tbody>'
            
            for currency, data in sorted(summary_by_currency.items()):
                net = data['deposits'] - data['withdrawals']
                net_class = 'text-success' if net >= 0 else 'text-danger'
                
                html += f'<tr>'
                html += f'<td><strong>{currency}</strong></td>'
                html += f'<td class="text-center">'
                html += f'{data["deposits"]:,.2f}<br/>'
                html += f'<small class="text-muted">({data["deposit_count"]} ops)</small>'
                html += f'</td>'
                html += f'<td class="text-center">'
                html += f'{data["withdrawals"]:,.2f}<br/>'
                html += f'<small class="text-muted">({data["withdrawal_count"]} ops)</small>'
                html += f'</td>'
                html += f'<td class="text-center {net_class}">'
                html += f'<strong>{net:+,.2f}</strong>'
                html += f'</td>'
                html += f'</tr>'
            
            html += '</tbody></table>'
            
            wizard.operations_summary = html
    
    @api.depends('session_id')
    def _compute_totals(self):
        """Calcula totales de operaciones"""
        for wizard in self:
            if wizard.session_id:
                done_operations = wizard.session_id.operation_ids.filtered(lambda o: o.state == 'done')
                deposits = done_operations.filtered(lambda o: o.operation_type == 'deposit')
                withdrawals = done_operations.filtered(lambda o: o.operation_type == 'withdrawal')
                
                wizard.total_deposits_count = len(deposits)
                wizard.total_withdrawals_count = len(withdrawals)
                wizard.total_operations_count = len(done_operations)
            else:
                wizard.total_deposits_count = 0
                wizard.total_withdrawals_count = 0
                wizard.total_operations_count = 0
    
    @api.depends('balance_line_ids.difference')
    def _compute_has_discrepancies(self):
        """Determina si hay discrepancias"""
        for wizard in self:
            differences = wizard.balance_line_ids.mapped('difference')
            wizard.has_discrepancies = any(diff != 0 for diff in differences)
            wizard.total_discrepancy = sum(abs(diff) for diff in differences)
    
    def action_count_cash(self):
        """Abre wizard para contar efectivo de una línea específica"""
        self.ensure_one()
        
        # Obtener la línea desde el contexto
        line_id = self.env.context.get('line_id')
        if not line_id:
            raise UserError(_('No se pudo identificar la línea a contar.'))
        
        line = self.balance_line_ids.browse(line_id)
        if not line.cashbox_line_id.is_cash:
            raise UserError(_('El conteo solo aplica para líneas de efectivo.'))
        
        # Abrir wizard de conteo
        return {
            'name': _('Contar %s') % line.cashbox_line_id.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.cash_count_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_currency_type': line.cashbox_line_id.currency_type,
                'default_current_amount': line.system_balance,
                'close_line_id': line.id,
            }
        }
    
    def _validate_closing(self):
        """Validaciones antes de cerrar"""
        # Verificar operaciones pendientes
        if self.session_id.pending_operation_count > 0:
            raise ValidationError(
                _('No se puede cerrar la sesión con %d operaciones pendientes.') 
                % self.session_id.pending_operation_count
            )
        
        # Verificar PIN si se requiere
        if self.session_id.cashbox_id.require_pin and self.session_id.pin_hash:
            if not self.confirm_pin:
                raise ValidationError(_('Debe ingresar su PIN de sesión para confirmar el cierre.'))
            
            if not self.session_id.verify_pin(self.confirm_pin):
                raise ValidationError(_('PIN incorrecto. Por favor verifique.'))
        
        # Verificar discrepancias
        if self.has_discrepancies and not self.force_close:
            if not self.discrepancy_notes:
                raise ValidationError(
                    _('Hay discrepancias por %.2f. Debe justificarlas o marcar "Forzar Cierre".') 
                    % self.total_discrepancy
                )
        
        # Verificar que todos los balances estén declarados
        for line in self.balance_line_ids:
            if line.cashbox_line_id.is_cash and line.counted_balance == 0 and line.system_balance != 0:
                if not self.force_close:
                    raise ValidationError(
                        _('Debe contar el efectivo de %s o marcar "Forzar Cierre".') 
                        % line.cashbox_line_id.display_name
                    )
    
    def _create_closing_balances(self):
        """Crea o actualiza los balances de cierre"""
        Balance = self.env['sucursales_cajas.balance']
        
        for line in self.balance_line_ids:
            if line.balance_id:
                # Actualizar balance existente
                line.balance_id.write({
                    'declared_amount': line.declared_balance,
                    'counted_amount': line.counted_balance if line.cashbox_line_id.is_cash else 0,
                    'notes': line.notes,
                })
                balance = line.balance_id
            else:
                # Crear nuevo balance
                balance_vals = {
                    'session_id': self.session_id.id,
                    'balance_type': 'closing',
                    'cashbox_line_id': line.cashbox_line_id.id,
                    'system_balance': line.system_balance,
                    'declared_amount': line.declared_balance,
                    'counted_amount': line.counted_balance if line.cashbox_line_id.is_cash else 0,
                    'notes': line.notes,
                }
                balance = Balance.create(balance_vals)
            
            # Confirmar el balance
            if balance.state == 'draft':
                balance.action_confirm()
    
    def action_close_session(self):
        """Cierra la sesión"""
        self.ensure_one()
        
        # Validaciones
        self._validate_closing()
        
        # Crear/actualizar balances de cierre
        self._create_closing_balances()
        
        # Actualizar observaciones de la sesión
        notes = self.closing_notes or ''
        if self.has_discrepancies and self.discrepancy_notes:
            if notes:
                notes += '\n\n'
            notes += f"[Discrepancias] {self.discrepancy_notes}"
        
        self.session_id.closing_notes = notes
        
        # Cerrar la sesión
        self.session_id.action_close_session()
        
        # Imprimir reporte si está marcado
        if self.print_report:
            # TODO: Implementar reporte
            pass
        
        # Mostrar mensaje de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sesión Cerrada'),
                'message': _('La sesión %s ha sido cerrada exitosamente.') % self.session_id.name,
                'sticky': False,
                'type': 'success',
            }
        }


class CloseSessionWizardLine(models.TransientModel):
    _name = 'sucursales_cajas.close_session_wizard.line'
    _description = 'Línea de Balance de Cierre'
    _order = 'sequence'
    
    wizard_id = fields.Many2one(
        'sucursales_cajas.close_session_wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    # Balance relacionado (si existe)
    balance_id = fields.Many2one(
        'sucursales_cajas.balance',
        string='Balance'
    )
    
    # Subcaja
    cashbox_line_id = fields.Many2one(
        'sucursales_cajas.cashbox_line',
        string='Subcaja',
        required=True,
        readonly=True
    )
    
    line_name = fields.Char(
        related='cashbox_line_id.display_name',
        string='Subcaja'
    )
    
    currency_type = fields.Selection(
        related='cashbox_line_id.currency_type',
        string='Moneda'
    )
    
    is_cash = fields.Boolean(
        related='cashbox_line_id.is_cash',
        string='Es Efectivo'
    )
    
    # Balances
    opening_balance = fields.Float(
        string='Saldo Apertura',
        compute='_compute_opening_balance'
    )
    
    system_balance = fields.Float(
        string='Saldo Sistema',
        readonly=True,
        help="Saldo calculado según las operaciones"
    )
    
    declared_balance = fields.Float(
        string='Saldo Declarado',
        help="Saldo declarado al cerrar"
    )
    
    counted_balance = fields.Float(
        string='Saldo Contado',
        help="Saldo contado físicamente (solo efectivo)"
    )
    
    difference = fields.Float(
        string='Diferencia',
        compute='_compute_difference',
        store=True
    )
    
    # Movimientos del día
    deposits_amount = fields.Float(
        string='Depósitos',
        compute='_compute_movements'
    )
    
    withdrawals_amount = fields.Float(
        string='Retiros',
        compute='_compute_movements'
    )
    
    net_movement = fields.Float(
        string='Movimiento Neto',
        compute='_compute_movements'
    )
    
    # Notas
    notes = fields.Text(
        string='Observaciones'
    )
    
    @api.depends('cashbox_line_id', 'wizard_id.session_id')
    def _compute_opening_balance(self):
        """Obtiene el saldo de apertura"""
        for line in self:
            if line.wizard_id.session_id:
                opening = line.wizard_id.session_id.opening_balance_ids.filtered(
                    lambda b: b.cashbox_line_id == line.cashbox_line_id
                )
                if opening:
                    line.opening_balance = opening[0].declared_amount
                else:
                    line.opening_balance = 0.0
            else:
                line.opening_balance = 0.0
    
    @api.depends('cashbox_line_id', 'wizard_id.session_id')
    def _compute_movements(self):
        """Calcula los movimientos del día"""
        for line in self:
            deposits = 0.0
            withdrawals = 0.0
            
            if line.wizard_id.session_id and line.cashbox_line_id:
                # Filtrar operaciones de esta subcaja
                operations = line.wizard_id.session_id.operation_ids.filtered(
                    lambda o: o.state == 'done' and 
                    o.cashbox_line_id == line.cashbox_line_id
                )
                
                for op in operations:
                    if op.operation_type == 'deposit':
                        deposits += op.amount
                    elif op.operation_type == 'withdrawal':
                        withdrawals += op.amount
            
            line.deposits_amount = deposits
            line.withdrawals_amount = withdrawals
            line.net_movement = deposits - withdrawals
    
    @api.depends('system_balance', 'declared_balance', 'counted_balance', 'is_cash')
    def _compute_difference(self):
        """Calcula la diferencia"""
        for line in self:
            if line.is_cash and line.counted_balance:
                # Para efectivo, usar el monto contado
                line.difference = line.counted_balance - line.system_balance
            else:
                # Para otros, usar el monto declarado
                line.difference = line.declared_balance - line.system_balance
    
    @api.onchange('declared_balance')
    def _onchange_declared_balance(self):
        """Advierte si hay diferencia significativa"""
        if self.system_balance and self.declared_balance:
            diff = abs(self.declared_balance - self.system_balance)
            if self.system_balance != 0:
                diff_percent = diff / abs(self.system_balance) * 100
            else:
                diff_percent = 100 if diff > 0 else 0
            
            if diff_percent > 5:  # Más del 5% de diferencia
                return {
                    'warning': {
                        'title': _('Diferencia Detectada'),
                        'message': _('Hay una diferencia del %.1f%% entre el saldo declarado '
                                   'y el saldo del sistema.') % diff_percent
                    }
                }