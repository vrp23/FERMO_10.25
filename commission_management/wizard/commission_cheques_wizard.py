from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

class CommissionChequesWizard(models.TransientModel):
    _name = 'commission.cheques.wizard'
    _description = 'Wizard para liquidación de comisiones de cheques'
    
    # Campos básicos
    name = fields.Char(string='Referencia', default='Nueva Liquidación')
    operator_id = fields.Many2one('res.users', string='Operador', required=True)
    commission_rate = fields.Float(string='Tasa de Comisión (%)', default=30.0, required=True)
    
    # Período
    period_start = fields.Date(string='Fecha Desde', required=True, 
                              default=lambda self: date.today().replace(day=1))
    period_end = fields.Date(string='Fecha Hasta', required=True,
                            default=lambda self: date.today())
    
    # Filtros
    include_sold = fields.Boolean(string='Incluir Cheques Vendidos', default=True)
    include_rejected = fields.Boolean(string='Incluir Cheques Rechazados', default=True)
    
    # Líneas calculadas
    line_ids = fields.One2many('commission.cheques.wizard.line', 'wizard_id', string='Líneas')
    
    # Totales
    total_base = fields.Float(string='Base Total', compute='_compute_totals', store=True)
    total_commission = fields.Float(string='Comisión Total', compute='_compute_totals', store=True)
    check_count = fields.Integer(string='Cantidad de Cheques', compute='_compute_totals', store=True)
    
    @api.depends('line_ids.base_amount', 'line_ids.commission_amount')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_base = sum(wizard.line_ids.mapped('base_amount'))
            wizard.total_commission = sum(wizard.line_ids.mapped('commission_amount'))
            wizard.check_count = len(wizard.line_ids)
    
    @api.onchange('operator_id')
    def _onchange_operator_id(self):
        """Al cambiar el operador, actualizar la tasa de comisión si tiene configurada"""
        if self.operator_id:
            # Buscar el partner del operador
            partner = self.env['res.partner'].search([
                ('user_id', '=', self.operator_id.id)
            ], limit=1)
            
            if partner and partner.commission_checks:
                self.commission_rate = partner.commission_checks
    
    def action_calculate(self):
        """Calcula las comisiones basándose en los parámetros"""
        self.ensure_one()
        self._calculate_commissions()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'commission.cheques.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
    
    def _calculate_commissions(self):
        """Calcula las comisiones de cheques para el operador en el período"""
        self.ensure_one()
        
        # Limpiar líneas existentes
        self.line_ids.unlink()
        
        # Construir dominio base
        domain = [
            ('fecha_pago', '<=', self.period_end),  # El cheque debe haber pasado su fecha de pago
        ]
        
        # Filtro de estados
        states = []
        if self.include_sold:
            states.append('vendido')
        if self.include_rejected:
            states.append('rechazado')
        
        if states:
            domain.append(('state', 'in', states))
        else:
            raise UserError(_('Debe seleccionar al menos un estado de cheque para liquidar.'))
        
        # Buscar cheques que cumplan criterios
        checks = self.env['chequera.check'].search(domain)
        
        # Filtrar por operador
        checks_to_process = self.env['chequera.check']
        
        for check in checks:
            # Verificar si el operador está relacionado con el cheque
            include_check = False
            
            # Verificar vendedor de compra
            if check.vendedor_id_compra == self.operator_id:
                include_check = True
            
            # Verificar vendedor de venta
            if check.vendedor_id_venta == self.operator_id:
                include_check = True
            
            # Verificar operador asignado al cliente/proveedor
            if check.cliente_id and check.cliente_id.assigned_seller_id == self.operator_id:
                include_check = True
            
            if check.proveedor_id and check.proveedor_id.assigned_seller_id == self.operator_id:
                include_check = True
            
            # Verificar que no haya sido liquidado ya
            if check.commission_liquidated:
                include_check = False
            
            # Verificar que la fecha de pago esté dentro del período
            if check.fecha_pago > self.period_end or check.fecha_pago < self.period_start:
                include_check = False
            
            if include_check:
                checks_to_process += check
        
        # Crear líneas para cada cheque
        sequence = 10
        for check in checks_to_process:
            # Calcular la ganancia del cheque
            ganancia = 0.0
            if check.precio_venta and check.precio_compra:
                ganancia = check.precio_venta - check.precio_compra
            
            # Si no hay ganancia, saltar
            if ganancia <= 0:
                continue
            
            # Obtener la fecha de operación correcta - CORRECCIÓN AQUÍ
            operation_date = fields.Date.today()
            if check.operation_id:
                # La fecha está en el wizard de compra
                operation_date = check.operation_id.fecha_operacion or check.write_date.date()
            elif check.sale_operation_id:
                # La fecha está en el wizard de venta
                operation_date = check.sale_operation_id.fecha_operacion or check.write_date.date()
            else:
                # Si no hay operación, usar la fecha del cheque
                operation_date = check.fecha_pago or check.write_date.date()
            
            # Determinar el vendedor responsable
            vendedor = check.vendedor_id_venta or check.vendedor_id_compra or self.operator_id
            
            # Obtener tasa de comisión específica si existe
            commission_rate = self.commission_rate
            if check.cliente_id and hasattr(check.cliente_id, 'commission_checks'):
                if check.cliente_id.commission_checks > 0:
                    commission_rate = check.cliente_id.commission_checks
            
            # Crear línea
            self.env['commission.cheques.wizard.line'].create({
                'wizard_id': self.id,
                'sequence': sequence,
                'check_id': check.id,
                'check_number': check.numero_cheque,
                'bank_name': check.banco_id.name if check.banco_id else '',
                'operation_date': operation_date,
                'fecha_pago': check.fecha_pago,
                'partner_id': check.cliente_id.id if check.cliente_id else check.proveedor_id.id,
                'purchase_price': check.precio_compra,
                'sale_price': check.precio_venta,
                'base_amount': ganancia,
                'commission_rate': commission_rate,
                'commission_amount': ganancia * commission_rate / 100,
            })
            
            sequence += 10
        
        if not self.line_ids:
            raise UserError(_('No se encontraron cheques para liquidar con los criterios especificados.'))
        
        return True
    
    def action_create_liquidation(self):
        """Crea la liquidación de comisiones"""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_('No hay líneas para liquidar. Primero debe calcular las comisiones.'))
        
        # Crear la liquidación
        liquidation = self.env['commission.liquidation'].create({
            'operator_id': self.operator_id.id,
            'liquidation_type': 'cheques',
            'date': fields.Date.today(),
            'period_start': self.period_start,
            'period_end': self.period_end,
            'state': 'draft',
        })
        
        # Crear las líneas de liquidación
        for wizard_line in self.line_ids:
            self.env['commission.liquidation.line'].create({
                'liquidation_id': liquidation.id,
                'sequence': wizard_line.sequence,
                'description': f'Cheque {wizard_line.check_number} - {wizard_line.bank_name}',
                'source_model': 'chequera.check',
                'source_reference': wizard_line.check_id.name,
                'operation_date': wizard_line.operation_date,
                'partner_id': wizard_line.partner_id.id,
                'base_amount': wizard_line.base_amount,
                'commission_rate': wizard_line.commission_rate,
                'commission_amount': wizard_line.commission_amount,
                'check_id': wizard_line.check_id.id,
                'purchase_price': wizard_line.purchase_price,
                'sale_price': wizard_line.sale_price,
            })
            
            # Marcar el cheque como liquidado
            wizard_line.check_id.write({
                'commission_liquidated': True,
                'commission_liquidation_id': liquidation.id,
            })
        
        # Abrir la liquidación creada
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'commission.liquidation',
            'view_mode': 'form',
            'res_id': liquidation.id,
            'target': 'current',
        }


class CommissionChequesWizardLine(models.TransientModel):
    _name = 'commission.cheques.wizard.line'
    _description = 'Línea del Wizard de Comisiones de Cheques'
    _order = 'sequence, id'
    
    wizard_id = fields.Many2one('commission.cheques.wizard', string='Wizard', 
                                required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia', default=10)
    
    # Datos del cheque
    check_id = fields.Many2one('chequera.check', string='Cheque', required=True)
    check_number = fields.Char(string='Número Cheque', required=True)
    bank_name = fields.Char(string='Banco')
    
    # Fechas
    operation_date = fields.Date(string='Fecha Operación')
    fecha_pago = fields.Date(string='Fecha Pago')
    
    # Partner
    partner_id = fields.Many2one('res.partner', string='Cliente/Proveedor')
    
    # Valores
    purchase_price = fields.Float(string='Precio Compra')
    sale_price = fields.Float(string='Precio Venta')
    base_amount = fields.Float(string='Ganancia', required=True)
    
    # Comisión
    commission_rate = fields.Float(string='Tasa (%)', required=True)
    commission_amount = fields.Float(string='Comisión', required=True)
    
    @api.onchange('base_amount', 'commission_rate')
    def _onchange_calculate_commission(self):
        """Recalcula la comisión cuando cambian los valores"""
        if self.base_amount and self.commission_rate:
            self.commission_amount = self.base_amount * self.commission_rate / 100