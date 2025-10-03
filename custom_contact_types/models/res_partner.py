from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Campo para asignar múltiples tipos de contacto (MODIFICADO: Many2one -> Many2many)
    partner_type_ids = fields.Many2many(
        'res.partner.type',
        'res_partner_partner_type_rel',
        'partner_id',
        'type_id',
        string='Tipos de Contacto'
    )
    
    # Campos legacy - mantener para compatibilidad
    pesification_rate = fields.Float(string='Tasa de Pesificación (%)', default=0.0)
    monthly_interest = fields.Float(string='Interés mensual (%)', default=0.0)
    
    # NUEVOS CAMPOS - Tasas diferenciadas para compra
    tasa_pesificacion_compra = fields.Float(string='Tasa de Pesificación Compra (%)', default=0.0)
    interes_mensual_compra = fields.Float(string='Interés mensual Compra (%)', default=0.0)
    
    # NUEVOS CAMPOS - Tasas diferenciadas para venta
    tasa_pesificacion_venta = fields.Float(string='Tasa de Pesificación Venta (%)', default=0.0)
    interes_mensual_venta = fields.Float(string='Interés mensual Venta (%)', default=0.0)
    
    # Campo operador (antes vendedor)
    assigned_seller_id = fields.Many2one('res.users', string='Operador asignado')
    
    # Campos de comisiones
    commission_checks = fields.Float(string='Comisiones - Cheques (%)', default=0.0)
    commission_dollars = fields.Float(string='Comisiones - Dólares (%)', default=0.0)
    commission_crypto = fields.Float(string='Comisiones - Criptos (%)', default=0.0)
    commission_transfers = fields.Float(string='Comisiones - Transferencias (%)', default=0.0)
    commission_cables = fields.Float(string='Comisiones - Cables (%)', default=0.0)
    
    @api.onchange('assigned_seller_id')
    def _onchange_assigned_seller_id(self):
        """Sincroniza el vendedor asignado con el comercial nativo de Odoo"""
        if self.assigned_seller_id:
            self.user_id = self.assigned_seller_id
    
    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Sincroniza el comercial nativo de Odoo con el vendedor asignado"""
        if self.user_id:
            self.assigned_seller_id = self.user_id
    
    @api.model
    def create(self, vals):
        """Al crear, si hay valores legacy, copiarlos a los nuevos campos"""
        if 'pesification_rate' in vals and vals.get('pesification_rate'):
            if 'tasa_pesificacion_compra' not in vals:
                vals['tasa_pesificacion_compra'] = vals['pesification_rate']
            if 'tasa_pesificacion_venta' not in vals:
                vals['tasa_pesificacion_venta'] = vals['pesification_rate']
                
        if 'monthly_interest' in vals and vals.get('monthly_interest'):
            if 'interes_mensual_compra' not in vals:
                vals['interes_mensual_compra'] = vals['monthly_interest']
            if 'interes_mensual_venta' not in vals:
                vals['interes_mensual_venta'] = vals['monthly_interest']
        
        return super(ResPartner, self).create(vals)
    
    def write(self, vals):
        """Al actualizar campos legacy, actualizar también los nuevos si están vacíos"""
        if 'pesification_rate' in vals:
            for partner in self:
                if not partner.tasa_pesificacion_compra:
                    vals['tasa_pesificacion_compra'] = vals['pesification_rate']
                if not partner.tasa_pesificacion_venta:
                    vals['tasa_pesificacion_venta'] = vals['pesification_rate']
                    
        if 'monthly_interest' in vals:
            for partner in self:
                if not partner.interes_mensual_compra:
                    vals['interes_mensual_compra'] = vals['monthly_interest']
                if not partner.interes_mensual_venta:
                    vals['interes_mensual_venta'] = vals['monthly_interest']
        
        return super(ResPartner, self).write(vals)