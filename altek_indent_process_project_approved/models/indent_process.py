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


class IndentSector(models.Model):
    _name = 'indent.sector'

    name = fields.Char(string="Sector", required=True)


class IndentProcess(models.Model):
    _name = 'indent.process'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Indent Process'

    @api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order',
                 'order_ids.company_id')
    def _compute_sale_data(self):
        """Get Quotation and Sales related data to the smart buttons"""
        for indent in self:
            total = 0.0
            quotation_cnt = 0
            sale_order_cnt = 0
            company_currency = self.env.company.currency_id
            for order in indent.order_ids:
                if order.state in ('draft', 'sent'):
                    quotation_cnt += 1
                if order.state not in ('draft', 'sent', 'cancel'):
                    sale_order_cnt += 1
                    total += order.currency_id._convert(
                        order.amount_untaxed, company_currency, order.company_id,
                        order.date_order or fields.Date.today())
            indent.sale_amount_total = total
            indent.quotation_count = quotation_cnt
            indent.sale_order_count = sale_order_cnt

    @api.depends('order_line.price_subtotal')
    def _amount_all(self):
        """
        Compute the total amounts of the lines.
        """
        for order in self:
            amount_total = 0.0
            commission_amount_total = 0.0
            for line in order.order_line:
                amount_total += line.price_subtotal
                commission_amount_total += line.commission_amount
            order.update({
                'amount_total': amount_total,
                'commission_amount_total': commission_amount_total
            })

    def _activity_data(self):
        """
        Compute the count of activities.
        """
        count = 0
        if self.activity_ids:
            for activity in self.activity_ids:
                count += 1
        self.update({
            'activity_count': count,
        })

    def _activity_done_data(self):
        """
        Compute the count of done activities.
        """
        count = 0
        done_activity = self.env['indent.process.activities'].search([('res_id', '=', self.id)])
        if done_activity:
            for activity in done_activity:
                count += 1
        self.update({
            'activity_done_count': count,
        })

    def _indent_sheet_count(self):
        """
        Compute the count of indent sheets.
        """
        count = 0
        sheets = self.env['indent.sheet'].search([('indent_id', '=', self.id)])
        if sheets:
            for sheet in sheets:
                count += 1
        self.update({
            'indent_sheet_count': count,
        })

    def _debit_note_count(self):
        """
        Compute the count of debit notes.
        """
        select_query = """SELECT indent_process_id FROM account_move_indent_process_rel 
                            WHERE indent_process_id = (%s)"""
        self.env.cr.execute(select_query, [self.id])
        results = self.env.cr.dictfetchall()

        count = 0
        invoices = self.env['account.move'].search([('indent_id', '=', self.id)])
        if invoices:
            for invoice in invoices:
                count += 1
        else:
            count = len(results)
        self.update({
            'debit_note_count': count,
        })

    name = fields.Char(string="Indent No", readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string="Customer", domain="[('customer_rank','=', 1)]", tracking=1,
                                 required=1)
    customer_expected_date = fields.Date(string="Customer Expected Date", tracking=2)
    user_id = fields.Many2one(
        'res.users', string='Salesperson', index=True, tracking=3, default=lambda self: self.env.user,
        domain=lambda self: [('groups_id', 'in', self.env.ref('sales_team.group_sale_salesman').id)])
    sector_id = fields.Many2one('indent.sector', string="Customer Sector", tracking=4, required=1)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validate', 'Validated'),
        ('cancel', 'Canceled'),
        ('rejected', 'Indent Sheet Rejected'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('awaiting_order_confirmation', 'Awaiting Order Confirmation'),
        ('order_confirmed', 'Order Confirmed'),
        ('booking_confirmation_received', 'Booking Confirmation Received'),
        ('collect_copy_documents', 'Copy Documents'),
        ('document_process_complete', 'Document Process Completed'),
        ('customer_payment_followup', 'Customer Payments followup'),
        ('pending_debit_note', 'Pending Debit Note'),
        ('commission_payment_followup', 'Commission Payments Followup'),
        ('payments_recovered', 'Payment Recovered'),
    ], string='Status', readonly=True, copy=False, index=True, default='draft', tracking=5)
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain="[('supplier_rank','=', 1)]", tracking=6,
                                  required=1)
    supplier_sector_id = fields.Many2one('indent.sector', string="Supplier Sector", tracking=7, required=1)
    etd = fields.Date(string="ETD", help="Estimated Time of Departure", tracking=8)
    eta = fields.Date(string="ETA", help="Estimated Time of Arrival", tracking=9)
    order_line = fields.One2many('indent.process.line', 'indent_id', string='Indent Lines', copy=True, auto_join=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', tracking=10)
    commission_amount_total = fields.Monetary(string='Commission Total', store=True, readonly=True,
                                               compute='_amount_all', tracking=11)
    note = fields.Text('Terms and conditions', tracking=12)
    sale_amount_total = fields.Monetary(compute='_compute_sale_data', string="Sum of Orders",
                                        help="Untaxed Total of Confirmed Orders")
    quotation_count = fields.Integer(compute='_compute_sale_data', string="Number of Quotations")
    sale_order_count = fields.Integer(compute='_compute_sale_data', string="Number of Sale Orders")
    activity_count = fields.Integer(compute='_activity_data', string="Number of Activities")
    activity_done_count = fields.Integer(compute='_activity_done_data', string="Number of Done Activities")
    indent_sheet_count = fields.Integer(compute='_indent_sheet_count', string="Number of Indent Sheets")
    debit_note_count = fields.Integer(compute='_debit_note_count', string="Number of Debit Notes")
    order_ids = fields.One2many('sale.order', 'indent_id', string='Orders')
    indent_ids = fields.One2many('indent.sheet', 'indent_id', string='Indent Sheets')
    invoice_ids = fields.One2many('account.move', 'indent_id', string='Indent Sheets')
    received_invoice = fields.Boolean(string='Invoice', default=False)
    received_packing_list = fields.Boolean(string='Packing List', default=False)
    received_coa = fields.Boolean(string='COA', default=False)
    received_health_certificate = fields.Boolean(string='Health Certificate', default=False)
    received_coo = fields.Boolean(string='COO', default=False)
    received_bl = fields.Boolean(string='BL', default=False)
    received_other_docs = fields.Boolean(string='Other Documents', default=False)
    bl_date = fields.Date(string="BL Date", tracking=13)
    property_payment_term_id = fields.Many2one('account.payment.term',
                                               string='Customer Payment Terms',
                                               help="This payment term will be used instead of the default one for sales orders and customer invoices",
                                               required="1")
    property_supplier_payment_term_id = fields.Many2one('account.payment.term',
                                                        string='Supplier Payment Terms',
                                                        help="This payment term will be used instead of the default one for purchase orders and vendor bills",
                                                        required="1")
    customer_payment_date = fields.Date(string="Customer Payment Date")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company)
    so_number = fields.Char(string="SO Number", tracking=14)
    so_date = fields.Date(string="SO Date", tracking=15)
    vessel_details = fields.Text(string="Vessel Details", tracking=16)
    bl_number = fields.Char(string="BL Number", tracking=17)
    courier_ref_number = fields.Char(string="Courier Reference Number", tracking=18)
    remarks = fields.Text(string="Remarks", tracking=19)
    debit_note_created = fields.Boolean(string='Debit Note Created', default=False)
    invoice_ids = fields.Many2many("account.move", string='Invoices', readonly=True,
                                   copy=False, search="_search_invoice_ids")
    get_for_the_report = fields.Boolean(string='Report Generated', default=False)

    def view_activities(self):
        """View related current activities"""
        self.ensure_one()
        action = self.env.ref('mail.mail_activity_action').read()[0]
        action['domain'] = [('id', 'in', self.activity_ids.ids)]
        action['view_mode'] = 'form'
        return action

    def view_done_activities(self):
        """View related done activities"""
        self.ensure_one()
        action = self.env.ref('altek_indent_process_project_approved.done_activity_action').read()[0]
        action['domain'] = [('res_id', '=', self.id)]
        action['view_mode'] = 'tree'
        return action

    def action_validate(self):
        """Validate function of the indent process
        Check some mandatory fields and load the schedule activity wizard wth default data"""
        if not self.partner_id:
            raise UserError('Please select a customer to validate')
        if not self.supplier_id:
            raise UserError('Please select a supplier to validate')
        if not self.order_line:
            raise UserError('Please add one or more products to the Product Lines')
        self.sudo().write({
            'state': 'validate'
        })

    def button_cancel(self):
        """Indent Sheet Cancel Function"""
        if self.order_line:
            for invoice in self.order_line:
                if invoice.invoice_number:
                    raise UserError('You cannot cancel Indent when invoice details already added.')

            self.sudo().write({
                'state': 'cancel'
            })

    def order_confirmed(self):
        """Oder confirmation function"""

        self.activity_ids._action_done()
        self.sudo().write({
            'state': 'order_confirmed'
        })

    def order_confirmed_next(self):
        """Oder confirmation next function"""

        self.sudo().write({
            'state': 'booking_confirmation_received'
        })

    def booking_confirmation_received_next(self):
        """Booking confirmation next function"""
        self.sudo().write({
            'state': 'collect_copy_documents'
        })

    def copy_document_next(self):
        """Copy Document next function"""
        if self.bl_date and self.bl_number:
            self.sudo().write({
                'state': 'document_process_complete'
            })
        else:
            raise UserError('Please add BL date & BL Number to got to the next state')

    def document_process_complete_next(self):
        """Document Process Complete next function"""
        activity_obj = self.env['mail.activity.type'].search([('customer_payment_follow', '=', True)])
        model_id = self.env['ir.model'].search([('model', '=', 'indent.process')])
        if self.property_payment_term_id:
            number_of_days = 0
            for days in self.property_payment_term_id.line_ids:
                number_of_days += days.days
        due_date = self.bl_date + timedelta(days=number_of_days)

        self.env['mail.activity'].create({
            'res_model_id': model_id.id,
            'res_model': model_id.model,
            'res_id': self.id,
            'res_name': self.name,
            'activity_type_id': activity_obj.id,
            'summary': activity_obj.summary,
            'note': activity_obj.default_description,
            'date_deadline': due_date,
            'user_id': activity_obj.default_user_id.id,
        })
        self.sudo().write({
            'state': 'customer_payment_followup'
        })

    def customer_payment_followup_next(self):
        """Customer Payment Followup next function"""
        self.activity_ids._action_done()

        activity_obj = self.env['mail.activity.type'].search([('create_debit_note', '=', True)])
        model_id = self.env['ir.model'].search([('model', '=', 'indent.process')])

        self.env['mail.activity'].create({
            'res_model_id': model_id.id,
            'res_model': model_id.model,
            'res_id': self.id,
            'res_name': self.name,
            'activity_type_id': activity_obj.id,
            'summary': activity_obj.summary,
            'note': activity_obj.default_description,
            'date_deadline': (datetime.now() + timedelta(days=0)).date(),
            'user_id': activity_obj.default_user_id.id,
        })
        self.sudo().write({
            'state': 'pending_debit_note'
        })

    def action_sale_quotations_indent(self):
        """Button action to load the quotation"""
        if not self.partner_id:
            return self.env["ir.actions.actions"]._for_xml_id("sale_crm.crm_quotation_partner_action")
        else:
            return self.action_new_quotation()

    def action_new_quotation(self):
        """Related action for above function
        Load all the default data to the quotation screen from the indent process"""
        action = self.env["ir.actions.actions"]._for_xml_id("altek_indent_process_project_approved.sale_action_quotations_indent")
        # get line items
        vals = []
        for line in self.order_line:
            vals.append((0, 0, {'product_id': line.product_id.id,
                                'name': line.product_id.name,
                                'product_uom_qty': line.product_uom_qty,
                                'product_uom': line.product_uom_qty,
                                'price_unit': line.price_unit}))
        action['context'] = {
            'search_default_indent_id': self.id,
            'default_indent_id': self.id,
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_currency_id': self.currency_id.id,
            'default_payment_term_id': self.property_payment_term_id.id,
            'default_order_line': vals
        }
        return action

    def action_indent_sheet_indent(self):
        """Button action to load the indent sheet"""
        return self.action_new_indent_sheet()

    def action_new_indent_sheet(self):
        """Related action for above function
        Load all the default data to the quotation screen from the indent process"""
        action = self.env["ir.actions.actions"]._for_xml_id("altek_indent_process_project_approved.indent_sheet_action_button")
        # get line items
        vals = []
        for line in self.order_line:
            vals.append((0, 0, {'product_id': line.product_id.id,
                                'name': line.product_id.name,
                                'product_uom_qty': line.product_uom_qty,
                                'price_unit': line.price_unit}))
        order_id = False
        shipment_id = False
        if self.order_ids:
            order_id = self.order_ids[0].id
        action['context'] = {
            'search_default_indent_id': self.id,
            'default_indent_id': self.id,
            'search_default_supplier_id': self.supplier_id.id,
            'default_supplier_id': self.supplier_id.id,
            'default_partner_id': self.partner_id.id,
            'default_supplier_contact_no': self.supplier_id.phone,
            'default_supplier_sector_id': self.supplier_sector_id.id,
            'default_country_id': self.supplier_id.country_origin.id,
            'default_order_id': order_id,
            'default_indent_sheet_line': vals
        }
        return action

    def action_view_sale_quotation(self):
        """Redirect to the specific quotations related to indent process when click the Quotation smart button"""
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action['context'] = {
            'search_default_draft': 1,
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_indent_id': self.id
        }
        action['domain'] = [('indent_id', '=', self.id), ('state', 'in', ['draft', 'sent'])]
        quotations = self.mapped('order_ids').filtered(lambda l: l.state in ('draft', 'sent'))
        if len(quotations) == 1:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = quotations.id
        return action

    def action_view_sale_order(self):
        """Redirect to the specific Sales Order related to indent process when click the Quotation smart button"""
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        action['context'] = {
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_indent_id': self.id,
        }
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'not in', ('draft', 'sent', 'cancel'))]
        orders = self.mapped('order_ids').filtered(lambda l: l.state not in ('draft', 'sent', 'cancel'))
        if len(orders) == 1:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = orders.id
        return action

    def action_view_indent_sheet(self):
        """Redirect to the specific Indent Sheet related to indent process when click the Indent Sheet smart button"""
        self.ensure_one()
        action = self.env.ref('altek_indent_process_project_approved.default_indent_sheet_action').read()[0]
        action['domain'] = [('indent_id', '=', self.id)]
        action['view_mode'] = 'tree'
        return action

    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids')
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['indent_id'] = self.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        context = {
            'default_move_type': 'out_invoice',
        }
        for x in self:
            x.ensure_one()
        journal = self.env['account.move'].with_context(default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (
                self.company_id.name, self.company_id.id))

        if len(self) == 1:
            """Get product related information"""
            product_obj = self.env['product.product'].search([('default_code', '=', 'SUP_COM')])
            """Get related indent sheet data"""
            commission = self.commission_amount_total

            vals = [{
                'ref': '',
                'move_type': 'out_invoice',
                'narration': '',
                'invoice_date': fields.Date.today(),
                'currency_id': self.currency_id.id,
                'campaign_id': False,
                'medium_id': False,
                'source_id': False,
                'invoice_user_id': False,
                'team_id': False,
                'partner_id': self.supplier_id.id,
                'partner_shipping_id': False,
                'fiscal_position_id': False,
                'partner_bank_id': False,
                'journal_id': journal.id,  # company comes from the journal
                'invoice_origin': self.name,
                'invoice_payment_term_id': self.property_supplier_payment_term_id.id,
                'payment_reference': False,
                'transaction_ids': [(6, 0, [])],
                'invoice_line_ids': [(0, 0,
                                      {'display_type': False,
                                       'account_id': product_obj.categ_id.property_account_income_categ_id.id or product_obj.property_account_income_id.id,
                                       'exclude_from_invoice_tab': False,
                                       'sequence': 1,
                                       'name': product_obj.name,
                                       'product_id': product_obj.id,
                                       'product_uom_id': 1,
                                       'quantity': 1,
                                       'discount': 0.0,
                                       'price_unit': commission,
                                       'tax_ids': [(6, 0, [])],
                                       'analytic_tag_ids': [(6, 0, [])]
                                       })],
                'company_id': self.company_id.id,
                'indent_id': self.id
            }]

            moves = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(vals)
            return {
                'name': _('Invoice created'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'account.move',
                'view_id': self.env.ref('account.view_move_form').id,
                'target': 'current',
                'res_id': moves.id,
            }
        else:
            """Get product related information"""
            product_obj = self.env['product.product'].search([('default_code', '=', 'SUP_COM')])
            """Get related indent sheet data"""
            commission = 0.0
            for x in self:
                commission += x.commission_amount_total

            vals = [{
                'ref': '',
                'move_type': 'out_invoice',
                'narration': '',
                'invoice_date': fields.Date.today(),
                'currency_id': self[0].currency_id.id,
                'campaign_id': False,
                'medium_id': False,
                'source_id': False,
                'invoice_user_id': False,
                'team_id': False,
                'partner_id': self[0].supplier_id.id,
                'partner_shipping_id': False,
                'fiscal_position_id': False,
                'partner_bank_id': False,
                'journal_id': journal.id,  # company comes from the journal
                'invoice_origin': self[0].name,
                'invoice_payment_term_id': self[0].property_supplier_payment_term_id.id,
                'payment_reference': False,
                'transaction_ids': [(6, 0, [])],
                'invoice_line_ids': [(0, 0,
                                      {'display_type': False,
                                       'account_id': product_obj.categ_id.property_account_income_categ_id.id or product_obj.property_account_income_id.id,
                                       'exclude_from_invoice_tab': False,
                                       'sequence': 1,
                                       'name': product_obj.name,
                                       'product_id': product_obj.id,
                                       'product_uom_id': 1,
                                       'quantity': 1,
                                       'discount': 0.0,
                                       'price_unit': commission,
                                       'tax_ids': [(6, 0, [])],
                                       'analytic_tag_ids': [(6, 0, [])]
                                       })],
                'company_id': self[0].company_id.id,
            }]

            moves = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(vals)
            if moves:
                for x in self:
                    query = """ INSERT INTO account_move_indent_process_rel
                                                (indent_process_id, account_move_id)
                                            VALUES (%s, %s)"""

                    self.env.cr.execute(query, [x.id, moves.id])
            return {
                'name': _('Invoice created'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'account.move',
                'view_id': self.env.ref('account.view_move_form').id,
                'target': 'current',
                'res_id': moves.id,
            }

    def _create_invoices(self, grouped=False, final=False, date=None):

        if not self.env['account.move'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.move']

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for x in self:
            x.ensure_one()
        journal = self.env['account.move'].with_context(default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (
                self.company_id.name, self.company_id.id))

        if len(self) == 1:
            """Get product related information"""
            product_obj = self.env['product.product'].search([('default_code', '=', 'SUP_COM')])
            """Get related indent sheet data"""
            commission = self.commission_amount_total

            # 1) Create invoices.
            invoice_vals_list = []
            vals = {
                'ref': '',
                'move_type': 'out_invoice',
                'narration': '',
                'invoice_date': fields.Date.today(),
                'currency_id': self.currency_id.id,
                'campaign_id': False,
                'medium_id': False,
                'source_id': False,
                'invoice_user_id': False,
                'team_id': False,
                'partner_id': self.supplier_id.id,
                'partner_shipping_id': False,
                'fiscal_position_id': False,
                'partner_bank_id': False,
                'journal_id': journal.id,  # company comes from the journal
                'invoice_origin': self.name,
                'invoice_payment_term_id': self.property_supplier_payment_term_id.id,
                'payment_reference': False,
                'transaction_ids': [(6, 0, [])],
                'invoice_line_ids': [(0, 0,
                                      {'display_type': False,
                                       'account_id': product_obj.categ_id.property_account_income_categ_id.id or product_obj.property_account_income_id.id,
                                       'exclude_from_invoice_tab': False,
                                       'sequence': 1,
                                       'name': product_obj.name,
                                       'product_id': product_obj.id,
                                       'product_uom_id': 1,
                                       'quantity': 1,
                                       'discount': 0.0,
                                       'price_unit': commission,
                                       'tax_ids': [(6, 0, [])],
                                       'analytic_tag_ids': [(6, 0, [])]
                                       })],
                'company_id': self.company_id.id,
                'indent_id': self.id
            }
            invoice_vals_list.append(vals)
            moves = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(invoice_vals_list)

            return moves
        else:
            """Get product related information"""
            product_obj = self.env['product.product'].search([('default_code', '=', 'SUP_COM')])
            """Get related indent sheet data"""
            commission = 0.0
            for x in self:
                commission += x.commission_amount_total

            vals = [{
                'ref': '',
                'move_type': 'out_invoice',
                'narration': '',
                'invoice_date': fields.Date.today(),
                'currency_id': self[0].currency_id.id,
                'campaign_id': False,
                'medium_id': False,
                'source_id': False,
                'invoice_user_id': False,
                'team_id': False,
                'partner_id': self[0].supplier_id.id,
                'partner_shipping_id': False,
                'fiscal_position_id': False,
                'partner_bank_id': False,
                'journal_id': journal.id,  # company comes from the journal
                'invoice_origin': self[0].name,
                'invoice_payment_term_id': self[0].property_supplier_payment_term_id.id,
                'payment_reference': False,
                'transaction_ids': [(6, 0, [])],
                'invoice_line_ids': [(0, 0,
                                      {'display_type': False,
                                       'account_id': product_obj.categ_id.property_account_income_categ_id.id or product_obj.property_account_income_id.id,
                                       'exclude_from_invoice_tab': False,
                                       'sequence': 1,
                                       'name': product_obj.name,
                                       'product_id': product_obj.id,
                                       'product_uom_id': 1,
                                       'quantity': 1,
                                       'discount': 0.0,
                                       'price_unit': commission,
                                       'tax_ids': [(6, 0, [])],
                                       'analytic_tag_ids': [(6, 0, [])]
                                       })],
                'company_id': self[0].company_id.id,
            }]

            moves = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(vals)
            if moves:
                for x in self:
                    query = """ INSERT INTO account_move_indent_process_rel
                                                            (indent_process_id, account_move_id)
                                                        VALUES (%s, %s)"""

                    self.env.cr.execute(query, [x.id, moves.id])
            return moves

    def action_view_invoice_smart_button(self):
        """Redirect to the specific Indent Sheet related to indent process when click the Indent Sheet smart button"""
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action['context'] = {
            'default_indent_id': self.id,
        }
        action['domain'] = [('indent_id', '=', self.id)]
        orders = self.mapped('invoice_ids').filtered(lambda l: l.state not in 'cancel')
        if len(orders) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = orders.id
        return action

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
            Sales Person
            Sector
        """
        if not self.partner_id:
            self.update({
                'user_id': False,
                'sector_id': False,
                'property_payment_term_id': False,
            })
            return

        partner_user = self.partner_id.user_id or self.partner_id.commercial_partner_id.user_id
        sector_id = self.partner_id.sector_id
        payment_term_id = self.partner_id.property_payment_term_id
        values = {}
        user_id = partner_user.id
        if not self.env.context.get('not_self_saleperson'):
            user_id = user_id or self.env.uid
        if user_id and self.user_id.id != user_id:
            values['user_id'] = user_id
        if sector_id:
            values['sector_id'] = sector_id.id
        if payment_term_id:
            values['property_payment_term_id'] = payment_term_id.id

        self.update(values)

    @api.onchange('supplier_id')
    def onchange_supplier_id(self):
        """
        Update the following fields when the supplier is changed:
            Sector
        """
        if not self.supplier_id:
            self.update({
                'supplier_sector_id': False,
                'property_supplier_payment_term_id': False,
                'currency_id': False,
            })
            return
        sector_id = self.supplier_id.sector_id
        supplier_payment_term_id = self.supplier_id.property_supplier_payment_term_id
        currency_id = self.supplier_id.currency_id_origin.id
        values = {}
        if sector_id:
            values['supplier_sector_id'] = sector_id.id
        if supplier_payment_term_id:
            values['property_supplier_payment_term_id'] = supplier_payment_term_id.id
        if currency_id:
            values['currency_id'] = currency_id

        self.update(values)

    @api.model
    def create(self, vals):
        """Call for the relates Indent sequence and get the number to create the form"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('indent.process') or _('New')

        result = super(IndentProcess, self).create(vals)
        return result


class IndentProcessLine(models.Model):
    _name = 'indent.process.line'

    indent_id = fields.Many2one('indent.process', string='Indent Reference', required=True, ondelete='cascade', index=True, copy=False)
    name = fields.Text(string='Description', required=True)
    product_id = fields.Many2one(
        'product.product', string='Product', domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), "
                                                    "('company_id', '=', company_id)]",
        change_default=True, ondelete='restrict', check_company=True)  # Unrequired company
    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id", domain=[('sale_ok', '=', True)])
    product_uom_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True, default=1.0)
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    currency_id = fields.Many2one(related='indent_id.currency_id', depends=['indent_id.currency_id'], store=True,
                                  string='Currency', readonly=True)
    commission_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage'),
    ], string='Commission Type', default='percentage')
    commission_amount = fields.Float('Commission Amount', default=0.0)
    commission_percentage = fields.Float('Commission Percentage', default=0.0)
    invoice_number = fields.Char(string="Invoice Number")
    invoice_date = fields.Date(string="Invoice Date")

    @api.depends('product_uom_qty', 'price_unit', 'commission_type', 'commission_amount', 'commission_percentage')
    def _compute_amount(self):
        """
        Compute the amounts of the Indent line.
        """
        for line in self:
            price = (line.price_unit * line.product_uom_qty)
            if line.commission_type == 'percentage':
                commission_amount = ((line.price_unit * line.product_uom_qty) * line.commission_percentage) / 100
            else:
                commission_amount = line.commission_amount
            line.update({
                'price_subtotal': price,
                'commission_amount': commission_amount
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
        if self.indent_id.partner_id:
            vals['price_unit'] = self.product_id.list_price
            vals['name'] = self.product_id.name
            vals['commission_percentage'] = self.product_id.indent_commission
        self.update(vals)


class IndentProcessActivities(models.Model):
    _name = 'indent.process.activities'

    res_id = fields.Many2oneReference(string='Related Document ID', index=True, required=True, model_field='res_model')
    activity_type_id = fields.Many2one('mail.activity.type', string='Activity Type', ondelete='restrict')
    activity_category = fields.Selection(related='activity_type_id.category', readonly=True)
    activity_decoration = fields.Selection(related='activity_type_id.decoration_type', readonly=True)
    icon = fields.Char('Icon', related='activity_type_id.icon', readonly=True)
    summary = fields.Char('Summary')
    note = fields.Html('Note', sanitize_style=True)
    date_deadline = fields.Date('Due Date', index=True, required=True, default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', 'Assigned to', default=lambda self: self.env.user, index=True, required=True)
    request_partner_id = fields.Many2one('res.partner', string='Requesting Partner')
    recommended_activity_type_id = fields.Many2one('mail.activity.type', string="Recommended Activity Type")
    previous_activity_type_id = fields.Many2one('mail.activity.type', string='Previous Activity Type', readonly=True)


class InheritMailActivity(models.Model):
    _inherit = 'mail.activity'

    # def action_feedback_schedule_next(self, feedback=False):
    #     res_id = self.res_id
    #     res_model = self.res_model if self.res_model == 'indent.process' else False
    #     ctx = dict(
    #         clean_context(self.env.context),
    #         default_previous_activity_type_id=self.activity_type_id.id,
    #         activity_previous_deadline=self.date_deadline,
    #         default_res_id=self.res_id,
    #         default_res_model=self.res_model,
    #     )
    #     messages, next_activities = self._action_done(
    #         feedback=feedback)  # will unlink activity, dont access self after that
    #     if next_activities:
    #         if res_model:
    #             return {
    #                 'name': _('Schedule an Activity'),
    #                 'context': ctx,
    #                 'view_mode': 'form',
    #                 'res_model': 'indent.process',
    #                 'res_id': res_id,
    #                 'views': [(False, 'form')],
    #                 'type': 'ir.actions.act_window',
    #                 'target': 'main',
    #             }
    #         else:
    #             return False
    #     if res_model:
    #         return {
    #             'name': _('Schedule an Activity'),
    #             'context': ctx,
    #             'view_mode': 'form',
    #             'res_model': 'indent.process',
    #             'res_id': res_id,
    #             'views': [(False, 'form')],
    #             'type': 'ir.actions.act_window',
    #             'target': 'main',
    #         }
    #     else:
    #         return {
    #             'name': _('Schedule an Activity'),
    #             'context': ctx,
    #             'view_mode': 'form',
    #             'res_model': 'mail.activity',
    #             'views': [(False, 'form')],
    #             'type': 'ir.actions.act_window',
    #             'target': 'new',
    #         }
    #
    # def action_feedback(self, feedback=False, attachment_ids=None):
    #     self = self.with_context(clean_context(self.env.context))
    #     res_id = self.res_id
    #     res_model = self.res_model if self.res_model == 'indent.process' else False
    #     messages, next_activities = self._action_done(feedback=feedback, attachment_ids=attachment_ids)
    #     if res_model:
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'reload',
    #         }
    #         # return {
    #         #     'name': _('Schedule an Activity'),
    #         #     'view_mode': 'form',
    #         #     'res_model': 'indent.process',
    #         #     'res_id': res_id,
    #         #     'views': [(False, 'form')],
    #         #     'type': 'ir.actions.act_window',
    #         #     'target': 'main',
    #         # }
    #     else:
    #         return messages.ids and messages.ids[0] or False

    def _action_done(self, feedback=False, attachment_ids=None):
        """ Private implementation of marking activity as done: posting a message, deleting activity
            (since done), and eventually create the automatical next activity (depending on config).
            :param feedback: optional feedback from user when marking activity as done
            :param attachment_ids: list of ir.attachment ids to attach to the posted mail.message
            :returns (messages, activities) where
                - messages is a recordset of posted mail.message
                - activities is a recordset of mail.activity of forced automically created activities
        """
        # marking as 'done'
        messages = self.env['mail.message']
        next_activities_values = []

        # Search for all attachments linked to the activities we are about to unlink. This way, we
        # can link them to the message posted and prevent their deletion.
        attachments = self.env['ir.attachment'].search_read([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
        ], ['id', 'res_id'])

        activity_attachments = defaultdict(list)
        for attachment in attachments:
            activity_id = attachment['res_id']
            activity_attachments[activity_id].append(attachment['id'])

        for activity in self:
            # extract value to generate next activities
            if activity.force_next:
                Activity = self.env['mail.activity'].with_context(activity_previous_deadline=activity.date_deadline)  # context key is required in the onchange to set deadline
                vals = Activity.default_get(Activity.fields_get())

                vals.update({
                    'previous_activity_type_id': activity.activity_type_id.id,
                    'res_id': activity.res_id,
                    'res_model': activity.res_model,
                    'res_model_id': self.env['ir.model']._get(activity.res_model).id,
                })
                virtual_activity = Activity.new(vals)
                virtual_activity._onchange_previous_activity_type_id()
                virtual_activity._onchange_activity_type_id()
                next_activities_values.append(virtual_activity._convert_to_write(virtual_activity._cache))

            # post message on activity, before deleting it
            record = self.env[activity.res_model].browse(activity.res_id)
            record.message_post_with_view(
                'mail.message_activity_done',
                values={
                    'activity': activity,
                    'feedback': feedback,
                    'display_assignee': activity.user_id != self.env.user
                },
                subtype_id=self.env['ir.model.data'].xmlid_to_res_id('mail.mt_activities'),
                mail_activity_type_id=activity.activity_type_id.id,
                attachment_ids=[(4, attachment_id) for attachment_id in attachment_ids] if attachment_ids else [],
            )

            # Moving the attachments in the message
            # TODO: Fix void res_id on attachment when you create an activity with an image
            # directly, see route /web_editor/attachment/add
            activity_message = record.message_ids[0]
            message_attachments = self.env['ir.attachment'].browse(activity_attachments[activity.id])
            if message_attachments:
                message_attachments.write({
                    'res_id': activity_message.id,
                    'res_model': activity_message._name,
                })
                activity_message.attachment_ids = message_attachments
            messages |= activity_message

            next_activities = self.env['mail.activity'].create(next_activities_values)

            """Create a new record in a new class to refer all the done activities related to the Indent Process"""
            self.env['indent.process.activities'].create({
                'res_id': self.res_id,
                'activity_type_id': self.activity_type_id.id,
                'activity_category': self.activity_category,
                'activity_decoration': self.activity_decoration,
                'icon': self.icon,
                'summary': self.summary,
                'note': self.note,
                'date_deadline': self.date_deadline,
                'user_id': self.user_id.id,
                'request_partner_id': self.request_partner_id.id,
                'recommended_activity_type_id': self.recommended_activity_type_id.id,
                'previous_activity_type_id': self.previous_activity_type_id.id
            })

        self.unlink()  # will unlink activity, dont access `self` after that

        return messages, next_activities


class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    indent_sheet_approved = fields.Boolean(string='Indent Sheet Approved', default=False)
    customer_payment_follow = fields.Boolean(string='Customer Payment Followup', default=False)
    create_debit_note = fields.Boolean(string='Create Debit Note', default=False)
    followup_outstanding_payment = fields.Boolean(string='Followup Outstanding Payments', default=False)




