# USB Receipt Printer CLI

Command-line tool for printing Sarabun-based fuel receipts directly to ESC/POS USB printers (XP-58 / XP-58IIH).

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

## 4. Examples

### Basic print (payload file)
```cmd
printer --payload receipts/demo.json
```

### Using batch helper (after PATH setup)
```cmd
printer --payload receipts/demo.json
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
printer --payload "{\"customer\":{\"name\":\"PTT\"},\"items\":[{\"name\":\"Gasohol 95\",\"amount\":38.25,\"quantity\":10}] }"
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
    "points": 30
}
```

Field notes:

- `customer` *(optional object)* – include when you want a name/code section. Both `name` and `code` are optional strings.
- `items` *(required list)* – each entry must include `name` (string), `amount` (price per liter), and `quantity` (liters).
- `total` *(optional number)* – omit to auto-calculate from `amount × quantity`.
- `transection` *(optional string)* – external transaction/bill reference printed beneath the header.
- `promotion` *(optional string)* – label that prints under the totals block.
- `points` *(optional integer)* – loyalty points earned for the transaction.

## 5. Printer Feedback

- On success the CLI prints `[OK] Receipt printed successfully`.
- If validation fails or the printer cannot be reached, it prints `[ERROR] ...` to stderr and returns a non-zero exit code so scripts can detect failures.

That's it! Use the CLI whenever you need an immediate printout directly from your terminal.
