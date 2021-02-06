from odoo import fields, api, _, models


class InheritResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    main_bank_id = fields.Many2one('main.bank', 'Bank')
    partner_id = fields.Many2one('res.partner', 'Account Holder', ondelete='cascade', index=True,
                                 domain=[('parent_id', '=', False)], required=True)
    account_type = fields.Selection([('savings', 'Savings'), ('hold', 'Hold'), ('current', 'Current')], string="Account type")

    @api.onchange('bank_id')
    def onchange_bank_id(self):
        """Onchnage bank ID"""
        if self.bank_id:
            self.main_bank_id = self.bank_id.main_bank_id.id