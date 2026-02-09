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
| `--header-image` | Override header image path. Defaults to `config/settings.json` value. |
| `--header-title` | Override title text printed above the receipt header. |
| `--header-description` | Override smaller description line under the title. |
| `--receipt-title` | Override receipt title text printed above the items list. |
| `--footer-label` | Override footer text printed before cutting. |
| `--footer-image` | Override footer image path. |
| `--port` | Override printer queue in `PORT:NAME` form, e.g. `USB001:"XP-58 (copy 1)"`. |
| `--config` | Launch the Tkinter configuration UI and exit without printing. |
| `--test` | Print a test page with dummy data to verify printer setup and auto-calculation. |
| `--serve` | Run the Flask API server (optionally specify host:port). |

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
    --footer-image assets/images/custom_footer.png ^
    --port USB001:"XP-58 (copy 2)"
```

### Inline JSON payload
```cmd
printer --payload "{\"header_info\":{\"Customer Name\":\"PTT\"},\"items\":[{\"name\":\"Gasohol 95\",\"amount\":38.25,\"quantity\":10}],\"transaction_info\":{\"received\":500.00,\"change\":127.50}}" 
```

### Payload structure

```json
{
    "header_info": {
        "Customer Name": "PTT Station",
        "Customer Code": "CUST-001",
        "Transaction": "TX-2025-11-001",
        "Promotion": "PT Max Card"
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

Field notes:

- `header_info` *(optional object)* – arbitrary key/value pairs for header information (e.g., customer details, transaction ID).
- `items` *(required list)* – each entry must include `name` (string), `amount` (price per unit), and `quantity` (number of units).
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

## 5. Printer Feedback

- **Receipt Print:** On success, prints `[OK] Receipt printed successfully`. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.
- **Test Print:** On success, prints `[OK] Test page printed successfully`. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.
- **Open Drawer:** On success, the drawer opens and the command exits with code 0. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.
- **Config UI:** Exits with code 0 when the window closes (or non-zero if startup fails).
- **Serve:** Starts the Flask server; exits with code 0 on normal shutdown or non-zero on startup error.

That's it! Use the CLI tools whenever you need an immediate printout or to open the cash drawer directly from your terminal.
