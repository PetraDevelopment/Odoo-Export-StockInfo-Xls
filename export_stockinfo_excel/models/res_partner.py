from odoo import models, fields


class Partner(models.Model):
    _inherit = 'res.partner'

    supplier = fields.Many2many('wizard.stock.history',  invisible=True)


class Category(models.Model):
    _inherit = 'product.category'

    obj = fields.Many2many('wizard.stock.history',  invisible=True)


class Warehouse(models.Model):
    _inherit = 'stock.warehouse'

    obj = fields.Many2many('wizard.stock.history',   invisible=True)

class location(models.Model):
    _inherit = 'stock.location'

    obj = fields.Many2many('wizard.stock.history', invisible=True)