# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from datetime import datetime, timedelta


class AccountMove(models.Model):
    _inherit = 'account.move'

    indent_id = fields.Many2one('indent.process', string='Indent Process')

    def action_post(self):
        return_objects = super(AccountMove, self).action_post()
        if return_objects:
            for obj in return_objects:
                if obj.indent_id:
                    obj.indent_id.activity_ids._action_done()

                    activity_obj = self.env['mail.activity.type'].search([('followup_outstanding_payment', '=', True)])
                    model_id = self.env['ir.model'].search([('model', '=', 'indent.process')])

                    if obj.indent_id.property_supplier_payment_term_id:
                        number_of_days = 0
                        for days in obj.indent_id.property_supplier_payment_term_id.line_ids:
                            number_of_days += days.days
                    due_date = self.invoice_date + timedelta(days=number_of_days)

                    self.env['mail.activity'].create({
                        'res_model_id': model_id.id,
                        'res_model': model_id.model,
                        'res_id': obj.indent_id.id,
                        'res_name': obj.indent_id.name,
                        'activity_type_id': activity_obj.id,
                        'summary': activity_obj.summary,
                        'note': activity_obj.default_description,
                        'date_deadline': due_date,
                        'user_id': activity_obj.default_user_id.id,
                    })
                    obj.indent_id.write({
                        'debit_note_created': True,
                        'state': 'commission_payment_followup'
                    })
                else:
                    select_query = """SELECT indent_process_id FROM account_move_indent_process_rel 
                    WHERE account_move_id = (%s)"""
                    self.env.cr.execute(select_query, [self.id])
                    results = self.env.cr.dictfetchall()
                    for indent in results:
                        indent_obj = self.env['indent.process'].browse(indent.get('indent_process_id'))

                        indent_obj.activity_ids._action_done()

                        activity_obj = self.env['mail.activity.type'].search(
                            [('followup_outstanding_payment', '=', True)])
                        model_id = self.env['ir.model'].search([('model', '=', 'indent.process')])

                        if indent_obj.property_supplier_payment_term_id:
                            number_of_days = 0
                            for days in indent_obj.property_supplier_payment_term_id.line_ids:
                                number_of_days += days.days
                        due_date = self.invoice_date + timedelta(days=number_of_days)

                        self.env['mail.activity'].create({
                            'res_model_id': model_id.id,
                            'res_model': model_id.model,
                            'res_id': indent_obj.id,
                            'res_name': indent_obj.name,
                            'activity_type_id': activity_obj.id,
                            'summary': activity_obj.summary,
                            'note': activity_obj.default_description,
                            'date_deadline': due_date,
                            'user_id': activity_obj.default_user_id.id,
                        })
                        indent_obj.write({
                            'debit_note_created': True,
                            'state': 'commission_payment_followup'
                        })
        return return_objects

    def button_draft(self):
        AccountMoveLine = self.env['account.move.line']
        excluded_move_ids = []

        if self._context.get('suspense_moves_mode'):
            excluded_move_ids = AccountMoveLine.search(AccountMoveLine._get_suspense_moves_domain() + [('move_id', 'in', self.ids)]).mapped('move_id').ids

        for move in self:
            if move in move.line_ids.mapped('full_reconcile_id.exchange_move_id'):
                raise UserError(_('You cannot reset to draft an exchange difference journal entry.'))
            if move.tax_cash_basis_rec_id:
                raise UserError(_('You cannot reset to draft a tax cash basis journal entry.'))
            if move.restrict_mode_hash_table and move.state == 'posted' and move.id not in excluded_move_ids:
                raise UserError(_('You cannot modify a posted entry of this journal because it is in strict mode.'))
            # We remove all the analytics entries for this journal
            move.mapped('line_ids.analytic_line_ids').unlink()

        self.mapped('line_ids').remove_move_reconcile()
        self.write({'state': 'draft', 'is_move_sent': False})
        if self.indent_id:
            self.indent_id.write({
                        'debit_note_created': False
                    })
