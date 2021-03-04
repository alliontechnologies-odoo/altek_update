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


class IndentSheet(models.Model):

    _name = 'indent.sheet'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Indent Sheet'

    name = fields.Char(string="Indent Sheet No", readonly=True, default='New')
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain="[('supplier_rank','=', 1)]", tracking=1)
    partner_id = fields.Many2one('res.partner', string="Customer", domain="[('customer_rank','=', 1)]", tracking=1)
    supplier_sector_id = fields.Many2one('indent.sector', string="Supplier Sector", tracking=2)
    supplier_contact_no = fields.Char(string="Supplier Contact No", tracking=3)
    order_id = fields.Many2one('sale.order', string='Order No', tracking=4)
    date = fields.Date(string="Date", default=fields.Date.context_today, tracking=5)
    customer_po_no = fields.Char(string="Customer PO No", tracking=6)
    customer_po_date = fields.Date(string="Customer PO Date", tracking=7)
    packing = fields.Char(string="Packing", tracking=7)
    hs_code = fields.Char(string="HS Code", tracking=8)
    shipment = fields.Char(string="Shipment", tracking=9)
    finance = fields.Char(string="Finance", tracking=10)
    port_of_shipment = fields.Char(string="Port of Shipment", tracking=11)
    country_id = fields.Many2one('res.country', string="Country of Origin", tracking=12)
    main_bank_id = fields.Many2one('main.bank', string='Bank', tracking=13)
    marks = fields.Char(string="Marks", tracking=14)
    indent_sheet_line = fields.One2many('indent.sheet.line', 'indent_sheet_id', string='Indent Lines', copy=True,
                                        auto_join=True, tracking=15)
    currency_id = fields.Many2one(related='supplier_id.currency_id', store=True, tracking=16)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent_to_approval', 'Sent to Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', readonly=True, copy=False, index=True, default='draft', tracking=17)
    incoterm_id = fields.Many2one('account.incoterms', string='Incoterm', tracking=18)
    amount_total = fields.Monetary(string='Lines Total', store=True, readonly=True, compute='_amount_all', tracking=19)
    type_total = fields.Monetary(string='Shipping Arrangement Total', store=True, readonly=True, compute='_amount_type',
                                 tracking=20)
    freight_total = fields.Monetary(string='Freight Total', store=True, readonly=True, compute='_amount_type',
                                    tracking=21)
    insurance_total = fields.Monetary(string='Insurance Total', store=True, readonly=True, compute='_amount_all',
                                      tracking=22)
    grand_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_grand_all', tracking=23)
    indent_id = fields.Many2one('indent.process', string='Indent Process')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    quotation_count = fields.Integer(compute='_compute_sale_data', string="Number of Quotations")
    comments = fields.Text('Comments', tracking=24)
    re_marks = fields.Char(string="Remarks", tracking=25)
    reference_pi_no = fields.Char(string="Reference PI No", tracking=26)
    url = fields.Char("URL")

    def action_sent_to_approval(self):
        # get current model
        if request.params.get('model'):
            model = self.env['ir.model'].search([('model', '=', request.params.get('model'))])
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'assign.user.wizard',
            'target': 'new',
            'context': {'default_indent_sheet_id': self.id,
                        'default_model_id': model.id}
        }

    def action_approved(self):
        # get current model
        if request.params.get('model'):
            model = self.env['ir.model'].search([('model', '=', 'indent.process')])
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'comment.wizard',
            'target': 'new',
            'context': {'default_indent_sheet_id': self.id,
                        'default_model_id': model.id,
                        'default_type': 'approved'}
        }

    def action_reject(self):
        # get current model
        if request.params.get('model'):
            model = self.env['ir.model'].search([('model', '=', request.params.get('model'))])
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'comment.wizard',
            'target': 'new',
            'context': {'default_indent_sheet_id': self.id,
                        'default_model_id': model.id,
                        'default_type': 'reject'}
        }

    @api.depends('indent_sheet_line.price_subtotal', 'amount_total')
    def _amount_all(self):
        """
        Compute the total amounts of the lines.
        """
        for order in self:
            amount_total = 0.0
            for line in order.indent_sheet_line:
                amount_total += line.price_subtotal
            order.update({
                'amount_total': amount_total,
            })

    @api.depends('incoterm_id')
    def _amount_type(self):
        """
        Compute the percentage of the line total.
        """
        shipment_total = 0.0
        freight_total = 0.0
        insurance_total = 0.0
        if self.amount_total:
            self.update({
                'type_total': self.amount_total * self.incoterm_id.calculation_percentage,
                'freight_total': self.amount_total * self.incoterm_id.freight_percentage,
                'insurance_total': self.amount_total * self.incoterm_id.insurance_percentage,
            })
        else:
            self.update({
                'type_total': shipment_total,
                'freight_total': freight_total,
                'insurance_total': insurance_total
            })

    @api.depends('type_total', 'freight_total', 'insurance_total')
    def _grand_all(self):
        """
        Compute the grand total.
        """
        grand_total = 0.0
        if self.amount_total:
            self.update({
                'grand_total': self.type_total + self.freight_total + self.insurance_total
            })
        else:
            self.update({
                'grand_total': grand_total,
            })

    @api.model
    def create(self, vals):
        """Call for the relates Indent Sheet sequence and get the number to create the form"""
        if vals.get('name', _('New')) == _('New'):
            auto_generated = self.env['ir.sequence'].next_by_code('indent.sheet') or _('New')
            company_short_code = self.env['res.company'].browse(vals['company_id']).short_code or ''
            sector_code = self.env['indent.sector'].browse(vals['supplier_sector_id']).code or ''
            customer_short_code = self.env['res.partner'].browse(vals['partner_id']).customer_short_code or ''
            supplier_short_code = self.env['res.partner'].browse(vals['supplier_id']).supplier_short_code or ''
            vals['name'] = company_short_code + '/' + sector_code + '/' +supplier_short_code + '/' + customer_short_code + '/' + auto_generated or _('New')
        if vals['name']:
            customer_short_code = self.env['res.partner'].browse(vals['partner_id']).customer_short_code or ''
            supplier_short_code = self.env['res.partner'].browse(vals['supplier_id']).supplier_short_code or ''
            country_origin = self.env['res.country'].browse(vals['country_id']).code or ''
            vals['marks'] = supplier_short_code + '/' + country_origin + '/' + customer_short_code + '/' + vals['name']
        result = super(IndentSheet, self).create(vals)
        return result


class IndentSheetLine(models.Model):
    _name = 'indent.sheet.line'

    indent_sheet_id = fields.Many2one('indent.sheet', string='Indent Reference', required=True, ondelete='cascade', index=True, copy=False)
    name = fields.Text(string='Description', required=True)
    product_id = fields.Many2one(
        'product.product', string='Product', domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        change_default=True, ondelete='restrict', check_company=True)  # Unrequired company
    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id", domain=[('sale_ok', '=', True)])
    product_uom_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True, default=1.0)
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    currency_id = fields.Many2one(related='indent_sheet_id.currency_id', depends=['indent_sheet_id.currency_id'], store=True, string='Currency', readonly=True)

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_amount(self):
        """
        Compute the amounts of the Indent line.
        """
        for line in self:
            price = line.price_unit * line.product_uom_qty
            line.update({
                'price_subtotal': price,
            })

    @api.onchange('product_id')
    def product_id_change(self):
        """Default load values to the below fields when change the product field,
                Description,
                Price Unit
        """
        if not self.product_id:
            return
        vals = {}
        if self.indent_sheet_id.supplier_id:
            vals['price_unit'] = self.product_id.list_price
            vals['name'] = self.product_id.name
        self.update(vals)







