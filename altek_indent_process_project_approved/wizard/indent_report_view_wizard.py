from odoo import api, fields, models, _
from datetime import datetime
from datetime import timedelta
from odoo.exceptions import AccessError, UserError, ValidationError


class IndentReportViewWizard(models.TransientModel):
    _name = 'indent.report.view.wizard'

    start_date = fields.Date(string="Start Date", required=1)
    end_date = fields.Date(string="End Date", required=1)
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain="[('supplier_rank','=', 1)]", required=1)

    def preview(self):
        indent_list = []
        account_move = self.env['account.move'].search([('partner_id', '=', self.supplier_id.id),
                                                        ('move_type', '=', 'out_invoice'),
                                                        ('state', '=', 'posted'),
                                                        ('date', '>=', self.start_date),
                                                        ('date', '<=', self.end_date)])
        for invoice in account_move:
            if invoice.indent_id:
                indent_list.append(invoice.indent_id.id)
            else:
                select_query = """SELECT indent_process_id FROM account_move_indent_process_rel 
                                                            WHERE account_move_id = (%s)"""
                self.env.cr.execute(select_query, [invoice.id])
                results = self.env.cr.dictfetchall()
                for indent in results:
                    indent_list.append(indent.get('indent_process_id'))
        currency_id = None
        vals = []
        for indent in indent_list:
            indent_obj = self.env['indent.process'].search([('id', '=', indent),
                                                            ('state', '=', 'commission_payment_followup'),
                                                            ('get_for_the_report', '!=', True)])
            if indent_obj:
                for line in indent_obj.order_line:
                    vals.append((0, 0, {'invoice_no': line.invoice_number,
                                        'invoice_date': line.invoice_date,
                                        'indent_sheet': indent_obj.indent_ids[0].name,
                                        'customer': indent_obj.partner_id.name,
                                        'product': line.product_id.name,
                                        'qty': line.product_uom_qty,
                                        'value': line.price_subtotal,
                                        'commission': line.commission_amount}))
                indent_obj.write({
                    'get_for_the_report': True,
                })
                currency_id = indent_obj.currency_id.id
            else:
                raise UserError('No data for the report')

        values = [{
            'name': self.env['ir.sequence'].next_by_code('indent.report.preview') or _('New'),
            'supplier_id':self.supplier_id.id,
            'date': fields.Date.today(),
            'description': 'Indent Commission from ' + str(self.start_date) + ' to ' + str(self.end_date) + ' - ' + str(self.supplier_id.name),
            'currency_id': currency_id,
            'indent_report_preview_line': vals,
        }]

        preview = self.env['indent.report.preview'].sudo().create(values)

        return {
            'name': _('Indent Report Preview'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'indent.report.preview',
            'view_id': self.env.ref('altek_indent_process_project_approved.indent_report_preview_view_from').id,
            'target': 'current',
            'res_id': preview.id,
        }
