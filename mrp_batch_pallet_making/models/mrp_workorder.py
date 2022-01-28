# -*- coding: utf-8 -*-

from odoo import _, models, fields, api
from odoo.tools import float_compare, float_round, float_is_zero, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class MrpWorkorder(models.Model):
    _name = 'mrp.workorder'
    _inherit = ['mrp.workorder', 'barcodes.barcode_events_mixin']
    _order = 'date_planned_start asc'

    product_qty_per_workcenter = fields.Float('Quantity to Produce', readonly=True, related='production_id.product_qty_per_workcenter')

    skip_packing_rules = fields.Boolean('Use Normal Workcenter Rules', default=False)

#     finished_move_lot_ids = fields.One2many('stock.move.lots', 'workorder_id', domain=lambda self: [('product_id', '!=', self.product_id.id),
#                                                                                                     ('lot_produced_id', '!=', False),
#                                                                                                     ('quantity_done', '>', 0),
#                                                                                                     ('done_wo', '=', True)],
#                                             string='Finished Lots')

    current_step = fields.Integer('Current Number', default=0, readonly=True)
    time_start = fields.Char('Time', compute="_get_time_start", store=True)
    step_time_start = fields.Datetime('Step Start Time', readonly = True)
    mo_time_start = fields.Datetime('MO Time', store=True, related='production_id.date_planned_start')
    order_active = fields.Boolean(default=False)
    
    
    def call_gen_final_lot(self):
        self.generate_final_lot_code()
        
#     def _generate_final_lot_code(self):
#         for wo in self:
#             if wo.product_id.lot_abbv and '[USER_DEFINED' in wo.product_id.lot_abbv:
#                 return wo.action_view_generate_lot_wizard()
#             else:
# #                 gen_date = datetime.strptime(self.date_planned_start or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
#                 gen_date = self.date_planned_start or fields.Datetime.now()
#                 lot_name = wo.product_id.gen_lot_code(gen_date=gen_date)
#                 existing_lots = self.env['stock.production.lot'].search([('name', '=', lot_name), ('product_id', '=', wo.product_id.id)])
# 
#                 if len(existing_lots.ids) > 0:
# #                     wo.final_lot_id = existing_lots.ids[0]
#                     wo.finished_lot_id = existing_lots.ids[0]
#                 else:
# #                     wo.final_lot_id = wo.env['stock.production.lot'].create({
#                     wo.finished_lot_id = wo.env['stock.production.lot'].create({
#                         'name': lot_name,
#                         'product_id': wo.product_id.id,
#                         'gen_date': gen_date,
#                     }).id
#                     wo.finished_lot_id.sudo()._use_gen_date()
#                     wo.final_lot_id.sudo()._use_gen_date()
#         return True

#     def write(self, vals):
#         if vals.get('finished_move_lot_ids') and self.state != 'done':
#             del vals['finished_move_lot_ids']
#             if not vals:
#                 return True
#         res = super(MrpWorkorder, self).write(vals)
#         return res

    # depends will cause the value to compute anytime the date_start field is updated.
    @api.onchange('qty_producing')
    def _onchange_qty_producing(self):
        """ Update stock.move.lot records, according to the new qty currently
        produced. """
        moves = self.move_raw_ids.filtered(lambda move: move.state not in ('done',
                                                                           'cancel') and move.product_id.tracking != 'none' and move.product_id.id != self.production_id.product_id.id)
        for move in moves:
            move_lots = self.move_line_ids.filtered(lambda move_lot: move_lot.move_id == move)
            if not move_lots:
                continue

            """ START : Calculate new_qty value on by John 01/27/20"""
            child_locations = self.env['stock.location'].search([('location_id', 'child_of', self.production_id.location_src_id.id)])
            quants_at_location = self.env['stock.quant'].search(['&', ('lot_id', '=', move.last_lot_id.id), ('product_id', '=', move.product_id.id), ('location_id', 'in', child_locations.ids)])
#             quantity_at_location = sum(quants_at_location.mapped('qty'))
            quantity_at_location = sum(quants_at_location.mapped('quantity'))

            # previously_committed = sum(move_lots.move_id.active_move_lot_ids.filtered(lambda x: x.product_id == move.product_id and x.lot_id == move.last_lot_id and move.state not in ['done', 'cancel'] and x.done_wo).mapped('quantity_done'))
            previously_committed = sum(move_lots.mapped('move_id.move_line_ids').filtered(
                lambda x: x.product_id == move.product_id and x.lot_id == move.last_lot_id and move.state not in [
                    'done'
                    '', 'cancel']).mapped('qty_done'))

            available = quantity_at_location - previously_committed

            #new_qty = move.unit_factor * self.qty_producing if (available >= move.unit_factor * self.qty_producing ) else available
            new_qty = move.unit_factor * self.qty_producing

            """Modified by James for workorder view to always input qty needed as Done"""

            if move.product_id.skip_wo_check:
                available = max(new_qty, 0)
            else:
                available = max(min(available, new_qty), 0)


            """ END """

            if move.product_id.tracking == 'lot':
                move_lots[0].product_uom_qty = new_qty
                move_lots[0].qty_done = new_qty
            elif move.product_id.tracking == 'serial':
                # Create extra pseudo record
                location_dest_id = move.location_dest_id._get_putaway_strategy(move.product_id).id or move.location_dest_id.id
                qty_todo = new_qty - sum(move_lots.mapped('product_uom_qty'))
                if float_compare(qty_todo, 0.0, precision_rounding=move.product_uom.rounding) > 0:
                    while float_compare(qty_todo, 0.0, precision_rounding=move.product_uom.rounding) > 0:
                        self.move_line_ids.create({'move_id': move.id,
                                                  'lot_id': False,
                                                  'qty_done': min(1.0, qty_todo),
                                                  'product_uom_id': move.product_id.uom_id.id,
                                                  'product_uom_qty': min(1.0, qty_todo),
                                                  'workorder_id': self._origin.id,
                                                  'production_id': move.production_id.id,
#                                                   'location_id':location_ids and location_ids[0].id,
                                                  'location_id': move.location_id.id,
                                                  'location_dest_id': location_dest_id,
                                                  'product_id': move.product_id.id})
                        
#                         self.active_move_lot_ids += self.env['stock.move.lots'].new({
#                             'move_id': move.id,
#                             'product_id': move.product_id.id,
#                             'lot_id': False,
#                             'quantity': min(1.0, qty_todo),
#                             'quantity_done': min(1.0, qty_todo),
#                             'workorder_id': self.id,
#                             'done_wo': False
#                         })
                        qty_todo -= 1
                elif float_compare(qty_todo, 0.0, precision_rounding=move.product_uom.rounding) < 0:
                    qty_todo = abs(qty_todo)
                    for move_lot in move_lots:
                        if qty_todo <= 0:
                            break
                        if not move_lot.lot_id and qty_todo >= move_lot.product_uom_qty:
                            qty_todo = qty_todo - move_lot.product_uom_qty
                            self.active_move_lot_ids -= move_lot  # Difference operator
                        else:
                            move_lot.product_uom_qty = move_lot.product_uom_qty - qty_todo
                            if move_lot.qty_done - qty_todo > 0:
                                move_lot.qty_done = move_lot.qty_done - qty_todo
                            else:
                                move_lot.qty_done = 0
                            qty_todo = 0
                            
    @api.depends('date_start')
    def _get_time_start(self):
        # Import to iterate when using @api.multi, otherwise you can affect all records. Or use self.ensure_one()
        for wo in self:
            if wo.date_start:
                # Convert the date_start (which returns as a string) to a time string.
#                 time = datetime.strptime(wo.date_start, DEFAULT_SERVER_DATETIME_FORMAT).strfptime('%H:%M:%S')
                time = wo.date_start.strftime('%H:%M:%S')
                wo.time_start = time

    @api.onchange('select_lot_ids')
    def _select_lot(self):
        super(MrpWorkorder, self)._select_lot()
        if self.workcenter_id.workcenter_type in ['batch', 'pallet']:
            lot_ids = self.select_lot_ids
            stock_move = self.env['stock.move']
            for lot in lot_ids:
                stock_move_ids = stock_move.search(
                    [('product_id', '=', lot.product_id.id), ('raw_material_production_id', '=', self.production_id.id)])
                stock_move_ids.write({'last_lot_id': lot._origin.id})

    def button_finish(self):
        self.ensure_one()
        if self.workcenter_id.workcenter_type == 'pallet' and not self.skip_packing_rules:
            # Confirm this behavior.
            current_package = self.production_id.package_ids.filtered(lambda x: x.start_date and not x.end_date)
            # if current_package:
            #     current_package.start_date = False

        if self.workcenter_id.workcenter_type in ['batch', 'pallet'] and not self.skip_packing_rules:
            # Prevent record_production from finalizing the workorder.
            if self._context.get('clicked_finish'):
                return super(MrpWorkorder, self).button_finish()
#             else:
#                 self._generate_lot_ids()
        else:
            return super(MrpWorkorder, self).button_finish()
        
        
    def record_production(self):
        self.ensure_one()
#         if any([not x.lot_id and x.quantity_done for x in self.active_move_lot_ids]):
#             raise ValidationError("Lot codes must be set if there is a quantity greater than zero.")

        if self.workcenter_id.workcenter_type in ['batch', 'pallet'] and not self.skip_packing_rules:
            # Time tracking on packages.
            if not self.production_id.package_ids:
                raise ValidationError("You must generate the packages on the Manufacturing Order before you can begin.")
            current_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == self.current_step + 1)

            if current_package and current_package.start_date and not current_package.end_date:
                # If the current package doesn't have an end_date, we will set it.
                current_package.end_date = datetime.now()
                next_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == current_package.pallet_number + 1)
                if next_package:
                    next_package.start_date = datetime.now()

            elif current_package and not current_package.start_date and not current_package.end_date:
                # If the current package doesnt have a start date or end date, we'll check for a previous package.
                prev_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == current_package.pallet_number - 1)
                if prev_package and prev_package.end_date:
                    current_package.end_date = datetime.now()
                    current_package.start_date = prev_package.end_date
                    next_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == current_package.pallet_number + 1)
                    if next_package:
                        next_package.start_date = datetime.now()

            elif not current_package:
                # If there is no packages found, then we can't continue.
                raise ValidationError("There are no more package left to do.")

            """ END """

            """
                Set the qty_producing to 1, this will cause the move_lots to_do
                to compute to the amounts required to produce 1 qty. This will also 
                make the record_production method only record production of 1 qty, allowing
                you to continue recording more consumption of raw materials.
            """
            self.qty_producing = 1
            lot_id = self.finished_lot_id

            """
                current mo check module by Hoon
            """
            # records = self.env['mrp.workorder'].search([('workcenter_id', '=', self.workcenter_id.id)])
            # for work in records:
            #     work.order_active = False
            # self.order_active = True

        # Execute normal workcenter record_production() method.
#         res = super(MrpWorkorder, self).record_production()

            self._check_sn_uniqueness()
            self._check_company()
    #         if any(x.quality_state == 'none' for x in self.check_ids):
    #             raise UserError(_('You still need to do the quality checks!'))
            if float_compare(self.qty_producing, 0, precision_rounding=self.product_uom_id.rounding) <= 0:
                raise UserError(_('Please set the quantity you are currently producing. It should be different from zero.'))
    
            if self.production_id.product_id.tracking != 'none' and not self.finished_lot_id and self.move_raw_ids:
                raise UserError(_('You should provide a lot/serial number for the final product'))
    
            # Suggest a finished lot on the next workorder
            if self.next_work_order_id and self.product_tracking != 'none' and not self.next_work_order_id.finished_lot_id:
                self.production_id.lot_producing_id = self.finished_lot_id
                self.next_work_order_id.finished_lot_id = self.finished_lot_id
            backorder = False
            # Trigger the backorder process if we produce less than expected
    #         if float_compare(self.qty_producing, self.qty_remaining, precision_rounding=self.product_uom_id.rounding) == -1 and self.is_first_started_wo:
    #             backorder = self.production_id._generate_backorder_productions(close_mo=False)
    #             self.production_id.product_qty = self.qty_producing
    #         else:
    #             if self.operation_id:
    #                 backorder = (self.production_id.procurement_group_id.mrp_production_ids - self.production_id).filtered(
    #                     lambda p: p.workorder_ids.filtered(lambda wo: wo.operation_id == self.operation_id).state not in ('cancel', 'done')
    #                 )[:1]
    #             else:
    #                 index = list(self.production_id.workorder_ids).index(self)
    #                 backorder = (self.production_id.procurement_group_id.mrp_production_ids - self.production_id).filtered(
    #                     lambda p: p.workorder_ids[index].state not in ('cancel', 'done')
    #                 )[:1]
    
            # Update workorder quantity produced
    #         self.qty_produced = self.qty_producing
            self.qty_produced += self.qty_producing
    
            # One a piece is produced, you can launch the next work order
            self._start_nextworkorder()
            self.button_finish()
    
            if backorder:
                for wo in (self.production_id | backorder).workorder_ids:
                    if wo.state in ('done', 'cancel'):
                        continue
                    wo.current_quality_check_id.update(wo._defaults_from_move(wo.move_id))
                    if wo.move_id:
                        wo._update_component_quantity()
                if not self.env.context.get('no_start_next'):
                    if self.operation_id:
                        return backorder.workorder_ids.filtered(lambda wo: wo.operation_id == self.operation_id).open_tablet_view()
                    else:
                        index = list(self.production_id.workorder_ids).index(self)
                        return backorder.workorder_ids[index].open_tablet_view()
            if self.workcenter_id.workcenter_type in ['batch', 'pallet'] and not self.skip_packing_rules:
                self.current_step += 1
    
                # Set qty_producing to 1, and recompute move_lots
                self.qty_producing = 1
                self._onchange_qty_producing()
                self.step_time_start = ''
    
                # Bring in the final_lot used in last batch.
                self.finished_lot_id = lot_id and lot_id.id or False
        else:
            res = super(MrpWorkorder, self).record_production()
            return res
        
        return True

#     def record_production(self):
#         self.ensure_one()
#         if any([not x.lot_id and x.quantity_done for x in self.active_move_lot_ids]):
#             raise ValidationError("Lot codes must be set if there is a quantity greater than zero.")
# 
#         if self.workcenter_id.workcenter_type in ['batch', 'pallet'] and not self.skip_packing_rules:
#             # Time tracking on packages.
#             if not self.production_id.package_ids:
#                 raise ValidationError("You must generate the packages on the Manufacturing Order before you can begin.")
#             current_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == self.current_step + 1)
# 
#             if current_package and current_package.start_date and not current_package.end_date:
#                 # If the current package doesn't have an end_date, we will set it.
#                 current_package.end_date = datetime.now()
#                 next_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == current_package.pallet_number + 1)
#                 if next_package:
#                     next_package.start_date = datetime.now()
# 
#             elif current_package and not current_package.start_date and not current_package.end_date:
#                 # If the current package doesnt have a start date or end date, we'll check for a previous package.
#                 prev_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == current_package.pallet_number - 1)
#                 if prev_package and prev_package.end_date:
#                     current_package.end_date = datetime.now()
#                     current_package.start_date = prev_package.end_date
#                     next_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == current_package.pallet_number + 1)
#                     if next_package:
#                         next_package.start_date = datetime.now()
# 
#             elif not current_package:
#                 # If there is no packages found, then we can't continue.
#                 raise ValidationError("There are no more package left to do.")
# 
#             # Loop and collate the warnings into one string, and present at the end if any warnings.
#             warnings = ''
#             p = self.env['decimal.precision'].precision_get('Product Unit of Measure')
#             """ START : Worning Message when the amount of raw material is not right on by John 01/31/20"""
#             for product in self.raw_product_ids:
#                 sum_product_quantity = self.active_move_lot_ids.read_group(
#                     ['&', '&', ('product_id', '=', product.id), ('workorder_id', '=', self.id) , ('done_wo', '=', False)],
#                     ['product_id', 'quantity', 'quantity_done'], ['product_id'])
# 
#                 sum_quantity = sum(l['quantity'] for l in sum_product_quantity)
#                 sum_quantity_done = sum(l['quantity_done'] for l in sum_product_quantity)
# 
#                 """It will check for material available, for all materials except BULK"""
# 
#                 if float_compare(sum_quantity_done, sum_quantity, precision_digits=p) == -1:
#                     if not product.skip_wo_check:
#                         if not warnings:
#                             warnings = _(
#                                 "The amount for the following raw materials is insufficient:\n\n")
#                         warnings += _(
#                                 "%s\nRequested: %.3f\nAvailable: %.3f \n\n") % (
#                             product.name, sum_quantity, sum_quantity_done)
# 
#             if warnings:
#                 raise UserError(warnings)
#                     # raise UserError(
#                     #     _(
#                     #         "The amount for raw material( %s ) is not correct.\nPlease Check it!\nRequested: %.3f\nAvailable: %.3f") % (
#                     #     product.name, sum_quantity, sum_quantity_done))
#             """ END """
# 
#             """
#                 Set the qty_producing to 1, this will cause the move_lots to_do
#                 to compute to the amounts required to produce 1 qty. This will also 
#                 make the record_production method only record production of 1 qty, allowing
#                 you to continue recording more consumption of raw materials.
#             """
#             self.qty_producing = 1
#             lot_id = self.finished_lot_id
# 
#             """
#                 current mo check module by Hoon
#             """
#             # records = self.env['mrp.workorder'].search([('workcenter_id', '=', self.workcenter_id.id)])
#             # for work in records:
#             #     work.order_active = False
#             # self.order_active = True
# 
#         # Execute normal workcenter record_production() method.
#         res = super(MrpWorkorder, self).record_production()
# 
#         """
#             Use existing record_production method for next button, 
#             when the workcenter type is batch or pallet, increment 
#             the current_step and perform any other custom operations.
#         """
#         if self.workcenter_id.workcenter_type in ['batch', 'pallet'] and not self.skip_packing_rules:
#             self.current_step += 1
# 
#             # Set qty_producing to 1, and recompute move_lots
#             self.qty_producing = 1
#             self._onchange_qty_producing()
#             self.step_time_start = ''
# 
#             # Bring in the final_lot used in last batch.
#             self.finished_lot_id = lot_id
# 
#             for raw_material in self.active_move_lot_ids:
#                 stock_move = self.env['stock.move']
#                 stock_move_ids = stock_move.search(['&','&', ('product_id', '=', raw_material.product_id.id),('workorder_id', '=', raw_material.workorder_id.id), ('raw_material_production_id', '=', raw_material.production_id.id)])
#                 raw_material.lot_id = stock_move_ids[0].last_lot_id.id
# 
#         return res

    def button_start(self):
        for wo in self:
            if wo.workcenter_id.workcenter_type in ['batch', 'pallet'] and not wo.skip_packing_rules:
                # Time tracking on packages.
                if not wo.production_id.package_ids:
                    raise ValidationError("There are no package to pack on this Manufacturing Order.")

                if not wo.finished_lot_id:
                    raise ValidationError("You must first select a Finished Lot code before continuing.")

                next_package = wo.production_id.package_ids.filtered(lambda x: x.pallet_number == self.current_step + 1 and x.default_lot_code_id == wo.finished_lot_id)
                if not next_package:
                    raise ValidationError("There are no package left to pack on this Manufacturing Order.")
                current_package = wo.production_id.package_ids.filtered(lambda x: x.pallet_number == self.current_step and x.default_lot_code_id == wo.finished_lot_id)
                # current_package = wo.production_id.package_ids.filtered(lambda x: x.start_date and not x.end_date)
                if current_package:
                    current_package.end_date = datetime.now()
                next_package.start_date = datetime.now()
                """
                    At start of Workorder, set qty_producing.
                    Then force _onchange_qty_producing to 
                    recalulate move_lots quantities needed.
                """
                wo.qty_producing = 1
#                 wo._onchange_qty_producing()

                raw_product_ids = wo.production_id.move_raw_ids.filtered(lambda x: x.workorder_id.id == wo.id)
                if not raw_product_ids:
                    raw_product_ids = wo.production_id.move_raw_ids
                
                for raw_id in raw_product_ids:
                    location_dest_id = raw_id.location_dest_id._get_putaway_strategy(raw_id.product_id).id or raw_id.location_dest_id.id
                    wo.move_line_ids.create({'move_id': raw_id.id,
                                                  'lot_id': False,
                                                  'qty_done': 0,
                                                  'product_uom_id': raw_id.product_id.uom_id.id,
                                                  'product_uom_qty': raw_id.product_uom_qty,
                                                  'workorder_id': wo.id,
                                                  'production_id': wo.production_id.id,
#                                                   'location_id':location_ids and location_ids[0].id,
                                                  'location_id': raw_id.location_id.id,
                                                  'location_dest_id': location_dest_id,
                                                  'product_id': raw_id.product_id.id})

        super(MrpWorkorder, self).button_start()

    def scan_barcode(self, barcode):
        self.ensure_one()
        package = self.env['stock.quant.package'].search([('name', '=', barcode)], limit=1)
        if self.workcenter_id.workcenter_type in ['batch', 'pallet']:
            # When scanning package barcode, mark the end time of the scanned code, and start the next package.
            if package:
                if self.state in ['done', 'cancel']:
                    raise ValidationError("The workorder is finished or cancelled.")
                if self.state in ['pending', 'ready']:
                    raise ValidationError("The workorder must be started first.")
                if package.production_id != self.production_id:
                    raise ValidationError("The scanned pallet, %s, belongs to another production order: %s" % (
                    barcode, package.production_id.name))
                current_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == self.current_step + 1 and x.default_lot_code_id == self.finished_lot_id)
                # current_package = self.production_id.package_ids.filtered(lambda x: x.start_date and not x.end_date)
                if package != current_package:
                    raise ValidationError("The current package in progress is %s." % current_package.name)
                return {
                    'record_production': True
                }

            # Search for a matching lot code, and restrict searching to only products on the workorder.
            lot_ids = self.env['stock.production.lot'].search([('product_id', 'in', self.active_move_lot_ids.mapped('product_id').ids), ('name', '=', barcode)], limit=1)

            if lot_ids:
                stock_move = self.env['stock.move']
                stock_move_ids = stock_move.search([('product_id', '=', lot_ids[0].product_id.id),
                                                    ('raw_material_production_id', '=', self.production_id.id)])
                stock_move_ids.write({'last_lot_id': lot_ids[0].id})

                # Add custom barcode scanner handler, to enter quantities needed, rather than increment by 1.
                if lot_ids.product_id == self.product_id:
                    self.finished_lot_id = lot_ids.filtered(lambda x: x.product_id == self.product_id)
                else:
                    # In case multiple lot codes are found
                    active_move_lots = self.active_move_lot_ids.filtered(
                        lambda l: l.product_id in lot_ids.mapped('product_id'))
                    if active_move_lots:
                        lot = lot_ids.filtered(lambda l: l.product_id == active_move_lots[0].product_id)
                        current_active_lots = self.active_move_lot_ids.filtered(
                            lambda l: l.product_id in lot.product_id)

                        blank_move_lot = active_move_lots.filtered(lambda m: not m.lot_id)
                        child_location = self.env['stock.location'].search(
                            [('location_id', 'child_of', self.production_id.location_src_id.id)])
                        quantity_at_location = sum(lot.mapped('quant_ids').filtered(
                            lambda x: bool(set(x.mapped('location_id').ids) & set(child_location.ids))).mapped('qty'))

                        # Get the remaining quantity to do.
                        quantity_done = current_active_lots.filtered(lambda m: m.lot_id.id).mapped('quantity_done')
                        quantity = current_active_lots.mapped('quantity')
                        quantity_todo = sum(quantity) - sum(quantity_done)

                        if blank_move_lot:
                            blank_move_lot[0].lot_id = lot.id
                            if not lot.product_id.allow_negative_stock and not lot.product_id.categ_id.allow_negative_stock and not lot.product_id.skip_wo_check:
                                blank_move_lot[0].quantity_done = max(min(quantity_at_location, quantity_todo), 0)
                            else:
                                blank_move_lot[0].quantity_done = quantity_todo
                        else:
                            # Use create() since calling method directly from JS RPC Call.
                            if not lot.product_id.allow_negative_stock and not lot.product_id.categ_id.allow_negative_stock and not lot.product_id.skip_wo_check:
                                self.active_move_lot_ids.create({'move_id': active_move_lots[0].move_id.id,
                                                              'lot_id': lot.id,
                                                              'quantity_done': max(
                                                                  min(quantity_at_location, quantity_todo), 0),
                                                              'quantity': 0.0,
                                                              'workorder_id': self.id,
                                                              'production_id': self.production_id.id,
                                                              'product_id': lot.product_id.id,
                                                              'done_wo': False})
                            else:
                                self.active_move_lot_ids.create({'move_id': active_move_lots[0].move_id.id,
                                                              'lot_id': lot.id,
                                                              'quantity_done': max(quantity_todo, 0),
                                                              'quantity': 0.0,
                                                              'workorder_id': self.id,
                                                              'production_id': self.production_id.id,
                                                              'product_id': lot.product_id.id,
                                                              'done_wo': False})
        else:
            super(MrpWorkorder, self).on_barcode_scanned(barcode)

    def on_barcode_scanned(self, barcode):
        self.ensure_one()
        package = self.env['stock.quant.package'].search([('name', '=', barcode)], limit=1)
        if self.workcenter_id.workcenter_type in ['batch', 'pallet']:
            # When scanning package barcode, mark the end time of the scanned code, and start the next package.
            if package:
                if self.state in ['done', 'cancel']:
                    raise ValidationError("The workorder is finished or cancelled.")
                if self.state in ['pending', 'ready']:
                    raise ValidationError("The workorder must be started first.")
                if package.production_id != self.production_id:
                    raise ValidationError("The scanned pallet, %s, belongs to another production order: %s" % (barcode, package.production_id.name))
                current_package = self.production_id.package_ids.filtered(lambda x: x.pallet_number == self.current_step + 1 and x.default_lot_code_id == self.finished_lot_id)
                if package != current_package:
                    raise ValidationError("The current package in progress is %s." % current_package.name)
#                 self._origin.record_production()
                self._origin.button_finish()

            lot_ids = self.env['stock.production.lot'].search([('name', '=', barcode)], limit=1)

            if lot_ids:
                stock_move = self.env['stock.move']
                stock_move_ids = stock_move.search([('product_id', '=', lot_ids[0].product_id.id),
                                                    ('raw_material_production_id', '=', self.production_id.id)])
                stock_move_ids.write({'last_lot_id': lot_ids[0].id})

                # Add custom barcode scanner handler, to enter quantities needed, rather than increment by 1.
                if lot_ids.product_id == self.product_id:
                    self.finished_lot_id = lot_ids.filtered(lambda x: x.product_id == self.product_id)
                    
            
#                 else:
#                     # In case multiple lot codes are found
#                     active_move_lots = self.active_move_lot_ids.filtered(lambda l: l.product_id in lot_ids.mapped('product_id'))
#                     if active_move_lots:
#                         lot = lot_ids.filtered(lambda l: l.product_id == active_move_lots[0].product_id)
#                         current_active_lots = self.active_move_lot_ids.filtered(lambda l: l.product_id in lot.product_id)
# 
#                         blank_move_lot = active_move_lots.filtered(lambda m: not m.lot_id)
#                         child_location = self.env['stock.location'].search(
#                             [('location_id', 'child_of', self.production_id.location_src_id.id)])
#                         quantity_at_location = sum(lot.mapped('quant_ids').filtered(lambda x: bool(set(x.mapped('location_id').ids) & set(child_location.ids))).mapped('qty'))
# 
#                         # Get the remaining quantity to do.
#                         quantity_done = current_active_lots.filtered(lambda m: m.lot_id.id).mapped('quantity_done')
#                         quantity = current_active_lots.mapped('quantity')
#                         quantity_todo = sum(quantity) - sum(quantity_done)
# 
#                         if blank_move_lot:
#                             blank_move_lot[0].lot_id = lot.id
#                             if not lot.product_id.allow_negative_stock and not lot.product_id.categ_id.allow_negative_stock and not lot.product_id.skip_wo_check:
#                                 blank_move_lot[0].quantity_done = max(min(quantity_at_location, quantity_todo), 0)
#                             else:
#                                 blank_move_lot[0].quantity_done = quantity_todo
#                         else:
#                             if not lot.product_id.allow_negative_stock and not lot.product_id.categ_id.allow_negative_stock and not lot.product_id.skip_wo_check:
#                                 self.active_move_lot_ids.new({'move_id': active_move_lots[0].move_id.id,
#                                                               'lot_id': lot.id,
#                                                               'quantity_done': max(
#                                                                   min(quantity_at_location, quantity_todo), 0),
#                                                               'quantity': 0.0,
#                                                               'workorder_id': self.id,
#                                                               'production_id': self.production_id.id,
#                                                               'product_id': lot.product_id.id,
#                                                               'done_wo': False})
#                             else:
#                                 self.active_move_lot_ids.new({'move_id': active_move_lots[0].move_id.id,
#                                                               'lot_id': lot.id,
#                                                               'quantity_done': quantity_todo,
#                                                               'quantity': 0.0,
#                                                               'workorder_id': self.id,
#                                                               'production_id': self.production_id.id,
#                                                               'product_id': lot.product_id.id,
#                                                               'done_wo': False})
        else:
            super(MrpWorkorder, self).on_barcode_scanned(barcode)

    def action_confirm(self):
        return {
            'name': 'Finish Production',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder.confirmation',
            'view_type': 'form',
            'view_mode': 'form',
            # 'res_id' : new.id
            'target': 'new',
        }

