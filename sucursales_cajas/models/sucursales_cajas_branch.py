# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SucursalesCajasBranch(models.Model):
    _name = 'sucursales_cajas.branch'
    _description = 'Sucursal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'
    
    # Campos básicos
    name = fields.Char(
        string='Nombre de la Sucursal', 
        required=True, 
        tracking=True,
        help="Nombre identificativo de la sucursal"
    )
    
    code = fields.Char(
        string='Código', 
        help="Código único de la sucursal",
        tracking=True
    )
    
    address = fields.Text(
        string='Domicilio', 
        required=True,
        tracking=True
    )
    
    phone = fields.Char(
        string='Teléfono', 
        tracking=True
    )
    
    email = fields.Char(
        string='Email',
        tracking=True
    )
    
    # Relación con compañía
    company_id = fields.Many2one(
        'res.company', 
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    
    # Usuarios permitidos
    allowed_user_ids = fields.Many2many(
        'res.users',
        'sucursales_cajas_branch_users_rel',
        'branch_id',
        'user_id',
        string='Usuarios Permitidos',
        help="Usuarios que pueden acceder a esta sucursal",
        tracking=True
    )
    
    # Relación con cajas
    cashbox_ids = fields.One2many(
        'sucursales_cajas.cashbox',
        'branch_id',
        string='Cajas',
        help="Cajas pertenecientes a esta sucursal"
    )
    
    # Campos computados
    cashbox_count = fields.Integer(
        string='Cantidad de Cajas',
        compute='_compute_cashbox_count',
        store=True
    )
    
    active_sessions_count = fields.Integer(
        string='Sesiones Activas',
        compute='_compute_active_sessions_count',
        store=True  # AGREGADO STORE=TRUE AQUÍ
    )
    
    # Estado
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )
    
    # Manager de la sucursal
    manager_id = fields.Many2one(
        'res.users',
        string='Gerente/Responsable',
        tracking=True,
        help="Usuario responsable de la sucursal"
    )
    
    # Notas
    notes = fields.Text(
        string='Notas',
        help="Notas adicionales sobre la sucursal"
    )
    
    # Constraints SQL
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code, company_id)', 
         'El código de sucursal debe ser único por empresa!'),
        ('name_unique', 'UNIQUE(name, company_id)', 
         'El nombre de sucursal debe ser único por empresa!'),
    ]
    
    @api.depends('cashbox_ids')
    def _compute_cashbox_count(self):
        """Calcula la cantidad de cajas de la sucursal"""
        for branch in self:
            branch.cashbox_count = len(branch.cashbox_ids)
    
    @api.depends('cashbox_ids', 'cashbox_ids.active_session_id', 'cashbox_ids.active_session_id.state')  # ACTUALIZADA CON DEPENDENCIAS
    def _compute_active_sessions_count(self):
        """Calcula la cantidad de sesiones activas en la sucursal"""
        for branch in self:
            active_sessions = branch.cashbox_ids.filtered(
                lambda c: c.active_session_id and c.active_session_id.state == 'open'
            )
            branch.active_sessions_count = len(active_sessions)
    
    @api.constrains('allowed_user_ids', 'manager_id')
    def _check_manager_in_allowed_users(self):
        """Verifica que el gerente esté en los usuarios permitidos"""
        for branch in self:
            if branch.manager_id and branch.manager_id not in branch.allowed_user_ids:
                raise ValidationError(
                    _('El gerente/responsable debe estar incluido en los usuarios permitidos de la sucursal.')
                )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para validaciones adicionales"""
        for vals in vals_list:
            # Auto-generar código si no se proporciona
            if not vals.get('code'):
                company_id = vals.get('company_id', self.env.company.id)
                sequence = self.search_count([('company_id', '=', company_id)]) + 1
                vals['code'] = f'SUC{sequence:03d}'
            
            # Si hay un manager, agregarlo a usuarios permitidos
            if vals.get('manager_id') and vals.get('allowed_user_ids'):
                user_ids = vals['allowed_user_ids'][0][2] if vals['allowed_user_ids'] else []
                if vals['manager_id'] not in user_ids:
                    user_ids.append(vals['manager_id'])
                    vals['allowed_user_ids'] = [(6, 0, user_ids)]
            elif vals.get('manager_id'):
                vals['allowed_user_ids'] = [(6, 0, [vals['manager_id']])]
                
        return super(SucursalesCajasBranch, self).create(vals_list)
    
    def write(self, vals):
        """Override write para validaciones adicionales"""
        # Si se actualiza el manager, agregarlo a usuarios permitidos
        if vals.get('manager_id'):
            for branch in self:
                current_users = branch.allowed_user_ids.ids
                if vals['manager_id'] not in current_users:
                    current_users.append(vals['manager_id'])
                    vals['allowed_user_ids'] = [(6, 0, current_users)]
                    
        return super(SucursalesCajasBranch, self).write(vals)
    
    @api.onchange('manager_id')
    def _onchange_manager_id(self):
        """Al cambiar el manager, sugerir agregarlo a usuarios permitidos"""
        if self.manager_id and self.manager_id not in self.allowed_user_ids:
            self.allowed_user_ids = [(4, self.manager_id.id)]
    
    def name_get(self):
        """Personalizar el display name"""
        result = []
        for branch in self:
            if branch.code:
                name = f'[{branch.code}] {branch.name}'
            else:
                name = branch.name
            result.append((branch.id, name))
        return result
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, order=None):
        """Permitir buscar por código o nombre"""
        args = args or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
            return self.search(domain + args, limit=limit, order=order).ids
        return super()._name_search(name, args, operator, limit, order)
    
    def action_view_cashboxes(self):
        """Acción para ver las cajas de la sucursal"""
        self.ensure_one()
        return {
            'name': _('Cajas de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.cashbox',
            'view_mode': 'tree,form',
            'domain': [('branch_id', '=', self.id)],
            'context': {
                'default_branch_id': self.id,
                'search_default_active': 1,
            }
        }
    
    def action_view_active_sessions(self):
        """Acción para ver las sesiones activas de la sucursal"""
        self.ensure_one()
        session_ids = self.cashbox_ids.mapped('active_session_id').filtered(
            lambda s: s.state == 'open'
        ).ids
        
        return {
            'name': _('Sesiones Activas - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sucursales_cajas.session',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', session_ids)],
            'context': {
                'create': False,
            }
        }
    
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """Override copy para manejar duplicación"""
        default = dict(default or {})
        default.update({
            'name': _("%s (Copia)") % self.name,
            'code': False,  # Forzar regeneración de código
        })
        return super(SucursalesCajasBranch, self).copy(default)
    
    def unlink(self):
        """Override unlink para validaciones antes de eliminar"""
        for branch in self:
            if branch.cashbox_ids:
                raise UserError(
                    _('No se puede eliminar la sucursal "%s" porque tiene cajas asociadas. '
                      'Primero debe eliminar o reasignar las cajas.') % branch.name
                )
            
            # Verificar si hay operaciones asociadas
            operations = self.env['sucursales_cajas.operation'].search([
                ('cashbox_id.branch_id', '=', branch.id)
            ], limit=1)
            
            if operations:
                raise UserError(
                    _('No se puede eliminar la sucursal "%s" porque tiene operaciones registradas.') 
                    % branch.name
                )
                
        return super(SucursalesCajasBranch, self).unlink()