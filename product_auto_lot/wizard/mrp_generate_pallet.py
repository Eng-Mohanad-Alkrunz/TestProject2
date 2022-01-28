# -*- coding: utf-8 -*-

import math

from odoo.addons import decimal_precision as dp
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

import re


class MrpWorkcenterPalletWizard(models.TransientModel):
    _name = "mrp.workcenter.pallet.wizard"
    _description = "Workcenter Pallet Code Generator"

    # TODO: Review and improve behavior when MO quantity causes change in initial demand.
    production_id = fields.Many2one('mrp.production', 'Production Order', store=True)
    # workorder_id = fields.Many2one('mrp.workorder', 'Workorder', required=False)
    warehouse_id = fields.Many2one('stock.warehouse', related='production_id.picking_type_id.warehouse_id', readonly=True)
    location_source_id = fields.Many2one('stock.location', related='production_id.location_dest_id', readonly=True)
    manu_packing_type_id = fields.Many2one('stock.picking.type', related='production_id.picking_type_id.warehouse_id.manu_packing_type_id', readonly=True)
    picking_ids = fields.Many2many('stock.picking', string='Pickings', related='production_id.picking_ids', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', related='production_id.product_id', readonly=True)
    company_id = fields.Many2one('res.company')
    print_only = fields.Boolean('Print Only', help='If true, everything is completed and only printing is available.', readonly=True)
    nothing_to_print = fields.Boolean('Nothing to Print', help='If true, nothing can be printed.', readonly=True)
    warehouse_code = fields.Char('Warehouse Code', related='warehouse_id.lot_abbv', readonly=True)

    gen_date = fields.Datetime('Date of Manufacture', default=fields.Datetime.now())

    # finished data
    lot_name = fields.Char(string='Pallet Code')

    page_from = fields.Integer('Page From')
    page_to = fields.Integer('Page To')

    last_pallet_number = fields.Integer('Last Pallet', readonly=True)

    # user defined variables
    product_qty_per_pallet = fields.Float('Product Quantity per Pallet', default=1, digits=dp.get_precision('Product Unit of Measure'), required=True)
    qty_of_pallets = fields.Float('Quantity of Pallets', compute='_get_pallets_quantity')
    qty_to_pack = fields.Float('Quantity to Pack', compute='_get_pallets_quantity')
    filter = fields.Char('Filter', help='If there are more then one lot, enter the last characters of the lot you want to pack.')
    hide_user_defined = fields.Boolean('Hide User Defined field.', store=False)
    user_defined = fields.Char('Variable', help="This could refer to the machine or rack number. "
                                                "Refer to a supervisor or company procedure manual "
                                                "if you are unsure what to enter.")
    pallet_start_number = fields.Integer('First Pallet Number', default=1)
    number_of_pallets = fields.Integer('Number of Pallets to Pack', default=1, store=True)
    description = fields.Char('Description', readonly=True)
    sequence_step = fields.Selection([
        ('even_odd', 'Even/Odd'),
        ('serial', 'Serial')], 'Sequence Step',
        default='serial', required=1,
        help='When using Even or Odd, make sure the '
             'starting pallet number is even or odd number.')

    paper_size = fields.Selection(
        [("letter", "Letter"),("card", "6x4 Card")],
        "Paper Size", default="letter", required=1,
        help='Choose the paper size for printing.')

    @api.onchange('production_id')
    def _hide_user_defined(self):
        # Make sure production order has location dest of palletizing.
        # if self.production_id.location_dest_id.id != self.production_id.picking_type_id.warehouse_id.wh_mrp_pack_stock_loc_id.id:
        #    raise UserError("The Manufacturing Order must have a Palletizing destination location.")
        if self.product_id.id:
            self.product_qty_per_pallet = self.production_id.bom_id.product_qty_per_pallet
 
            if len(self.production_id.package_ids) > 0:
                self.last_pallet_number = self.production_id.package_ids.sorted(key=lambda r: r.pallet_number, reverse=True).mapped('pallet_number')[0]
 
            if re.search(r'\[USER_DEFINED_?[\w_]*\]', self.product_id.pallet_abbv or '') is not None:
                self.hide_user_defined = False
            else:
                self.hide_user_defined = True
            if self.production_id.sequence_step:
                self.sequence_step = self.production_id.sequence_step
 
    @api.onchange('user_defined', 'production_id', 'pallet_start_number', 'filter', 'gen_date')
    def _user_defined(self):
        if self.production_id:
#             gen_date = datetime.strptime(self.gen_date or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
            gen_date = self.gen_date or fields.Datetime.now()
            self.lot_name = self.production_id.product_id.gen_pallet_code(machine_number=self.filter,
                                                                          warehouse_code=self.warehouse_code,
                                                                          pallet_number=self.pallet_start_number,
                                                                          user_defined=self.user_defined,
                                                                          gen_date=gen_date)
 
    @api.onchange('production_id', 'product_qty_per_pallet', 'filter')
    def get_number_of_pallets(self):
        # Sum the quantity to pack, and divide by the qty per pallet to get the number of pallets to pack.
        existing_package_count = len(self.production_id.package_ids.ids)
        number_of_pallets = max(math.ceil((self.production_id.product_qty / self.product_qty_per_pallet) - existing_package_count), 0)
        self.number_of_pallets = number_of_pallets
        self.page_from = 1
        self.page_to = existing_package_count
 
        if len(self.production_id.package_ids) > 0:
            self.pallet_start_number = self.last_pallet_number + 1 or 1
 
    @api.onchange('sequence_step')
    def get_pallet_start_number(self):
        if len(self.production_id.package_ids) > 0:
            last_pallet = self.last_pallet_number
            if self.pallet_start_number == last_pallet + 1 and self.sequence_step == 'even_odd':
                self.pallet_start_number = last_pallet + 2
            elif self.pallet_start_number == last_pallet + 2 and self.sequence_step == 'serial':
                self.pallet_start_number = last_pallet + 1

#     @api.multi
    def create_packages(self):
        if self.pallet_start_number < 0 or self.number_of_pallets < 0 or self.product_qty_per_pallet < 0:
            raise ValidationError("The Number of Pallets, Pallet Start Number, and Product Quantity per Pallet "
                                  "must all be a positive number.")

        if self.number_of_pallets == 0:
            raise ValidationError("Number of pallets must be greater than 0.")
        if self.number_of_pallets > 350:
            raise ValidationError("Number of pallets must be less than 350.")
        # Loop by the number of pallets to be packed.
        if self.sequence_step == 'serial':
            xrange_list = range(self.pallet_start_number, self.pallet_start_number + self.number_of_pallets)
        else:
            xrange_list = range(self.pallet_start_number, self.pallet_start_number + (self.number_of_pallets * 2), 2)
#         gen_date = datetime.strptime(self.gen_date or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
        gen_date = self.gen_date or fields.Datetime.now()
        lot_name = self.production_id.product_id.gen_lot_code(user_defined=self.user_defined, gen_date=gen_date)

        self.production_id.sequence_step = self.sequence_step

        if len(self.env['stock.production.lot'].search(['&', ('name', '=', lot_name), ('product_id', '=', self.production_id.product_id.id)])) == 0:
            lot_id = self.env['stock.production.lot'].create({
                'name': lot_name,
                'product_id': self.production_id.product_id.id,
                'gen_date': gen_date,
                'company_id': self.production_id.company_id.id,
            })
            lot_id.sudo()._use_gen_date()
        else:
            lot_id = self.env['stock.production.lot'].search(['&', ('name', '=', lot_name), ('product_id', '=', self.production_id.product_id.id)])

        picking_ids = self.picking_ids.filtered(lambda x:
                                                x.picking_type_id.id == self.manu_packing_type_id.id
                                                and x.state not in ['done', 'cancel'])

        for wo in self.production_id.workorder_ids.filtered(lambda w: w.state not in ['done', 'cancel']):
            if wo.finished_lot_id.id is False:
                wo.finished_lot_id = lot_id.id

            # If there are no packages and the start number is greater than 1
            if not self.production_id.package_ids and self.pallet_start_number > 1:
                wo.current_step = self.pallet_start_number - 1

        for x in xrange_list:
            pallet_number = str(x).zfill(3)

            pallet_code = self.production_id.product_id.gen_pallet_code(warehouse_code=self.warehouse_code,
                                                                        pallet_number=pallet_number,
                                                                        user_defined=self.user_defined,
                                                                        gen_date=gen_date)

            if len(self.env['stock.quant.package'].search([('name', '=', pallet_code)])) == 0:
                package = self.env['stock.quant.package'].create({
                    'name': pallet_code,
                    'default_lot_code_id': lot_id.id,
                    'production_id': self.production_id.id,
                    'pallet_number': int(pallet_number),
                    'company_id': self.production_id.company_id.id,
                })
            else:
                package = self.env['stock.quant.package'].search([('name', '=', pallet_code)])
                # If the package was created outside of an MO, we can set the package production id.
                if not package.production_id:
                    package.production_id = self.production_id.id
                if package.production_id.id and package.production_id.id != self.production_id.id:
                    raise ValidationError("One of the packages you are trying to create is already associated with "
                                          "another production order. \n"
                                          "\n" + package.production_id.name + " " + package.name)
                if package.location_id.id is not False and package.location_id.id != self.production_id.location_dest_id.id:
                    raise ValidationError("You are trying to create a pallet that already exists in a different location: " + pallet_code)

        return

    # Action Button: put_in_pack, then relaunch new wizard.
    @api.model
    def default_get(self, fields):
        rec = super(MrpWorkcenterPalletWizard, self).default_get(fields)
        context = dict(self._context or {})

        description = ''
        regex = re.compile(r'\[USER_DEFINED_([\w_]+)\]')
        match = None
        date_planned = False
        if context.get('active_id', False) is False:
            #TODO: Fix this error.
            raise ValidationError('Cannot run pallet generation on multiple workorders or manufacturing orders. Please only run on one at a time.')

        if context.get('default_production_id', False):
            production_id = self.env['mrp.production'].browse(context.get('default_production_id'))
            if production_id.product_id.pallet_abbv is not False:
                match = regex.search(production_id.product_id.pallet_abbv)
            date_planned = production_id.date_planned_start

        elif context.get('active_model', '') == 'mrp.production':
            production_id = self.env['mrp.production'].browse(context.get('active_id'))
            if production_id.product_id.pallet_abbv is not False:
                match = regex.search(production_id.product_id.pallet_abbv)
            date_planned = production_id.date_planned_start

        if match is not None and isinstance(match.group(1), str):
            description = match.group(1).replace('_', ' ').title()

        rec.update({
            'production_id': production_id.id,
            'description': description,
            'gen_date': date_planned,
            'product_qty_per_pallet': 1.00,
            'sequence_step': 'serial',
            'pallet_start_number': 1,
            'sequence_step': context.get('sequence_step', 'serial'),
            'paper_size': context.get('paper_size', 'letter')
        })

        return rec

#     @api.multi
    def _return_print(self):
        if len(self.production_id.package_ids) == 0:
            raise ValidationError('Unable to print because there are no packages associated with this Manufacturing Order.')
        self.page_from = self.page_from - 1 if self.page_from > 0 else 0
        if self.page_to > len(self.production_id.package_ids):
            raise ValidationError("The page selected does not exist. The maximum number of packages available to print is " + str(len(self.production_id.package_ids)))
        if self.page_from > self.page_to or self.page_to == 0:
            self.page_from = 0
            self.page_to = len(self.production_id.package_ids)

        if self.paper_size == 'letter':
            paper_size_key = 'product_auto_lot.action_report_stock_package_card_letter'
        else:
            paper_size_key = 'product_auto_lot.action_report_stock_package_card'
#         return True
        return self.env.ref(paper_size_key).report_action(self.production_id.package_ids[self.page_from:self.page_to])
#         return self.env['report'].get_action(self.production_id.package_ids[self.page_from:self.page_to], paper_size_key)

#     @api.multi
    def _return_view_mrp_generate_pallet(self):
        imd = self.env['ir.model.data'].sudo()

        action = imd.xmlid_to_object('product_auto_lot.action_view_generate_pallet_code_wizard')
        form_view_id = imd.xmlid_to_res_id('product_auto_lot.view_generate_pallet_code_wizard')

        action.context = str({
            'default_production_id': self.production_id.id,
            'sequence_step': self.sequence_step,
        })

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }

        return result

    ##
    ##
    ## Buttons
    ##
    ##

#     @api.multi
    def action_generate_and_print(self):
        number_packages = len(self.production_id.package_ids.ids)
        self.create_packages()
        if number_packages > 0:
            self.page_from = number_packages+1
            self.page_to = len(self.production_id.package_ids.ids)
        # Return printed report.
        action_dict = self._return_print()

        return action_dict

#     @api.multi
    def action_print(self):

        # Do nothing, print report.
        action_dict = self._return_print()

        return action_dict
    
    def action_view_generate_pallet_code_wizard(self):
        action = self.env.ref('product_auto_lot.action_view_generate_pallet_code_wizard').sudo()
        result = action.read()[0]
        print(action)
        print(result)
        return action

