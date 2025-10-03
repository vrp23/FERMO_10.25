from odoo import models, fields, api

class ChequeraFormulaConfig(models.Model):
    _name = 'chequera.formula_config'
    _description = 'Configuración de Fórmulas de Cálculo'
    _order = 'context_type, field_name'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    field_name = fields.Selection([
        ('pesificacion_valor_compra', 'Valor de pesificación (Compra)'),
        ('interes_valor_compra', 'Valor de interés (Compra)'),
        ('precio_compra', 'Precio de compra'),
        ('pesificacion_valor_venta', 'Valor de pesificación (Venta)'),
        ('interes_valor_venta', 'Valor de interés (Venta)'),
        ('precio_venta', 'Precio de venta')
    ], string='Campo a calcular', required=True)
    
    context_type = fields.Selection([
        ('compra', 'Compra'),
        ('venta', 'Venta')
    ], string='Tipo de contexto', required=True)
    
    code = fields.Text(string='Código Python', required=True,
                      help="Código Python para calcular el valor. Utilice 'record' para acceder al cheque actual.")
    
    active = fields.Boolean(string='Activo', default=True)
    
    description = fields.Text(string='Descripción', 
                            help="Descripción de la fórmula y su propósito.")
    
    @api.depends('field_name', 'context_type')
    def _compute_name(self):
        for formula in self:
            field_label = dict(formula._fields['field_name'].selection).get(formula.field_name, '')
            context_label = dict(formula._fields['context_type'].selection).get(formula.context_type, '')
            formula.name = f"{field_label} ({context_label})"
    
    @api.model
    def create(self, vals):
        """Al crear, verificar que no exista otra fórmula activa para el mismo campo y contexto"""
        res = super(ChequeraFormulaConfig, self).create(vals)
        self._check_unique_active_formula(res)
        return res
    
    def write(self, vals):
        """Al modificar, verificar que no exista otra fórmula activa para el mismo campo y contexto"""
        res = super(ChequeraFormulaConfig, self).write(vals)
        for formula in self:
            self._check_unique_active_formula(formula)
        return res
    
    def _check_unique_active_formula(self, formula):
        """Verificar que no haya más de una fórmula activa para el mismo campo y contexto"""
        if formula.active:
            # Buscar otras fórmulas activas para el mismo campo y contexto
            duplicate = self.search([
                ('id', '!=', formula.id),
                ('field_name', '=', formula.field_name),
                ('context_type', '=', formula.context_type),
                ('active', '=', True)
            ], limit=1)
            
            if duplicate:
                # Desactivar la otra fórmula
                duplicate.active = False