# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ChequeraCheckInherit(models.Model):
    _inherit = 'chequera.check'
    
    # Campos para comisiones
    commission_liquidated = fields.Boolean(
        string='Comisión Liquidada',
        readonly=True,
        default=False,
        tracking=True,
        help='Indica si la comisión por este cheque ya fue liquidada'
    )
    
    commission_liquidation_id = fields.Many2one(
        'commission.liquidation',
        string='Liquidación de Comisión',
        readonly=True,
        help='Liquidación donde se procesó la comisión de este cheque'
    )
    
    # Campo calculado para mostrar si es liquidable
    is_commission_liquidable = fields.Boolean(
        string='Liquidable para Comisión',
        compute='_compute_is_commission_liquidable',
        store=True,
        help='Indica si el cheque puede ser incluido en una liquidación de comisiones'
    )
    
    # Campo computado para la ganancia
    ganancia_calculada = fields.Float(
        string='Ganancia',
        compute='_compute_ganancia',
        store=True,
        help='Ganancia calculada (Precio Venta - Precio Compra)'
    )
    
    @api.depends('precio_compra', 'precio_venta')
    def _compute_ganancia(self):
        """Calcula la ganancia del cheque"""
        for check in self:
            check.ganancia_calculada = check.precio_venta - check.precio_compra
    
    @api.depends('state', 'precio_compra', 'precio_venta', 'commission_liquidated')
    def _compute_is_commission_liquidable(self):
        """Determina si el cheque es liquidable para comisiones"""
        for check in self:
            # Es liquidable si:
            # - Está vendido
            # - Tiene precio de compra y venta
            # - No ha sido liquidado aún
            check.is_commission_liquidable = (
                check.state == 'vendido' and
                check.precio_compra > 0 and
                check.precio_venta > 0 and
                not check.commission_liquidated
            )
    
    def write(self, vals):
        """Override para validar cambios en cheques con comisión liquidada"""
        if self.filtered('commission_liquidated'):
            # Campos que no se pueden modificar si hay comisión liquidada
            protected_fields = [
                'precio_compra', 'precio_venta', 
                'vendedor_id_compra', 'vendedor_id_venta',
                'proveedor_id', 'cliente_id'
            ]
            
            for field in protected_fields:
                if field in vals:
                    raise ValidationError(
                        _('No se puede modificar el campo "%s" porque el cheque tiene comisión liquidada.') 
                        % self._fields[field].string
                    )
        
        return super().write(vals)