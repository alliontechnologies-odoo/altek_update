# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    _description = 'Register Payment'

    def action_create_payments(self):
        payments = self._create_payments()

        if self._context.get('dont_redirect_to_payments'):
            if self.payment_difference == 0:
                if self.env.context.get('active_model') == 'account.move':
                    invoice_obj = self.env['account.move'].browse(self.env.context.get('active_id'))
                    if invoice_obj.indent_id:
                        invoice_obj.indent_id.activity_ids._action_done()

                        invoice_obj.indent_id.write({
                            'state': 'payments_recovered'
                        })
                    else:
                        select_query = """SELECT indent_process_id FROM account_move_indent_process_rel 
                                            WHERE account_move_id = (%s)"""
                        self.env.cr.execute(select_query, [invoice_obj.id])
                        results = self.env.cr.dictfetchall()
                        for indent in results:
                            indent_obj = self.env['indent.process'].browse(indent.get('indent_process_id'))
                            indent_obj.activity_ids._action_done()

                            indent_obj.write({
                                'state': 'payments_recovered'
                            })
            return True

        action = {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'context': {'create': False},
        }
        if len(payments) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': payments.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', payments.ids)],
            })
        return action
