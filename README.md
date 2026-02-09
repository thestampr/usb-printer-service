# USB Fuel Receipt Printer Service

Python-based receipt printing system for XP-58 / XP-58IIH ESC/POS printers with UTF-8 Thai support, font rendering (including LINESeedSans), and dual entry points (Flask API + standalone CLI).

## Features

- Flask API (`server/app.py`) with CORS-enabled `POST /print` endpoint
- Standalone CLI (`printer` / `cli.py`) that prints directly via USB, no HTTP needed
- ESC/POS USB driver with Pillow-based rendering, image centering, and cut/feed helpers
- Font support for receipts (LINESeedSans included for Thai text, quantity in liters, price in baht)
- Optional header/footer text and image customization
- Windows Win32Raw printing with `pywin32`

## Installation

1. Install Python 3.10+ on Windows.
2. Clone this repository and open a terminal in the project root.
3. Run the helper script once:
  ```cmd
  setup.cmd
   ```
   This installs `virtualenv`, creates `.venv`, installs `requirements.txt`, and appends the project's `bin` folder to your user `PATH`.

Note: The system supports various fonts for rendering. LINESeedSans font files are included under `assets/fonts/LINESeedSans/` for Thai text support.

## Running the Flask API

```cmd
python main.py
```

Send a JSON payload to `POST http://localhost:5000/print` matching the structure below.

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
- Service host/port/debug flags

## Development Tips

- Use the `printer` CLI for rapid manual testing without running the server.
- For debugging prints enable logging via `logging.basicConfig(level=logging.DEBUG)` early in `main.py` or `printer_cli.py`.
- Keep the printer driver connected to the exact Windows queue name (e.g., `XP-58 (copy 1)`).
