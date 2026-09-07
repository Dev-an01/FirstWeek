-- Phase 10: OCR Metadata Migration
-- Adds parsing_method and ocr_applied columns to executive_documents table
-- to track how documents were processed.

-- Add parsing_method column
-- Values: pdfplumber, mineru, olmocr2, docx, text, json, image
ALTER TABLE executive_documents
ADD COLUMN IF NOT EXISTS parsing_method VARCHAR(30) DEFAULT 'pdfplumber';

-- Add ocr_applied column
-- True if OCR was used to extract text from the document
ALTER TABLE executive_documents
ADD COLUMN IF NOT EXISTS ocr_applied BOOLEAN DEFAULT false;

-- Add comments for documentation
COMMENT ON COLUMN executive_documents.parsing_method IS
'Method used to parse the document: pdfplumber, mineru, olmocr2, docx, text, json, image';

COMMENT ON COLUMN executive_documents.ocr_applied IS
'True if OCR was applied to extract text (scanned PDFs, images)';

-- Create index for filtering by parsing method (useful for debugging/analytics)
CREATE INDEX IF NOT EXISTS idx_exec_docs_parsing_method
ON executive_documents(parsing_method);

-- Create index for filtering by OCR applied
CREATE INDEX IF NOT EXISTS idx_exec_docs_ocr_applied
ON executive_documents(ocr_applied) WHERE ocr_applied = true;
