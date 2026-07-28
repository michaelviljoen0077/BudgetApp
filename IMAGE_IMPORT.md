# Image Import & AI Processing Features

## Overview

The Budget App now supports **intelligent image and PDF import** with:
- **OCR (Optical Character Recognition)** to extract text from images/PDFs
- **AI-powered document classification** to detect receipts vs bank statements
- **Automatic duplicate detection** across different import sources
- **Smart reconciliation** to prevent double-entry

---

## Features

### 1. Image/PDF Upload
Upload receipts or bank statements in multiple formats:
- **Images**: PNG, JPG, JPEG, BMP, TIFF, GIF
- **PDFs**: Both text-based and scanned PDFs

### 2. AI Document Classification
The AI automatically detects:
- **Receipt**: Single transaction from a store/restaurant
- **Bank Statement**: Multiple transactions from your bank

### 3. Duplicate Detection
Before importing, the system checks for duplicates by comparing:
- Transaction date (±3 days tolerance)
- Amount (1% tolerance)
- Merchant name
- Description text

### 4. Bank Statement Month Checking
When importing a bank statement, the system:
- Detects which month the statement covers
- Warns if you've already imported that month
- Prevents duplicate monthly imports

### 5. Receipt Reconciliation
When importing a receipt, the system:
- Searches for matching bank transactions
- Links receipts to bank statements
- Prevents double-counting expenses

---

## How to Use

### Step 1: Install Tesseract OCR (Required)

**Windows:**
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to: `C:\Program Files\Tesseract-OCR\`
3. Add to PATH or configure in code

**Mac:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

### Step 2: Install Python Dependencies
```bash
pip install -r backend/requirements.txt
```

New dependencies include:
- `pytesseract` - Python wrapper for Tesseract
- `Pillow` - Image processing
- `pdfplumber` - PDF text extraction
- `python-multipart` - File upload support

### Step 3: Start Backend with Ollama
```bash
# Start Ollama (in separate terminal)
ollama serve

# Pull Mistral model
ollama pull mistral

# Start backend
python run_backend.py
```

### Step 4: Use Image Import

1. **Open the app**
   ```bash
   python run_app.py
   ```

2. **Navigate to "Import" tab**

3. **Click "Import Image/PDF (Receipt or Statement)"**

4. **Select your file** (receipt photo or PDF statement)

5. **Wait for processing** (OCR + AI classification takes 5-30 seconds)

6. **Review results:**
   - Document type detected
   - Confidence score
   - Transactions imported
   - Duplicates found
   - Warnings (if any)

---

## Workflow Examples

### Example 1: Import a Receipt Photo

```
You: [Upload receipt.jpg from McDonald's]

System Processing:
✓ Extract text with OCR
✓ Classify as "receipt" (confidence: 95%)
✓ Parse transaction:
  - Date: 2025-12-14
  - Merchant: McDonald's
  - Amount: $12.50
✓ Check duplicates...
  → Found bank transaction from 2025-12-14 for $12.50 at McDonald's
  
Result:
⚠️  Duplicate found! This transaction is already in your bank statement.
Skipped import to prevent double-counting.
```

### Example 2: Import Bank Statement PDF

```
You: [Upload December_Statement.pdf]

System Processing:
✓ Extract text from PDF (15 transactions found)
✓ Classify as "bank_statement" (confidence: 98%)
✓ Check if December 2025 already imported...
  ✓ No existing statement found
✓ Process each transaction:
  - Transaction 1: $45.00 at Grocery Store → Imported
  - Transaction 2: $12.50 at McDonald's → Duplicate found (receipt), Skipped
  - Transaction 3: $89.99 at Amazon → Imported
  ...
  
Result:
✅ Imported 13 new transactions
⏭️  Skipped 2 duplicates (already from receipts)
```

### Example 3: Import Duplicate Statement

```
You: [Upload December_Statement.pdf again]

System Processing:
✓ Extract text from PDF
✓ Classify as "bank_statement"
✓ Check if December 2025 already imported...
  
Result:
⚠️  Warning: Statement for December 2025 may already exist
⏭️  Skipped 15 duplicate transactions
✅ Imported 0 new transactions
```

---

## API Endpoint

### `POST /imports/image`

Upload an image or PDF for intelligent import.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `file` (image or PDF file)

**Response:**
```json
{
  "document_type": "receipt",
  "confidence": 0.95,
  "extracted_text_length": 342,
  "imported": 1,
  "duplicates_found": 0,
  "warnings": [],
  "duplicate_details": null
}
```

**Fields:**
- `document_type`: "receipt", "bank_statement", or "unknown"
- `confidence`: AI classification confidence (0-1)
- `extracted_text_length`: Characters extracted via OCR
- `imported`: Number of new transactions imported
- `duplicates_found`: Number of duplicates skipped
- `warnings`: List of warning messages
- `duplicate_details`: Info about found duplicates (if any)

---

## Architecture

### Backend Components

1. **`image_service.py`** - OCR processing
   - Extracts text from images using Tesseract
   - Extracts text from PDFs using pdfplumber
   - Handles both text-based and scanned PDFs

2. **`ai_service.py`** - AI classification & parsing
   - `classify_document()` - Detects receipt vs statement
   - `parse_receipt()` - Extracts date, merchant, amount
   - `parse_bank_statement()` - Extracts multiple transactions
   - Uses Ollama (Mistral model) for intelligent parsing

3. **`reconciliation.py`** - Duplicate detection
   - `find_duplicates()` - Finds similar transactions
   - `check_month_statement_exists()` - Checks existing statements
   - `find_statement_transaction()` - Matches receipts to statements
   - Smart matching with date/amount/merchant similarity

4. **`main.py`** - API endpoint
   - `POST /imports/image` - Handles file upload
   - Orchestrates OCR → AI classification → parsing → duplicate check

### Frontend Components

1. **`api_client.py`**
   - `import_image()` - Uploads file to backend

2. **`main.py`**
   - Image import button in "Import" tab
   - Progress dialog during processing
   - Result display with warnings

---

## Configuration

### Tesseract Path (Windows)
If Tesseract is not in your PATH, configure it in `backend/main.py`:

```python
image_service = get_image_service(
    tesseract_path="C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
)
```

### AI Service Provider
Choose your AI provider in `backend/main.py`:

```python
# Local Ollama (default)
ai_service = get_ai_service(provider="local", model="mistral")

# No AI (basic parsing only)
ai_service = get_ai_service(provider="noop")

# Remote API (future)
ai_service = get_ai_service(provider="openai", api_key="...")
```

### Duplicate Detection Thresholds

Adjust in `backend/reconciliation.py`:

```python
duplicates = reconciliation_service.find_duplicates(
    new_transaction,
    date_tolerance_days=3,      # ±3 days
    amount_tolerance_percent=0.01  # ±1%
)
```

---

## Troubleshooting

### "Could not extract meaningful text"
- **Cause**: Image quality too low or OCR failed
- **Solution**: 
  - Use higher resolution images
  - Ensure text is clear and readable
  - Check that Tesseract is installed

### "Could not classify document"
- **Cause**: AI confidence too low
- **Solution**:
  - Ensure Ollama is running
  - Check that document is actually a receipt/statement
  - Try manually importing as CSV instead

### "Tesseract not found"
- **Cause**: Tesseract not installed or not in PATH
- **Solution**:
  - Install Tesseract (see Step 1 above)
  - Configure path in backend initialization

### Duplicate detection too aggressive
- **Solution**: Adjust thresholds in `reconciliation.py`
  - Increase `date_tolerance_days` for wider date range
  - Increase `amount_tolerance_percent` for more amount variation

### Ollama connection errors
- **Cause**: Ollama not running or wrong URL
- **Solution**:
  - Start Ollama: `ollama serve`
  - Check URL in `backend/main.py` (should be `http://localhost:11434`)

---

## Performance Notes

- **OCR Processing**: 2-10 seconds per image
- **PDF Processing**: 5-30 seconds depending on pages
- **AI Classification**: 1-3 seconds with Ollama
- **Duplicate Detection**: <1 second for 1000 transactions

**Optimization Tips:**
- Use clear, high-contrast images
- Crop images to just the receipt/statement
- For large PDFs, consider splitting into smaller files

---

## Future Enhancements

- [ ] Multi-language OCR support
- [ ] Receipt item extraction (individual line items)
- [ ] Auto-categorization after import
- [ ] Bulk upload (multiple files at once)
- [ ] Mobile app integration
- [ ] Cloud OCR fallback (Google Vision, AWS Textract)
- [ ] Receipt photo capture from camera
- [ ] Statement parsing for specific banks (Chase, Bank of America, etc.)

---

## Security & Privacy

**All processing is LOCAL:**
- OCR runs on your machine (Tesseract)
- AI runs on your machine (Ollama)
- Images never leave your computer
- No cloud services required

Your financial data stays private and secure.
