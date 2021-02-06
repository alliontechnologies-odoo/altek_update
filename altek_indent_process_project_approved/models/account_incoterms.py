# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountIncoterms(models.Model):
    _inherit = 'account.incoterms'
    _description = 'Incoterms'

    calculation_percentage = fields.Float(string="Percentage %")
    freight_percentage = fields.Float(string="Freight Percentage %")
    insurance_percentage = fields.Float(string="Insurance Percentage %")
