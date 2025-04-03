from odoo import models, fields, api
from odoo.exceptions import ValidationError
import datetime

class AsientoFinal(models.Model):
    _name = 'final.generator'

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Moneda'
    )
    
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True
    )
    year = fields.Selection(
        selection=[(str(y), str(y)) for y in range(2023, (datetime.datetime.now().year)+1)], 
        string='Año'
    )
    date = fields.Date('Fecha de cierre',compute='_compute_date',store=True)
    patrimonial = fields.Many2one(
        'account.move', 
        string='Asiento Patrimonial',
        help='Asiento patrimonial',
        ondelete='set null',  # o 'cascade' o 'restrict' según necesites
        copy=False,
        domain=[('move_type', '=', 'entry')],  # Filtra solo asientos regulares si es necesario
        readonly=True,  # Si no debe ser editable directamente
        index=True  # Para mejor rendimiento en búsquedas
    )
    refundicion = fields.Many2one(
        'account.move', 
        string='Asiento de Refundición',
        help='Asiento de refundición',
        ondelete='set null',  # o 'cascade' o 'restrict' según necesites
        copy=False,
        domain=[('move_type', '=', 'entry')],  # Filtra solo asientos regulares si es necesario
        readonly=True,  # Si no debe ser editable directamente
        index=True  # Para mejor rendimiento en búsquedas
    )
    line_ids = fields.One2many('final.generator.line', 'final_id', string='Líneas')
    patrimonial_line_ids = fields.One2many(
        'final.generator.line',
        'final_id',
        compute ='_compute_filtered_lines',
        domain=[('type', '=', 'patrimonial')]
    )

    refundicion_line_ids = fields.One2many(
        'final.generator.line',
        'final_id',
        compute ='_compute_filtered_lines',
        domain=[('type', '=', 'refundicion')]
    )
    total_patrimonial = fields.Monetary('Total Patrimonial')
    total_refundicion = fields.Monetary('Total Refundición')
    
    @api.depends('year')
    def _compute_date(self):
        for record in self:
            if record.year:
                year_int = int(record.year)
                record.date = datetime.date(year_int, 12, 31)
            else:
                record.date = False
        
    @api.depends('line_ids', 'line_ids.type')
    def _compute_filtered_lines(self):
        for record in self:
            # Filtramos las líneas según su tipo
            record.patrimonial_line_ids = record.line_ids.filtered(lambda l: l.type == 'patrimonial')
            record.refundicion_line_ids = record.line_ids.filtered(lambda l: l.type == 'refundicion')
    
    def action_create_move(self):
        """ Crea las líneas de asiento en el modelo final.generator.line """
        self.ensure_one()
        
        # Eliminar líneas existentes si las hay (opcional)
        self.line_ids.unlink()
        
        accounts = self.env['account.account'].search([('deprecated', '=', False)])
        line_vals = []
        total_debit = 0.0
        total_credit = 0.0
    
        for account in accounts:
            balance = self._get_balance(account)
            if balance:
                first_digit = account.code[0]
                line_type = False
                
                if first_digit in ('1', '2', '3'):
                    line_type = 'patrimonial'
                elif first_digit in ('4', '5'):
                    line_type = 'refundicion'
                if line_type:
                    debit = -balance if balance < 0 else 0.0
                    credit = balance if balance > 0 else 0.0
                    
                    line_vals.append((0, 0, {
                        'type': line_type,
                        'account_id': account.id,
                        'debit': debit,
                        'credit': credit,
                        'balance': balance,
                        'final_id': self.id,
                    }))
                    total_debit += debit
                    total_credit += credit
    
        if not line_vals:
            raise ValidationError("No hay cuentas con saldo para transferir.")
    
        # Crear todas las líneas
        self.write({'line_ids': line_vals})

    def _get_balance(self, account):
        """ Obtiene el saldo de la cuenta hasta la fecha indicada, solo de asientos publicados """
        self.ensure_one()
        query = """
            SELECT SUM(debit - credit) FROM account_move_line aml
            JOIN account_move am ON aml.move_id = am.id
            WHERE aml.account_id = %s AND aml.date <= %s AND am.state = 'posted'
        """
        self.env.cr.execute(query, (account.id, self.date))
        result = self.env.cr.fetchone()
        return result[0] if result and result[0] else 0.0

    def generar_asientos(self):
        self.ensure_one()
        
        # Verificar que hay líneas para procesar
        if not self.line_ids:
            raise ValidationError("No hay líneas contables para generar los asientos.")
        
        # Eliminar asientos existentes si los hay
        if self.patrimonial:
            self.patrimonial.button_draft()
            self.patrimonial.unlink()
        if self.refundicion:
            self.refundicion.button_draft()
            self.refundicion.unlink()
        
        # Obtener la cuenta de contrapartida (ajusta esto según tu necesidad)
        # Por ejemplo, podrías usar una cuenta configurable o una específica
        journal = self.env['account.journal'].browse(39)
        cuenta_contrapartida = self.env['account.account'].search([
            ('code', '=', '3.3.1.01.010'),  # Cambia por el código de tu cuenta de contrapartida
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not cuenta_contrapartida:
            raise ValidationError("No se encontró la cuenta de contrapartida configurada.")
        
        # Crear asiento patrimonial
        if self.patrimonial_line_ids:
            lineas_patrimonial = []
            total_debito = 0
            total_credito = 0
            
            for linea in self.patrimonial_line_ids:
                lineas_patrimonial.append((0, 0, {
                    'account_id': linea.account_id.id,
                    'name': f"Cierre patrimonial {self.year}",
                    'debit': linea.debit,
                    'credit': linea.credit,
                }))
                total_debito += linea.debit
                total_credito += linea.credit
            
            # Agregar línea de contrapartida
            if total_debito > total_credito:
                lineas_patrimonial.append((0, 0, {
                    'account_id': cuenta_contrapartida.id,
                    'name': f"Contrapartida patrimonial {self.year}",
                    'credit': total_debito - total_credito,
                }))
            elif total_credito > total_debito:
                lineas_patrimonial.append((0, 0, {
                    'account_id': cuenta_contrapartida.id,
                    'name': f"Contrapartida patrimonial {self.year}",
                    'debit': total_credito - total_debito,
                }))
            
            asiento_patrimonial = self.env['account.move'].create({
                'move_type': 'entry',
                'date': self.date,
                'ref': f"Cierre Patrimonial {self.year}",
                'journal_id': journal.id,
                'line_ids': lineas_patrimonial,
                'company_id': self.company_id.id,
            })
            asiento_patrimonial.action_post()
            self.patrimonial = asiento_patrimonial
        
        # Crear asiento de refundición
        if self.refundicion_line_ids:
            lineas_refundicion = []
            total_debito = 0
            total_credito = 0
            
            for linea in self.refundicion_line_ids:
                lineas_refundicion.append((0, 0, {
                    'account_id': linea.account_id.id,
                    'name': f"Cierre refundición {self.year}",
                    'debit': linea.debit,
                    'credit': linea.credit,
                }))
                total_debito += linea.debit
                total_credito += linea.credit
            
            # Agregar línea de contrapartida
            if total_debito > total_credito:
                lineas_refundicion.append((0, 0, {
                    'account_id': cuenta_contrapartida.id,
                    'name': f"Contrapartida refundición {self.year}",
                    'credit': total_debito - total_credito,
                }))
            elif total_credito > total_debito:
                lineas_refundicion.append((0, 0, {
                    'account_id': cuenta_contrapartida.id,
                    'name': f"Contrapartida refundición {self.year}",
                    'debit': total_credito - total_debito,
                }))
            
            asiento_refundicion = self.env['account.move'].create({
                'move_type': 'entry',
                'date': self.date,
                'ref': f"Cierre Refundición {self.year}",
                'journal_id': self.env['account.journal'].search([
                    ('type', '=', 'general'),
                    ('company_id', '=', self.company_id.id)
                ], limit=1).id,
                'line_ids': lineas_refundicion,
                'company_id': self.company_id.id,
            })
            asiento_refundicion.action_post()
            self.refundicion = asiento_refundicion
        
        # Actualizar totales
        self.total_patrimonial = sum(self.patrimonial_line_ids.mapped('balance'))
        self.total_refundicion = sum(self.refundicion_line_ids.mapped('balance'))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Asientos generados',
                'message': 'Los asientos contables se han generado correctamente.',
                'sticky': False,
            }
        }



class LineasDeAsiento(models.Model):
    _name = 'final.generator.line'
    
    company_currency_id = fields.Many2one(
        'res.currency', 
        string='Moneda', 
        readonly=True,
        default=lambda self: self.env.company.currency_id.id,
        help="Moneda de la compañía"
    )
    account_id = fields.Many2one('account.account',string='Cuenta', ondelete='set null',readonly=True)
    debit = fields.Monetary('Débito', currency_field='company_currency_id')
    credit = fields.Monetary('Crédito', currency_field='company_currency_id')
    balance = fields.Monetary('Balance', currency_field='company_currency_id')
    type = fields.Selection([('refundicion','Refundición'),('patrimonial','Patrimonial')])
    final_id = fields.Many2one('final.generator',string='Asiento Final')
    