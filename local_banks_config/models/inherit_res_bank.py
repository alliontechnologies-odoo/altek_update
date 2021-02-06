from odoo import fields, models, api, _


class InheritResBank(models.Model):
    _inherit = 'res.bank'

    main_bank_id = fields.Many2one('main.bank', string="Bank")
