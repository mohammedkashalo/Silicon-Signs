frappe.ui.form.on('Quotation', {
    refresh(frm) {
        frm.add_custom_button(__('Configure Sign'), function () {
            let dialog, attr_fg = null, attr_key_map = {};

            const base_fields = [
                {
                    label: 'Sign Template',
                    fieldname: 'sign_template',
                    fieldtype: 'Link',
                    options: 'Item',
                    reqd: 1,
                    change: () => load_attributes_into_dialog(),
                    get_query: () => ({ filters: { has_variants: 1 } })
                },

                // --- Optional ad-hoc fields used only for pricing (keep or remove as you like) ---
                {
                    fieldtype: 'Attach',
                    label: 'Design File (SVG)',
                    fieldname: 'design_svg',
                    options: 'Attach',
                    reqd: 0
                },

                {
                    fieldtype: 'Button',
                    label: 'Calculate Perimeter',
                    fieldname: 'calculate_perimeter_btn',
                    click: async () => {
                        const file_url = dialog.get_value('design_svg');
                        if (!file_url ) {
                            frappe.msgprint(__('Please upload a valid SVG file.'));
                            return;
                        }

                        const res = await frappe.call({
                            method: 'silicon_signs.api.calculate_perimeter',
                            args: { file_url }
                        });

                        const perimeter = res.message?.perimeter_inches;
                        if (perimeter) {
                            if (attr_fg) {
                                await attr_fg.set_value('attr__perimeter_inches', perimeter);
                            } else {
                                frappe.msgprint(__('Attribute fields not yet loaded.'));
                            }
                        } else {
                            frappe.msgprint(__('Could not calculate perimeter.'));
                        }
                    }
                },
                { fieldtype: 'Section Break' },

                { fieldtype: 'Section Break', label: 'Variant Attributes' },
                { fieldtype: 'HTML', fieldname: 'attrs_html', options: '<div class="text-muted">Choose attribute values for the variant:</div>' }
            ];

            dialog = new frappe.ui.Dialog({
                title: __('Sign Configuration'),
                fields: base_fields,
                primary_action_label: __('Save'),
                async primary_action() {
                    try {
                        const vals = dialog.get_values();
                        if (!vals || !vals.sign_template) {
                            frappe.msgprint(__('Please choose a Sign Template.'));
                            return;
                        }

                        // 1) Collect attribute values from FieldGroup
                        if (!attr_fg) {
                            frappe.throw(__('Please wait for attributes to load.'));
                        }
                        const attr_vals = attr_fg.get_values(); // validates reqd fields
                        if (!attr_vals) return; // FieldGroup will highlight missing

                        // Map FieldGroup fieldnames back to actual Item Attribute names
                        const attr_args = {};
                        Object.keys(attr_vals).forEach(k => {
                            const attr_name = attr_key_map[k]; // real attribute (with spaces/case)
                            if (attr_name) attr_args[attr_name] = attr_vals[k];
                        });

                        const template = vals.sign_template;
                        console.log("the vals", vals)

                        // 2) Compute a “random-ish” price (replace with your logic anytime)
                        const av = attr_fg.get_values();


                        const pr = await frappe.call({
                            method: 'silicon_signs.silicon_signs.doctype.sign_pricing_template.api.price_item_by_attributes',
                            args: {
                                item_template: template,
                                attributes: attr_args
                            }
                        });
                        const { price, breakdown } = pr.message || {};

                        // 3) Find or create the variant
                        const getResp = await frappe.call({
                            method: 'erpnext.controllers.item_variant.get_variant',
                            args: { template, args: attr_args }
                        });
                        let item_code = getResp && getResp.message ? getResp.message : null;

                        if (!item_code) {
                            const createResp = await frappe.call({
                                method: 'erpnext.controllers.item_variant.create_variant',
                                args: { item: template, args: attr_args }
                            });
                            item_code = createResp && createResp.message
                                ? (createResp.message.name || createResp.message.item_code || createResp.message)
                                : null;
                        }
                        if (!item_code) frappe.throw(__('Could not determine the created variant Item Code.'));

                        // 4) Upsert Item Price for the quotation’s selling price list
                        const price_list = frm.doc.selling_price_list || 'Standard Selling';
                        const currency = frm.doc.currency || (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || 'USD';

                        // Try to read UOM for Item Price


                        // Check for existing Item Price
                        let existingPrice = null;
                        try {
                            const res = await frappe.db.get_list('Item Price', {
                                fields: ['name', 'price_list_rate'],
                                filters: { item_code, price_list },
                                limit: 1
                            });
                            existingPrice = (res && res.length) ? res[0] : null;
                        } catch (e) { /* ignore */ }

                        if (existingPrice) {
                            await frappe.call({
                                method: 'frappe.client.set_value',
                                args: {
                                    doctype: 'Item Price',
                                    name: existingPrice.name,
                                    fieldname: 'price_list_rate',
                                    value: price
                                }
                            });
                        } else {
                            await frappe.call({
                                method: 'frappe.client.insert',
                                args: {
                                    doc: {
                                        doctype: 'Item Price',
                                        item_code,
                                        price_list,
                                        price_list_rate: price,
                                        currency,
                                        uom: "Nos",
                                        selling: 1
                                    }
                                }
                            });
                        }

                        // 5) Add to Quotation items and save
                        const grid = frm.get_field('items').grid;

                        // Try to reuse the last row if it's empty
                        let row = (frm.doc.items || []).slice(-1)[0];
                        const is_empty = row && !row.item_code && !row.item_name && !row.description;

                        if (!row || !is_empty) {
                            // No empty tail row → create one
                            row = frm.add_child('items');
                        }

                        // Set values via model.set_value to trigger fetches and child validations
                        await frappe.model.set_value(row.doctype, row.name, 'item_code', item_code);
                        await frappe.model.set_value(row.doctype, row.name, 'qty', 1);
                        await frappe.model.set_value(row.doctype, row.name, 'uom', 'Nos');
                        await frappe.model.set_value(row.doctype, row.name, 'rate', price);

                        // (Optional) if you also want item_name explicitly:
                        // await frappe.model.set_value(row.doctype, row.name, 'item_name', item_code);

                        await frm.refresh_field('items');

                        // optional: persist now so the new row + pricing is saved immediately
                        await frm.save();

                        const price_formatted = frappe.format(price, { fieldtype: 'Currency', options: currency });
                        frappe.msgprint(__('Item Variant {0} added with price {1}.', [item_code.bold(), price_formatted]));

                        dialog.hide();
                    } catch (err) {
                        console.error(err);
                        frappe.msgprint({
                            title: __('Error'),
                            indicator: 'red',
                            message: __(err.message || err)
                        });
                    }
                }
            });

            dialog.show();

            // ----- Helpers -----
            async function load_attributes_into_dialog() {
                const template = dialog.get_value('sign_template');
                if (!template) return;

                try {
                    const item = await frappe.db.get_doc('Item', template);
                    const attrs = (item && item.attributes) ? item.attributes : [];

                    // Prepare container for FieldGroup
                    const holder = dialog.get_field('attrs_html').$wrapper.empty();
                    attr_key_map = {};

                    // Build dynamic fields
                    const fields = [];
                    let colCounter = 0;
                    for (const row of attrs) {
                        const attr_name = row.attribute;
                        if (!attr_name) continue;

                        const attrDoc = await frappe.db.get_doc('Item Attribute', attr_name);
                        const options = (attrDoc && attrDoc.item_attribute_values || []).map(v => v.attribute_value);

                        const scrub = (s) => (frappe.scrub ? frappe.scrub(s) : (s || '').toString().toLowerCase().replace(/\W+/g, '_'));
                        const fname = 'attr__' + scrub(attr_name);
                        attr_key_map[fname] = attr_name; // map back to real attribute

                        fields.push({
                            label: attr_name,
                            fieldname: fname,
                            fieldtype: row.numeric_values ? 'Float' : 'Select',
                            options: row.numeric_values ? undefined : options,
                            reqd: 1
                        });
                        colCounter++;
                        console.log("counter", colCounter)
                        if (colCounter % 2 === 1) {
                            console.log("adding col")
                            fields.push({ fieldtype: 'Column Break' });
                        } else {
                            // after the 2nd field in the row, start a new row
                            fields.push({ fieldtype: 'Section Break' });
                        }
                    }

                    // if we ended with a single field dangling in the row, ensure we break the row
                    if (colCounter % 2 === 1) {
                        fields.push({ fieldtype: 'Section Break' });

                    }

                    // Make FieldGroup
                    attr_fg = new frappe.ui.FieldGroup({
                        fields,
                        body: holder
                    });
                    await attr_fg.make();
                } catch (e) {
                    console.error(e);
                    frappe.msgprint(__('Could not load attributes for the selected template.'));
                }
            }

            function flt(v) { return parseFloat(v || 0) || 0; }
            function cint(v) { return parseInt(v || 0, 10) || 0; }
        });
    }
});
