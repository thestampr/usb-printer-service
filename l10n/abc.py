from abc import ABC, abstractmethod

class Locale(ABC):
    """
    Abstract Base Class for locale classes.
    Child classes must implement the required methods and define localized strings.
    """

    # Common properties
    @property
    @abstractmethod
    def locale_name(self) -> str:
        """Return the name of the locale."""
        pass
    @property
    @abstractmethod
    def button_reset(self) -> str:
        """Return the localized string for 'Reset' button."""
        pass
    @property
    @abstractmethod
    def button_save(self) -> str:
        """Return the localized string for 'Save' button."""
        pass
    @property
    @abstractmethod
    def button_cancel(self) -> str:
        """Return the localized string for 'Cancel' button."""
        pass

    # Receipt
    @property
    @abstractmethod
    def r_number(self) -> str:
        """Return the localized string for 'No.' label."""
        pass
    @property
    @abstractmethod
    def r_customer(self) -> str:
        """Return the localized string for 'Customer' label."""
        pass
    @property
    @abstractmethod
    def r_customer_name(self) -> str:
        """Return the localized string for 'Customer Name' label."""
        pass
    @property
    @abstractmethod
    def r_customer_code(self) -> str:
        """Return the localized string for 'Customer Code' label."""
        pass
    @property
    @abstractmethod
    def r_transaction(self) -> str:
        """Return the localized string for 'Transaction' label."""
        pass
    @property
    @abstractmethod
    def r_promotion(self) -> str:
        """Return the localized string for 'Promotion' label."""
        pass
    @property
    @abstractmethod
    def r_date(self) -> str:
        """Return the localized string for 'Date' label."""
        pass
    @property
    @abstractmethod
    def r_time(self) -> str:
        """Return the localized string for 'Time' label."""
        pass
    @property
    @abstractmethod
    def r_cashier(self) -> str:
        """Return the localized string for 'Cashier' label."""
        pass
    @property
    @abstractmethod
    def r_address(self) -> str:
        """Return the localized string for 'Address' label."""
        pass
    @property
    @abstractmethod
    def r_tax_id(self) -> str:
        """Return the localized string for 'Tax ID' label."""
        pass
    @property
    @abstractmethod
    def r_tax_id_customer(self) -> str:
        """Return the localized string for 'Tax ID / Customer' label."""
        pass
    @property
    @abstractmethod
    def r_branch(self) -> str:
        """Return the localized string for 'Branch' label."""
        pass
    @property
    @abstractmethod
    def r_car_plate(self) -> str:
        """Return the localized string for 'Car Plate' label."""
        pass
    @property
    @abstractmethod
    def r_item(self) -> str:
        """Return the localized string for 'Item' column."""
        pass
    @property
    @abstractmethod
    def r_amount(self) -> str:
        """Return the localized string for 'Amount' column."""
        pass
    @property
    @abstractmethod
    def r_quantity(self) -> str:
        """Return the localized string for 'Quantity' column."""
        pass
    @property
    @abstractmethod
    def r_total(self) -> str:
        """Return the localized string for 'Total' column."""
        pass
    @property
    @abstractmethod
    def r_value(self) -> str:
        """Return the localized string for 'Value' label."""
        pass
    @property
    @abstractmethod
    def r_vat(self) -> str:
        """Return the localized string for 'VAT' label."""
        pass
    @property
    @abstractmethod
    def r_total_label(self) -> str:
        """Return the localized string for 'Total' label."""
        pass
    @property
    @abstractmethod
    def r_points(self) -> str:
        """Return the localized string for 'Points' label."""
        pass
    @property
    @abstractmethod
    def r_received(self) -> str:
        """Return the localized string for 'Received' label."""
        pass
    @property
    @abstractmethod
    def r_change(self) -> str:
        """Return the localized string for 'Change' label."""
        pass
    @property
    @abstractmethod
    def r_discount(self) -> str:
        """Return the localized string for 'Discount' label."""
        pass
    
    # Tab names
    @property
    @abstractmethod
    def tab_printer(self) -> str:
        """Return the localized string for 'Printer' tab."""
        pass
    @property
    @abstractmethod
    def tab_layout(self) -> str:
        """Return the localized string for 'Layout' tab."""
        pass
    @property
    @abstractmethod
    def tab_services(self) -> str:
        """Return the localized string for 'Services' tab."""
        pass
    
    # Printer page
    @property
    @abstractmethod
    def page_printer_usbport(self) -> str:
        """Return the localized string for 'USB Port' setting."""
        pass
    @property
    @abstractmethod
    def page_printer_usbname(self) -> str:
        """Return the localized string for 'USB Name' setting."""
        pass
    @property
    @abstractmethod
    def page_printer_encoding(self) -> str:
        """Return the localized string for 'Encoding' setting."""
        pass
    @property
    @abstractmethod
    def page_printer_linewidth(self) -> str:
        """Return the localized string for 'Line Width' setting."""
        pass
    @property
    @abstractmethod
    def page_printer_pixelwidth(self) -> str:
        """Return the localized string for 'Pixel Width' setting."""
        pass
    @property
    @abstractmethod
    def page_printer_download_driver(self) -> str:
        """Return the localized string for 'Download Driver' setting."""
        pass

    # Layout page
    @property
    @abstractmethod
    def page_layout_header_image(self) -> str:
        """Return the localized string for 'Header Image' section."""
        pass
    @property
    @abstractmethod
    def page_layout_header_title(self) -> str:
        """Return the localized string for 'Header Title' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_header_description(self) -> str:
        """Return the localized string for 'Header Description' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_receipt_title(self) -> str:
        """Return the localized string for 'Receipt Title' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_footer_label(self) -> str:
        """Return the localized string for 'Footer Label' section label."""
        pass
    @property
    @abstractmethod
    def page_layout_footer_image(self) -> str:
        """Return the localized string for 'Footer Image' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_advanced(self) -> str:
        """Return the localized string for 'Advanced' section."""
        pass
    @property
    @abstractmethod
    def page_layout_fontfamily(self) -> str:
        """Return the localized string for 'Font Family' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_fontpath(self) -> str:
        """Return the localized string for 'Font Path' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_fontsize(self) -> str:
        """Return the localized string for 'Font Size' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_fontsize_small(self) -> str:
        """Return the localized string for 'Small Font Size' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_line_spacing(self) -> str:
        """Return the localized string for 'Line Spacing' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_curency(self) -> str:
        """Return the localized string for 'Currency' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_volume_unit(self) -> str:
        """Return the localized string for 'Volume Unit' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_browse(self) -> str:
        """Return the localized string for 'Browse' button."""
        pass
    @property
    @abstractmethod
    def page_layout_clear(self) -> str:
        """Return the localized string for 'Clear' button."""
        pass
    @property
    @abstractmethod
    def page_layout_open_folder(self) -> str:
        """Return the localized string for 'Open in folder' button."""
        pass
    @property
    @abstractmethod
    def page_layout_image_scale(self) -> str:
        """Return the localized string for 'Image Scale' setting."""
        pass
    @property
    @abstractmethod
    def page_layout_preview(self) -> str:
        """Return the localized string for 'Preview' section."""
        pass
    @property
    @abstractmethod
    def page_layout_preview_print(self) -> str:
        """Return the localized string for 'Print Preview' button."""
        pass

    # Services page
    @property
    @abstractmethod
    def page_services_host(self) -> str:
        """Return the localized string for 'Host' setting."""
        pass
    @property
    @abstractmethod
    def page_services_port(self) -> str:
        """Return the localized string for 'Port' setting."""
        pass
    @property
    @abstractmethod
    def page_services_debug_mode(self) -> str:
        """Return the localized string for 'Debug Mode' setting."""
        pass
