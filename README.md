# USB Fuel Receipt Printer Service

Python-based receipt printing system for XP-58 / XP-58IIH ESC/POS printers with UTF-8 Thai support, Sarabun font rendering, and dual entry points (Flask API + standalone CLI).

## Features

- Flask API (`server/app.py`) with CORS-enabled `POST /print` endpoint
- Standalone CLI (`printer` / `cli.py`) that prints directly via USB, no HTTP needed
- ESC/POS USB driver with Pillow-based Thai rendering, image centering, and cut/feed helpers
- Sarabun-SeimiBold font template for fuel receipts (quantity in liters, price in baht)
- Optional header/footer text and image customization
- Windows Win32Raw printing with `pywin32`

## Project Structure

```
config/
  settings.py
printer/
  driver.py
  utils.py
  template.py
server/
  app.py
main.py
cli.py
printer.bat
PRINTER_CLI.md
```

## Installation

1. Install Python 3.10+ on Windows.
2. Clone this repository and open a terminal in the project root.
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
4. Make sure the Sarabun font files under `assets/fonts/Sarabun/` exist; update `config/settings.py` if using a different path.

## Running the Flask API

```cmd
python main.py
```

Send a JSON payload to `POST http://localhost:5000/print` matching the structure below.

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

**Field notes**

- `customer` *(optional object)* – use when a name/code should appear. Both subfields are optional strings.
- `items` *(required list)* – each item needs `name` (string), `amount` (price per liter), and `quantity` (liters).
- `total` *(optional number)* – omit to auto-calc from `amount × quantity`.
- `transection` *(optional string)* – external transaction / bill reference printed under the header.
- `promotion` *(optional string)* – text printed beneath the totals block.
- `points` *(optional integer)* – loyalty points earned.
- `extras` *(optional object)* – arbitrary key/value pairs (e.g., pump, cashier, terminal) printed after the totals block.

## Using the CLI

Quick example:

```cmd
printer --payload receipts/demo.json --port USB001:"XP-58 (copy 1)"
```

## Opening the Cash Drawer

Send a `POST` request to `/open-drawer` to trigger the cash drawer kick.

or use the CLI:

```cmd
open-drawer
```

## Configuration

Edit `config/settings.py` to adjust:

- Printer queue name/port
- Header/footer text and images
- Layout defaults (font size, currency, units)
- Service host/port/debug flags

## Development Tips

- Use the `printer` CLI for rapid manual testing without running the server.
- For debugging prints enable logging via `logging.basicConfig(level=logging.DEBUG)` early in `main.py` or `cli.py`.
- Keep the printer driver connected to the exact Windows queue name (e.g., `XP-58 (copy 1)`).
