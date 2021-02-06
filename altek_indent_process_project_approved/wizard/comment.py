from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class CommentWizard(models.TransientModel):
    _name = 'comment.wizard'

    comment = fields.Text('Comment')
    type = fields.Selection([
        ('approved', 'Approved'),
        ('reject', 'rejected'),
    ], string='Type', copy=False, index=True)
    indent_sheet_id = fields.Many2one('indent.sheet')
    model_id = fields.Many2one('ir.model')

    def approval_submission(self):
        if self.type == 'approved':
            """Schedule Activity"""
            """Get the activity"""
            activity_obj = self.env['mail.activity.type'].search([('indent_sheet_approved', '=', True)])

            self.env['mail.activity'].create({
                'res_model_id': self.model_id.id,
                'res_model': self.model_id.model,
                'res_id': self.indent_sheet_id.indent_id.id,
                'res_name': self.indent_sheet_id.indent_id.name,
                'activity_type_id': activity_obj.id,
                'summary': activity_obj.summary,
                'note': activity_obj.default_description,
                'date_deadline': (datetime.now() + timedelta(days=activity_obj.delay_count)).date(),
                'user_id': activity_obj.default_user_id.id,
            })

            self.indent_sheet_id.indent_id.write({
                'state': 'awaiting_order_confirmation'
            })
            self.indent_sheet_id.write({
                'state': 'approved',
                'comments': self.comment
            })
            template_id = self.env.ref('altek_indent_process_project_approved.mail_template_for_approve_indent_sheet')
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = base_url + '/web?login/#id=' + str(
                self._context.get('active_id')) + '&view_type=form&model=indent.sheet'
            self.indent_sheet_id.write({
                'url': url,
            })
            self.env['mail.template'].browse(template_id.id).send_mail(self.id, True)
        else:
            self.indent_sheet_id.write({
                'state': 'rejected',
                'comments': self.comment
            })
            self.indent_sheet_id.indent_id.write({
                'state': 'rejected'
            })
            template_id = self.env.ref('altek_indent_process_project_approved.mail_template_for_cancel_indent_sheet')
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = base_url + '/web?login/#id=' + str(
                self._context.get('active_id')) + '&view_type=form&model=indent.sheet'
            self.indent_sheet_id.write({
                'url': url,
            })
            self.env['mail.template'].browse(template_id.id).send_mail(self.id, True)
