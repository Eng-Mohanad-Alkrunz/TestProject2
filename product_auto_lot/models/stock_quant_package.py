
from datetime import datetime

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare, float_round
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class QuantPackage(models.Model):
    _inherit = "stock.quant.package"

    # I didn't want to do it this way, but my hands were tied.
    production_id = fields.Many2one('mrp.production', string='Production Order', copy=False)
    pallet_number = fields.Integer('Pallet Number')
    default_lot_code_id = fields.Many2one('stock.production.lot', string='Default Lot Code', copy=False)
    routing_id = fields.Many2one('mrp.routing.workcenter', string='Routing')

    sale_id = fields.Many2one('sale.order', string='Sale Order')
    delivery_id = fields.Many2one('stock.picking', string='Delivery Order')
    shipping_date = fields.Datetime('Shipping Date', related='delivery_id.stock_pickup_date', store=False)
    new_bbd_format = fields.Char('New BBD', calculate='_new_bbd_format')

#     supervisor = fields.Many2one('mrp.supervisor', string='Supervisor Verification')
    note = fields.Char(string='Note')

    _sql_constraints = [
        ('package_name_uniq', 'unique(name)', _("A package or pallet must have a unique code!")),
    ]

    single_product_package = fields.Boolean('Single Product Package', help='True if all products in package are the same product.', compute='_single_product_package')

    def _single_product_package(self):
        return

#     @api.multi
    def _get_routing_id(self):
        for rec in self:
            if rec.production_id:
                rec.routing_id = rec.production_id.routing_id

#     @api.multi
    def _new_bbd_format(self):
        for rec in self:
            if rec.production_id.new_bbd_format:
                rec.new_bbd_format = rec.production_id.new_bbd_format

#     @api.multi
    def unlink(self):
        # Only allow ERP Managers to delete packages that have lot code/Production Order
        if self.env.user.has_group('base.group_erp_manager') is False:
            if any(package.production_id and package.production_id.state in ['done', 'progress'] and package.default_lot_code_id for package in self):
                raise UserError(_('You do not have sufficient permissions to delete these '
                                  'packages. Check with an administrator.'))
            if any(package.sale_id for package in self):
                raise UserError(_('You cannot delete packages that have been shipped to a customer.'))

        return super(QuantPackage, self).unlink()

