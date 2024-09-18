from odoo import fields, models


class ProductCategory(models.Model):
    
    _inherit = 'product.category'

    stock_report_ids = fields.Many2many('stock.xls.report',
                                        string="Stock Report",
                                        help="Retrieve Stock Report IDs.",
                                        invisible=True)
