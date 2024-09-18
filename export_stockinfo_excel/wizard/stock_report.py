
import io
import json
from datetime import datetime
from urllib import request
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
from odoo import api, fields, models, _
from odoo.tools import date_utils

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class StockReport(models.TransientModel):
   

    _name = "stock.xls.report"
    _description = "Current Stock History"

    tracking_wise = fields.Selection([
        ('warehouse_wise', 'warehouse'),
        ('location_wise', 'location ') ],
        string='Generate Report Based on',  required=True)
    warehouse = fields.Many2many('stock.warehouse', string='Warehouse')
    location = fields.Many2many('stock.location', string='Location')
    category = fields.Many2many('product.category')
    supplier= fields.Many2many('res.partner',  invisible=True)

    start_date=fields.Datetime(string='From date' )
    end_date=fields.Datetime(string='To date' )
    enable_red_text = fields.Boolean(string='Enable Red Text for Negative Quantity')

    filter_active = fields.Boolean(string='Active Product Only')
    
    @api.constrains('tracking_wise')
    def _check_tracking_wise(self):
        for record in self:
            if not record.tracking_wise:
                raise ValidationError(_("Please choose 'warehouse' or 'location' to generate Report."))

    def validate_fields(self):
        if not self.tracking_wise:
            raise UserError(_("Please choose 'warehouse' or 'location' to generate Report."))
        if self.tracking_wise == 'warehouse_wise' and not self.warehouse:
            raise UserError(_("Please choose at least one warehouse."))
        elif self.tracking_wise == 'location_wise' and not self.location:
            raise UserError(_("Please choose at least one location."))
        

    def export_xls(self):
        self.validate_fields()

      

        data = {
            'ids': self.ids,
            'model': self._name,
            'warehouse': self.warehouse.ids ,
            'location': self.location.ids ,
            'category': self.category.ids,  # Pass selected category IDs
            'supplier': self.supplier.ids,  # Add selected supplier IDs
            'start_date':self.start_date,
            'end_date':self.end_date,
        }
        
        if self.tracking_wise == 'location_wise':
            lines = self.get_lines_location(data ,self.location.ids)
        print(data,"ppppppppppppppppppppppppppppppppppppppppppppppppppppppppppp")
       
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'stock.xls.report',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Export Stock product',
                     },
            'report_type': 'stock_xlsx'
        }


    def get_warehouse(self, data):
        wh = data.warehouse.mapped('id')
        obj = self.env['stock.warehouse'].search([('id', 'in', wh)])
        l1 = []
        l2 = []
        for j in obj:
            l1.append(j.name)
            l2.append(j.id)
        return l1, l2
    
    def get_location(self, data):
        loc = data.location.mapped('id')
        obj = self.env['stock.location'].search([('id', 'in', loc)])
        l1 = []
        l2 = []
        for j in obj:
            l1.append(j.display_name)
            l2.append(j.id)
        return l1, l2

    def get_supplier(self, data):
        sup = data.supplier.mapped('id')
        obj = self.env['res.partner'].search([('id', 'in', sup)])
        supplier_name = []
        supplier_id = []
        for j in obj:
            supplier_name.append(j.display_name)
            supplier_id.append(j.id)
        print(supplier_name,supplier_id,"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        return supplier_name,supplier_id
    


    def get_lines_warehouse(self, send_data, warehouse,supplier_name ):
        print('HAUEEUUDFUDVDSKVFVFDDBDFMBGFFMBFGMB FGM FG FG MF MFMM MF MFM FM FM MF',send_data)
        lines = []
       
       
       

        self._cr.execute("""
            SELECT view_location_id 
            FROM stock_warehouse 
            WHERE id in(%s) 
        """, (warehouse,))
        view_location_id = self._cr.fetchone()
        if not view_location_id:
            raise ValueError("The specified warehouse does not exist.")
        view_location_id = view_location_id[0]

        # Retrieve all locations under the warehouse's view_location_id
        self._cr.execute("""
            WITH RECURSIVE location_tree AS (
                SELECT id, location_id
                FROM stock_location
                WHERE id in (%s)
                UNION ALL
                SELECT sl.id, sl.location_id
                FROM stock_location sl
                INNER JOIN location_tree lt ON lt.id = sl.location_id
            )
            SELECT id, name
            FROM stock_location
            WHERE id IN (SELECT id FROM location_tree)
        """, (view_location_id,))

        # Fetch all locations
        all_locations = self._cr.fetchall()

        # Print or process the locations
        # locations_list = [loc[0] for loc in all_locations]
        locations_list = tuple([loc[0] for loc in all_locations])
        # print(f"locations_list: {locations_list}")
        # for location_name in locations_list:
        #     print(f"Location: {location_name}")
        
        if send_data['supplier']:
            supplier_ids = tuple([sup for sup in send_data['supplier']])
            
            # Start constructing the sale_query
            sale_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id, 
                    date(s_p.date_done), 
                    p_t.categ_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            sale_query += f" AND s_p.location_id in {locations_list}"
            
            # Handle single or multiple supplier IDs
            if len(supplier_ids) == 1:
                supplier_id = supplier_ids[0]
                sale_query += f" AND s_p.partner_id = {supplier_id}"
            else:
                sale_query += f" AND s_p.partner_id in {supplier_ids}"
            
            # Group by clause for sale_query
            sale_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id,
                s_p.date_done,
                p_t.categ_id;
            """

            # Start constructing the purchase_query
            purchase_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            purchase_query += f" AND s_p.location_dest_id in {locations_list}"
            
            # Handle single or multiple supplier IDs
            if len(supplier_ids) == 1:
                supplier_id = supplier_ids[0]
                purchase_query += f" AND s_p.partner_id = {supplier_id}"
            else:
                purchase_query += f" AND s_p.partner_id in {supplier_ids}"
            
            # Group by clause for purchase_query
            purchase_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id;
            """
            
            # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            
            # Ensure product_ids is a tuple
            products = tuple(product)
            print("OOODEODOEODOEODEODOEDOEODODEDOE", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]

      
        elif send_data['start_date'] and send_data['end_date']:
            start_date = send_data['start_date']
            end_date = send_data['end_date']
            
            # Start constructing the sale_query
            sale_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id, 
                    date(s_p.date_done), 
                    p_t.categ_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            sale_query += f" AND s_p.location_id in {locations_list}"
            
            # sale_query += f" AND s_p.date_done BETWEEN '{start_date}' AND '{end_date} ' "
            sale_query += f" AND s_p.date_done >= '{start_date}' AND s_p.date_done < '{end_date}'"


            # Group by clause for sale_query
            sale_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id,
                s_p.date_done,
                p_t.categ_id;
            """

            # Start constructing the purchase_query
            purchase_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            purchase_query += f" AND s_p.location_dest_id in {locations_list}"
            
            # purchase_query += f" AND s_p.date_done BETWEEN '{start_date}' AND '{end_date} ' "
            purchase_query += f" AND s_p.date_done >= '{start_date}' AND s_p.date_done < '{end_date}'"

            # Group by clause for purchase_query
            purchase_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id;
            """
            

            sale_query1="""
                SELECT sum(quantity) as product_uom_qty,s_q.product_id as product_id,s_q.in_date
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id

                
            """
            sale_query1 += f" AND s_q.location_id in {locations_list}"

            # sale_query1 += f" AND s_q.in_date  BETWEEN '{start_date}' AND '{end_date} ' "
            sale_query1 += f" AND s_q.in_date >= '{start_date}' AND s_q.in_date < '{end_date}'"

            sale_query1 += """
            GROUP BY 
                s_q.product_id , s_q.in_date;
            """
            purchase_query1="""
                SELECT sum(quantity) as product_uom_qty,s_q.product_id as product_id,s_q.in_date
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id


            """
            purchase_query1 += f" AND s_q.location_id in {locations_list}"

            # purchase_query1 += f" AND s_q.in_date  BETWEEN '{start_date}' AND '{end_date} ' "
            purchase_query1 += f" AND s_q.in_date >= '{start_date}' AND s_q.in_date < '{end_date}'"

            purchase_query1 += """
            GROUP BY 
               s_q.product_id , s_q.in_date;
            """

             # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()
             # Execute the sale_query and fetch results
            self._cr.execute(sale_query1)
            sol_query_obj1 = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query1)
            pol_query_obj1 = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            product1 = [record['product_id'] for record in pol_query_obj1]


            # Ensure product_ids is a tuple
            products = tuple(product + product1)
            print("OOODEODOEODOEODEODOEDOEODODEDOE", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]


        elif send_data['category']:
            category_ids=tuple([cat for cat in send_data['category']])
            print(category_ids,'kjjkjkjkjkjkjkjkjkjkjjkjkjkjkjkjkjk')

            sale_query="""
                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                    FROM stock_move as s_m
                    join stock_picking as s_p on s_p.id=s_m.picking_id
                    join product_product as p_p on p_p.id=s_m.product_id
                    join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            sale_query += f" AND s_p.location_id in {locations_list}"

            if len(category_ids) == 1:
                category_id = category_ids[0]
                sale_query += f" AND p_t.categ_id = {category_id}"
            else:
                sale_query += f" AND p_t.categ_id in {category_ids}"
            
            sale_query += """
            GROUP BY 
               s_m.product_id,s_m.picking_type_id;
            """
            purchase_query="""
                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                    FROM stock_move as s_m
                    join stock_picking as s_p on s_p.id=s_m.picking_id
                    join product_product as p_p on p_p.id=s_m.product_id
                    join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            purchase_query += f" AND s_p.location_dest_id in {locations_list}"

            if len(category_ids) == 1:
                category_id = category_ids[0]
                purchase_query += f" AND p_t.categ_id = {category_id}"
            else:
                purchase_query += f" AND p_t.categ_id in {category_ids}"
            
            purchase_query += """
            GROUP BY 
               s_m.product_id,s_m.picking_type_id;
            """

            sale_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id ,p_t.categ_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            sale_query1 += f" AND s_q.location_id in {locations_list}"

            
            if len(category_ids) == 1:
                category_id = category_ids[0]
                sale_query1 += f" AND p_t.categ_id = {category_id}"
            else:
                sale_query1 += f" AND p_t.categ_id in {category_ids}"
            
            sale_query1 += """
            GROUP BY 
               s_q.quantity,s_q.product_id ,p_t.categ_id;
            """

            purchase_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id ,p_t.categ_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            purchase_query1 += f" AND s_q.location_id in {locations_list}"

            
            if len(category_ids) == 1:
                category_id = category_ids[0]
                purchase_query1 += f" AND p_t.categ_id = {category_id}"
            else:
                purchase_query1 += f" AND p_t.categ_id in {category_ids}"
            
            purchase_query1 += """
            GROUP BY 
               s_q.quantity,s_q.product_id ,p_t.categ_id;
            """
            
            # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()
            

            # Execute the sale_query and fetch results
            self._cr.execute(sale_query1)
            sol_query_obj1 = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query1)
            pol_query_obj1 = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            product1 = [record['product_id'] for record in pol_query_obj1]
            print(product1,"opdspdospdospdospdospdospodpsodpsodpsodpospdospdosd")

            # Ensure product_ids is a tuple
            products = tuple(product + product1 )

            # Ensure product_ids is a tuple
            # products = tuple(product)
            print("categoryyyyyyyyyyyy done", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]

        else:
            sale_query="""

                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                FROM stock_move as s_m
                join stock_picking as s_p on s_p.id=s_m.picking_id
                join product_product as p_p on p_p.id=s_m.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            sale_query += f" AND s_p.location_id in {locations_list}"
            
            sale_query += """
            GROUP BY 
                s_m.product_id,s_m.picking_type_id;
            """
            purchase_query="""
               	
                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                FROM stock_move as s_m
                join stock_picking as s_p on s_p.id=s_m.picking_id
                join product_product as p_p on p_p.id=s_m.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id """
            
            purchase_query += f" AND s_p.location_dest_id in {locations_list}"

            purchase_query += """
                GROUP BY 
                s_m.product_id,s_m.picking_type_id;
                """
            sale_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id """
            
            sale_query1 += f" AND s_q.location_id in {locations_list}"

           
            sale_query1 += """
                GROUP BY 
                s_q.quantity, s_q.product_id;
                """
            purchase_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id """
            purchase_query1 += f" AND s_q.location_id in {locations_list}"

           
            
            purchase_query1 += """
                GROUP BY 
                 s_q.quantity,s_q.product_id ;
                """
            # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()

            # Execute the sale_query and fetch results
            self._cr.execute(sale_query1)
            sol_query_obj1 = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query1)
            pol_query_obj1 = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            product1 = [record['product_id'] for record in pol_query_obj1]

            # Convert the lists to sets and get the difference
            unique_product1 = list(set(product1) - set(product))
            print (unique_product1,"::::::::::::::::::::::::::::::::::::::::::::")


            # Ensure product_ids is a tuple
            products = tuple(product + unique_product1 )
            print("warehouseeeeeeeeeeeeeee doneee", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]
        
        print(categ_products,'filtered_productsssssssssssssssssssss')

       
        for obj in categ_products:
            status = 'active' if obj.active else 'archive'
            sale_value = 0
            purchase_value = 0

            for sol_product in sol_query_obj:
                if sol_product['product_id'] == obj.id:
                    sale_value = sol_product['product_uom_qty']
            for pol_product in pol_query_obj:
                if pol_product['product_id'] == obj.id:
                    purchase_value = pol_product['product_uom_qty']
            virtual_available = obj.with_context({'warehouse': warehouse}).virtual_available
            outgoing_qty = obj.with_context({'warehouse': warehouse}).outgoing_qty
            incoming_qty = obj.with_context({'warehouse': warehouse}).incoming_qty
            available_qty = virtual_available + outgoing_qty - incoming_qty
            value = available_qty * obj.standard_price

            variant_values = ' , '.join([
                        f" {attr_value.name}"
                        for attr_value in obj.product_template_attribute_value_ids
                    ])
            
            vals = {
                'status': status,
                'sku': obj.default_code,
                'name': obj.name,
                'category': obj.categ_id.name,
                'cost_price': obj.standard_price,
                'available': available_qty,
                'virtual': virtual_available,
                'incoming': incoming_qty,
                'outgoing': outgoing_qty,
                'net_on_hand': obj.with_context({'warehouse': warehouse}).qty_available,
                'total_value': value,
                'sale_value': sale_value,
                'purchase_value': purchase_value,
                'variants': variant_values,

            }
            lines.append(vals)
            # print(lines)
        print(lines)
        return lines
    
    def get_lines_location(self, data, location_ids):
        lines = []
        print(data,"UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUu")
        # category_ids = data['category']

        # s=data.supplier
        supplier_ids=tuple([sup for sup in data['supplier']])
        print(supplier_ids,data,'||||||||||||||||||||||||||||||||||||||||||||||')



        if data['supplier']:
            supplier_ids = tuple([sup for sup in data['supplier']])
            
            # Start constructing the sale_query
            sale_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id, 
                    date(s_p.date_done), 
                    p_t.categ_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            
            # Handle single or multiple supplier IDs
            if len(supplier_ids) == 1:
                supplier_id = supplier_ids[0]
                sale_query += f" AND s_p.partner_id = {supplier_id}"
            else:
                sale_query += f" AND s_p.partner_id in {supplier_ids}"
            
            # Group by clause for sale_query
            sale_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id,
                s_p.date_done,
                p_t.categ_id;
            """

            # Start constructing the purchase_query
            purchase_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            
            # Handle single or multiple supplier IDs
            if len(supplier_ids) == 1:
                supplier_id = supplier_ids[0]
                purchase_query += f" AND s_p.partner_id = {supplier_id}"
            else:
                purchase_query += f" AND s_p.partner_id in {supplier_ids}"
            
            # Group by clause for purchase_query
            purchase_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id;
            """
            
            # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            
            # Ensure product_ids is a tuple
            products = tuple(product)
            print("OOODEODOEODOEODEODOEDOEODODEDOE", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]

      
        elif data['start_date'] and data['end_date']:
            start_date = data['start_date']
            end_date = data['end_date']
            
            # Start constructing the sale_query
            sale_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id, 
                    date(s_p.date_done), 
                    p_t.categ_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            
            sale_query += f" AND s_p.date_done >= '{start_date}' AND s_p.date_done < '{end_date}'"

            # Group by clause for sale_query
            sale_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id,
                s_p.date_done,
                p_t.categ_id;
            """

            # Start constructing the purchase_query
            purchase_query = """
                SELECT 
                    sum(product_uom_qty) as product_uom_qty, 
                    s_m.product_id as product_id, 
                    s_m.picking_type_id
                FROM 
                    stock_move as s_m
                JOIN 
                    stock_picking as s_p on s_p.id=s_m.picking_id
                JOIN 
                    product_product as p_p on p_p.id=s_m.product_id
                JOIN 
                    product_template as p_t on p_t.id=p_p.product_tmpl_id
                WHERE 
                    s_p.state in ('done')
            """
            
            purchase_query += f" AND s_p.date_done >= '{start_date}' AND s_p.date_done < '{end_date}'"

            # Group by clause for purchase_query
            purchase_query += """
            GROUP BY 
                s_m.product_id, 
                s_m.picking_type_id;
            """
            

            sale_query1="""
                SELECT sum(quantity) as product_uom_qty,s_q.product_id as product_id,s_q.in_date
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id

                
            """
            # sale_query1 += f" AND s_q.in_date  BETWEEN '{start_date}' AND '{end_date} ' "
            sale_query1 += f" AND s_q.in_date >= '{start_date}' AND s_q.in_date < '{end_date}'"

            sale_query1 += """
            GROUP BY 
                s_q.product_id , s_q.in_date;
            """
            purchase_query1="""
                SELECT sum(quantity) as product_uom_qty,s_q.product_id as product_id,s_q.in_date
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id


            """
            # purchase_query1 += f" AND s_q.in_date  BETWEEN '{start_date}' AND '{end_date} ' "
            purchase_query1 += f" AND s_q.in_date >= '{start_date}' AND s_q.in_date < '{end_date}'"

            purchase_query1 += """
            GROUP BY 
               s_q.product_id , s_q.in_date;
            """

             # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()
             # Execute the sale_query and fetch results
            self._cr.execute(sale_query1)
            sol_query_obj1 = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query1)
            pol_query_obj1 = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            product1 = [record['product_id'] for record in pol_query_obj1]


            # Ensure product_ids is a tuple
            products = tuple(product + product1)
            print("OOODEODOEODOEODEODOEDOEODODEDOE", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]

        elif data['category']:
            category_ids=tuple([cat for cat in data['category']])
            print(category_ids,'kjjkjkjkjkjkjkjkjkjkjjkjkjkjkjkjkjk')

            sale_query="""
                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                    FROM stock_move as s_m
                    join stock_picking as s_p on s_p.id=s_m.picking_id
                    join product_product as p_p on p_p.id=s_m.product_id
                    join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            

            if len(category_ids) == 1:
                category_id = category_ids[0]
                sale_query += f" AND p_t.categ_id = {category_id}"
            else:
                sale_query += f" AND p_t.categ_id in {category_ids}"
            
            sale_query += """
            GROUP BY 
               s_m.product_id,s_m.picking_type_id;
            """
            purchase_query="""
                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                    FROM stock_move as s_m
                    join stock_picking as s_p on s_p.id=s_m.picking_id
                    join product_product as p_p on p_p.id=s_m.product_id
                    join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            

            if len(category_ids) == 1:
                category_id = category_ids[0]
                purchase_query += f" AND p_t.categ_id = {category_id}"
            else:
                purchase_query += f" AND p_t.categ_id in {category_ids}"
            
            purchase_query += """
            GROUP BY 
               s_m.product_id,s_m.picking_type_id;
            """

            sale_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id ,p_t.categ_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            # sale_query1 += f" AND s_q.location_id in {locations_list}"

            
            if len(category_ids) == 1:
                category_id = category_ids[0]
                sale_query1 += f" AND p_t.categ_id = {category_id}"
            else:
                sale_query1 += f" AND p_t.categ_id in {category_ids}"
            
            sale_query1 += """
            GROUP BY 
               s_q.quantity,s_q.product_id ,p_t.categ_id;
            """

            purchase_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id ,p_t.categ_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            # purchase_query1 += f" AND s_q.location_id in {locations_list}"

            
            if len(category_ids) == 1:
                category_id = category_ids[0]
                purchase_query1 += f" AND p_t.categ_id = {category_id}"
            else:
                purchase_query1 += f" AND p_t.categ_id in {category_ids}"
            
            purchase_query1 += """
            GROUP BY 
               s_q.quantity,s_q.product_id ,p_t.categ_id;
            """
            
            # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()
            

            # Execute the sale_query and fetch results
            self._cr.execute(sale_query1)
            sol_query_obj1 = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query1)
            pol_query_obj1 = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            product1 = [record['product_id'] for record in pol_query_obj1]
            print(product1,"opdspdospdospdospdospdospodpsodpsodpsodpospdospdosd")

            # Ensure product_ids is a tuple
            products = tuple(product + product1 )

            # Ensure product_ids is a tuple
            # products = tuple(product)
            print("categoryyyyyyyyyyyy done", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]

        else:
            sale_query="""

                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                FROM stock_move as s_m
                join stock_picking as s_p on s_p.id=s_m.picking_id
                join product_product as p_p on p_p.id=s_m.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id"""
            
            
            sale_query += """
            GROUP BY 
                s_m.product_id,s_m.picking_type_id;
            """
            purchase_query="""
               	
                SELECT sum(product_uom_qty) as product_uom_qty,s_m.product_id as product_id,s_m.picking_type_id	
                FROM stock_move as s_m
                join stock_picking as s_p on s_p.id=s_m.picking_id
                join product_product as p_p on p_p.id=s_m.product_id
                join product_template as p_t on p_t.id=p_p.product_tmpl_id """
            

            purchase_query += """
                GROUP BY 
                s_m.product_id,s_m.picking_type_id;
                """
            sale_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id """
           
           
            sale_query1 += """
                GROUP BY 
                s_q.quantity, s_q.product_id;
                """
            purchase_query1="""
                SELECT s_q.quantity as product_uom_qty,s_q.product_id as product_id
                FROM stock_quant as s_q
                join product_product as p_p on p_p.id=s_q.product_id """
           
            
            purchase_query1 += """
                GROUP BY 
                 s_q.quantity,s_q.product_id ;
                """
            # Execute the sale_query and fetch results
            self._cr.execute(sale_query)
            sol_query_obj = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query)
            pol_query_obj = self._cr.dictfetchall()

            # Execute the sale_query and fetch results
            self._cr.execute(sale_query1)
            sol_query_obj1 = self._cr.dictfetchall()
            
            # Execute the purchase_query and fetch results
            self._cr.execute(purchase_query1)
            pol_query_obj1 = self._cr.dictfetchall()
            
            # Extract product IDs from the purchase query results
            product = [record['product_id'] for record in pol_query_obj]
            product1 = [record['product_id'] for record in pol_query_obj1]

            # Convert the lists to sets and get the difference
            unique_product1 = list(set(product1) - set(product))
            print (unique_product1,"::::::::::::::::::::::::::::::::::::::::::::")


            # Ensure product_ids is a tuple
            products = tuple(product + unique_product1 )
            print("warehouseeeeeeeeeeeeeee doneee", products)
            if products:
                categ_products = self.env['product.product'].search([('id', 'in', products)])
            else:
                categ_products=[]

        quants = self.env['stock.quant'].search([
            ('location_id', 'in', location_ids),
            ('product_id', 'in', products),
        ])
        print("kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",quants)
        # print(products,'filtered_productsssssssssssssssssssss')


        # Process the fetched quants data
        for quant in quants:
            product=self.env['product.product'].search([
                ('id', '=', quant.product_id.id)
               
                    
            ])
            variant_values = ' , '.join([
                        f" {attr_value.name}"
                        for attr_value in product.product_template_attribute_value_ids
                    ])
            vals = {
                # 'sku': quant.product_id.default_code,
                'name': quant.product_id.name,
                'location': quant.location_id.display_name,
                'quantity': quant.quantity,
                'available': quant.available_quantity,
                'variant':variant_values,


                # Add other fields as needed
            }
            lines.append(vals)
        print("gggggggggggggggggggggggggggggggggggggg",lines)
        return lines


    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        lines = self.browse(data['ids'])
        d = lines.category
        s=lines.supplier

        print(d,'mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm')

        get_warehouse = self.get_warehouse(lines)
        get_location=self.get_location(lines)
        print(get_location,"vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
        comp = self.env.user.company_id.name
        # Get start and end dates from the form
        start_date = lines.start_date
        end_date = lines.end_date
        

        # Create a worksheet for Stock Info
        sheet = workbook.add_worksheet('Stock Info')
        format0 = workbook.add_format({'font_size': 20, 'align': 'center', 'bold': True})
        format1 = workbook.add_format({'font_size': 14, 'align': 'vcenter', 'bold': True})
        format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'bold': True})
        format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'bold': True})
        format3 = workbook.add_format({'bottom': True, 'top': True, 'font_size': 12 })
        format4 = workbook.add_format({'font_size': 12, 'align': 'left', 'bold': True})
        font_size_8 = workbook.add_format({'font_size': 8, 'align': 'center'})
        font_size_8_l = workbook.add_format({'font_size': 8, 'align': 'left'})
        font_size_8_r = workbook.add_format({'font_size': 8, 'align': 'right'})
        red_mark = workbook.add_format({'font_size': 8, 'bg_color': 'red'})
        green_mark = workbook.add_format({'font_size': 8, 'bg_color': '90EE90'})  # New green format
        justify = workbook.add_format({'font_size': 12})
        format3.set_align('center')
        justify.set_align('justify')
        format1.set_align('center')
        red_mark.set_align('center')
        green_mark.set_align('center') 

        # Initialize row and column counters
        row_num = 1
        col_num = 0
        if lines.tracking_wise == 'warehouse_wise':
            for warehouse_name, warehouse_id in zip(*get_warehouse):
                # Write warehouse name at the top of each table

                sheet.merge_range(row_num, col_num, row_num, col_num + 10, f'Warehouse: {warehouse_name}', format0)
                row_num += 2

                # Write date interval in the sheet
                sheet.merge_range(row_num, col_num, row_num, col_num + 10, f'Report Date: {start_date} - {end_date}', format1)
                row_num += 2

                # Write table headers

                sheet.write(row_num, col_num, 'Internal Reference', format21)
                sheet.merge_range(row_num, col_num + 1, row_num, col_num + 3, 'Product Name', format21)
                sheet.merge_range(row_num, col_num + 4, row_num, col_num + 5, 'Product Category', format21)
                sheet.merge_range(row_num, col_num + 6,row_num, col_num + 8, 'Attribute Values', format21)

                sheet.write(row_num, col_num + 9, 'Cost Price', format21)
                sheet.write(row_num, col_num + 10, 'Available', format21)
                sheet.write(row_num, col_num + 11, 'Incoming', format21)
                sheet.write(row_num, col_num + 12, 'Outgoing', format21)
                sheet.merge_range(row_num, col_num + 13, row_num, col_num + 14, 'Net On Hand', format21)
                sheet.merge_range(row_num, col_num + 15, row_num, col_num + 16, 'Forecasted Stock', format21)
                sheet.merge_range(row_num, col_num + 17, row_num, col_num + 18, 'Total Sold', format21)
                sheet.merge_range(row_num, col_num + 19, row_num, col_num + 20, 'Total Purchased', format21)
                sheet.write(row_num, col_num + 21, 'Valuation', format21)
                sheet.write(row_num, col_num + 22, 'status', format21)

                row_num += 1
                # other headers...
                # row_num += 1

                
                # Get lines for the current warehouse
                get_line = self.get_lines_warehouse(data, warehouse_id,s)

                for each in get_line:
                    # Write data to the table
                    sheet.write(row_num, col_num, each['sku'], font_size_8)
                    sheet.merge_range(row_num, col_num + 1, row_num, col_num + 3, each['name'], font_size_8)
                    sheet.merge_range(row_num, col_num + 4, row_num, col_num + 5, each['category'], font_size_8)
                    sheet.merge_range(row_num, col_num + 6, row_num, col_num + 8,each['variants'], font_size_8)

                    sheet.write(row_num, col_num + 9, each['cost_price'], font_size_8)
                    sheet.write(row_num, col_num + 10, each['available'], green_mark)
                    sheet.write(row_num, col_num + 11, each['incoming'], font_size_8)
                    sheet.write(row_num, col_num + 12, each['outgoing'], font_size_8)
                    sheet.merge_range(row_num, col_num + 13, row_num, col_num + 14, each['net_on_hand'], font_size_8)
                    sheet.merge_range(row_num, col_num + 15, row_num, col_num + 16, each['virtual'], font_size_8)
                    sheet.merge_range(row_num, col_num + 17, row_num, col_num + 18, each['sale_value'], font_size_8)
                    sheet.merge_range(row_num, col_num + 19, row_num, col_num + 20, each['purchase_value'], font_size_8)
                    sheet.write(row_num, col_num + 21, each['total_value'], font_size_8)
                    sheet.write(row_num,col_num + 22,each['status'],font_size_8)



                    # Check if enable_red_text is True and the value is negative, apply red formatting
                    if lines.enable_red_text and each['available'] < 0:
                        sheet.write(row_num, col_num + 10, each['available'], red_mark)
                    if lines.enable_red_text and each['incoming'] < 0:
                        sheet.write(row_num, col_num + 11, each['incoming'], red_mark)
                    if lines.enable_red_text and each['outgoing'] < 0:
                        sheet.write(row_num, col_num + 12, each['outgoing'], red_mark)
                    if lines.enable_red_text and each['net_on_hand'] < 0:
                        sheet.merge_range(row_num, col_num + 13, row_num,col_num + 14, each['net_on_hand'], red_mark)
                    if lines.enable_red_text and each['virtual'] < 0:
                        sheet.merge_range(row_num, col_num + 15,row_num, col_num + 16, each['virtual'], red_mark)
                    if lines.enable_red_text and each['sale_value'] < 0:
                        sheet.merge_range(row_num, col_num + 17, row_num,col_num + 18, each['sale_value'], red_mark)
                    if lines.enable_red_text and each['purchase_value'] < 0:
                        sheet.merge_range(row_num, col_num + 19,row_num, col_num + 20, each['purchase_value'], red_mark)
                    if lines.enable_red_text and each['total_value'] < 0:
                        sheet.write(row_num, col_num + 21, each['total_value'], red_mark)
                    
                    row_num += 1

                # Add space between tables
                row_num += 6
        if lines.tracking_wise == 'location_wise':
            for location_name, location_id in zip(*self.get_location(lines)):
                # Write location name at the top of each table
                sheet.merge_range(row_num, col_num, row_num, col_num +10 , f'Location: {location_name}', format0)
                row_num += 2

                # Write date interval in the sheet
                sheet.merge_range(row_num, col_num, row_num, col_num+10 , f'Report Date: {start_date} - {end_date}', format1)
                row_num += 2

                # Write table headers
                sheet.merge_range(row_num, col_num  ,row_num,col_num + 1, 'Product Name', format21)
                sheet.merge_range(row_num, col_num + 2,row_num, col_num + 4, 'Attribute Values', format21)

                sheet.merge_range(row_num, col_num + 5, row_num, col_num + 6, 'Location Name', format21)
                sheet.merge_range(row_num, col_num + 7, row_num, col_num + 8, 'Quantity', format21)
                sheet.merge_range(row_num, col_num + 9, row_num, col_num + 10, 'available', format21)

                # Add other headers as needed
                row_num += 1

                # Get lines for the current location
                location_lines = self.get_lines_location(data, [location_id])

                for each in location_lines:
                    sheet.merge_range(row_num, col_num  ,row_num,col_num + 1, each['name'], font_size_8)
                    sheet.merge_range(row_num, col_num + 2, row_num, col_num + 4, each['variant'], font_size_8)
      
                    sheet.merge_range(row_num, col_num + 5, row_num, col_num + 6, each['location'], font_size_8)
                    sheet.merge_range(row_num, col_num + 7, row_num, col_num + 8, each['quantity'], font_size_8)
                    sheet.merge_range(row_num, col_num + 9, row_num, col_num + 10, each['available'], font_size_8)

                    # Add other data as needed


                    if lines.enable_red_text and each['quantity'] < 0:
                        sheet.merge_range(row_num, col_num + 7, row_num, col_num + 8, each['quantity'], red_mark)
                    if lines.enable_red_text and each['available'] < 0:
                        sheet.merge_range(row_num, col_num + 9, row_num, col_num + 10, each['available'], red_mark)


                    row_num += 1

                row_num += 6
        


        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

    def export_pdf(self):
        self.validate_fields()

        data = {
            'ids': self.ids,
            'model': self._name,
            'warehouse': self.warehouse.ids ,
            'location': self.location.ids ,
            'category': self.category.ids,  # Pass selected category IDs
            'supplier': self.supplier.ids,  # Add selected supplier IDs
            'start_date': self.start_date.strftime('%Y-%m-%d %H:%M:%S') if self.start_date else '',
            'end_date': self.end_date.strftime('%Y-%m-%d %H:%M:%S') if self.end_date else '',
        }
        print("QWQWEEWRRQEWRFEQWFWFVVDCCCCCCCCCCCCCCCCCCCCSSSSSSSSSSSSSSSSSSSSSSFEEEEEEEEEEEEEE",data)

        # Add start_date and end_date to the data dictionary
        data['start_date_str'] = data['start_date']
        data['end_date_str'] = data['end_date']
        data['start_date'] = fields.Datetime.from_string(data['start_date'])
        data['end_date'] = fields.Datetime.from_string(data['end_date'])

        if self.tracking_wise == 'warehouse_wise':
            # Get selected warehouse IDs
            warehouse_ids = self.warehouse.ids
            category_ids = self.category.ids  # Add this line
            supplier=self.supplier.ids
            print(category_ids,'OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO')

            # Initialize a list to store data for each warehouse
            warehouse_data = []

            for warehouse_id in warehouse_ids:
                # Get data for the current warehouse
                warehouse_data.append(self.get_warehouse_data(data,warehouse_id,supplier))

            print("Warehouse Data:", warehouse_data)  # Debug statement

            # Pass warehouse data to the XML report template
            return self.env.ref('export_stockinfo_excel.pdf_stock_action_report').report_action(self, data={
                'warehouse_data': warehouse_data,
                'start_date_str': data['start_date_str'],  # Pass start_date_str to the template
                'end_date_str': data['end_date_str'],  # Pass end_date_str to the template
         
            })
        elif self.tracking_wise == 'location_wise':
            # Get selected location IDs
            location_ids = self.location.ids
            # Initialize a list to store data for each location
            location_data = []

            for location_id in location_ids:
                # Get data for the current location
                location_data.append(self.get_location_data(data,location_id))

            print("Location Data:", location_data)  # Debug statement

            # Pass location data to the XML report template
            return self.env.ref('export_stockinfo_excel.pdf_stock_action_report').report_action(self, data={
                'location_data': location_data,
                'start_date_str': data['start_date_str'],  # Pass start_date_str to the template
                'end_date_str': data['end_date_str'],  # Pass end_date_str to the template
         
            })
        
    def get_warehouse_data(self, data,warehouse_id,supplier):
        # Retrieve data for products stored in the specified warehouse
        dic = {
            'warehouse_name': '',
            'product_data': [],
        }

        # Fetch warehouse name
        warehouse_name = self.env['stock.warehouse'].browse(warehouse_id).name
        dic['warehouse_name'] = warehouse_name

        # Get the correct data for the current warehouse
        warehouse_data = self.env['stock.xls.report'].browse(self._context.get('active_ids', []))
        product_data = self.get_lines_warehouse(data, warehouse_id,supplier)

        
        print("Product Data for Warehouseeeeeeeeeeeeeeeeeeeeeeee", warehouse_id, ":", product_data)  # Debug statement

       # Ensure product data is in the expected format of list of dictionaries
        for product in product_data:
            product_dict = {
                'sku': product['sku'],
                'name': product['name'],
                'category': product['category'],
                'cost_price': product['cost_price'],
                'available': product['available'],
                'incoming': product['incoming'],
                'outgoing': product['outgoing'],
                'net_on_hand': product['net_on_hand'],
                'virtual': product['virtual'],
                'sale_value': product['sale_value'],
                'purchase_value': product['purchase_value'],
                'total_value': product['total_value'],
                'variants': product['variants'],

                # Add other fields as needed
            }
            # print(product_dict,'TRRTRTRTRRRRRRRRRRRRRRTRTRTRTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT')

            dic['product_data'].append(product_dict)

        print("kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",dic['product_data'])

        return dic
    
    def get_location_data(self,data, location_id):
        # Retrieve data for products stored in the specified location
        dic = {
            'location_name': '',
            'product_data': [],
        }

        # Fetch location name
        location_name = self.env['stock.location'].browse(location_id).display_name
        dic['location_name'] = location_name

        # Get the correct data for the current location
        location_data = self.env['stock.xls.report'].browse(self._context.get('active_ids', []))
        product_data = self.get_lines_location(data, [location_id])

        print("Product Data for Location:", location_id, ":", product_data)  # Debug statement

        # Ensure product data is in the expected format of list of dictionaries
        for product in product_data:
            product_dict = {
                'name': product['name'],
                'location':product['location'],
                'quantity': product['quantity'],
                'available': product['available'],
                'variant': product['variant'],

            }
            dic['product_data'].append(product_dict)


        return dic


  