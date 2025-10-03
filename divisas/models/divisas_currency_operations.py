# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class DivisasCurrencyOperations(models.Model):
    _inherit = 'divisas.currency'
    
    # Métodos de operaciones
    def action_confirm(self):
        """Confirma la operación y crea el movimiento en la wallet"""
        self.ensure_one()
        
        if not self.currency_type or not self.payment_currency_type:
            raise UserError(_('Debe seleccionar ambas monedas para la operación'))
        
        if self.currency_type == self.payment_currency_type:
            raise UserError(_('La moneda de operación y de pago no pueden ser iguales'))
        
        if self.amount <= 0:
            raise UserError(_('El monto debe ser mayor a cero'))
        
        if not self.exchange_rate or self.exchange_rate <= 0:
            raise UserError(_('El tipo de cambio debe ser mayor a cero'))
        
        # Crear el movimiento en la wallet
        wallet_movement = self.env['divisas.wallet.movement'].create({
            'partner_id': self.partner_id.id,
            'currency_operation_id': self.id,
            'operation_type': self.operation_type,
            'currency_type': self.currency_type,
            'payment_currency_type': self.payment_currency_type,
            'amount': self.amount,
            'payment_amount': self.payment_amount,
            'date': self.date,
            'notes': self.notes,
        })
        
        self.wallet_movement_id = wallet_movement.id
        
        # NUEVO: Procesar FIFO según el tipo de operación
        if self.operation_type == 'buy':
            self._process_fifo_purchase()
        elif self.operation_type == 'sell':
            self._process_fifo_sale()
        
        self.state = 'confirmed'
        return True
    
    def _process_fifo_purchase(self):
        """Procesa una compra creando un lote de inventario FIFO"""
        self.ensure_one()
        
        # Solo crear lote si la divisa comprada es USD o USDT
        if self.currency_type not in ['USD', 'USDT']:
            return
        
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
        
        # Crear el lote de inventario
        lot_vals = {
            'purchase_operation_id': self.id,
            'currency_type': self.currency_type,
            'quantity_purchased': self.amount,
            'quantity_available': self.amount,
            'acquisition_rate': acquisition_rate,
            'reference_currency': reference_currency,
            'date': self.date,
            'state': 'available'
        }
        
        inventory_lot = self.env['divisas.inventory.lot'].create(lot_vals)
        self.inventory_lot_id = inventory_lot.id
        self.is_fifo_processed = True
    
    def _process_fifo_sale(self):
        """Procesa una venta consumiendo lotes FIFO y calculando ganancias"""
        self.ensure_one()
        
        # Solo procesar FIFO si la divisa vendida es USD o USDT
        if self.currency_type not in ['USD', 'USDT']:
            return
        
        # Buscar lotes disponibles FIFO (ordenados por fecha ascendente)
        available_lots = self.env['divisas.inventory.lot'].search([
            ('currency_type', '=', self.currency_type),
            ('state', '=', 'available'),
            ('quantity_available', '>', 0)
        ], order='date asc, id asc')
        
        if not available_lots:
            raise UserError(_('No hay suficiente inventario de %s para realizar esta venta') % self.currency_type)
        
        # Cantidad que necesitamos consumir
        remaining_quantity = self.amount
        total_profit_ars = 0.0
        total_profit_usd = 0.0
        
        # Determinar si es una conversión USD/USDT
        if self.is_conversion:
            # Para conversiones, el TC de venta es directo
            sale_rate = self.exchange_rate
            calculate_usd_profit = True
        else:
            # Para operaciones con ARS
            calculate_usd_profit = False
            if self.payment_currency_type == 'ARS':
                sale_rate = self.exchange_rate
            else:
                # Convertir a ARS si es necesario
                if self.payment_currency_type == 'USD':
                    usd_to_ars = self.env['divisas.exchange.rate'].get_current_rate('USD', 'ARS', 'sell')
                    sale_rate = self.exchange_rate * usd_to_ars
                elif self.payment_currency_type == 'USDT':
                    usdt_to_ars = self.env['divisas.exchange.rate'].get_current_rate('USDT', 'ARS', 'sell')
                    sale_rate = self.exchange_rate * usdt_to_ars
                else:
                    sale_rate = self.exchange_rate
        
        # Consumir lotes FIFO
        for lot in available_lots:
            if remaining_quantity <= 0:
                break
            
            # Determinar cantidad a consumir de este lote
            consumed_quantity = min(remaining_quantity, lot.quantity_available)
            
            # Calcular ganancia según el tipo de operación
            if calculate_usd_profit:
                # Para conversiones USD/USDT
                if lot.reference_currency in ['USD', 'USDT']:
                    # Lote de una conversión previa
                    if self.currency_type == 'USD':
                        # Vendiendo USD
                        profit_usd = (sale_rate - lot.acquisition_rate) * consumed_quantity
                    else:
                        # Vendiendo USDT, la ganancia está en función del USD
                        profit_usd = ((1.0 / lot.acquisition_rate) - (1.0 / sale_rate)) * consumed_quantity
                else:
                    # Lote comprado con ARS, ahora vendido en conversión USD/USDT
                    # No calculamos ganancia USD en este caso, solo ARS
                    ars_acquisition_rate = lot.acquisition_rate
                    # Obtener TC actual para calcular valor en ARS de la venta
                    if self.currency_type == 'USD':
                        current_ars_rate = self.env['divisas.exchange.rate'].get_current_rate('USD', 'ARS', 'sell')
                    else:
                        current_ars_rate = self.env['divisas.exchange.rate'].get_current_rate('USDT', 'ARS', 'sell')
                    
                    profit_ars = (current_ars_rate - ars_acquisition_rate) * consumed_quantity
                    total_profit_ars += profit_ars
                    profit_usd = 0
                
                total_profit_usd += profit_usd
                profit_currency = 'USD' if profit_usd != 0 else 'ARS'
                
            else:
                # Para operaciones con ARS
                if lot.reference_currency == 'ARS':
                    profit_ars = (sale_rate - lot.acquisition_rate) * consumed_quantity
                else:
                    # Lote de conversión USD/USDT vendido por ARS
                    # Necesitamos convertir el TC de adquisición a ARS
                    if lot.currency_type == 'USD':
                        acquisition_ars = self.env['divisas.exchange.rate'].get_current_rate('USD', 'ARS', 'buy')
                    else:
                        acquisition_ars = self.env['divisas.exchange.rate'].get_current_rate('USDT', 'ARS', 'buy')
                    
                    profit_ars = (sale_rate - acquisition_ars) * consumed_quantity
                
                total_profit_ars += profit_ars
                profit_usd = 0
                profit_currency = 'ARS'
            
            # Actualizar cantidad disponible del lote
            lot.quantity_available -= consumed_quantity
            
            # Si se agotó el lote, cambiar estado
            if lot.quantity_available == 0:
                lot.state = 'exhausted'
            
            # Crear registro de consumo con ganancias
            consumption_vals = {
                'lot_id': lot.id,
                'sale_operation_id': self.id,
                'quantity_consumed': consumed_quantity,
                'acquisition_rate': lot.acquisition_rate,
                'consumption_rate': sale_rate,
                'profit_ars': profit_ars if not calculate_usd_profit else 0,
                'profit_usd': profit_usd if calculate_usd_profit else 0,
                'profit_currency': profit_currency,
                'state': 'active'
            }
            
            self.env['divisas.lot.consumption'].create(consumption_vals)
            
            remaining_quantity -= consumed_quantity
        
        # Verificar que se consumió toda la cantidad
        if remaining_quantity > 0:
            raise UserError(_('No hay suficiente inventario de %s para realizar esta venta. Faltan %.2f unidades') % 
                          (self.currency_type, remaining_quantity))
        
        # Registrar las ganancias totales
        if self.is_conversion:
            self.profit_usd = total_profit_usd
            self.profit_ars = total_profit_ars  # Puede tener valor si hubo lotes mixtos
        else:
            self.profit_ars = total_profit_ars
            self.profit_usd = 0.0
        
        self.is_fifo_processed = True
    
    def action_cancel(self):
        """Cancela la operación y revierte el movimiento en la wallet"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise UserError(_('Solo se pueden cancelar operaciones confirmadas'))
        
        # VALIDACIÓN ESPECIAL PARA COMPRAS
        if self.operation_type == 'buy' and self.inventory_lot_id:
            # Verificar si el lote tiene consumos activos
            active_consumptions = self.inventory_lot_id.consumption_ids.filtered(
                lambda c: c.state == 'active'
            )
            if active_consumptions:
                # Obtener información de las ventas asociadas
                sale_names = ', '.join(active_consumptions.mapped('sale_operation_id.name'))
                raise UserError(_(
                    'No se puede cancelar esta compra porque ya fue vendida parcial o totalmente.\n'
                    'Primero debe cancelar las ventas asociadas: %s.\n'
                    'Si no es posible cancelar las ventas asociadas, inicie una operación de venta compensatoria para revertir la compra.'
                ) % sale_names)
        
        # REVERTIR FIFO ANTES DE CANCELAR
        if self.is_fifo_processed:
            if self.operation_type == 'buy' and self.inventory_lot_id:
                # Cancelar el lote de inventario (ya validamos que no tiene consumos)
                self.inventory_lot_id.action_cancel()
            elif self.operation_type == 'sell':
                # Revertir todos los consumos de lotes
                for consumption in self.lot_consumption_ids:
                    consumption.action_revert()
                # Limpiar las ganancias
                self.profit_ars = 0.0
                self.profit_usd = 0.0
        
        if self.wallet_movement_id:
            self.wallet_movement_id.action_cancel()
            
        self.state = 'cancelled'
        return True