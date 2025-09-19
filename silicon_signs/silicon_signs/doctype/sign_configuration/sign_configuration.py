# Copyright (c) 2025, mohammedkashalo@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint
from frappe.model.document import Document
# from erpnext.manufacturing.doctype.work_order.work_order import make_bom


class SignConfiguration(Document):
    def validate(self):
        """Validate the Sign Configuration before saving"""
        # Add any validation logic here
        if self.perimeter_inches and self.perimeter_inches <= 0:
            frappe.throw(_("Perimeter must be greater than 0"))
            
        if self.led_count and self.led_count <= 0:
            frappe.throw(_("LED count must be greater than 0"))
            
        if self.sheet_count and self.sheet_count <= 0:
            frappe.throw(_("Sheet count must be greater than 0"))

    def on_submit(self):
        """Calculate pricing and create BOM when Sign Configuration is submitted"""
        self.calculate_pricing()
        self.update_quotation_item()
        self.create_bom()
        
    def calculate_pricing(self):
        """Calculate the pricing based on configuration options"""
        # Get pricing rates from Pricing Settings
        pricing_settings = frappe.get_doc("Pricing Settings")
        
        base_cost = 0
        
        # Calculate material cost based on perimeter
        if self.perimeter_inches:
            material_cost_per_inch = pricing_settings.material_cost_per_inch or 0.5
            base_cost += self.perimeter_inches * material_cost_per_inch
        
        # Calculate labor costs
        if self.perimeter_inches:
            bending_labor_rate = pricing_settings.bending_labor_per_inch or 0.3
            routing_labor_rate = pricing_settings.routing_labor_per_inch or 0.2
            trim_capping_labor_rate = pricing_settings.trim_capping_labor_per_inch or 0.25
            
            base_cost += self.perimeter_inches * (bending_labor_rate + routing_labor_rate + trim_capping_labor_rate)
        
        # Calculate LED cost
        if self.led_count:
            # Try to get LED cost from Item Price first, fall back to Pricing Settings
            led_item = pricing_settings.led_item
            if led_item:
                led_rate = self.get_item_price(led_item) or pricing_settings.led_cost_per_unit or 1.5
            else:
                led_rate = pricing_settings.led_cost_per_unit or 1.5
            base_cost += self.led_count * led_rate
        
        # Calculate sheet material cost
        if self.sheet_count:
            # Try to get sheet cost from Item Price first, fall back to Pricing Settings
            sheet_item = pricing_settings.sheet_item
            if sheet_item:
                sheet_rate = self.get_item_price(sheet_item) or pricing_settings.sheet_cost or 85.0
            else:
                sheet_rate = pricing_settings.sheet_cost or 85.0
            base_cost += self.sheet_count * sheet_rate
        
        # Add additional costs for options
        if self.paint_returns:
            paint_cost = pricing_settings.paint_returns_cost or 45.0
            base_cost += paint_cost
        
        if self.trim_cap:
            trim_cap_cost = pricing_settings.trim_cap_cost or 35.0
            base_cost += trim_cap_cost
        
        if self.raceway_wireway_backer:
            raceway_cost = pricing_settings.raceway_cost or 75.0
            base_cost += raceway_cost
        
        if self.vinyl_rta:
            # Calculate vinyl cost based on perimeter (approximation)
            if self.perimeter_inches:
                vinyl_cost_per_inch = pricing_settings.vinyl_rta_cost_per_inch or 0.15
                base_cost += self.perimeter_inches * vinyl_cost_per_inch
        
        if self.vinyl_printed:
            # Calculate printed vinyl cost based on perimeter (approximation)
            if self.perimeter_inches:
                printed_vinyl_cost_per_inch = pricing_settings.printed_vinyl_cost_per_inch or 0.25
                base_cost += self.perimeter_inches * printed_vinyl_cost_per_inch
        
        if self.crating_fee:
            crating_cost = pricing_settings.crating_fee or 120.0
            base_cost += crating_cost
        
        # Apply lighting type multiplier
        lighting_multiplier = 1.0
        if self.lighting_type == "Face-lit":
            lighting_multiplier = pricing_settings.face_lit_multiplier or 1.0
        elif self.lighting_type == "Reverse halo":
            lighting_multiplier = pricing_settings.reverse_halo_multiplier or 1.2
        elif self.lighting_type == "Dual Lit":
            lighting_multiplier = pricing_settings.dual_lit_multiplier or 1.5
        
        base_cost *= lighting_multiplier
        
        # Apply mounting type multiplier
        mounting_multiplier = 1.0
        if self.mounting_type == "Raceway":
            mounting_multiplier = pricing_settings.raceway_multiplier or 1.1
        elif self.mounting_type == "Wireway/Backer":
            mounting_multiplier = pricing_settings.wireway_multiplier or 1.15
        elif self.mounting_type == "Flush":
            mounting_multiplier = pricing_settings.flush_multiplier or 1.05
        
        base_cost *= mounting_multiplier
        
        # Apply profit margin
        profit_margin = pricing_settings.profit_margin or 0.3  # 30%
        final_price = base_cost * (1 + profit_margin)
        
        # Update the calculated rate
        self.calculated_rate = final_price
        self.save()

    def get_item_price(self, item_code):
        """Get the selling price for an item"""
        price = frappe.db.get_value("Item Price", 
                                   {"item_code": item_code, "selling": 1}, 
                                   "price_list_rate")
        return price

    def update_quotation_item(self):
        """Update the Quotation Item with the calculated rate"""
        quotation_item = frappe.get_doc("Quotation Item", self.quotation_item)
        quotation_item.rate = self.calculated_rate
        quotation_item.amount = self.calculated_rate * self.quantity
        quotation_item.save()
        
        # Recalculate quotation totals
        quotation = frappe.get_doc("Quotation", self.quotation)
        quotation.calculate_totals()
        quotation.save()

    def create_bom(self):
        """Create a Bill of Materials based on the sign configuration"""
        # Get the item code from the quotation item
        quotation_item = frappe.get_doc("Quotation Item", self.quotation_item)
        item_code = quotation_item.item_code
        
        # Get pricing settings for item references
        pricing_settings = frappe.get_doc("Pricing Settings")
        
        # Create a new BOM
        bom = frappe.new_doc("BOM")
        bom.item = item_code
        bom.quantity = 1  # BOM for one unit
        bom.uom = quotation_item.uom or "Unit"
        bom.with_operations = 1
        bom.is_active = 1
        
        # Add materials based on configuration
        if self.perimeter_inches and pricing_settings.trim_cap_item:
            # Add trim cap material
            bom.append("items", {
                "item_code": pricing_settings.trim_cap_item,
                "qty": self.perimeter_inches / 12,  # Convert inches to feet
                "uom": "Foot"
            })
        
        if self.sheet_count and pricing_settings.sheet_item:
            # Add sheet material
            bom.append("items", {
                "item_code": pricing_settings.sheet_item,
                "qty": self.sheet_count,
                "uom": "Unit"
            })
        
        if self.led_count and pricing_settings.led_item:
            # Add LEDs
            bom.append("items", {
                "item_code": pricing_settings.led_item,
                "qty": self.led_count,
                "uom": "Unit"
            })
        
        # Add additional materials based on options
        if self.paint_returns and pricing_settings.paint_item:
            bom.append("items", {
                "item_code": pricing_settings.paint_item,
                "qty": 1,  # Flat rate
                "uom": "Unit"
            })
        
        if self.crating_fee and pricing_settings.crate_item:
            bom.append("items", {
                "item_code": pricing_settings.crate_item,
                "qty": 1,  # Flat rate
                "uom": "Unit"
            })
        
        # Add operations (labor)
        if self.perimeter_inches:
            # Bending labor
            if pricing_settings.bending_operation:
                bom.append("operations", {
                    "operation": pricing_settings.bending_operation,
                    "time_in_mins": self.perimeter_inches * 0.5,  # 0.5 minutes per inch
                    "hour_rate": frappe.db.get_value("Operation", pricing_settings.bending_operation, "hour_rate") or 30
                })
            
            # Routing labor
            if pricing_settings.routing_operation:
                bom.append("operations", {
                    "operation": pricing_settings.routing_operation,
                    "time_in_mins": self.perimeter_inches * 0.3,  # 0.3 minutes per inch
                    "hour_rate": frappe.db.get_value("Operation", pricing_settings.routing_operation, "hour_rate") or 25
                })
        
        bom.insert()
        bom.submit()
        
        # Update the BOM reference in the Sign Configuration
        self.bom_reference = bom.name
        self.save()


# Create a whitelisted function to create sign configuration from quotation
@frappe.whitelist()
def create_sign_configuration(quotation, quotation_item):
    """Create a new Sign Configuration document linked to a Quotation Item"""
    doc = frappe.new_doc("Sign Configuration")
    doc.quotation = quotation
    doc.quotation_item = quotation_item
    return doc