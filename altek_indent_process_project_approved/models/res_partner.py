from odoo import fields, models, api, _


class InheritResPartner(models.Model):
    _inherit = 'res.partner'

    sector_id = fields.Many2one('indent.sector', string="Sector")
    customer_short_code = fields.Char(string="Customer Short code")
    supplier_short_code = fields.Char(string="Supplier Short Code")
    country_origin = fields.Many2one('res.country', string="Country of Origin")
    currency_id_origin = fields.Many2one('res.currency', string='Currency')


