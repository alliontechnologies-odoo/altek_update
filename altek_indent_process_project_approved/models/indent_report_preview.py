from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from collections import defaultdict
from odoo.tools.misc import clean_context
from odoo.http import request


class IndentReportPreview(models.Model):
    _name = 'indent.report.preview'
    _description = 'Indent Report Preview'

    def _amount_all(self):
        """
        Compute the total amounts of the lines.
        """
        for order in self:
            amount_total = 0.0
            for line in order.indent_report_preview_line:
                amount_total += line.commission
            order.update({
                'amount_total': amount_total,
            })

    @api.depends('currency_id', 'amount_total')
    def _compute_check_amount_in_words(self):
        """Computing the total amount in words"""
        for pay in self:
            if pay.currency_id:
                pay.check_amount_in_words = str(pay.currency_id.amount_to_text(pay.amount_total)).upper()
            else:
                pay.check_amount_in_words = False

    name = fields.Char(string="No", readonly=True, default='New')
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain="[('supplier_rank','=', 1)]", readonly=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company)
    description = fields.Char(string="Description", readonly=True)
    amount_total = fields.Monetary(string='Total', readonly=True, compute='_amount_all')
    indent_report_preview_line = fields.One2many('indent.report.preview.line', 'indent_report_id',
                                                 string='Report Lines', copy=True, auto_join=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency')
    check_amount_in_words = fields.Char(string="Amount in Words", compute='_compute_check_amount_in_words')
    bank_id = fields.Many2one('res.partner.bank', string="Bank Account")


class IndentReportPreviewLine(models.Model):
    _name = 'indent.report.preview.line'

    indent_report_id = fields.Many2one('indent.report.preview', string='Indent Report Preview', required=True,
                                       ondelete='cascade', index=True, copy=False)
    invoice_no = fields.Char(string='Invoice No')
    invoice_date = fields.Date(string='Invoice Date')
    indent_sheet = fields.Char(string='Indent Sheet')
    customer = fields.Char(string='Customer')
    product = fields.Char(string='Product')
    qty = fields.Float(string='Quantity in Kgs')
    value = fields.Float(string='Value')
    commission = fields.Float(string='Commission')
