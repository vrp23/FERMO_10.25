# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json


class CashCountWizard(models.TransientModel):
    _name = 'sucursales_cajas.cash_count_wizard'
    _description = 'Wizard para Conteo de Efectivo'
    
    # Balance relacionado (si viene de un balance)
    balance_id = fields.Many2one(
        'sucursales_cajas.balance',
        string='Balance',
        readonly=True
    )
    
    # Moneda
    currency_type = fields.Selection([
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('EUR', 'Euros')
    ], string='Moneda', required=True, default='ARS')
    
    # Monto actual (para referencia)
    current_amount = fields.Float(
        string='Monto Actual/Anterior',
        readonly=True
    )
    
    # Líneas de denominaciones
    denomination_ids = fields.One2many(
        'sucursales_cajas.cash_count_wizard.line',
        'wizard_id',
        string='Denominaciones'
    )
    
    # Total calculado
    total_amount = fields.Float(
        string='Total Contado',
        compute='_compute_total_amount',
        store=True
    )
    
    # Diferencia
    difference = fields.Float(
        string='Diferencia',
        compute='_compute_difference',
        store=True
    )
    
    # Mostrar resumen
    summary_html = fields.Html(
        string='Resumen',
        compute='_compute_summary'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Carga valores por defecto y crea líneas de denominaciones"""
        res = super().default_get(fields_list)
        
        # Obtener denominaciones según la moneda
        currency = res.get('currency_type', 'ARS')
        denominations = self._get_denominations_for_currency(currency)
        
        # Crear líneas de denominaciones
        lines = []
        for i, denom in enumerate(denominations):
            lines.append((0, 0, {
                'sequence': i * 10,
                'denomination': denom,
                'quantity': 0,
                'subtotal': 0.0,
            }))
        
        res['denomination_ids'] = lines
        
        return res
    
    @api.model
    def _get_denominations_for_currency(self, currency_type):
        """Retorna las denominaciones de billetes según la moneda"""
        denominations = {
            'ARS': [
                10000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1, 0.50, 0.25, 0.10, 0.05
            ],
            'USD': [
                100, 50, 20, 10, 5, 2, 1
            ],
            'EUR': [
                500, 200, 100, 50, 20, 10, 5
            ]
        }
        
        return denominations.get(currency_type, [])
    
    @api.depends('denomination_ids.subtotal')
    def _compute_total_amount(self):
        """Calcula el total contado"""
        for wizard in self:
            wizard.total_amount = sum(wizard.denomination_ids.mapped('subtotal'))
    
    @api.depends('total_amount', 'current_amount')
    def _compute_difference(self):
        """Calcula la diferencia con el monto actual"""
        for wizard in self:
            wizard.difference = wizard.total_amount - wizard.current_amount
    
    @api.depends('denomination_ids', 'total_amount', 'difference')
    def _compute_summary(self):
        """Genera HTML de resumen"""
        for wizard in self:
            # Filtrar solo denominaciones con cantidad > 0
            active_denoms = wizard.denomination_ids.filtered(lambda d: d.quantity > 0)
            
            if not active_denoms:
                wizard.summary_html = '<p class="text-muted">No se han contado billetes aún.</p>'
                continue
            
            # Construir tabla HTML
            html = '<table class="table table-sm table-bordered">'
            html += '<thead><tr><th>Denominación</th><th class="text-center">Cantidad</th><th class="text-right">Subtotal</th></tr></thead>'
            html += '<tbody>'
            
            # Agrupar por billetes y monedas
            billetes = active_denoms.filtered(lambda d: d.denomination >= 1)
            monedas = active_denoms.filtered(lambda d: d.denomination < 1)
            
            # Mostrar billetes
            if billetes:
                html += '<tr class="table-active"><td colspan="3"><strong>Billetes</strong></td></tr>'
                for line in billetes.sorted('denomination', reverse=True):
                    html += f'<tr><td>${line.denomination:g}</td>'
                    html += f'<td class="text-center">{line.quantity}</td>'
                    html += f'<td class="text-right">${line.subtotal:,.2f}</td></tr>'
            
            # Mostrar monedas
            if monedas:
                html += '<tr class="table-active"><td colspan="3"><strong>Monedas</strong></td></tr>'
                for line in monedas.sorted('denomination', reverse=True):
                    html += f'<tr><td>${line.denomination:.2f}</td>'
                    html += f'<td class="text-center">{line.quantity}</td>'
                    html += f'<td class="text-right">${line.subtotal:,.2f}</td></tr>'
            
            # Total
            html += '</tbody><tfoot>'
            html += f'<tr class="table-info"><th colspan="2">Total Contado</th>'
            html += f'<th class="text-right">${wizard.total_amount:,.2f}</th></tr>'
            
            # Mostrar diferencia si hay monto de referencia
            if wizard.current_amount:
                diff_class = 'success' if wizard.difference >= 0 else 'danger'
                html += f'<tr><td colspan="2">Monto Sistema</td>'
                html += f'<td class="text-right">${wizard.current_amount:,.2f}</td></tr>'
                html += f'<tr class="table-{diff_class}"><th colspan="2">Diferencia</th>'
                html += f'<th class="text-right">${wizard.difference:,.2f}</th></tr>'
            
            html += '</tfoot></table>'
            
            wizard.summary_html = html
    
    @api.onchange('currency_type')
    def _onchange_currency_type(self):
        """Recrea las líneas de denominaciones al cambiar la moneda"""
        # Limpiar líneas existentes
        self.denomination_ids = [(5, 0, 0)]
        
        # Crear nuevas líneas
        denominations = self._get_denominations_for_currency(self.currency_type)
        lines = []
        for i, denom in enumerate(denominations):
            lines.append((0, 0, {
                'sequence': i * 10,
                'denomination': denom,
                'quantity': 0,
                'subtotal': 0.0,
            }))
        
        self.denomination_ids = lines
    
    def action_quick_count(self):
        """Abre un diálogo para conteo rápido por totales"""
        # TODO: Implementar wizard de conteo rápido
        raise UserError(_('Función de conteo rápido en desarrollo.'))
    
    def action_confirm(self):
        """Confirma el conteo"""
        self.ensure_one()
        
        if self.total_amount == 0:
            raise ValidationError(_('Debe contar al menos algunos billetes antes de confirmar.'))
        
        # Si está relacionado con un balance, actualizarlo
        if self.balance_id:
            # Preparar detalle de billetes en JSON
            bill_details = {}
            for line in self.denomination_ids.filtered(lambda l: l.quantity > 0):
                bill_details[str(line.denomination)] = line.quantity
            
            # Actualizar el balance
            self.balance_id.write({
                'counted_amount': self.total_amount,
                'bill_details': json.dumps(bill_details) if bill_details else False,
            })
            
            # Si el balance está en borrador, sugerir confirmarlo
            if self.balance_id.state == 'draft':
                return {
                    'name': _('Confirmar Balance'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'sucursales_cajas.balance',
                    'res_id': self.balance_id.id,
                    'view_mode': 'form',
                    'target': 'current',
                    'context': {
                        'show_success_message': _('Conteo registrado exitosamente. Total: $%s') % self.total_amount,
                    }
                }
        
        # Mostrar mensaje de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conteo Confirmado'),
                'message': _('Total contado: %s %s') % (self.currency_type, self.total_amount),
                'sticky': False,
                'type': 'success',
            }
        }
    
    def action_print_count(self):
        """Imprime el detalle del conteo"""
        self.ensure_one()
        # TODO: Implementar reporte de conteo
        raise UserError(_('Función de impresión en desarrollo.'))


class CashCountWizardLine(models.TransientModel):
    _name = 'sucursales_cajas.cash_count_wizard.line'
    _description = 'Línea de Conteo de Efectivo'
    _order = 'sequence, denomination desc'
    
    wizard_id = fields.Many2one(
        'sucursales_cajas.cash_count_wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    denomination = fields.Float(
        string='Denominación',
        required=True,
        readonly=True
    )
    
    denomination_display = fields.Char(
        string='Denominación',
        compute='_compute_denomination_display'
    )
    
    quantity = fields.Integer(
        string='Cantidad',
        default=0
    )
    
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True
    )
    
    is_bill = fields.Boolean(
        string='Es Billete',
        compute='_compute_is_bill'
    )
    
    @api.depends('denomination')
    def _compute_denomination_display(self):
        """Formatea la denominación para mostrar"""
        for line in self:
            if line.denomination >= 1:
                # Mostrar sin decimales para billetes
                line.denomination_display = f"${int(line.denomination)}"
            else:
                # Mostrar con 2 decimales para monedas
                line.denomination_display = f"${line.denomination:.2f}"
    
    @api.depends('denomination')
    def _compute_is_bill(self):
        """Determina si es billete o moneda"""
        for line in self:
            line.is_bill = line.denomination >= 1
    
    @api.depends('denomination', 'quantity')
    def _compute_subtotal(self):
        """Calcula el subtotal de la línea"""
        for line in self:
            line.subtotal = line.denomination * line.quantity
    
    @api.onchange('quantity')
    def _onchange_quantity(self):
        """Valida cantidad negativa"""
        if self.quantity < 0:
            self.quantity = 0
            return {
                'warning': {
                    'title': _('Cantidad Inválida'),
                    'message': _('La cantidad no puede ser negativa.')
                }
            }