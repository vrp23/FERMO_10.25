from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ELIMINAR campos duplicados - ahora están en custom_contact_types
    # Solo mantener campos específicos de chequera
    
    # Relación con los movimientos de wallet
    wallet_cheques_ids = fields.One2many(
        'chequera.wallet.movement', 'partner_id', string='Movimientos de Wallet'
    )
    
    # Campo computado para el saldo de la wallet
    wallet_balance = fields.Float(
        string='Saldo de Wallet (ARS)', 
        compute='_compute_wallet_balance',
        help='Saldo actual calculado a partir de los movimientos de la Wallet'
    )
    
    # Campos computados para contar cheques
    check_comprados_count = fields.Integer(
        string='Cheques Comprados',
        compute='_compute_check_counts'
    )
    
    check_vendidos_count = fields.Integer(
        string='Cheques Vendidos',
        compute='_compute_check_counts'
    )
    
    @api.depends('wallet_cheques_ids', 'wallet_cheques_ids.monto', 
                'wallet_cheques_ids.tipo', 'wallet_cheques_ids.active',
                'wallet_cheques_ids.state')
    def _compute_wallet_balance(self):
        """Calcular el saldo de la wallet basado en los movimientos activos confirmados"""
        for partner in self:
            balance = 0.0
            wallet_movements = partner.wallet_cheques_ids.filtered(
                lambda m: m.active and m.state == 'confirmado'
            )
            
            for movement in wallet_movements:
                if movement.tipo == 'compra':
                    balance += movement.monto
                elif movement.tipo == 'venta':
                    balance -= movement.monto
                elif movement.tipo == 'anulacion':
                    balance += movement.monto
                    
            partner.wallet_balance = balance
    
    @api.depends('name')
    def _compute_check_counts(self):
        """Calcular la cantidad de cheques comprados y vendidos"""
        for partner in self:
            partner.check_comprados_count = self.env['chequera.check'].search_count([
                ('proveedor_id', '=', partner.id)
            ])
            partner.check_vendidos_count = self.env['chequera.check'].search_count([
                ('cliente_id', '=', partner.id)
            ])
    
    def action_view_checks_comprados(self):
        """Ver cheques comprados de este partner"""
        self.ensure_one()
        return {
            'name': _('Cheques Comprados'),
            'view_mode': 'tree,form',
            'res_model': 'chequera.check',
            'type': 'ir.actions.act_window',
            'domain': [('proveedor_id', '=', self.id)],
            'context': {'default_proveedor_id': self.id}
        }
    
    def action_view_checks_vendidos(self):
        """Ver cheques vendidos a este partner"""
        self.ensure_one()
        return {
            'name': _('Cheques Vendidos'),
            'view_mode': 'tree,form',
            'res_model': 'chequera.check',
            'type': 'ir.actions.act_window',
            'domain': [('cliente_id', '=', self.id)],
            'context': {'default_cliente_id': self.id}
        }