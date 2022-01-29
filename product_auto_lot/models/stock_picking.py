# -*- coding: utf-8 -*-

from collections import namedtuple
import json
import time

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
# from odoo.addons.procurement.models import procurement
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'barcodes.barcode_events_mixin']
    
    stock_pickup_date = fields.Datetime('Pickup Date',
                                help="Pickup date of all deliveries bound for customer. ",
                                store=True,
                                inverse = '_set_pickup')

    def _set_pickup(self):
        sale_order = self.sale_id

        if sale_order.pickup_date != self.stock_pickup_date:
            sale_order.write({'pickup_date': self.stock_pickup_date})

        if self.move_lines:
            for move in self.move_lines.filtered(lambda x: x.state not in ['done', 'cancel']):
                move.write({'stock_pickup_date': self.stock_pickup_date})


    production_id = fields.Many2one('mrp.production', 'Production Order')

    picking_lot_ids = fields.One2many('stock.picking.lot',
                                      'picking_id',
                                      string='Lot Codes',
                                      states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})

    package_quant_ids = fields.Many2many(
        'stock.quant',
        string='Packaged Quants',
        readonly=True)

    memo = fields.Text('Memo',
                       copy=False,
                       states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})

    pallet_operation_ids = fields.One2many('stock.pallet.operation', 'picking_id',
                                           string='Pallet Operations',
                                           states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})

#     @api.multi
    def do_unreserve(self):
        """
          Will remove all quants for picking in picking_ids
        """
        super(StockPicking, self).do_unreserve()
        for picking in self:
            picking.pallet_operation_ids.unlink()
            picking.picking_lot_ids.unlink()
            picking.memo = False

#     @api.multi
    def write(self, vals):
        res = super(StockPicking, self).write(vals)
        for picking in self:
            if picking.state in ['done', 'cancel']:
                continue
            if len(picking.pallet_operation_ids) == 0:
                picking.picking_lot_ids.unlink()
            # Unlink any pallets that may have been removed from the memo.
            if 'memo' in vals:
                for pallet_op in picking.pallet_operation_ids:

                    memo_codes = str(vals.get('memo')).split('\n')
                    if pallet_op.pallet_id.name not in memo_codes:

                        pallet_op.unlink()

                        for picking_lot in picking.picking_lot_ids:
                            if picking_lot.lot_id not in picking.pallet_operation_ids.exists().mapped('pallet_id').mapped(
                                    'default_lot_code_id'):
                                picking_lot.quantity = 0
                            else:
                                picking_lot.quantity = len(picking.pallet_operation_ids.exists().mapped('pallet_id').filtered(
                                    lambda x: x.default_lot_code_id.id == picking_lot.lot_id.id))
        return res

    @api.onchange('pallet_operation_ids')
    def onchange_pallet_operation_ids(self):
        if self._context.get('pallet_manual_input'):
            if hasattr(self, '_origin'):
                for pallet_id in self._origin.pallet_operation_ids:
                    if pallet_id not in self.pallet_operation_ids:
                        if pallet_id.pallet_id.name in str(self.memo):
                            self.memo = self.memo.replace(pallet_id.pallet_id.name + '\n', '')
                            self.memo = self.memo.replace(pallet_id.pallet_id.name, '')

            for picking_lot in self.picking_lot_ids:
                if picking_lot.lot_id not in self.pallet_operation_ids.mapped('pallet_id').mapped('default_lot_code_id'):
                    picking_lot.quantity = 0
                else:
                    picking_lot.quantity = len(self.pallet_operation_ids.mapped('pallet_id').filtered(lambda x: x.default_lot_code_id.id == picking_lot.lot_id.id))
            return
        # If pallet_operation_ids becomes empty, clear out picking_lot_ids

        if len(self.pallet_operation_ids) == 0:
            for picking_lot in self.picking_lot_ids:
                picking_lot.quantity = 0

    @api.onchange('memo')
    def onchange_memo(self):
        if self._context.get('manual_input') and self.memo and self.state not in ['done', 'cancel']:
            memo_codes = []
            if self.memo:
                memo_codes = self.memo.split('\n')
                # Iterate over all memo codes and attempt to add any pallets found.
                for code in memo_codes:
                    pallet = self.env['stock.quant.package'].search([('name', '=', code)])
                    if pallet:
                        self._check_destination_package(pallet)

    def _check_destination_package(self, package):
        if not package.quant_ids and not package.production_id.id:
            raise UserError(
                "The scanned package is empty:\n "
                "\n Package Code: " + str(package.name))

        # if not package.quant_ids and package.production_id.id:
        #     raise UserError("Please open the pack operation to scan pallet codes.")
        # package = self.env['stock.quant.package'].search([('name', '=', barcode)], limit=1)
        if package and package.default_lot_code_id and package.production_id:
            if package.id in self.pallet_operation_ids.mapped('pallet_id').ids:
                # Already entered
                return True
            else:
                self.pallet_operation_ids += self.pallet_operation_ids.new(
                    {'pallet_id': package.id})

                if package.default_lot_code_id.id not in self.picking_lot_ids.mapped('lot_id').ids:
                    self.picking_lot_ids += self.picking_lot_ids.new({
                        'lot_id': package.default_lot_code_id.id,
                        'product_id': package.default_lot_code_id.product_id.id,
                        'quantity': 1
                    })
                else:
                    lot = self.picking_lot_ids.filtered(lambda x: x.lot_id.id == package.default_lot_code_id.id)
                    lot[0].quantity += 1

            # Update the memo
            if self.memo and package.name not in self.memo:
                self.memo += package.name + '\n'
            elif self.memo is False:
                self.memo = package.name + '\n'
            return True

        return super(StockPicking, self)._check_destination_package(package)

    def on_barcode_scanned(self, barcode):
        if not self.picking_type_id.barcode_nomenclature_id:
            # Logic for packages in source location
            if self.pack_operation_product_ids:
                package_source = self.env['stock.quant.package'].search(
                    [('name', '=', barcode), ('location_id', 'child_of', self.location_id.id)], limit=1)

                # Select package to move if it contains quants.
                if package_source \
                        and package_source.id not in self.pack_operation_pack_ids.mapped('package_id').ids \
                        and package_source.quant_ids:
                    new_res = self._check_package_to_move(package_source)
                    if new_res:
                        return
        else:
            parsed_result = self.picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)
            # Logic for packages in source location
            if parsed_result['type'] == 'package':
                if self.pack_operation_product_ids:
                    package_source = self.env['stock.quant.package'].search(
                        [('name', '=', barcode), ('location_id', 'child_of', self.location_id.id)], limit=1)

                    # Select package to move if it contains quants.
                    if package_source \
                            and package_source.id not in self.pack_operation_pack_ids.mapped('package_id').ids \
                            and package_source.quant_ids:
                        new_res = self._check_package_to_move(package_source)
                        if new_res:
                            return

        return super(StockPicking, self).on_barcode_scanned(barcode)

    def _check_package_to_move(self, package):
        self.ensure_one()

        for pack_operation in self._origin.pack_operation_product_ids:
            if pack_operation.product_id.id in package.quant_ids.mapped('product_id').ids:
                # Add a pack line based on the package quants.
                for vals in self._origin._prepare_pack_ops(package.quant_ids, {}):
                    vals['fresh_record'] = False
                    vals['qty_done'] = 1.0
                    vals['is_done'] = True

                    self.pack_operation_pack_ids = [(4, x.id) for x in self.pack_operation_pack_ids] + [(0, 0, vals)]

                return True

#     @api.multi
    def unlink(self):
        if self.group_id:
            raise ValidationError("Stock pickings associated with a procurement group cannot be deleted")
        return super(StockPicking, self).unlink()

#     @api.multi
    def do_new_transfer(self, context={}, from_code=False):
        self.ensure_one()

        res = super(StockPicking, self).do_new_transfer()
        if isinstance(from_code, bool) and from_code == True:
            # Just in case, we make sure recompute_pack_op is False to prevent the Recompute button from appearing.
            self.recompute_pack_op = False
            if res is None:
                return
            if res.get('res_model') and res.get('res_model') == 'stock.immediate.transfer':
                context = res['context']
                wizard = self.env['stock.immediate.transfer'].with_context(context).browse(res['res_id'])

                return res
            elif res.get('res_model') and res.get('res_model') == 'stock.backorder.confirmation' and res.get('res_id'):
                context = res['context']
                wizard = self.env['stock.backorder.confirmation'].with_context(context).browse(res['res_id'])

                wizard.process()

                return wizard

        # Set the delivery_id and sale_id on the package.
        if self.sale_id.id and self.pallet_operation_ids:
            self.pallet_operation_ids.mapped('pallet_id').write({'delivery_id': self.id,
                                                                 'sale_id': self.sale_id.id,
                                                                 })

        return res

    # this is a copy of put_in_pack, this is so delivery won't inherit and prevent us from getting the package_id.
#     @api.multi
    def put_in_pallet(self, package=False):
        # TDE FIXME: reclean me
        QuantPackage = self.env["stock.quant.package"]

        for pick in self:
#             operations = [x for x in pick.pack_operation_ids if x.qty_done > 0 and (not x.result_package_id)]
            operations = [x for x in pick.move_line_ids if x.qty_done > 0 and (not x.result_package_id)]
#             pack_operation_ids = self.env['stock.pack.operation']
            pack_operation_ids = self.env['stock.move.line']
            for operation in operations:
                # If we haven't done all qty in operation, we have to split into 2 operation
                op = operation
                if operation.qty_done < operation.product_qty:
                    new_operation = operation.copy({'product_qty': operation.qty_done, 'qty_done': operation.qty_done})

                    operation.write({'product_qty': operation.product_qty - operation.qty_done, 'qty_done': 0})
#                     if operation.pack_lot_ids:
#                         packlots_transfer = [(4, x.id) for x in operation.pack_lot_ids]
#                         new_operation.write({'pack_lot_ids': packlots_transfer})

                        # the stock.pack.operation.lot records now belong to the new, packaged stock.pack.operation
                        # we have to create new ones with new quantities for our original, unfinished stock.pack.operation
#                         new_operation._copy_remaining_pack_lot_ids(operation)

                    op = new_operation
                pack_operation_ids |= op
            if operations:
                pack_operation_ids.check_tracking()
                if package is False:
                    package = QuantPackage.create({})
                pack_operation_ids.write({'result_package_id': package.id})
            else:
                raise UserError(_('Please process some quantities to put in the pack first!'))
        return package


class StockPalletOperation(models.Model):
    _name = 'stock.pallet.operation'

    picking_id = fields.Many2one('stock.picking', string='Picking', readonly=True)
    pallet_id = fields.Many2one('stock.quant.package', string='Pallet', readonly=True)
    lot_id = fields.Many2one('stock.production.lot', related='pallet_id.default_lot_code_id', store=False, readonly=True)

    @api.model
    def create(self, vals):
        picking_id = self.env['stock.picking'].browse(vals.get('picking_id'))

        # Check if the pallet is some how already on the picking.
        if vals.get('pallet_id') in picking_id.mapped('pallet_operation_ids.pallet_id').ids:
            raise ValidationError("This pallet has already been scanned on this picking.")

        # Check if the picking is some how already done or in cancelled state.
        if picking_id.state in ['done', 'cancel']:
            raise ValidationError("You cannot add pallets to a finished/cancelled picking.")

        res = super(StockPalletOperation, self).create(vals)

#         if res.lot_id:
#             pack_ops = res.picking_id.move_line_ids_without_package.filtered(lambda x: x.product_id.id == res.lot_id.product_id.id)
#             if pack_ops:
#                 pack_lot_ids = pack_ops.pack_lot_ids.filtered(lambda x: x.lot_id.id == res.lot_id.id)
#                 if pack_lot_ids:
#                     pack_lot_ids[0].do_plus()
# 
#                 else:
#                     pack_ops[0].pack_lot_ids.create({
#                         'lot_id': res.lot_id.id,
#                         'qty': 0,
#                         'plus_visible': False,
#                         'operation_id': pack_ops[0].id
#                     }).do_plus()
#                     # Locate pack lot that has zero done and greater than zero to do, then delete it.
#                     pack_ops.pack_lot_ids.filtered(lambda x: x.lot_id.id and x.qty_todo > 0 and x.qty == 0).unlink()
# 
#             else:
#                 # Create the pack operation.
#                 pack_ops.create({
#                     'product_id': res.lot_id.product_id.id,
#                     'product_qty': 0,
#                     'qty_done': 1,
#                     'product_uom_id': res.lot_id.product_uom_id.id,
#                     'picking_id': res.picking_id.id,
#                     'location_id': res.picking_id.location_id.id,
#                     'location_dest_id': res.picking_id.location_dest_id.id,
#                     'pack_lot_ids': [(0, 0, {
#                             'lot_id': res.lot_id.id,
#                             'qty': 1,
#                             'plus_visible': False,
#                         })]
#                 })

        return res

#     @api.multi
    def unlink(self):
        for pallet in self:
            pack_lot_ids = pallet.picking_id.move_line_ids_without_package.mapped('lot_id').filtered(lambda x: x.lot_id.id == pallet.lot_id.id)
            picking_lot_ids = pallet.mapped('picking_id').picking_lot_ids.filtered(lambda x: x.lot_id.id == pallet.lot_id.id)

            # Decrease quantity by 1
            if pack_lot_ids:
                pack_lot_ids[0].do_minus()
                # Unlink if 0 or less than.
                if pack_lot_ids[0].qty <= 0:
                    pack_op = pack_lot_ids[0].operation_id
                    pack_lot_ids[0].unlink()
                    # Unlink the pack_op if it has zero to do, and zero done.
                    if pack_op.product_qty == 0 and pack_op.qty_done == 0:
                        pack_op.unlink()

            if picking_lot_ids:
                picking_lot_ids[0].do_minus()

            # TODO: Re-enable this
            if pallet.picking_id.memo and pallet.pallet_id.name in pallet.picking_id.memo:
                pallet.picking_id.memo = pallet.picking_id.memo.replace(pallet.pallet_id.name + '\n', '')

        return super(StockPalletOperation, self).unlink()


class PickingLotQuantity(models.Model):
    _name = 'stock.picking.lot'

    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    lookup_code = fields.Char(string='Product Code', related='product_id.lookup_code', readonly=True, store=False)
    lot_id = fields.Many2one('stock.production.lot', string='Lot Code', required=True, readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Picking', readonly=True)
    quantity = fields.Float('Quantity', default=0, readonly=True)

#     @api.multi
    def write(self, vals):
        res = super(PickingLotQuantity, self).write(vals)
        for lot in self:
            if lot.quantity <= 0 and lot.exists():
                lot.unlink()
        return res

    def action_add_quantity(self, quantity):
        for lot in self:
            lot.quantity = lot.quantity + quantity
            # lot.write({'quantity': lot.quantity + quantity})

        return True

#     @api.multi
    def do_plus(self):
        return self.action_add_quantity(1)

#     @api.multi
    def do_minus(self):
        return self.action_add_quantity(-1)

