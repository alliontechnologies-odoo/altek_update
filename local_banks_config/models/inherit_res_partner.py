from odoo import fields, models, api, _


class InheritResPartner(models.Model):
    _inherit = 'res.partner'

    bank_account_id = fields.Many2one('res.partner.bank', string="Bank Account")