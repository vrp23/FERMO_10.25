# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CommissionReversalWizard(models.TransientModel):
    _name = 'commission.reversal.wizard'
    _description = 'Wizard para Revertir Liquidación'
    
    # Liquidación a revertir
    liquidation_id = fields.Many2one(
        'commission.liquidation',
        string='Liquidación a Revertir',
        required=True,
        readonly=True
    )
    
    # Información de la liquidación
    liquidation_info = fields.Html(
        string='Información de la Liquidación',
        compute='_compute_liquidation_info'
    )
    
    # Motivo
    reversal_reason = fields.Text(
        string='Motivo de Reversión',
        required=True
    )
    
    # Opciones
    create_reversal_entry = fields.Boolean(
        string='Crear Liquidación de Reversión',
        default=True,
        help='Crear una liquidación con valores negativos para compensar'
    )
    
    revert_wallet_movement = fields.Boolean(
        string='Revertir Movimiento de Wallet',
        default=True,
        help='Crear movimiento compensatorio en la wallet del operador'
    )
    
    unlock_operations = fields.Boolean(
        string='Desbloquear Operaciones',
        default=True,
        help='Permitir que las operaciones puedan ser liquidadas nuevamente'
    )
    
    @api.depends('liquidation_id')
    def _compute_liquidation_info(self):
        """Genera HTML con información de la liquidación"""
        for wizard in self:
            if not wizard.liquidation_id:
                wizard.liquidation_info = ''
                continue
            
            liq = wizard.liquidation_id
            
            html = '<div class="alert alert-warning">'
            html += '<h5>Liquidación a Revertir</h5>'
            html += '<table class="table table-sm">'
            html += f'<tr><td><strong>Número:</strong></td><td>{liq.name}</td></tr>'
            html += f'<tr><td><strong>Operador:</strong></td><td>{liq.operator_id.name}</td></tr>'
            html += f'<tr><td><strong>Fecha:</strong></td><td>{liq.date}</td></tr>'
            html += f'<tr><td><strong>Tipo:</strong></td><td>{dict(liq._fields["liquidation_type"].selection).get(liq.liquidation_type)}</td></tr>'
            html += f'<tr><td><strong>Comisión Total:</strong></td><td>${liq.total_commission:,.2f}</td></tr>'
            
            if liq.payment_date:
                html += f'<tr><td><strong>Fecha de Pago:</strong></td><td>{liq.payment_date}</td></tr>'
            
            html += '</table>'
            html += '<p class="mb-0"><strong>⚠️ Esta acción no se puede deshacer</strong></p>'
            html += '</div>'
            
            wizard.liquidation_info = html
    
    def action_confirm_reversal(self):
        """Confirma y ejecuta la reversión"""
        self.ensure_one()
        
        # Validaciones
        if self.liquidation_id.state != 'paid':
            raise UserError(_('Solo se pueden revertir liquidaciones pagadas.'))
        
        if self.liquidation_id.reversed_by_id:
            raise UserError(_('Esta liquidación ya fue revertida.'))
        
        # 1. Crear liquidación de reversión si está marcado
        reversal_liquidation = False
        if self.create_reversal_entry:
            reversal_vals = {
                'operator_id': self.liquidation_id.operator_id.id,
                'liquidation_type': self.liquidation_id.liquidation_type,
                'date': fields.Date.today(),
                'is_reversal': True,
                'reversal_liquidation_id': self.liquidation_id.id,
                'notes': f'Reversión de {self.liquidation_id.name}\nMotivo: {self.reversal_reason}',
                'state': 'confirmed',
            }
            
            # Copiar período si aplica
            if self.liquidation_id.liquidation_type == 'divisas':
                reversal_vals.update({
                    'period_start': self.liquidation_id.period_start,
                    'period_end': self.liquidation_id.period_end,
                })
            
            reversal_liquidation = self.env['commission.liquidation'].create(reversal_vals)
            
            # Crear líneas de reversión (con valores negativos)
            for line in self.liquidation_id.line_ids:
                reversal_line_vals = {
                    'liquidation_id': reversal_liquidation.id,
                    'description': f'Reversión: {line.description}',
                    'source_model': line.source_model,
                    'source_reference': line.source_reference,  # CORRECCIÓN: usar source_reference
                    'base_amount': -line.base_amount,
                    'commission_rate': line.commission_rate,
                    'commission_amount': -line.commission_amount,
                    'operation_date': line.operation_date,
                    'partner_id': line.partner_id.id if line.partner_id else False,
                }
                
                # Copiar referencias específicas según el tipo
                if line.check_id:
                    reversal_line_vals['check_id'] = line.check_id.id
                if line.currency_operation_id:
                    reversal_line_vals['currency_operation_id'] = line.currency_operation_id.id
                if line.cashbox_operation_id:
                    reversal_line_vals['cashbox_operation_id'] = line.cashbox_operation_id.id
                
                self.env['commission.liquidation.line'].create(reversal_line_vals)
        
        # 2. Revertir movimiento de wallet si está marcado
        if self.revert_wallet_movement and self.liquidation_id.wallet_movement_id:
            # Crear movimiento compensatorio
            original_movement = self.liquidation_id.wallet_movement_id
            reversal_movement_vals = {
                'partner_id': original_movement.partner_id.id,
                'tipo': 'anulacion',  # CORRECCIÓN: usar tipo existente
                'monto': -original_movement.monto,  # Negativo para compensar
                'fecha': fields.Date.today(),
                'notes': f'Reversión de comisión - {self.liquidation_id.name}\nMotivo: {self.reversal_reason}',
                'state': 'confirmado',
            }
            
            reversal_movement = self.env['chequera.wallet.movement'].create(reversal_movement_vals)
            
            # Si se creó liquidación de reversión, asociar el movimiento
            if reversal_liquidation:
                reversal_liquidation.write({
                    'wallet_movement_id': reversal_movement.id,
                    'payment_date': fields.Date.today(),
                    'state': 'paid'
                })
        
        # 3. Desbloquear operaciones si está marcado
        if self.unlock_operations:
            for line in self.liquidation_id.line_ids:
                # Desbloquear cheques
                if line.check_id:
                    line.check_id.write({
                        'commission_liquidated': False,
                        'commission_liquidation_id': False
                    })
                
                # Desbloquear operaciones de divisas
                if line.currency_operation_id:
                    line.currency_operation_id.write({
                        'commission_liquidated': False,
                        'commission_liquidation_id': False
                    })
                
                # Desbloquear operaciones de caja
                if line.cashbox_operation_id:
                    line.cashbox_operation_id.write({
                        'commission_liquidated': False,
                        'commission_liquidation_id': False
                    })
        
        # 4. Marcar la liquidación original como revertida
        self.liquidation_id.write({
            'reversed_by_id': reversal_liquidation.id if reversal_liquidation else False,
            'notes': (self.liquidation_id.notes or '') + 
                    f'\n\n[Revertida el {fields.Date.today()}]\nMotivo: {self.reversal_reason}'
        })
        
        # Mostrar mensaje de éxito
        if reversal_liquidation:
            return {
                'name': _('Reversión Completada'),
                'type': 'ir.actions.act_window',
                'res_model': 'commission.liquidation',
                'res_id': reversal_liquidation.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reversión Completada'),
                    'message': _('La liquidación ha sido revertida exitosamente.'),
                    'sticky': False,
                    'type': 'success',
                }
            }