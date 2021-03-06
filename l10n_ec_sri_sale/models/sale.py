# -*- coding: utf-8 -*-
import odoo.addons.decimal_precision as dp
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        super(SaleOrder, self)._amount_all()
        for order in self:
            so_lines = order.order_line

            impgrav_lines = so_lines.filtered(
                lambda l: 'ImpGrav' in l.tax_id.mapped('tax_group_id.name'))
            baseimpgrav = sum(line.price_subtotal for line in impgrav_lines) or 0.00

            # Restamos las líneas para obtener el valor no declarado.
            so_lines -= impgrav_lines

            nograiva_lines = so_lines.filtered(
                lambda l: 'NoGraIva' in l.tax_id.mapped('tax_group_id.name'))
            basenograiva = sum(line.price_subtotal for line in nograiva_lines) or 0.00
            so_lines -= nograiva_lines

            imponible_lines = so_lines.filtered(
                lambda l: 'Imponible' in l.tax_id.mapped('tax_group_id.name'))
            baseimponible = sum(line.price_subtotal for line in imponible_lines) or 0.00
            so_lines -= imponible_lines

            impexe_lines = so_lines.filtered(
                lambda l: 'ImpExe' in l.tax_id.mapped('tax_group_id.name'))
            baseimpexe = sum(line.price_subtotal for line in impexe_lines) or 0.00
            so_lines -= impexe_lines

            no_declarado = sum(line.price_subtotal for line in so_lines) or 0.00

            # Desde las líneas de impuesto pues requerimos el valor.
            montoiva = sum(line.montoiva for line in order.order_line)
            montoice = sum(line.montoice for line in order.order_line)

            # Campos informativos de uso interno.
            subtotal = basenograiva + baseimponible + baseimpgrav + baseimpexe
            total = subtotal + montoiva + montoice

            order.update({
                'basenograiva': basenograiva,
                'baseimponible': baseimponible,
                'baseimpgrav': baseimpgrav,
                'baseimpexe': baseimpexe,
                'montoiva': montoiva,
                'montoice': montoice,
                'subtotal': subtotal,
                'total': total,
                'no_declarado': no_declarado,
            })

    # Campos informativos del SRI.
    basenograiva = fields.Monetary(string="Subtotal no grava I.V.A.", compute=_amount_all, )
    baseimponible = fields.Monetary(string="Subtotal I.V.A. 0%", compute=_amount_all, )
    baseimpgrav = fields.Monetary(string="Subtotal gravado con I.V.A.", compute=_amount_all, )
    baseimpexe = fields.Monetary(string="Subtotal excento de I.V.A.", compute=_amount_all, )
    montoiva = fields.Monetary(string="Monto I.V.A", compute=_amount_all, )
    montoice = fields.Monetary(string="Monto I.V.A", compute=_amount_all, )

    # Otros campos informativos de uso interno.
    # No se usa los campos propios de Odoo porque estos restan las retenciones.
    total = fields.Monetary(
        string='TOTAL', compute=_amount_all, )
    subtotal = fields.Monetary(
        string='SUBTOTAL', compute=_amount_all, )
    no_declarado = fields.Monetary(
        string='VALOR NO DECLARADO', compute=_amount_all, )

    @api.multi
    def action_invoice_create(self, grouped=False, final=False):
        res = super(SaleOrder, self).action_invoice_create(grouped=grouped, final=final)
        inv = self.env['account.invoice'].browse(res)
        for i in inv:
            i.compute_sri_invoice_amounts()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def get_price(self):
        price_unit = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        return price_unit

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute montoiva and montoice for the SO line.
        """
        super(SaleOrderLine, self)._compute_amount()
        for line in self:
            price = line.get_price()
            taxes = line.tax_id.compute_all(
                price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_id)
            montoiva = 0.00
            montoice = 0.00

            for tax in taxes.get('taxes', []):
                impuesto = self.env['account.tax'].browse(tax['id'])
                if impuesto and impuesto.tax_group_id.name == 'ImpGrav':
                    montoiva += tax.get('amount')
                elif impuesto and impuesto.tax_group_id.name == 'Ice':
                    montoice += tax.get('amount')
            line.update({
                'montoiva': montoiva,
                'montoice': montoice,
            })

    montoiva = fields.Float(string="Monto I.V.A", compute=_compute_amount, digits=(9, 6), )
    montoice = fields.Float(string="Monto I.V.A", compute=_compute_amount, digits=(9, 6), )
