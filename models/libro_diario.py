from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)
class LibroDiario(models.TransientModel):
    _name = 'final.libro_diario'
    _description = 'Filtros para Libro Diario'

    date_from = fields.Date('Desde', required=True)
    date_to = fields.Date('Hasta', required=True)
    starting_number = fields.Integer('Número de Inicio', default=1)
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError("La fecha 'Desde' no puede ser mayor que la fecha 'Hasta'")
                
                
    def action_generate_report(self):
        self.ensure_one()
        move_ids = self.env['account.move'].search([
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', '=', 'posted')
            ], order='date, id')
            
        # Asignar solo los IDs, no los registros completos
        #self.move_ids = [(6, 0, move_ids.ids)]
        return {
            'type': 'ir.actions.report',
            'report_name': 'l10n_ar_asientos_de_cierre.report_final',
            'report_type': 'qweb-pdf',
            'data': {
                'doc_model': 'account.move',
                'item_ids': move_ids.ids,
                'items': move_ids,
                'start_number': self.starting_number,
                'date_from': self.date_from,
                'date_to': self.date_to,
            },
            'context': {
                'active_model': 'account.move',
                'active_ids': move_ids.ids,
            }
        }