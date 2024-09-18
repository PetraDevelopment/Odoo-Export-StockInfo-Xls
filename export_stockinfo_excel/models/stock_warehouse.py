from odoo import fields, models


class StockWarehouse(models.Model):
    
    _inherit = 'stock.warehouse'

    stock_report_ids = fields.Many2many('stock.xls.report',
                                        string="Stock Report",
                                        help="Retrieve Stock Report IDs.",
                                        invisible=True)

class location(models.Model):
    _inherit = 'stock.location'

    obj = fields.Many2many('stock.xls.report',string="Stock Report",help="Retrieve Stock Report IDs.", invisible=True)