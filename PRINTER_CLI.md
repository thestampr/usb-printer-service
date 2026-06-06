# USB Receipt Printer CLI & Cash Drawer

Command-line tools for printing LINESeedSans-based fuel receipts and opening the cash drawer via ESC/POS USB printers (XP-58 / XP-58IIH).

## 1. Installation

1. **Clone / copy** this repository locally.
2. **Install Python 3.10+** (Windows). Make sure `python` and `pip` are available in your terminal.
3. **Install dependencies** inside the project folder:
   ```cmd
   pip install -r requirements.txt
   ```
4. **Verify pywin32** is installed (required for Win32Raw printing).

## 2. Add CLI to PATH (optional but recommended)

The helper batch file `printer.bat` lives in the project root. Add that folder to your PATH so `printer` works from any directory.

1. Open *System Properties → Advanced → Environment Variables*.
2. Edit the **Path** entry under your user account.
3. Add the absolute path to this repository, e.g. `C:\Users\TheSt\Desktop\Dev\usb_printer_service`.
4. Open a new `cmd` window and verify: `printer --help`.

> Without PATH changes you can still run `python cli.py ...` inside the repo.

## 3. CLI Syntax

### Print Receipt

```
printer --payload <JSON string|path> [options]
```

| Option | Description |
| ------ | ----------- |
| `--payload` | **Required unless `--config`, `--test`, or `--serve` is used**. JSON string or path to a JSON file containing the receipt fields listed below. |
| `--locale` | Locale for receipt text; choose `en` (English) or `th` (Thai). Overrides the saved layout `receipt_locale` for this print. |
| `--header-image` | Override header image path. Defaults to `config/settings.json` value. |
| `--header-title` | Override title text printed above the receipt header. |
| `--header-description` | Override smaller description line under the title. |
| `--receipt-title` | Override receipt title text printed above the items list. |
| `--footer-label` | Override footer text printed before cutting. |
| `--footer-image` | Override footer image path. |
| `--header-image-scale` | Override header image scale as a percent of width (`0`–`100`). |
| `--footer-image-scale` | Override footer image scale as a percent of width (`0`–`100`). |
| `--port` | Override printer queue in `PORT:NAME` form, e.g. `USB001:"XP-58 (copy 1)"`. |
| `--paper-width` | Override paper width in mm: `58` or `80`. Sets the matching line/pixel width for this print. |
| `--config` | Launch the configuration UI (native window) and exit without printing. |
| `--test` | Print a test page with dummy data to verify printer setup and auto-calculation. |
| `--serve` | Run the Flask API server (optionally specify host:port). |
| `--update` | Check for a newer version on GitHub and install it if available (prompts for confirmation). |
| `--yes` / `-y` | Skip the confirmation prompt when used with `--update`. |

### Open Cash Drawer

```
open-drawer [--port PORT:NAME]
```

| Option | Description |
| ------ | ----------- |
| `--port` | Override printer queue in `PORT:NAME` form, e.g. `USB001:"XP-58 (copy 1)"`. |

This command sends the ESC/POS "kick_drawer" signal to open the cash drawer attached to the printer.

## 4. Examples

### Basic print (payload file)
```cmd
printer --payload receipts/demo.json
```

### Print test page
```cmd
printer --test
```

### Print with specific locale

```cmd
printer --payload receipts/demo.json --locale th
```

### Print on 80mm paper

```cmd
printer --payload receipts/demo.json --paper-width 80
```

The `--locale` flag overrides the saved `LAYOUT.receipt_locale` for the current print job. To change the default persisted locale, use the configuration UI (Layout → Preview) or update the `receipt_locale` key under the `LAYOUT` section in the settings JSON.

### Open the configuration UI
```cmd
printer --config
```

### Run the Flask API server
```cmd
printer --serve
printer --serve localhost:6000
```

### Open cash drawer
```cmd
open-drawer
```

### Open cash drawer with specific USB port
```cmd
open-drawer --port USB001:"XP-58"
```

### Using batch helper (after PATH setup)
```cmd
printer --payload receipts/demo.json
open-drawer
```

### Custom header/footer text in Thai
```cmd
printer --payload receipts/demo.json ^
    --header-title "PTT Station Rama 4" ^
    --header-description "บริการด้วยใจ" ^
    --footer-label "ขอบคุณที่ใช้บริการ"
```

### Override images and USB queue
```cmd
printer --payload receipts/demo.json ^
    --header-image assets/images/custom_header.png ^
    --header-image-scale 100 ^
    --footer-image assets/images/custom_footer.png ^
    --footer-image-scale 60 ^
    --port USB001:"XP-58 (copy 2)"
```

### Inline JSON payload
```cmd
printer --payload "{\"header_info\":{\"Customer Name\":\"PTT\"},\"items\":[{\"name\":\"Gasohol 95\",\"amount\":38.25,\"quantity\":10}],\"transaction_info\":{\"received\":500.00,\"change\":127.50}}" 
```

### Payload structure

```json
{
    "rfid": "",
    "info_title": "Tax Invoice (ABB)",
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
    },
    "images": {
        "header": {
            "src": "assets/images/custom_header.png",
            "scale": 100
        },
        "footer": {
            "src": "data:image/png;base64,iVBORw0KGgo...",
            "scale": 60
        }
    }
}
```

Field notes:

- `rfid` *(optional string)* – printed at the top-left of the receipt in the small font. Empty by default (not printed when blank).
- `info_title` *(optional string)* – printed centered just after the header description, in the main font size. Empty by default. (The legacy `info-title` key is still accepted.)
- `header_info` *(optional object)* – arbitrary key/value pairs for header information (e.g., customer details, transaction ID). Keys matching the recognized set (see the table in `README.md`, e.g. `Transaction`, `Cashier`, `Date`) are auto-translated to the active locale's label; unrecognized keys print verbatim.
- `items` *(required, non-empty list)* – each entry must include `name` (string), `amount` (price per unit), and `quantity` (number of units). The per-line total is `amount × quantity`. Items render as four columns: **Item / Amount / Qty / Total**.
- `footer_info` *(optional object)* – arbitrary key/value pairs for footer information (e.g., points, notes). Recognized keys are auto-translated like `header_info`.
- `transaction_info` *(optional object)* – transaction details with auto-calculation. Only the four keys below are read; any others are ignored.
  - `received` *(optional number)* – amount received from customer.
  - `change` *(optional number)* – change to return (auto-calculated if `received` and `total` known).
  - `discount` *(optional number)* – discount amount (applied to items total if `total` not provided).
  - `total` *(optional number)* – final total (auto-calculated from items if not provided).
- `images` *(optional object)* – per-print header/footer images, each with:
  - `src` *(string)* – a file path **or** a base64 string / `data:` URI of the image.
  - `scale` *(optional number)* – render size as a percent of width (`0`–`100`).
  - **Precedence:** the CLI flags `--header-image` / `--footer-image` / `--header-image-scale` / `--footer-image-scale` override the payload `images`, which in turn override the saved layout config.

**Auto-calculation rules:**
- If `total` not provided, it's calculated as sum of `amount × quantity` for all items.
- If `discount` provided and `total` not provided, `total = items_total - discount`.
- If `received` and `total` known but `change` not, `change = received - total`.
- If `change` and `total` known but `received` not, `received = total + change`.
- If `received` and `change` both provided, `total = received - change` (authoritative).
- If `received` and `change` both provided but `discount` not, `discount = items_total - total`.
- All derived monetary values are rounded to 2 decimals.

**Auto-derived display fields** (added for you — do not send these):
- Resolved `received`, `change`, and `discount` are appended to `footer_info` and print in the footer block as **Received**, **Change**, and **Discount**.
- A **Value** (pre-VAT) line and a **VAT 7%** line are computed from the total and printed just above it whenever the total is positive. VAT is treated as already included in the total: `vat = ⌊total × 0.07 / 1.07⌋`, `value = total − vat`.

**Legacy payload format** (still accepted for backward compatibility): if any of `customer`, `transection`, `promotion`, `points`, or `extras` appears at the top level, the payload is auto-converted to the structure above:

| Legacy field | Mapped to |
| ------------ | --------- |
| `customer` `{ "name", "code" }` | `header_info` → `Customer name` / `Customer Code` |
| `transection` *(note spelling)* | `header_info["Transaction"]` |
| `promotion` | `header_info["Promotion"]` |
| `points` | `footer_info["Points"]` |
| `total` | `transaction_info.total` |
| `extras` *(object)* | merged into `transaction_info` |

## 5. Printer Feedback

- **Receipt Print:** On success, prints `[OK] Receipt printed successfully`. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.
- **Test Print:** On success, prints `[OK] Test page printed successfully`. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.
- **Open Drawer:** On success, the drawer opens and the command exits with code 0. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.
- **Config UI:** Exits with code 0 when the window closes (or non-zero if startup fails).
- **Serve:** Starts the Flask server; exits with code 0 on normal shutdown or non-zero on startup error.

That's it! Use the CLI tools whenever you need an immediate printout or to open the cash drawer directly from your terminal.
