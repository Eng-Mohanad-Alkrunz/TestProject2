# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

from datetime import datetime
from dateutil import tz

from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round, float_compare
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

import string
import re
import logging

class ProductTemplate(models.Model):
    _inherit = "product.template"


    lot_abbv = fields.Char('Lot Code Format', help='To assist with manufacturing, '
                                'lot codes will automatically generate with this prefix.\n'
                                'You can add other pieces to be generated, such as \n'
                                '- [DATE]\n yyyymmdd'
                                '- [JULIAN] - Julian date code\n'
                                '- [JULIAN_DAY] - Julian day\n'
                                '- [YEARYY] - Last two digits of year\n'
                                '- [MONTH] - 01-12 Month\n'
                                '- [DAY] - 01-31 Day\n'
                                '- [YEAR] - Full year\n' 
                                '- [OPERATION_CODE] - Manufacturing Operation Code\n'                                
                                '- [WAREHOUSE_CODE] - Warehouse Code\n'
                                '- [USER_DEFINED] - Variable will be entered by user when creating lot\n'         
                                'For example, CCSS-[JULIAN_DAY]-[YEARYY] will output the Julian datecode: CCSS-19118\n'
                                'Add an extra underscore to offer employees tips on the user defined variable, \n'
                                'such as [USER_DEFINED_MACHINE_NUMBER], will print "Machine Number" below the field.\n')

    pallet_abbv = fields.Char('Pallet Code Format', help='To assist with manufacturing, '
                               'lot codes will automatically generate with this prefix.\n'
                               'You can add other pieces to be generated, such as \n'
                               '- [DATE]\n yyyymmdd'
                               '- [JULIAN] - Julian date code\n'
                               '- [JULIAN_DAY] - Julian day\n'
                               '- [YEARYY] - Last two digits of year\n'
                               '- [MONTH] - 01-12 Month\n'
                               '- [MM] - 01-12 Month\n' 
                               '- [DAY] - 01-31 Day\n'
                               '- [DD] - 01-31 Day\n' 
                               '- [YEAR] - Full year\n' 
                               '- [YY] - Full year\n' 
                               '-[YYMMDD] - YearMonthDay\n'
                               '-[DDMMYY] - DayMonthYear\n'
                               '-[MMDDYY] - MonthDayYear\n'
                               '- [OPERATION_CODE] - Manufacturing Operation Code\n'
                               '- [WORKCENTER_CODE] - The Workcenter Code\n'                                
                               '- [WAREHOUSE_CODE] - Warehouse Code\n'
                               '- [MACHINE_NO] - Machine Number\n'
                               '- [PALLET_NO] - Pallet Number\n'
                               '- [LOT_CODE] - Lot Code to be packed (Only one lot per package)\n'
                               '- [USER_DEFINED] - Variable will be entered by user when creating lot\n'
                               'For example, CCSS-[JULIAN_DAY]-[YEARYY] will output the Julian datecode: CCSS-19118\n'
                               'Add an extra underscore to offer employees tips on the user defined variable, \n'
                               'such as [USER_DEFINED_VERSION], will print "Version Number" below the field.\n')


class ProductProduct(models.Model):
    _inherit = "product.product"

    lookup_code = fields.Char(string='Product Code')
    last_lot_idx = fields.Char('Last lot index', help='Returns Last idx')

    @api.model
    def _regex(self, lotcode, search, user_defined):
        result = re.sub(search, user_defined or '', lotcode)
        return result

    @api.model
    def gen_lot_code(self, user_defined='', gen_date=datetime.now()):
        if self.lot_abbv is False:
            # If no format is specified.
            julian = '%d%03d' % (gen_date.timetuple().tm_year, gen_date.timetuple().tm_yday)
            if self.default_code is not False:
                return str(self.default_code) + str('-') + julian
            else:
                return julian

        if self.env.context.get('tz', False):
            gen_date = gen_date.replace(tzinfo=tz.tzutc())
            gen_date = gen_date.astimezone(tz.gettz(self.env.context['tz']))



        lot_name = self.lot_abbv
        if "[000]" in lot_name:
            cr = self.env.cr
            sql = """
            SELECT last_lot_idx FROM product_product
            where last_lot_idx is not NULL
            ORDER BY last_lot_idx DESC  """
            cr.execute(sql)
            response = cr.dictfetchall()
            _logger = logging.getLogger(__name__)
            if len(response) > 0:
                last_index = response[0]['last_lot_idx']
                if last_index is None:
                    last_index = "001"
                else:
                    last_index = int(last_index) + 1
                    if last_index < 10:
                        last_index = "00"+str(last_index)
                    elif last_index >= 10 and last_index <= 99:
                        last_index = "0"+str(last_index)
                    else:
                        last_index = str(last_index)
                lot_name = str.replace(lot_name,'[000]',last_index,1)
                self.env.cr.execute(f"""
                            Update  product_product
                            SET last_lot_idx= '{last_index}'
                            where id = '{self.id}'
                            """)
            else:
                lot_name = str.replace(lot_name, '[000]', "001", 1)



        lot_name = str.replace(lot_name, '[JULIAN]', '%d%03d' % (gen_date.timetuple().tm_year, gen_date.timetuple().tm_yday), 1)
        lot_name = str.replace(lot_name, '[JULIAN_DAY]', str(gen_date.timetuple().tm_yday).zfill(3), 1)
        lot_name = str.replace(lot_name, '[YEARYY]', gen_date.strftime("%y"), 1)
        lot_name = str.replace(lot_name, '[YEAR]', gen_date.strftime("%Y"), 1)
        lot_name = str.replace(lot_name, '[YYYY]', gen_date.strftime("%Y"), 1)
        lot_name = str.replace(lot_name, '[STATION_CODE]', '', 1)
        lot_name = str.replace(lot_name, '[DATE]', fields.Date.to_string(gen_date), 1)

        lot_name = str.replace(lot_name, '[MMDDYY]', gen_date.strftime("%m").zfill(2)+gen_date.strftime("%d").zfill(2)+gen_date.strftime("%Y"), 1)
        lot_name = str.replace(lot_name, '[DDMMYY]', gen_date.strftime("%d").zfill(2)+gen_date.strftime("%m").zfill(2)+gen_date.strftime("%Y"), 1)
        lot_name = str.replace(lot_name, '[YYMMDD]', gen_date.strftime("%Y")+gen_date.strftime("%m").zfill(2)+gen_date.strftime("%d").zfill(2), 1)


        lot_name = str.replace(lot_name, '[DAY]', gen_date.strftime("%d").zfill(2), 1)
        lot_name = str.replace(lot_name, '[DD]', gen_date.strftime("%d").zfill(2), 1)
        lot_name = str.replace(lot_name, '[MONTH]', gen_date.strftime("%m").zfill(2), 1)
        lot_name = str.replace(lot_name, '[MM]', gen_date.strftime("%m").zfill(2), 1)
        lot_name = str.replace(lot_name, '[SECOND]', gen_date.strftime("%S").zfill(2), 1)
        lot_name = str.replace(lot_name, '[HOUR]', gen_date.strftime("%H").zfill(2), 1)
        lot_name = str.replace(lot_name, '[MINUTE]', gen_date.strftime("%M").zfill(2), 1)

        #TODO: implement STATION_CODE and WAREHOUSE_CODE
        # lot_name = str.replace(lot_name, '[STATION_CODE]', '', 1)

        context = dict(self._context or {})

        if context.get('default_workorder_id', False) is not False:
            workorder_id = self.env['mrp.workorder'].browse(context.get('default_workorder_id', False))
            if workorder_id.production_id.picking_type_id.lot_abbv:
                lot_name = str.replace(lot_name, '[OPERATION_CODE]', workorder_id.production_id.picking_type_id.lot_abbv, 1)
            if workorder_id.production_id.picking_type_id.warehouse_id.lot_abbv:
                lot_name = str.replace(lot_name, '[WAREHOUSE_CODE]', workorder_id.production_id.picking_type_id.warehouse_id.lot_abbv, 1)
            if workorder_id.workcenter_id.lot_abbv:
                lot_name = str.replace(lot_name, '[WORKCENTER_CODE]', workorder_id.workcenter_id.lot_abbv, 1)
        if context.get('default_production_id', False) is not False:
            production_id = self.env['mrp.production'].browse(context.get('default_production_id', False))
            if production_id.picking_type_id.lot_abbv:
                lot_name = str.replace(lot_name, '[OPERATION_CODE]', production_id.picking_type_id.lot_abbv, 1)
            if production_id.picking_type_id.warehouse_id.lot_abbv:
                lot_name = str.replace(lot_name, '[WAREHOUSE_CODE]', production_id.picking_type_id.warehouse_id.lot_abbv, 1)
            # If on a production order, we should only do it if there is one workorder, one workcenter..
            if len(production_id.workorder_ids) == 1 and production_id.workorder_ids.workcenter_id.lot_abbv:
                lot_name = str.replace(lot_name, '[WORKCENTER_CODE]', production_id.workorder_ids.workcenter_id.lot_abbv, 1)

        if user_defined:
            # lot_name = str.replace(lot_name, '[USER_DEFINED]', user_defined, 1)
            lot_name = self._regex(lotcode=lot_name, search=r'\[USER_DEFINED_?[\w_]*\]', user_defined=user_defined)

        #TODO: Replace any sequential dashes with single dashes.
        return lot_name

    @api.model
    def gen_pallet_code(self, machine_number='0', warehouse_code='', operation_code='', pallet_number='', user_defined='', lot_code='', gen_date=datetime.now()):
        if self.pallet_abbv is False:
            # If no format is specified.
            julian = '%d%03d' % (gen_date.timetuple().tm_year, gen_date.timetuple().tm_yday)
            if pallet_number is not '':
                julian = julian + '-' + str(pallet_number).zfill(3)
            if self.default_code is not False:
                return str(self.default_code) + str('-') + julian
            else:
                return julian

        if self.env.context.get('tz', False):
            gen_date = gen_date.replace(tzinfo=tz.tzutc())
            gen_date = gen_date.astimezone(tz.gettz(self.env.context['tz']))

        lot_name = self.pallet_abbv
        lot_name = str.replace(lot_name, '[JULIAN]', '%d%03d' % (gen_date.timetuple().tm_year, gen_date.timetuple().tm_yday), 1)
        lot_name = str.replace(lot_name, '[JULIAN_DAY]', str(gen_date.timetuple().tm_yday).zfill(3), 1)
        lot_name = str.replace(lot_name, '[YEARYY]', gen_date.strftime("%y"), 1)
        lot_name = str.replace(lot_name, '[YEAR]', gen_date.strftime("%Y"), 1)
        lot_name = str.replace(lot_name, '[STATION_CODE]', '', 1)
        lot_name = str.replace(lot_name, '[DATE]', fields.Date.to_string(gen_date), 1)

        lot_name = str.replace(lot_name, '[DAY]', gen_date.strftime("%d").zfill(2), 1)
        lot_name = str.replace(lot_name, '[MONTH]', gen_date.strftime("%m").zfill(2), 1)
        lot_name = str.replace(lot_name, '[SECOND]', gen_date.strftime("%S").zfill(2), 1)
        lot_name = str.replace(lot_name, '[HOUR]', gen_date.strftime("%H").zfill(2), 1)
        lot_name = str.replace(lot_name, '[MINUTE]', gen_date.strftime("%M").zfill(2), 1)

        # TODO: implement STATION_CODE and WAREHOUSE_CODE
        # lot_name = str.replace(lot_name, '[STATION_CODE]', '', 1)

        context = dict(self._context or {})

        if context.get('default_workorder_id', False) is not False:
            workorder_id = self.env['mrp.workorder'].browse(context.get('default_workorder_id', False))
            if workorder_id.production_id.picking_type_id.lot_abbv:
                lot_name = str.replace(lot_name, '[OPERATION_CODE]',
                                          workorder_id.production_id.picking_type_id.lot_abbv, 1)
            if workorder_id.workcenter_id.lot_abbv:
                lot_name = str.replace(lot_name, '[WORKCENTER_CODE]', workorder_id.workcenter_id.lot_abbv, 1)
        if context.get('default_production_id', False) is not False:
            production_id = self.env['mrp.production'].browse(context.get('default_production_id', False))
            if production_id.picking_type_id.lot_abbv:
                lot_name = str.replace(lot_name, '[OPERATION_CODE]', production_id.picking_type_id.lot_abbv, 1)
            if production_id.picking_type_id.warehouse_id.lot_abbv:
                lot_name = str.replace(lot_name, '[WAREHOUSE_ID]', production_id.picking_type_id.warehouse_id.lot_abbv, 1)
            if len(production_id.workorder_ids) == 1 and production_id.workorder_ids.workcenter_id.lot_abbv:
                lot_name = str.replace(lot_name, '[WORKCENTER_CODE]', production_id.workorder_ids.workcenter_id.lot_abbv, 1)

        if operation_code or warehouse_code:
            if operation_code:
                lot_name = str.replace(lot_name, '[OPERATION_CODE]', operation_code)
            if warehouse_code:
                lot_name = str.replace(lot_name, '[WAREHOUSE_CODE]', warehouse_code)

        lot_name = str.replace(lot_name, '[MACHINE_NO]', machine_number or '', 1)
        lot_name = str.replace(lot_name, '[LOT_CODE]', lot_code or '', 1)

        if user_defined:
            # lot_name = str.replace(lot_name, '[USER_DEFINED]', user_defined or '', 1)
            lot_name = self._regex(lotcode=lot_name, search=r'\[USER_DEFINED_?[\w_]*\]', user_defined=user_defined)

        if '[PALLET_NO]' not in lot_name:
            lot_name = lot_name + '-' + str(pallet_number).zfill(3)
        else:
            lot_name = str.replace(lot_name, '[PALLET_NO]', str(pallet_number).zfill(3) or '', 1)

        return lot_name

