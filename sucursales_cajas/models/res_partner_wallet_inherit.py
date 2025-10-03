from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    @api.depends('wallet_cheques_ids', 'wallet_cheques_ids.monto', 
                'wallet_cheques_ids.tipo', 'wallet_cheques_ids.active',
                'wallet_cheques_ids.state')
    def _compute_wallet_balance(self):
        """Extender el cálculo para incluir operaciones de caja"""
        super()._compute_wallet_balance()
        
        for partner in self:
            # Agregar/restar operaciones de caja
            cashbox_movements = partner.wallet_cheques_ids.filtered(
                lambda m: m.active and m.state == 'confirmado' and m.tipo == 'cashbox_operation'
            )
            
            for movement in cashbox_movements:
                # Los movimientos positivos suman, los negativos restan
                partner.wallet_balance += movement.monto