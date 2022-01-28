# -*- coding: utf-8 -*-


from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.addons import decimal_precision as dp


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    lot_abbv = fields.Char('Lot Code', help='This value will be used in lot code generation where \n'
                                            '[WORKCENTER_CODE] is defined.')

