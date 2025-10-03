from odoo import models, fields, api

class ChequeraSecurityGroup(models.Model):
    """Modelo para definir los grupos de seguridad del módulo"""
    _name = 'chequera.security.group'
    _description = 'Grupos de Seguridad para Chequera'
    _auto = False  # No crear tabla
    
    # Este es un modelo técnico que no crea tabla en la BD
    # Se usa solo para definir los grupos de seguridad
    
    def init(self):
        """Crear los grupos de seguridad al instalar el módulo"""
        # No hacemos nada aquí, los grupos se crean con datos XML