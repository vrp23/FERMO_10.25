from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date

class CommissionLiquidation(models.Model):
    _name = 'commission.liquidation'
    _description = 'Liquidación de Comisiones'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    # Identificación
    name = fields.Char(string='Número', required=True, readonly=True, default='Nueva', copy=False)
    operator_id = fields.Many2one('res.users', string='Operador', required=True, tracking=True)
    liquidation_type = fields.Selection([
        ('cheques', 'Cheques'),
        ('divisas', 'Divisas'),
        ('caja', 'Operaciones de Caja'),
        ('manual', 'Manual')
    ], string='Tipo', required=True, tracking=True)
    
    # Fechas
    date = fields.Date(string='Fecha', required=True, default=fields.Date.today, tracking=True)
    period_start = fields.Date(string='Período Desde')
    period_end = fields.Date(string='Período Hasta')
    
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Calculado'),
        ('confirmed', 'Confirmado'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    # Líneas
    line_ids = fields.One2many('commission.liquidation.line', 'liquidation_id', string='Líneas')
    line_count = fields.Integer(string='Cantidad de Líneas', compute='_compute_counts', store=True)
    check_count = fields.Integer(string='Cantidad de Cheques', compute='_compute_counts', store=True)
    
    # Totales
    total_base = fields.Float(string='Base Total', compute='_compute_totals', store=True)
    total_commission = fields.Float(string='Comisión Total', compute='_compute_totals', store=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', 
                                  default=lambda self: self.env.company.currency_id)
    
    # Pago
    payment_date = fields.Date(string='Fecha de Pago', tracking=True)
    wallet_movement_id = fields.Many2one('chequera.wallet.movement', string='Movimiento de Wallet')
    operator_partner_id = fields.Many2one('res.partner', string='Contacto del Operador')
    
    # Reversión
    is_reversal = fields.Boolean(string='Es Reversión', default=False)
    reversal_liquidation_id = fields.Many2one('commission.liquidation', string='Liquidación Revertida')
    reversed_by_id = fields.Many2one('commission.liquidation', string='Revertida Por')
    
    # Notas
    notes = fields.Text(string='Notas')
    
    # Empresa
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Genera el número de liquidación al crear"""
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                prefix = {
                    'cheques': 'LIQ/CHQ/',
                    'divisas': 'LIQ/DIV/',
                    'caja': 'LIQ/CAJA/',
                    'manual': 'LIQ/MAN/'
                }.get(vals.get('liquidation_type', 'manual'), 'LIQ/')
                
                vals['name'] = self.env['ir.sequence'].next_by_code('commission.liquidation') or prefix + '00001'
        
        return super(CommissionLiquidation, self).create(vals_list)
    
    @api.depends('line_ids')
    def _compute_counts(self):
        """Calcula los contadores"""
        for liquidation in self:
            liquidation.line_count = len(liquidation.line_ids)
            
            if liquidation.liquidation_type == 'cheques':
                liquidation.check_count = len(liquidation.line_ids.filtered('check_id'))
            else:
                liquidation.check_count = 0
    
    @api.depends('line_ids.base_amount', 'line_ids.commission_amount')
    def _compute_totals(self):
        """Calcula los totales"""
        for liquidation in self:
            liquidation.total_base = sum(liquidation.line_ids.mapped('base_amount'))
            liquidation.total_commission = sum(liquidation.line_ids.mapped('commission_amount'))
    
    def action_calculate_commissions(self):
        """Abre el wizard correspondiente para calcular comisiones"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Solo se pueden calcular comisiones en liquidaciones en borrador.'))
        
        # Determinar qué wizard abrir según el tipo
        if self.liquidation_type == 'cheques':
            return {
                'name': _('Calcular Comisiones de Cheques'),
                'type': 'ir.actions.act_window',
                'res_model': 'commission.cheques.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_operator_id': self.operator_id.id,
                    'default_period_start': self.period_start or date.today().replace(day=1),
                    'default_period_end': self.period_end or date.today(),
                }
            }
        
        elif self.liquidation_type == 'divisas':
            return {
                'name': _('Calcular Comisiones de Divisas'),
                'type': 'ir.actions.act_window',
                'res_model': 'commission.divisas.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_operator_id': self.operator_id.id,
                    'default_period_start': self.period_start or date.today().replace(day=1),
                    'default_period_end': self.period_end or date.today(),
                }
            }
        
        elif self.liquidation_type == 'caja':
            return {
                'name': _('Calcular Comisiones de Caja'),
                'type': 'ir.actions.act_window',
                'res_model': 'commission.caja.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_operator_id': self.operator_id.id,
                    'default_period_start': self.period_start or date.today().replace(day=1),
                    'default_period_end': self.period_end or date.today(),
                }
            }
        
        else:
            raise UserError(_('Tipo de liquidación no soportado para cálculo automático.'))
    
    def action_confirm(self):
        """Confirma la liquidación y marca las operaciones como liquidadas"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Solo se pueden confirmar liquidaciones en borrador.'))
        
        if not self.line_ids:
            raise UserError(_('No hay líneas de liquidación para confirmar.'))
        
        # Marcar operaciones como liquidadas según el tipo
        for line in self.line_ids:
            # Para cheques
            if line.check_id:
                line.check_id.write({
                    'commission_liquidated': True,
                    'commission_liquidation_id': self.id,
                })
            
            # Para operaciones de divisas
            if line.currency_operation_id:
                line.currency_operation_id.write({
                    'commission_liquidated': True,
                    'commission_liquidation_id': self.id,
                })
            
            # Para operaciones de caja
            if line.cashbox_operation_id:
                line.cashbox_operation_id.write({
                    'commission_liquidated': True,
                    'commission_liquidation_id': self.id,
                })
        
        self.write({
            'state': 'confirmed',
        })
        
        # Mensaje en el chatter
        self.message_post(
            body=_('Liquidación confirmada con %d líneas. Total de comisión: %s') % 
                 (len(self.line_ids), self.total_commission)
        )
        
        return True
    
    def action_pay(self):
        """Registra el pago de la liquidación"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise UserError(_('Solo se pueden pagar liquidaciones confirmadas.'))
        
        # Obtener el partner del operador
        operator_partner = self.env['res.partner'].search([
            ('user_id', '=', self.operator_id.id)
        ], limit=1)
        
        if not operator_partner:
            raise UserError(_('El operador no tiene un contacto asociado. No se puede registrar el pago.'))
        
        # Crear movimiento en wallet con context especial para saltar validación
        wallet_movement = self.env['chequera.wallet.movement'].with_context(from_operation=True).create({
            'partner_id': operator_partner.id,
            'tipo': 'anulacion',  # Usar un tipo existente que no requiera validación
            'monto': self.total_commission,
            'fecha': fields.Date.today(),
            'notes': f'Pago de comisión - Liquidación {self.name}',
            'state': 'confirmado',
        })
        
        # Actualizar la liquidación
        self.write({
            'state': 'paid',
            'payment_date': fields.Date.today(),
            'wallet_movement_id': wallet_movement.id,
            'operator_partner_id': operator_partner.id,
        })
        
        # Mensaje en el chatter
        self.message_post(
            body=_('Pago registrado. Movimiento de wallet creado por %s') % self.total_commission
        )
        
        return True
    
    def action_cancel(self):
        """Cancela la liquidación"""
        self.ensure_one()
        
        if self.state == 'paid':
            raise UserError(_('No se pueden cancelar liquidaciones pagadas. Use la opción de reversión.'))
        
        if self.state == 'cancelled':
            raise UserError(_('La liquidación ya está cancelada.'))
        
        # Desmarcar operaciones como liquidadas
        for line in self.line_ids:
            # Para cheques
            if line.check_id and line.check_id.commission_liquidation_id.id == self.id:
                line.check_id.write({
                    'commission_liquidated': False,
                    'commission_liquidation_id': False,
                })
            
            # Para operaciones de divisas
            if line.currency_operation_id and line.currency_operation_id.commission_liquidation_id.id == self.id:
                line.currency_operation_id.write({
                    'commission_liquidated': False,
                    'commission_liquidation_id': False,
                })
            
            # Para operaciones de caja
            if line.cashbox_operation_id and line.cashbox_operation_id.commission_liquidation_id.id == self.id:
                line.cashbox_operation_id.write({
                    'commission_liquidated': False,
                    'commission_liquidation_id': False,
                })
        
        self.write({
            'state': 'cancelled',
        })
        
        return True
    
    def action_revert(self):
        """Abre el wizard de reversión"""
        self.ensure_one()
        
        if self.state != 'paid':
            raise UserError(_('Solo se pueden revertir liquidaciones pagadas.'))
        
        if self.reversed_by_id:
            raise UserError(_('Esta liquidación ya fue revertida.'))
        
        return {
            'name': _('Revertir Liquidación'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.reversal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_liquidation_id': self.id,
            }
        }
    
    def action_view_source_operations(self):
        """Abre una vista con las operaciones origen de la liquidación"""
        self.ensure_one()
        
        # Recolectar IDs según el tipo de liquidación
        if self.liquidation_type == 'cheques':
            check_ids = self.line_ids.filtered('check_id').mapped('check_id').ids
            
            if check_ids:
                return {
                    'name': _('Cheques Liquidados'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'chequera.check',
                    'view_mode': 'tree,form',
                    'domain': [('id', 'in', check_ids)],
                    'context': {'create': False},
                }
        
        elif self.liquidation_type == 'divisas':
            operation_ids = self.line_ids.filtered('currency_operation_id').mapped('currency_operation_id').ids
            
            if operation_ids:
                return {
                    'name': _('Operaciones de Divisas Liquidadas'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'divisas.currency',
                    'view_mode': 'tree,form',
                    'domain': [('id', 'in', operation_ids)],
                    'context': {'create': False},
                }
        
        elif self.liquidation_type == 'caja':
            operation_ids = self.line_ids.filtered('cashbox_operation_id').mapped('cashbox_operation_id').ids
            
            if operation_ids:
                return {
                    'name': _('Operaciones de Caja Liquidadas'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'sucursales_cajas.operation',
                    'view_mode': 'tree,form',
                    'domain': [('id', 'in', operation_ids)],
                    'context': {'create': False},
                }
        
        # Si no hay operaciones específicas, mostrar las líneas
        return {
            'name': _('Líneas de Liquidación'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.liquidation.line',
            'view_mode': 'tree,form',
            'domain': [('liquidation_id', '=', self.id)],
            'context': {'create': False},
        }
    
    def unlink(self):
        """Validaciones antes de eliminar"""
        for liquidation in self:
            if liquidation.state not in ('draft', 'cancelled'):
                raise UserError(_('Solo se pueden eliminar liquidaciones en borrador o canceladas.'))
        
        return super(CommissionLiquidation, self).unlink()
    
    @api.onchange('liquidation_type')
    def _onchange_liquidation_type(self):
        """Ajusta valores según el tipo de liquidación"""
        if self.liquidation_type == 'divisas':
            # Sugerir el mes actual
            today = date.today()
            self.period_start = today.replace(day=1)
            
            # Último día del mes
            if today.month == 12:
                self.period_end = today.replace(day=31)
            else:
                from datetime import timedelta
                next_month = today.replace(month=today.month + 1, day=1)
                self.period_end = next_month - timedelta(days=1)
    
    def action_print_report(self):
        """Imprime el reporte de liquidación"""
        self.ensure_one()
        # TODO: Implementar reporte PDF
        return self.env.ref('commission_management.action_report_commission_liquidation').report_action(self)
    
    def action_add_cost(self):
        """Abre el wizard para agregar un costo/gasto"""
        self.ensure_one()
        
        return {
            'name': _('Registrar Costo/Gasto'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.cost.cashbox.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_liquidation_id': self.id,
                'default_date': fields.Date.today(),
            }
        }