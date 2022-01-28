# -*- coding: utf-8 -*-

import math

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

import re


class MrpWorkcenterLotWizard(models.TransientModel):
    _name = "mrp.workcenter.lot.wizard"
    _description = "Workcenter Lot Code Generator"

    workorder_id = fields.Many2one('mrp.workorder', 'Workorder')
    product_id = fields.Many2one('product.product', 'Product', related='workorder_id.product_id', readonly=True)
    company_id = fields.Many2one('res.company')

    lot_name = fields.Char('Lot Code')

    gen_date = fields.Datetime('Date of Manufacture')

    user_defined = fields.Char('Variable', help="This could refer to the machine or rack number. Refer to a supervisor or company procedure manual if you are unsure what to enter.")

    description = fields.Char('Description', readonly=True)

    @api.onchange('user_defined', 'gen_date')
    def _user_defined(self):
#         gen_date = datetime.strptime(self.gen_date or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
        gen_date = self.gen_date or fields.Datetime.now()
        self.lot_name = self.with_context(
            default_workorder_id=self.workorder_id.id).workorder_id.product_id.gen_lot_code(
                                                                    user_defined=self.user_defined,
                                                                    gen_date=gen_date)

    @api.onchange('workorder_id')
    def _on_workorder_id(self):
        if self.workorder_id.id:
#             gen_date = datetime.strptime(self.gen_date or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
            gen_date = self.gen_date or fields.Datetime.now()
            self.lot_name = self.with_context(default_workorder_id=self.workorder_id.id).workorder_id.product_id.gen_lot_code(self.user_defined, gen_date=gen_date)

            regex = re.compile(r'\[USER_DEFINED_([\w_]+)\]')
            match = regex.search(self.workorder_id.product_id.lot_abbv)
            if match is not None and isinstance(match.group(1), str):
                self.description = match.group(1).capitalize()

#     @api.multi
    def save_lot_code(self):
        stock_production_lot = self.env['stock.production.lot']
#         gen_date = datetime.strptime(self.gen_date or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
        gen_date = self.gen_date or fields.Datetime.now()
        lot_name = self.with_context(default_workorder_id=self.workorder_id.id).workorder_id.product_id.gen_lot_code(self.user_defined, gen_date=gen_date)
        existing_lot_id = stock_production_lot.search(['&', ('name', '=', lot_name), ('product_id', '=', self.workorder_id.product_id.id)])
        if existing_lot_id:
            self.workorder_id.finished_lot_id = existing_lot_id
        else:
            self.workorder_id.finished_lot_id = self.env['stock.production.lot'].create({
                'name': self.with_context(default_workorder_id=self.workorder_id.id).workorder_id.product_id.gen_lot_code(self.user_defined, gen_date=gen_date),
                'product_id': self.workorder_id.product_id.id,
                'gen_date': gen_date,
                'company_id': self.workorder_id.production_id.company_id.id,
            }).id
            self.workorder_id.finished_lot_id.sudo()._use_gen_date()

    @api.model
    def default_get(self, fields):
        rec = super(MrpWorkcenterLotWizard, self).default_get(fields)
        context = dict(self._context or {})

        if context.get('default_workorder_id', False) is False:
            raise UserError('Unable to determine the work order.')

        regex = re.compile(r'\[USER_DEFINED_([\w_]+)\]')
        workorder = self.env['mrp.workorder'].browse(context.get('default_workorder_id', False))
        match = regex.search(workorder.product_id.lot_abbv)
        if match is not None and isinstance(match.group(1), str):
            description = match.group(1).replace('_', ' ').title()
            rec['description'] = description

        if rec.get('gen_date', False) is False:
            rec['gen_date'] = workorder.date_planned_start

        return rec
    
    def action_view_generate_lot_code_wizard(self):
        action = self.env.ref('product_auto_lot.action_view_generate_lot_code_wizard').sudo()
        result = action.read()[0]
        print(action)
        print(result)
        return action

