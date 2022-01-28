# -*- coding: utf-8 -*-

from odoo import api, models, fields
from odoo.addons import decimal_precision as dp
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError

import re


class MrpImportPackages(models.TransientModel):
    _name = 'mrp.import.packages.wizard'
    _description = "Import Packages to Manufacturing Order"

    lot_code = fields.Char('Lot Code')
    user_defined = fields.Char('Variable', help="This could refer to the machine or rack number. "
                                                "Refer to a supervisor or company procedure manual "
                                                "if you are unsure what to enter.")

    description = fields.Char('Description', readonly=True)

    production_id = fields.Many2one('mrp.production', string='Production Order')

    @api.model
    def default_get(self, rec_fields):
        rec = super(MrpImportPackages, self).default_get(rec_fields)
        context = dict(self._context or {})

        if context.get('default_production_id', False) is False:
            raise UserError('Unable to determine the manufacturing order.')

        regex = re.compile(r'\[USER_DEFINED_([\w_]+)\]')
        production = self.env['mrp.production'].browse(context.get('default_production_id', False))
        rec['production_id'] = production.id

        match = regex.search(production.product_id.lot_abbv or "")
        if match is not None and isinstance(match.group(1), str):
            description = match.group(1).replace('_', ' ').title()
            rec['description'] = description

#         gen_date = datetime.strptime(production.date_planned_start, DEFAULT_SERVER_DATETIME_FORMAT)
        gen_date = production.date_planned_start
        rec['lot_code'] = production.product_id.gen_lot_code(gen_date=gen_date)

        return rec

    @api.onchange('user_defined', 'production_id')
    def _user_defined(self):
        if self.production_id:
#             gen_date = datetime.strptime(self.production_id.date_planned_start, DEFAULT_SERVER_DATETIME_FORMAT)
            gen_date = self.production_id.date_planned_start
            self.lot_code = self.with_context(
                default_production_id=self.production_id.id).production_id.product_id.gen_lot_code(
                user_defined=self.user_defined,
                gen_date=gen_date)

    def action_import_packages(self):
        self.ensure_one()

#         gen_date = datetime.strptime(self.production_id.date_planned_start, DEFAULT_SERVER_DATETIME_FORMAT)
        gen_date = self.production_id.date_planned_start
        lot_code = self.production_id.product_id.with_context(default_production_id=self.production_id.id).gen_lot_code(user_defined=self.user_defined, gen_date=gen_date)
        lot_id = self.env['stock.production.lot'].search(
            [('name', '=', lot_code), ('product_id', '=', self.production_id.product_id.id)])

        if lot_id:
            packages = self.env['stock.quant.package'].search(
                [('default_lot_code_id', '=', lot_id.id), ('end_date', '=', False)])

            if not packages:
                raise UserError("No packages were found.")

            if packages:
                packages.write({'production_id': self.production_id.id})
                current_step = packages.sorted(key=lambda r: r.pallet_number)[0].pallet_number - 1
                self.production_id.workorder_ids.write({'finished_lot_id': packages[0].default_lot_code_id.id})
                if current_step > 0:
                    self.production_id.workorder_ids.write({'current_step': current_step})
                    
                    
    def action_view_import_package_wizard(self):
        action = self.env.ref('mrp_batch_pallet_making.action_view_import_package_wizard').sudo()
        result = action.read()[0]
        print(action)
        print(result)
        return action
        
        
        
        
        
        
        
        
        

