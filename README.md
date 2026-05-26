# USB Fuel Receipt Printer Service

Python-based receipt printing system for XP-58 / XP-58IIH ESC/POS printers with UTF-8 Thai support, font rendering (including LINESeedSans), and dual entry points (Flask API + standalone CLI).

## Features

- Flask API (`server/app.py`) with CORS-enabled `POST /print` endpoint
- Standalone CLI (`printer` / `cli.py`) that prints directly via USB, no HTTP needed
- ESC/POS USB driver with Pillow-based rendering, image centering, and cut/feed helpers
- Font support for receipts (LINESeedSans included for Thai text, quantity in liters, price in baht)
- Optional header/footer text and image customization
- Windows Win32Raw printing with `pywin32`
- Auto-calculation of totals, change, and discounts from itemized data
- Configuration UI for printer settings, layout defaults, and service options
- Locale-aware rendering with English and Thai labels for common receipt fields (e.g., Customer, Total, Points)

## Installation

### Method 1: Local Setup (Development)

1. Install Python 3.10+ on Windows.
2. Clone this repository and open a terminal in the project root.
3. Run the helper script once:
  ```cmd
  setup.cmd
  ```
  This installs `virtualenv`, creates `.venv`, installs `requirements.txt`, and appends the project's `bin` folder to your user `PATH`. The `PATH` change is applied immediately, so open a **new** terminal afterwards to use the `printer` / `open-drawer` commands.

### Method 2: One-Click Installer (Recommended)

1. Copy [installer.bat](installer.bat) to your local machine.
2. Run `installer.bat` as Administrator.
3. This will automatically:
   - Check/Install Python if missing.
   - Configure the virtual environment.
   - Setup system PATH and shortcuts.

#### Updating

Run `installer.bat` again to update. It auto-detects an existing install under `%USERPROFILE%\.lib`, downloads the latest version, copies it over, and refreshes dependencies. Your saved configuration (`config/temp.settings.json`), virtual environment (`.venv`), and custom header/footer images are preserved across updates.

> **Note**: The `PATH` update takes effect automatically — just open a **new** terminal and run `printer --help`. Terminals that were already open won't pick up the change until reopened.

> **Note**: The system supports various fonts for rendering. LINESeedSans font files are included under `assets/fonts/LINESeedSans/` for Thai text support.

## Running the Flask API

```cmd
python main.py
```

Send a JSON payload to `POST http://localhost:5000/print` matching the structure below.

### Payload structure

```json
{
    "header_info": {
        "Customer Name": "Dummy",
        "Customer Code": "CT-9904",
        "Transaction": "TXN-TEST-1234",
        "Promotion": "TestOnProd",
    },
    "items": [
        {
            "name": "Gasohol 95",
            "amount": 38.25,
            "quantity": 10.0
        }
    ],
    "footer_info": {
        "Points": "30"
    },
    "transaction_info": {
        "received": 500.00,
        "change": 127.50,
        "discount": 10.00,
        "total": 382.50
    }
}
```

**Field notes**

- `header_info` *(optional object)* – arbitrary key/value pairs for header information (e.g., customer details, transaction ID).
- `items` *(required list)* – each item needs `name` (string), `amount` (price per unit), and `quantity` (number of units).
- `footer_info` *(optional object)* – arbitrary key/value pairs for footer information (e.g., points, notes).
- `transaction_info` *(optional object)* – transaction details with auto-calculation:
  - `received` *(optional number)* – amount received from customer.
  - `change` *(optional number)* – change to return (auto-calculated if `received` and `total` known).
  - `discount` *(optional number)* – discount amount (applied to items total if `total` not provided).
  - `total` *(optional number)* – final total (auto-calculated from items if not provided).

**Auto-calculation rules:**
- If `total` not provided, it's calculated as sum of `amount × quantity` for all items.
- If `discount` provided and `total` not provided, `total = items_total - discount`.
- If `received` and `total` known but `change` not, `change = received - total`.
- If `change` and `total` known but `received` not, `received = total + change`.
- If `received` and `change` both provided, `total = received - change` (authoritative).
- If `received` and `change` both provided but `discount` not, `discount = items_total - total`.

### Pre-translated header/footer keys

The renderer will automatically map a set of well-known keys in `header_info` and `footer_info` to locale-specific labels (case-insensitive). The table below shows the recognized key names and their English and Thai labels.

| Key (input) | English label | Thai label |
| --- | --- | --- |
| `no.` / `number` | No. | เลขที่ |
| `customer` | Customer | ลูกค้า |
| `customer name` | Customer Name | ชื่อลูกค้า |
| `customer code` | Customer Code | รหัสลูกค้า |
| `transaction` | Transaction | เลขรายการ |
| `promotion` | Promotion | โปรโมชั่น |
| `date` | Date | วันที่ |
| `time` | Time | เวลา |
| `cashier` | Cashier | พนักงานขาย |
| `address` | Address | ที่อยู่ |
| `tax id` | Tax ID (store) | เลขผู้เสียภาษี (ร้านค้า) |
| `tax id customer` | Tax ID (customer) | เลขผู้เสียภาษี (ลูกค้า) |
| `branch` | Branch | สาขา |
| `car plate` | Car Plate | ทะเบียนรถ |
| `points` | Points | คะแนน |
| `received` | Received | รับเงิน |
| `change` | Change | เงินทอน |
| `discount` | Discount | ส่วนลด |

Example:

```json
{
    "header_info": { "Transaction": "TXN-123", "Cashier": "Alice" },
    "footer_info": { "Points": "150", "Received": 500.00 }
}
```

The keys `Transaction`, `Cashier`, `Points`, and `Received` in the example will be translated to the selected locale's labels when the receipt is rendered.

## Using the CLI

Quick example:

```cmd
printer --payload receipts/demo.json --port USB001:"XP-58 (copy 1)"
```

You can run the Flask API directly from the CLI (default host/port come from the current configuration):

```cmd
printer --serve
printer --serve localhost:6000
```

Test the printer with a sample receipt:

```cmd
printer --test
```

This prints a test receipt with dummy data and demonstrates auto-calculation (e.g., received amount and computed change).

## Opening the Cash Drawer

Send a `POST` request to `/open-drawer` to trigger the cash drawer kick.

or use the CLI:

```cmd
open-drawer
```

## Configuration

Use the configuration UI 

```cmd
printer --config
```

to adjust printer, layout, and service settings.

- Printer queue name/port
- Header/footer text and images (with file pickers)
- Layout defaults (font size, currency, units)
- Receipt locale: `receipt_locale` ("en" or "th") — controls the language used for receipt labels (e.g., Item, Qty, Total). You can change this from the Layout → Preview header in the configuration UI or via the CLI `--locale` flag; the CLI flag overrides the saved setting for that print job.
- Service host/port/debug flags

## Development Tips

- Use the `printer` CLI for rapid manual testing without running the server.
- For debugging prints enable logging via `logging.basicConfig(level=logging.DEBUG)` early in `main.py` or `printer_cli.py`.
- Keep the printer driver connected to the exact Windows queue name (e.g., `XP-58 (copy 1)`).
