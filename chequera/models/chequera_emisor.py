# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ChequeraEmisor(models.Model):
    _name = 'chequera.emisor'
    _description = 'Emisor de Cheques'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True
    )
    
    cuit = fields.Char(
        string='CUIT/CUIL',
        tracking=True
    )
    
    telefono = fields.Char(
        string='Teléfono',
        tracking=True
    )
    
    email = fields.Char(
        string='Email',
        tracking=True
    )
    
    direccion = fields.Text(
        string='Dirección',
        tracking=True
    )
    
    notas = fields.Text(
        string='Notas'
    )
    
    check_count = fields.Integer(
        string='Cantidad de cheques',
        compute='_compute_check_count'
    )
    
    check_ids = fields.One2many(
        'chequera.check',
        'emisor_id',
        string='Cheques emitidos'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    @api.depends('check_ids')
    def _compute_check_count(self):
        for record in self:
            record.check_count = len(record.check_ids)
    
    def action_view_checks(self):
        """Muestra los cheques del emisor"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cheques de %s' % self.name,
            'res_model': 'chequera.check',
            'view_mode': 'tree,form',
            'domain': [('emisor_id', '=', self.id)],
            'context': {
                'default_emisor_id': self.id,
            }
        }