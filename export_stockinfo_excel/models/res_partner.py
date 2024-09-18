from odoo import fields, models


class ResPartner(models.Model):
    
    _inherit = 'res.partner'

    stock_report_ids = fields.Many2many('stock.xls.report',
                                        string="Stock Report",
                                        help="Retrieve Stock Report IDs.",
                                        invisible=True)
