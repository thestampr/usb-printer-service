from .abc import Locale

class LocaleTH(Locale):
    @property
    def locale_name(self) -> str:
        return "ไทย"
    
    @property
    def button_reset(self) -> str:
        return "รีเซ็ต"
    @property
    def button_save(self) -> str:
        return "บันทึก"
    @property
    def button_cancel(self) -> str:
        return "ยกเลิก"
    
    @property
    def r_number(self) -> str:
        return "เลขที่"
    @property
    def r_customer(self) -> str:
        return "ลูกค้า"
    @property
    def r_customer_name(self) -> str:
        return "ชื่อลูกค้า"
    @property
    def r_customer_code(self) -> str:
        return "รหัสลูกค้า"
    @property
    def r_transaction(self) -> str:
        return "เลขรายการ"
    @property
    def r_promotion(self) -> str:
        return "โปรโมชั่น"
    @property
    def r_date(self) -> str:
        return "วันที่"
    @property
    def r_time(self) -> str:
        return "เวลา"
    @property
    def r_cashier(self) -> str:
        return "พนักงานขาย"
    @property
    def r_address(self) -> str:
        return "ที่อยู่"
    @property
    def r_tax_id(self) -> str:
        return "เลขผู้เสียภาษี (ร้านค้า)"
    @property
    def r_tax_id_customer(self) -> str:
        return "เลขผู้เสียภาษี (ลูกค้า)"
    @property
    def r_branch(self) -> str:
        return "สาขา"
    @property
    def r_car_plate(self) -> str:
        return "ทะเบียนรถ"
    @property
    def r_item(self) -> str:
        return "รายการ"
    @property
    def r_amount(self) -> str:
        return "ราคา"
    @property
    def r_quantity(self) -> str:
        return "จำนวน"
    @property
    def r_total(self) -> str:
        return "รวม"
    @property
    def r_value(self) -> str:
        return "มูลค่า"
    @property
    def r_vat(self) -> str:
        return "ภาษีมูลค่าเพิ่ม 7%"
    @property
    def r_total_label(self) -> str:
        return "รวมทั้งหมด"
    @property
    def r_points(self) -> str:
        return "คะแนน"
    @property
    def r_received(self) -> str:
        return "รับเงิน"
    @property
    def r_change(self) -> str:
        return "เงินทอน"
    @property
    def r_discount(self) -> str:
        return "ส่วนลด"
    
    @property
    def tab_printer(self) -> str:
        return "เครื่องพิมพ์"
    @property
    def tab_layout(self) -> str:
        return "เค้าโครง"
    @property
    def tab_services(self) -> str:
        return "บริการ"
    
    @property
    def page_printer_usbport(self) -> str:
        return "พอร์ต USB"
    @property
    def page_printer_usbname(self) -> str:
        return "ชื่อ USB"
    @property
    def page_printer_linewidth(self) -> str:
        return "ความกว้างบรรทัด"
    @property
    def page_printer_pixelwidth(self) -> str:
        return "ความกว้างพิกเซล"
    @property
    def page_printer_download_driver(self) -> str:
        return "ดาวน์โหลดไดรเวอร์"
    
    @property
    def page_layout_header_image(self) -> str:
        return "รูปภาพส่วนหัว"
    @property
    def page_layout_header_title(self) -> str:
        return "หัวข้อส่วนหัว"
    @property
    def page_layout_header_description(self) -> str:
        return "คำอธิบายส่วนหัว"
    @property
    def page_layout_receipt_title(self) -> str:
        return "หัวข้อใบเสร็จ"
    @property
    def page_layout_footer_label(self) -> str:
        return "ป้ายส่วนท้าย"
    @property
    def page_layout_footer_image(self) -> str:
        return "รูปภาพส่วนท้าย"
    @property
    def page_layout_advanced(self) -> str:
        return "ขั้นสูง"
    @property
    def page_layout_fontfamily(self) -> str:
        return "ตระกูลฟอนต์"
    @property
    def page_layout_fontpath(self) -> str:
        return "เส้นทางฟอนต์"
    @property
    def page_layout_fontsize(self) -> str:
        return "ขนาดฟอนต์"
    @property
    def page_layout_fontsize_small(self) -> str:
        return "ขนาดฟอนต์เล็ก"
    @property
    def page_layout_line_spacing(self) -> str:
        return "ระยะห่างบรรทัด"
    @property
    def page_layout_curency(self) -> str:
        return "สกุลเงิน"
    @property
    def page_layout_volume_unit(self) -> str:
        return "หน่วยปริมาตร"
    @property
    def page_layout_browse(self) -> str:
        return "เรียกดู"
    @property
    def page_layout_clear(self) -> str:
        return "ล้าง"
    @property
    def page_layout_open_folder(self) -> str:
        return "เปิดในโฟลเดอร์"
    @property
    def page_layout_image_scale(self) -> str:
        return "ขนาดรูปภาพ"
    @property
    def page_layout_preview(self) -> str:
        return "แสดงตัวอย่าง"
    @property
    def page_layout_preview_print(self) -> str:
        return "พิมพ์ตัวอย่าง"
    
    @property
    def page_services_host(self) -> str:
        return "โฮสต์"
    @property
    def page_services_port(self) -> str:
        return "พอร์ต"
    @property
    def page_services_debug_mode(self) -> str:
        return "โหมดแก้ไขข้อบกพร่อง"