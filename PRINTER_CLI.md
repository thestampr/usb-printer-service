# USB Receipt Printer CLI & Cash Drawer

Command-line tools for printing Sarabun-based fuel receipts and opening the cash drawer via ESC/POS USB printers (XP-58 / XP-58IIH).

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
| `--payload` | **Required**. JSON string or path to a JSON file containing the receipt fields listed below. |
| `--header-image` | Override header image path. Defaults to `config/settings.py` value. |
| `--header-title` | Override title text printed above the receipt header. |
| `--header-description` | Override smaller description line under the title. |
| `--receipt-title` | Override receipt title text printed above the items list. |
| `--footer-label` | Override footer text printed before cutting. |
| `--footer-image` | Override footer image path. |
| `--port` | Override printer queue in `PORT:NAME` form, e.g. `USB001:"XP-58 (copy 1)"`. |

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
printer --payload "{\"customer\":{\"name\":\"PTT\"},\"items\":[{\"name\":\"Gasohol 95\",\"amount\":38.25,\"quantity\":10}],\"extras\":{\"Recieved\":\"500.00\",\"Change\":\"127.50\",\"Discount\":\"-10.00\"}}" 
```

### Payload structure

```json
{
    "customer": {
        "name": "PTT Station",
        "code": "CUST-001"
    },
    "items": [
        {
            "name": "Gasohol 95",
            "amount": 38.25,
            "quantity": 10.0
        }
    ],
    "total": 382.5,
    "transection": "TX-2025-11-001",
    "promotion": "PT Max Card",
    "points": 30,
    "extras": {
        "Recieved": "500.00",
        "Change": "127.50",
        "Discount": "-10.00"
    }
}
```

Field notes:

- `customer` *(optional object)* – include when you want a name/code section. Both `name` and `code` are optional strings.
- `items` *(required list)* – each entry must include `name` (string), `amount` (price per liter), and `quantity` (liters).
- `total` *(optional number)* – omit to auto-calculate from `amount × quantity`.
- `transection` *(optional string)* – external transaction/bill reference printed beneath the header.
- `promotion` *(optional string)* – label that prints under the totals block.
- `points` *(optional integer)* – loyalty points earned for the transaction.
- `extras` *(optional object)* – arbitrary key/value pairs (e.g., pump, cashier, kiosk) printed after totals.

## 5. Printer Feedback

- **Receipt Print:** On success, prints `[OK] Receipt printed successfully`. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.
- **Open Drawer:** On success, the drawer opens and the command exits with code 0. On error, prints `[ERROR] ...` to stderr and returns non-zero exit code.

That's it! Use the CLI tools whenever you need an immediate printout or to open the cash drawer directly from your terminal.
