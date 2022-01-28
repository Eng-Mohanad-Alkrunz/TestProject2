# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import float_compare, float_round, float_is_zero


class MrpRouting(models.Model):
    _inherit = 'mrp.routing.workcenter'

    routing_type = fields.Selection([('sequenced', 'Sequence'),
                                        ('parallel', 'Parallel')], 'Routing Type',
                                       default='sequenced',
                                       required=True,
                                       help='Sequence - All workorder operations happen in sequence.\n'
                                            'Parallel - All workorder operations happen in parallel.')
