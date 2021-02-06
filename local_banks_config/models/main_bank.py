from odoo import fields, models, api, _


class MainBank(models.Model):
    _name = 'main.bank'

    name = fields.Char('Name')
    code = fields.Char('Code')
    image = fields.Binary("Image", attachment=True)
    branch_ids = fields.One2many('res.bank', 'main_bank_id')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'There cannot be a record with same Code!')
    ]
