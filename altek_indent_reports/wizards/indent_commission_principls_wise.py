from odoo import fields, api, models
import xlsxwriter
import base64


class IndentCommissionPrincipleWiseReportWizard(models.TransientModel):
    _name = 'indent.commission.principle.wise.report.wizard'

    from_date = fields.Date("From")
    to_date = fields.Date("To")
    sector_id = fields.Many2one('indent.sector', string="Principle",)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Customer')

    def get_report(self):
        """Creates the invoice report report"""
        # "Setting name for the report"
        report = 'INDENT COMMISSION - PRINCIPAL WISE  - FROM ' + str(self.from_date) + ' to ' + str(self.to_date)
        workbook = xlsxwriter.Workbook(report)

        # Create worksheet 1
        worksheet = workbook.add_worksheet('INDENT COMMISSION - PRINCIPAL WISE')
        worksheet.set_landscape()

        heading = workbook.add_format({'bold': True, 'align': 'left', 'font_size': '14'})
        heading_2 = workbook.add_format({'bold': True, 'align': 'left', 'font_size': '12'})
        font_right = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'font_size': 10, 'num_format': '#,##0.00', 'border': 1})
        font_center = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'font_size': 10, 'border': 1})
        font_center_bold = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'font_size': 10, 'bold': True, 'border': 1})

        worksheet.set_column('A:B', 16)
        worksheet.set_column('B:C', 11)
        worksheet.set_column('C:D', 45)
        worksheet.set_column('D:F', 16)
        worksheet.set_column('F:G', 16)
        worksheet.set_column('G:K', 16)
        worksheet.set_column('K:L', 16)
        worksheet.set_column('L:N', 16)
        worksheet.set_row(0, 20)

        row = 0
        col = 0

        # Write data on the worksheet
        worksheet.write(row, col, str(self.company_id.name).upper(), heading)

        worksheet.write(row + 4, col, "INDENT COMMISSION - PRINCIPAL WISE  - FROM " + str(self.from_date) + ' TO ' + str(self.to_date), heading_2)

        col = 0
        row = 6

        worksheet.write(row, col, "Sales person", font_center_bold)
        worksheet.write(row, col + 1, "Indent income no", font_center_bold)
        worksheet.write(row, col + 2, "Month of Recognition", font_center_bold)
        worksheet.write(row, col + 3, "Supplier name", font_center_bold)
        worksheet.write(row, col + 4, "Product name", font_center_bold)
        worksheet.write(row, col + 5, "Currency type", font_center_bold)
        worksheet.write(row, col + 6, "Indent  Value", font_center_bold)
        worksheet.write(row, col + 7, "Commission %", font_center_bold)
        worksheet.write(row, col + 8, "Commission Value (USD/EURO)", font_center_bold)
        worksheet.write(row, col + 9, "Commission Value (LKR)", font_center_bold)

        row += 1

        # for credit_note in credit_notes:
        #     worksheet.write(row, col, credit_note.name, font_center)
        #     worksheet.write(row, col + 1, str(credit_note.date), font_center)
        #     worksheet.write(row, col + 2, credit_note.partner_id.name, font_center)
        #     worksheet.write(row, col + 3, credit_note.partner_id.vat or None, font_center)
        #     worksheet.write(row, col + 4, credit_note.amount_total, font_right)
        #     worksheet.write(row, col + 5, credit_note.amount_tax, font_right)
        #     worksheet.write(row, col + 6, credit_note.reversed_entry_id.name, font_right)
        #     worksheet.write(row, col + 7, credit_note.reversed_entry_id.amount_total, font_right)
        #     row += 1
        workbook.close()
        return report

    def download_report(self):
        """Get the report type from the context and downloads the report"""
        report = self.get_report()

        my_report_data = open(report, 'rb+')
        f = my_report_data.read()
        values = {
            'name': 'INDENT COMMISSION - PRINCIPAL WISE ' + str(self.from_date) + ' to ' + str(self.to_date),
            'res_model': 'ir.ui.view',
            'res_id': False,
            'type': 'binary',
            'public': True,
            'datas': base64.encodestring(f),
        }
        attachment_id = self.env['ir.attachment'].sudo().create(values)
        download_url = '/web/content/' + str(attachment_id.id) + '?download=True'
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "new",
        }