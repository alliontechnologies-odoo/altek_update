from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class AssignUserWizard(models.TransientModel):
    _name = 'assign.user.wizard'

    user_id = fields.Many2one('res.users', string="Assigned to", required=1, domain=lambda self: [('groups_id', 'in', self.env.ref('altek_indent_process_project_approved.group_indent_sheet_approval').id)])
    indent_sheet_id = fields.Many2one('indent.sheet')
    model_id = fields.Many2one('ir.model')

    def approval_submission(self):
        self.indent_sheet_id.write({
            'state': 'sent_to_approval'
        })
        self.indent_sheet_id.indent_id.write({
            'state': 'awaiting_approval'
        })

        template_id = self.env.ref('altek_indent_process_project_approved.mail_template_for_approval_indent_sheet')
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/web?login/#id=' + str(
            self._context.get('active_id')) + '&view_type=form&model=indent.sheet'
        self.indent_sheet_id.write({
            'url': url,
        })
        self.env['mail.template'].browse(template_id.id).send_mail(self.id, True)
