# -*- coding: utf-8 -*-

import math

from odoo.addons import decimal_precision as dp
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, MissingError
from odoo.tools import float_round

import re


class MrpUnpackPallet(models.TransientModel):
    _name = "mrp.workcenter.pallet.unpack.wizard"
    _description = "Unpack Pallets"

#     @api.multi
    def unpack_packages(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])

        package_ids = self.env['stock.quant.package'].browse(active_ids)

        quant_ids = package_ids.mapped('quant_ids')

        # Attempt to get the delivery order and sale order from the stock history.
        for package in package_ids:

            # Find the most recent picking that is connected to a sale order.
            history_id = package.quant_ids.mapped('history_ids').filtered(lambda x:
                           x.picking_id.sale_id.id
                           ).sorted(lambda x: x.date, reverse=True)

            # Update the sale_id and delivery_id of the package before unpacking.
            if history_id and history_id[0].picking_id:
                package.sale_id = history_id[0].picking_id.sale_id.id
                package.delivery_id = history_id[0].picking_id.id

        # Unpack - This code is identical to the unpack method of packages, but doesn't show a view after.
        for package in package_ids:
            package.mapped('quant_ids').sudo().write({'package_id': package.parent_id.id})
            package.mapped('children_ids').write({'parent_id': package.parent_id.id})

        # Try to merge quants to clean up any messes.
        quant_ids.merge_stock_quants()

        # Try to reconcile any quants that still exist after merging, with negative stock quants.
        for quant in quant_ids.exists():
            try:
                quant.sudo()._quant_reconcile_negative(False)
            except MissingError:
                print('Record does not exist or has been deleted.')
                continue

