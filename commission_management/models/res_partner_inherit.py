from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Campos para comisiones de socios
    is_commission_partner = fields.Boolean(
        string='Es Socio Comisionista',
        compute='_compute_is_commission_partner',
        store=True
    )
    
    commission_percentage = fields.Float(
        string='Porcentaje de Comisión',
        help='Porcentaje de participación en las ganancias como socio'
    )
    
    # Contadores de liquidaciones
    operator_commission_count = fields.Integer(
        string='Liquidaciones como Operador',
        compute='_compute_commission_counts'
    )
    
    partner_commission_count = fields.Integer(
        string='Liquidaciones como Socio',
        compute='_compute_commission_counts'
    )
    
    @api.depends('partner_type_ids', 'partner_type_ids.is_commission_partner')  # MODIFICADO
    def _compute_is_commission_partner(self):
        """Determina si es un socio comisionista basado en el tipo"""
        for partner in self:
            # MODIFICADO: Verificar si alguno de los tipos tiene is_commission_partner = True
            partner.is_commission_partner = any(
                partner.partner_type_ids.mapped('is_commission_partner')
            )
    
    def _compute_commission_counts(self):
        """Cuenta las liquidaciones del partner"""
        for partner in self:
            # Liquidaciones como operador (si tiene usuario asociado)
            operator_count = 0
            if partner.user_id:
                operator_count = self.env['commission.liquidation'].search_count([
                    ('operator_id', '=', partner.user_id.id)
                ])
            partner.operator_commission_count = operator_count
            
            # Liquidaciones como socio
            partner_lines = self.env['commission.partner.liquidation.line'].search([
                ('partner_id', '=', partner.id)
            ])
            partner.partner_commission_count = len(partner_lines.mapped('liquidation_id'))
    
    def action_view_operator_liquidations(self):
        """Ver liquidaciones como operador"""
        self.ensure_one()
        
        if not self.user_id:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'name': 'Liquidaciones como Operador',
            'type': 'ir.actions.act_window',
            'res_model': 'commission.liquidation',
            'view_mode': 'tree,form',
            'domain': [('operator_id', '=', self.user_id.id)],
            'context': {'default_operator_id': self.user_id.id}
        }
    
    def action_view_partner_liquidations(self):
        """Ver liquidaciones como socio"""
        self.ensure_one()
        
        # Buscar líneas de liquidación de socio
        partner_lines = self.env['commission.partner.liquidation.line'].search([
            ('partner_id', '=', self.id)
        ])
        
        liquidation_ids = partner_lines.mapped('liquidation_id').ids
        
        return {
            'name': 'Liquidaciones como Socio',
            'type': 'ir.actions.act_window',
            'res_model': 'commission.partner.liquidation',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', liquidation_ids)],
        }


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    # Campo computado para obtener el partner del usuario
    partner_id_commission = fields.Many2one(
        'res.partner',
        string='Contacto Asociado',
        compute='_compute_operator_partner',
        store=True,
        help='Partner asociado a este usuario para comisiones'
    )
    
    @api.depends('partner_id')
    def _compute_operator_partner(self):
        """Obtiene el partner asociado al usuario"""
        for user in self:
            # El usuario ya tiene un partner_id nativo en Odoo
            user.partner_id_commission = user.partner_id