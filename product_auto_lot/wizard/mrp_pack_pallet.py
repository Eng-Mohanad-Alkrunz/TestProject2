# -*- coding: utf-8 -*-

import math

from odoo.addons import decimal_precision as dp
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round

import re


class MrpWorkcenterPalletWizard(models.TransientModel):
    _name = "mrp.workcenter.pallet.pack.wizard"
    _description = "Workcenter Pallet Code Generator"

    # TODO: Review and improve behavior when MO quantity causes change in initial demand.

    # related data
    production_id = fields.Many2one('mrp.production', 'Production Order', store=True)
    warehouse_id = fields.Many2one('stock.warehouse', related='production_id.picking_type_id.warehouse_id', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    location_source_id = fields.Many2one('stock.location', related='production_id.location_dest_id', readonly=True)
    manu_packing_type_id = fields.Many2one('stock.picking.type', related='production_id.picking_type_id.warehouse_id.manu_packing_type_id', readonly=True)
    picking_ids = fields.Many2many('stock.picking', string='Pickings', related='production_id.picking_ids', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', related='production_id.product_id', readonly=True)
    print_only = fields.Boolean('Print Only', help='If true, everything is completed and only printing is available.', readonly=True)
    nothing_to_print = fields.Boolean('Nothing to Print', help='If true, nothing can be printed.', readonly=True)
    warehouse_code = fields.Char('Warehouse Code', related='warehouse_id.lot_abbv', readonly=True)

    date_backdating = fields.Datetime(string='Actual Movement Date')

    # computed data
    lot_ids = fields.Many2many('stock.production.lot', string='Lots', store=True, readonly=True)

    page_from = fields.Integer('Page From')
    page_to = fields.Integer('Page To')

    # user defined variables
    product_qty_per_pallet = fields.Float('Product Quantity per Pallet', default=1, digits=dp.get_precision('Product Unit of Measure'), required=True)
    qty_of_pallets = fields.Float('Quantity of Pallets', compute='_get_pallets_quantity')
    qty_to_pack = fields.Float('Quantity to Pack', compute='_get_pallets_quantity')

    no_palletizing_pickings = fields.Boolean('Palletizing Missing')

    number_of_pallets = fields.Integer('Number of Pallets to Pack', default=1, store=True)
    description = fields.Char('Description', readonly=True)
    sequence_step = fields.Selection([
                                    ('even_odd', 'Even/Odd'),
                                    ('serial', 'Serial')], 'Sequence Step',
                                    default='serial', required=1,
                                    help='When using Even or Odd, make sure the '
                                         'starting pallet number is even or odd number.')

    location_dest_id = fields.Many2one('stock.location', string='Destination Location', required=False)
    location_src_id = fields.Many2one('stock.location', string='Source Location', related='production_id.location_dest_id', readonly=True)

#     @api.multi
    def create_palletizing_picking(self, location_src=False, location_dest=False):
        # Check if any open palletizing pickings exist
        if len(self.picking_ids.filtered(lambda x: x.picking_type_id.id == self.manu_packing_type_id.id
                                                   and x.state not in ['done', 'cancel'])) > 0:
            return

        completed_picking_ids = self.picking_ids.filtered(lambda x: x.picking_type_id.id == self.manu_packing_type_id.id
                                                           and x.state in ['done', 'cancel'])

        location_src = self.production_id.picking_type_id.warehouse_id.manu_packing_type_id.default_location_src_id.id
        location_dest = self.production_id.picking_type_id.warehouse_id.manu_packing_type_id.default_location_dest_id.id

        qty_to_pack = sum(self.lot_ids.mapped('quantity_to_pack'))
        # create the palletizing picking, use the palletizing location set on the picking.
        palletizing_id = self.env['stock.picking'].create({
            'origin': self.production_id.name,
            'production_id': self.production_id.id,
            'move_type': 'direct',
            'location_id': location_src,
            'location_dest_id': location_dest,
            'picking_type_id': self.production_id.picking_type_id.warehouse_id.manu_packing_type_id.id,
            'group_id': self.production_id.procurement_group_id.id,
            'move_lines': [(0, 0, {
                        'product_id': self.production_id.product_id.id,
                        'product_uom_qty': qty_to_pack,
                        'product_uom': self.production_id.product_uom_id.id,
                        'location_id': location_src,
                        'location_dest_id': location_dest,
                        'picking_type_id': self.production_id.picking_type_id.warehouse_id.manu_packing_type_id.id,
                        'name': self.production_id.product_id.display_name,
                        # 'picking_id': palletizing_id.id,
                    })]
        })
        self.production_id.write({"picking_ids":[(4,palletizing_id.id)]})
        if self.date_backdating:
            palletizing_id.min_date = self.date_backdating
        palletizing_id.group_id = self.production_id.procurement_group_id.id
        palletizing_id.action_confirm()
        palletizing_id.action_assign()
#         palletizing_id.force_assign()

    # Check if there is any packing left to do.
    @api.onchange('production_id', 'lot_ids')
    def _print_only(self):
        if not self.picking_ids:
            self.print_only = False
            self.no_palletizing_pickings = True
            return
        self.product_qty_per_pallet = self.production_id.bom_id.product_qty_per_pallet
        picking_ids = self.picking_ids.filtered(lambda x:
                                                x.picking_type_id.id == self.manu_packing_type_id.id
                                                and x.state not in ['done', 'cancel'])
        package_ids = self.picking_ids.filtered(lambda x:
                                                x.picking_type_id.id == self.manu_packing_type_id.id
                                                # and x.state not in ['done']
                                                ).mapped('pack_operation_product_ids').filtered(lambda x:
                                                                                                x.product_id.id == self.product_id.id
                                                                                                and x.result_package_id.id).mapped('result_package_id')
        if len(picking_ids) == 0:
            self.print_only = True
        if len(package_ids) == 0:
            self.nothing_to_print = True

        if len(self.picking_ids.filtered(lambda x: x.picking_type_id.id == self.manu_packing_type_id.id)) == 0:
            self.no_palletizing_pickings = True

        if sum(self.lot_ids.mapped('quantity_to_pack')) == 0:
            self.print_only = True
        else:
            self.print_only = False

    @api.onchange('production_id', 'product_qty_per_pallet', 'filter')
    def get_number_of_pallets(self):
        # Sum the quantity to pack, and divide by the qty per pallet to get the number of pallets to pack.
        qty_to_pack = sum(self.lot_ids.mapped('quantity_to_pack'))
        number_of_pallets = math.ceil(qty_to_pack / self.product_qty_per_pallet)
        # (self.production_id.product_qty / self.product_qty_per_pallet) - existing_package_count)
        self.number_of_pallets = number_of_pallets

        self.page_from = 1
        self.page_to = self.number_of_pallets
        self.page_to = len(self.production_id.package_ids.ids)

    # get the lot ids from the finished goods quants, and filter to lots ending with the related machine number.
    @api.onchange('filter', 'production_id', 'product_qty_per_pallet')
    def get_lots(self):
        # Get a flat list of lots that are manufactured and filter for the machine number if set.
        location_id = self.production_id.move_finished_ids[0].location_dest_id
        
        print(self.production_id.move_finished_ids.move_line_ids.mapped('lot_id'))
        
#         quant_ids = self.production_id.move_finished_ids.filtered(lambda x: x.state == 'done').mapped('quant_ids')
#         lot_ids = quant_ids.filtered(lambda x: x.location_id.id == location_id.id).mapped('lot_id')
        lot_ids =  self.production_id.move_finished_ids.move_line_ids.mapped('lot_id')
        if len(lot_ids) > 0:
            self.lot_ids = [(6, 0, lot_ids.ids)]

        else:
            # Nothing found, reset.
            self.lot_ids = [(5, 0)]
            self.number_of_pallets = 0

#     @api.multi
    def put_in_pack(self):
        if len(self.lot_ids.ids) == 0:
            self.get_lots()
        if self.number_of_pallets == 0:
            raise ValidationError("Number of pallets must be greater than 0.")
        if not self.production_id.package_ids:
            raise ValidationError("There are no packages associated with this Manufacturing Order.")

        unpacked_package_ids = self.production_id.package_ids.filtered(lambda x: not x.quant_ids)
        if len(unpacked_package_ids) == 0:
            raise ValidationError("There are no empty packages to pack. Check the Palletizing picking and "
                                  "if the pallets are packed with an incorrect amount, cancel the picking and "
                                  "try Palletizing again.")

        self.create_palletizing_picking()

        # Update the dest move on the fly if it doesnt contain the same quantity as what was produced, only if it is still open.
        for move in self.production_id.move_finished_ids:
            for des_id in move.move_dest_ids:
                if des_id.product_uom_qty != move.product_uom_qty \
                        and move.product_uom.id == des_id.product_uom.id\
                        and des_id.state not in ['done', 'cancel']:
                    des_id.product_uom_qty = move.product_uom_qty

        result_package_ids = self.picking_ids.filtered(lambda x:
                                                           x.picking_type_id.id == self.manu_packing_type_id.id
                                                           and x.state not in ['done', 'cancel']).mapped(
                'move_line_ids_without_package').filtered(lambda x:
                                                       x.product_id.id == self.product_id.id
                                                       and x.result_package_id.id is not False).mapped('result_package_id')

        self.production_id.package_ids.mapped('default_lot_code_id')[0]._product_qty_at_context()

        #get the qualifying packages
        qualifying_package_ids = self.production_id.package_ids.filtered(lambda x: x not in result_package_ids)

        # Allow prioritizing a lot code if the quantity matches exactly that of another
        for default_lot_code in qualifying_package_ids.mapped('default_lot_code_id'):
            if default_lot_code.quantity_to_pack == self.number_of_pallets:
                qualifying_package_ids = qualifying_package_ids.filtered(lambda x: x.default_lot_code_id.id == default_lot_code.id)

        xrange_list = range(0, min(len(qualifying_package_ids), self.number_of_pallets,
                                    sum(self.lot_ids.mapped('quantity_to_pack'))))

        for x in xrange_list:
            # Loop over packages to pack default_lot_ids.
            try:
                package = qualifying_package_ids[x]
            except IndexError:
                continue

            package.default_lot_code_id._product_qty_at_context()

            if package.default_lot_code_id.id and package.default_lot_code_id.quantity_to_pack > 0:
                packed = self._pack(package=package, lot=package.default_lot_code_id)
                if packed is False:
                    # If packed returns False, we can assume no picking lines were found so
                    # the picking was validated.
                    # We should retry because there could
                    # be another picking that we need to work with.
                    packed = self._pack(package=package, lot=package.default_lot_code_id)

        picking_ids = self.picking_ids.filtered(lambda x:
                                                x.picking_type_id.id == self.manu_packing_type_id.id
                                                and x.state not in ['done', 'cancel'])

        for picking in picking_ids:
            picking_line_ids = picking.pack_operation_product_ids.filtered(lambda x:
                                                                           x.product_id.id == self.product_id.id
                                                                           and x.result_package_id.id is False)

            # Check if there are any more unpacked operations left on the picking and if none, Validate picking.
            # if len(picking_line_ids) == 0:
            #     picking.do_new_transfer(from_code=True)

        return

    # Returns False if no picking_lines were ready.
    @api.model
    def _pack(self, package, lot):
        # Find the picking with the warehouse's palletizing
        # operation that is not done or cancelled, and take the first one.
        picking_ids = self.picking_ids.filtered(lambda x:
                                                x.picking_type_id.id == self.manu_packing_type_id.id
                                                and x.state not in ['done', 'cancel'])

        if len(picking_ids) == 0:
            return True

        picking_line_ids = picking_ids.mapped('pack_operation_product_ids').filtered(lambda x:
                                                                           x.product_id.id == self.product_id.id
                                                                           and x.result_package_id.id is False)

        # If no non-packaged lines can be found, let's validate the picking, so that we can move on.
        if len(picking_line_ids) == 0:
            picking_ids[0].do_new_transfer(from_code=True)
            return False

        # If the amount left in the lot is less than the qty per pallet, we'll pack just the remaining amount in the lot.
        if lot.quantity_to_pack < self.product_qty_per_pallet:
            qty_to_pack = lot.quantity_to_pack

        # If the amount left on the line is less than the qty per pallet, we'll pack the remaining amount on the line.
        elif picking_line_ids[0].product_qty < self.product_qty_per_pallet:
            qty_to_pack = picking_line_ids[0].product_qty

        else:
            qty_to_pack = self.product_qty_per_pallet

        # remove any existing lots from the operation, then pack the set qty.
        picking_line_ids[0].pack_lot_ids.unlink()
        self.env['stock.pack.operation.lot'].create({'operation_id': picking_line_ids[0].id, 'lot_id': lot.id, 'qty': qty_to_pack})
        picking_line_ids[0].qty_done += qty_to_pack
        if self.date_backdating:
            picking_line_ids[0].date_backdating = self.date_backdating

        # Put into selected package.
        package_id = picking_ids[0].put_in_pallet(package=package)

        return True

    # Action Button: put_in_pack, then relaunch new wizard.

    @api.model
    def default_get(self, fields):
        context = dict(self._context or {})

        description = ''
        regex = re.compile(r'\[USER_DEFINED_([\w_]+)\]')
        match = None

        if context.get('active_id', False) is False:
            #TODO: Fix this error.
            raise ValidationError('Cannot run pallet generation on multiple workorders or manufacturing orders. Please only run on one at a time.')

        if context.get('default_production_id', False):
            production_id = self.env['mrp.production'].browse(context.get('default_production_id'))
            if production_id.product_id.pallet_abbv is not False:
                match = regex.search(production_id.product_id.pallet_abbv)

        elif context.get('active_model', '') == 'mrp.production':
            production_id = self.env['mrp.production'].browse(context.get('active_id'))
            if production_id.product_id.pallet_abbv is not False:
                match = regex.search(production_id.product_id.pallet_abbv)

        if match is not None and isinstance(match.group(1), str):
            description = match.group(1).replace('_', ' ').title()

        rec = {
            'production_id': production_id.id,
            'description': description,
            'product_qty_per_pallet': 1.00,
            'sequence_step': 'serial',
            'sequence_step': context.get('sequence_step', 'serial')
        }

        return rec

#     @api.multi
    def _return_print(self):
        if len(self.production_id.package_ids) == 0:
            raise ValidationError('Unable to print because there are no packages associated with this Manufacturing Order.')

        self.page_from = self.page_from - 1 if self.page_from > 0 else 0
        if self.page_to > len(self.production_id.package_ids):
            raise ValidationError("The page selected does not exist. The maximum number of packages available to print is " + len(self.production_id.package_ids))
        if self.page_from > self.page_to or self.page_to == 0:
            self.page_from = 0
            self.page_to = len(self.production_id.package_ids)
        return self.env['report'].get_action(self.production_id.package_ids[self.page_from:self.page_to], 'product_auto_lot.report_view_stock_package_card')

    ##
    ##
    ## Buttons
    ##
    ##

#     @api.multi
    def action_print(self):
        # Return printed report.
        action_dict = self._return_print()

        return action_dict

#     @api.multi
    def action_pack(self):
        self.put_in_pack()

        return {'type': 'ir.actions.act_window_close'}
    
    def action_view_pack_pallet_wizard(self):
        action = self.env.ref('product_auto_lot.action_view_pack_pallet_wizard').sudo()
        result = action.read()[0]
        print(action)
        print(result)
        return action

