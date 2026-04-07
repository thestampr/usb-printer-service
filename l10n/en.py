from .abc import Locale

class LocaleEN(Locale):
    @property
    def locale_name(self) -> str:
        return "English"
    
    @property
    def button_reset(self) -> str:
        return "Reset"
    @property
    def button_save(self) -> str:
        return "Save"
    @property
    def button_cancel(self) -> str:
        return "Cancel"
    
    @property
    def r_number(self) -> str:
        return "No."
    @property
    def r_customer(self) -> str:
        return "Customer"
    @property
    def r_customer_name(self) -> str:
        return "Customer Name"
    @property
    def r_customer_code(self) -> str:
        return "Customer Code"
    @property
    def r_transaction(self) -> str:
        return "Transaction"
    @property
    def r_promotion(self) -> str:
        return "Promotion"
    @property
    def r_date(self) -> str:
        return "Date"
    @property
    def r_time(self) -> str:
        return "Time"
    @property
    def r_cashier(self) -> str:
        return "Cashier"
    @property
    def r_address(self) -> str:
        return "Address"
    @property
    def r_tax_id(self) -> str:
        return "Tax ID (store)"
    @property
    def r_tax_id_customer(self) -> str:
        return "Tax ID (customer)"
    @property
    def r_branch(self) -> str:
        return "Branch"
    @property
    def r_car_plate(self) -> str:
        return "Car Plate"
    @property
    def r_item(self) -> str:
        return "Item"
    @property
    def r_amount(self) -> str:
        return "Amount"
    @property
    def r_quantity(self) -> str:
        return "Qty"
    @property
    def r_total(self) -> str:
        return "Total"
    @property
    def r_value(self) -> str:
        return "Value"
    @property
    def r_vat(self) -> str:
        return "VAT 7%"
    @property
    def r_total_label(self) -> str:
        return "Total"
    @property
    def r_points(self) -> str:
        return "Points"
    @property
    def r_received(self) -> str:
        return "Received"
    @property
    def r_change(self) -> str:
        return "Change"
    @property
    def r_discount(self) -> str:
        return "Discount"
    
    @property
    def tab_printer(self) -> str:
        return "Printer"
    @property
    def tab_layout(self) -> str:
        return "Layout"
    @property
    def tab_services(self) -> str:
        return "Services"
    
    @property
    def page_printer_usbport(self) -> str:
        return "USB Port"
    @property
    def page_printer_usbname(self) -> str:
        return "USB Name"
    @property
    def page_printer_encoding(self) -> str:
        return "Encoding"
    @property
    def page_printer_linewidth(self) -> str:
        return "Line Width"
    @property
    def page_printer_pixelwidth(self) -> str:
        return "Pixel Width"
    @property
    def page_printer_download_driver(self) -> str:
        return "Download Driver"
    
    @property
    def page_layout_header_image(self) -> str:
        return "Header Image"
    @property
    def page_layout_header_title(self) -> str:
        return "Header Title"
    @property
    def page_layout_header_description(self) -> str:
        return "Header Description"
    @property
    def page_layout_receipt_title(self) -> str:
        return "Receipt Title"
    @property
    def page_layout_footer_label(self) -> str:
        return "Footer Label"
    @property
    def page_layout_footer_image(self) -> str:
        return "Footer Image"
    @property
    def page_layout_advanced(self) -> str:
        return "Advanced"
    @property
    def page_layout_fontfamily(self) -> str:
        return "Font Family"
    @property
    def page_layout_fontpath(self) -> str:
        return "Font Path"
    @property
    def page_layout_fontsize(self) -> str:
        return "Font Size"
    @property
    def page_layout_fontsize_small(self) -> str:
        return "Small Font Size"
    @property
    def page_layout_line_spacing(self) -> str:
        return "Line Spacing"
    @property
    def page_layout_curency(self) -> str:
        return "Currency"
    @property
    def page_layout_volume_unit(self) -> str:
        return "Volume Unit"
    @property
    def page_layout_browse(self) -> str:
        return "Browse"
    @property
    def page_layout_clear(self) -> str:
        return "Clear"
    @property
    def page_layout_open_folder(self) -> str:
        return "Open in folder"
    @property
    def page_layout_image_scale(self) -> str:
        return "Image Scale"
    @property
    def page_layout_preview(self) -> str:
        return "Preview"
    @property
    def page_layout_preview_print(self) -> str:
        return "Print Preview"
    
    @property
    def page_services_host(self) -> str:
        return "Host"
    @property
    def page_services_port(self) -> str:
        return "Port"
    @property
    def page_services_debug_mode(self) -> str:
        return "Debug Mode"