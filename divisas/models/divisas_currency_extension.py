# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class DivisasCurrencyExtension(models.Model):
    """Extiende divisas.currency para soportar posiciones abiertas"""
    _inherit = 'divisas.currency'
    
    # Nuevos campos
    open_position_ids = fields.One2many('divisas.open.position',
                                       'sale_operation_id',
                                       string='Posiciones Abiertas')
    
    position_coverage_ids = fields.One2many('divisas.position.coverage',
                                           'purchase_operation_id',
                                           string='Coberturas de Posición')
    
    has_open_positions = fields.Boolean(string='Tiene Posiciones Abiertas',
                                       compute='_compute_has_open_positions',
                                       store=True)
    
    # NUEVO: Campo para rastrear cantidad usada en coberturas
    coverage_quantity_used = fields.Float(string='Cantidad Usada en Coberturas',
                                         default=0.0,
                                         help='Cantidad de esta compra usada para cubrir posiciones abiertas')
    
    @api.depends('open_position_ids', 'open_position_ids.state')
    def _compute_has_open_positions(self):
        for record in self:
            record.has_open_positions = any(
                pos.state in ['open', 'partial'] 
                for pos in record.open_position_ids
            )
    
    def _process_fifo_purchase(self):
        """Override para considerar coberturas antes de crear lote"""
        self.ensure_one()
        
        # Solo crear lote si la divisa comprada es USD o USDT
        if self.currency_type not in ['USD', 'USDT']:
            return super()._process_fifo_purchase()
        
        # PRIMERO: Cubrir posiciones abiertas
        quantity_used_for_coverage = self._cover_open_positions()
        
        # SEGUNDO: Crear lote solo con la cantidad restante
        remaining_quantity = self.amount - quantity_used_for_coverage
        
        if remaining_quantity > 0:
            # Determinar el tipo de cambio de adquisición
            if self.is_conversion:
                # Para conversiones USD/USDT, guardar el TC directo
                acquisition_rate = self.exchange_rate
                reference_currency = 'USD' if self.payment_currency_type == 'USD' else 'USDT'
            else:
                # Para operaciones con ARS, guardar el TC en ARS
                if self.payment_currency_type == 'ARS':
                    acquisition_rate = self.exchange_rate
                    reference_currency = 'ARS'
                else:
                    # Conversión a ARS para otros casos
                    if self.payment_currency_type == 'USD':
                        usd_to_ars = self.env['divisas.exchange.rate'].get_current_rate('USD', 'ARS', 'buy')
                        acquisition_rate = self.exchange_rate * usd_to_ars
                    elif self.payment_currency_type == 'USDT':
                        usdt_to_ars = self.env['divisas.exchange.rate'].get_current_rate('USDT', 'ARS', 'buy')
                        acquisition_rate = self.exchange_rate * usdt_to_ars
                    else:
                        acquisition_rate = self.exchange_rate
                    reference_currency = 'ARS'
            
            # Crear el lote de inventario SOLO con la cantidad restante
            lot_vals = {
                'purchase_operation_id': self.id,
                'currency_type': self.currency_type,
                'quantity_purchased': remaining_quantity,  # Solo el excedente
                'quantity_available': remaining_quantity,  # Solo el excedente
                'acquisition_rate': acquisition_rate,
                'reference_currency': reference_currency,
                'date': self.date,
                'state': 'available'
            }
            
            inventory_lot = self.env['divisas.inventory.lot'].create(lot_vals)
            self.inventory_lot_id = inventory_lot.id
            
            # Registrar mensaje sobre el lote creado
            self.message_post(
                body=_('📦 Lote de inventario creado: %.2f %s a TC %.2f %s') % 
                     (remaining_quantity, self.currency_type, acquisition_rate, reference_currency),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        # Guardar cantidad usada en coberturas
        self.coverage_quantity_used = quantity_used_for_coverage
        self.is_fifo_processed = True
    
    def _process_fifo_sale(self):
        """Override para permitir ventas sin inventario"""
        self.ensure_one()
        
        if self.currency_type not in ['USD', 'USDT']:
            return super()._process_fifo_sale()
        
        # Buscar lotes disponibles
        available_lots = self.env['divisas.inventory.lot'].search([
            ('currency_type', '=', self.currency_type),
            ('state', '=', 'available'),
            ('quantity_available', '>', 0)
        ], order='date asc, id asc')
        
        remaining_quantity = self.amount
        total_available = sum(available_lots.mapped('quantity_available'))
        
        # Consumir inventario existente primero
        total_profit_ars = 0.0
        total_profit_usd = 0.0
        
        for lot in available_lots:
            if remaining_quantity <= 0:
                break
            
            consumed_quantity = min(remaining_quantity, lot.quantity_available)
            
            # Calcular ganancias (código existente)
            if self.is_conversion:
                sale_rate = self.exchange_rate
                calculate_usd_profit = True
            else:
                calculate_usd_profit = False
                if self.payment_currency_type == 'ARS':
                    sale_rate = self.exchange_rate
                else:
                    # Convertir a ARS
                    if self.payment_currency_type == 'USD':
                        usd_to_ars = self.env['divisas.exchange.rate'].get_current_rate('USD', 'ARS', 'sell')
                        sale_rate = self.exchange_rate * usd_to_ars
                    elif self.payment_currency_type == 'USDT':
                        usdt_to_ars = self.env['divisas.exchange.rate'].get_current_rate('USDT', 'ARS', 'sell')
                        sale_rate = self.exchange_rate * usdt_to_ars
                    else:
                        sale_rate = self.exchange_rate
            
            # Calcular profit según tipo
            if calculate_usd_profit and lot.reference_currency in ['USD', 'USDT']:
                if self.currency_type == 'USD':
                    profit_usd = (sale_rate - lot.acquisition_rate) * consumed_quantity
                else:
                    profit_usd = ((1.0 / lot.acquisition_rate) - (1.0 / sale_rate)) * consumed_quantity
                profit_ars = 0
                profit_currency = 'USD'
            else:
                profit_ars = (sale_rate - lot.acquisition_rate) * consumed_quantity
                profit_usd = 0
                profit_currency = 'ARS'
            
            total_profit_ars += profit_ars
            total_profit_usd += profit_usd
            
            # Actualizar lote
            lot.quantity_available -= consumed_quantity
            if lot.quantity_available == 0:
                lot.state = 'exhausted'
            
            # Crear consumo
            self.env['divisas.lot.consumption'].create({
                'lot_id': lot.id,
                'sale_operation_id': self.id,
                'quantity_consumed': consumed_quantity,
                'consumption_rate': sale_rate,
                'profit_ars': profit_ars,
                'profit_usd': profit_usd,
                'profit_currency': profit_currency,
                'state': 'active'
            })
            
            remaining_quantity -= consumed_quantity
        
        # Si queda cantidad sin cubrir, crear posición abierta
        if remaining_quantity > 0:
            position = self._create_open_position(remaining_quantity)
            
            # Registrar mensaje en el chatter del documento
            self.message_post(
                body=_('⚠️ Se creó una posición abierta #%s por %.2f %s que será cubierta con futuras compras.') % 
                     (position.name, remaining_quantity, self.currency_type),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        # Registrar ganancias
        if self.is_conversion:
            self.profit_usd = total_profit_usd
            self.profit_ars = total_profit_ars
        else:
            self.profit_ars = total_profit_ars
            self.profit_usd = 0.0
        
        self.is_fifo_processed = True
    
    def _create_open_position(self, quantity):
        """Crea una posición abierta"""
        self.ensure_one()
        
        position_vals = {
            'sale_operation_id': self.id,
            'currency_type': self.currency_type,
            'quantity_open': quantity,
            'sale_rate': self.exchange_rate,
            'payment_currency': self.payment_currency_type,
            'state': 'open'
        }
        
        return self.env['divisas.open.position'].create(position_vals)
    
    def _cover_open_positions(self):
        """Cubre posiciones abiertas con una compra y retorna cantidad usada"""
        self.ensure_one()
        
        # Buscar posiciones abiertas FIFO
        open_positions = self.env['divisas.open.position'].search([
            ('currency_type', '=', self.currency_type),
            ('state', 'in', ['open', 'partial'])
        ], order='create_date asc')
        
        if not open_positions:
            return 0.0  # No se usó nada para coberturas
        
        remaining_quantity = self.amount
        total_quantity_covered = 0.0
        covered_positions = []
        
        for position in open_positions:
            if remaining_quantity <= 0:
                break
            
            quantity_to_cover = min(
                remaining_quantity,
                position.quantity_pending
            )
            
            # Calcular ganancia/pérdida
            if self.is_conversion:
                # Conversión USD/USDT
                profit_usd = (position.sale_rate - self.exchange_rate) * quantity_to_cover
                profit_ars = 0
                profit_currency = 'USD'
            else:
                # Operación con ARS
                profit_ars = (position.sale_rate - self.exchange_rate) * quantity_to_cover
                profit_usd = 0
                profit_currency = 'ARS'
            
            # Crear registro de cobertura
            self.env['divisas.position.coverage'].create({
                'position_id': position.id,
                'purchase_operation_id': self.id,
                'quantity_covered': quantity_to_cover,
                'purchase_rate': self.exchange_rate,
                'profit_ars': profit_ars,
                'profit_usd': profit_usd,
                'profit_currency': profit_currency
            })
            
            # Actualizar posición
            position.quantity_covered += quantity_to_cover
            
            if position.quantity_covered >= position.quantity_open:
                position.state = 'closed'
                position.date_closed = fields.Date.today()
            else:
                position.state = 'partial'
            
            remaining_quantity -= quantity_to_cover
            total_quantity_covered += quantity_to_cover
            
            covered_positions.append({
                'name': position.name,
                'quantity': quantity_to_cover,
                'profit_ars': profit_ars,
                'profit_usd': profit_usd
            })
        
        # Si se cubrieron posiciones, registrar en el chatter
        if covered_positions:
            message_lines = []
            total_profit_ars = sum(p['profit_ars'] for p in covered_positions)
            total_profit_usd = sum(p['profit_usd'] for p in covered_positions)
            
            for pos in covered_positions:
                profit_text = ''
                if pos['profit_ars'] != 0:
                    profit_text = f" (Ganancia: ARS {pos['profit_ars']:,.2f})"
                elif pos['profit_usd'] != 0:
                    profit_text = f" (Ganancia: USD {pos['profit_usd']:,.2f})"
                
                message_lines.append(
                    f"✅ {pos['name']}: {pos['quantity']:.2f} {self.currency_type}{profit_text}"
                )
            
            # Agregar totales si hay múltiples posiciones
            if len(covered_positions) > 1:
                message_lines.append('─' * 30)
                message_lines.append(f"<b>Total cubierto: {total_quantity_covered:.2f} {self.currency_type}</b>")
                if total_profit_ars != 0:
                    message_lines.append(f"<b>Ganancia total ARS: {total_profit_ars:,.2f}</b>")
                if total_profit_usd != 0:
                    message_lines.append(f"<b>Ganancia total USD: {total_profit_usd:,.2f}</b>")
            
            self.message_post(
                body=_('Posiciones cubiertas:<br/>%s') % '<br/>'.join(message_lines),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        return total_quantity_covered  # Retornar cantidad total usada en coberturas