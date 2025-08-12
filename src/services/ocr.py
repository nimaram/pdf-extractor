import ocrmypdf
import pdfplumber
import json
import re
from pathlib import Path
from typing import Any, Optional
import logging

logging.getLogger("ocrmypdf").setLevel(logging.INFO)


class PDFExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Create output directory for processed files
        self.output_dir = self.pdf_path.parent / "processed"
        self.output_dir.mkdir(exist_ok=True)

    def extract_text_with_ocr(
        self,
        force_ocr: bool = False,
        use_advanced: bool = False,
        tesseract_path: str = None,
    ) -> Optional[str]:
        """
        Extract text using OCRmyPDF's optimized pipeline.
        Returns the path to the OCR'd PDF if successful.

        Args:
            force_ocr: Force OCR even if text exists
            use_advanced: Try to use advanced features (clean, remove_background) if available
            tesseract_path: Path to tesseract executable (optional)
        """
        output_path = self.output_dir / f"{self.pdf_path.stem}_ocr.pdf"

        try:
            if tesseract_path:
                import pytesseract

                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                print(f"Using Tesseract at: {tesseract_path}")

            # Basic OCR options (Windows-compatible)
            ocr_options = {
                "input_file": str(self.pdf_path),
                "output_file": str(output_path),
                "skip_text": False,  # Keep original text if exists
                "force_ocr": force_ocr,  # Force OCR even if text exists
                "optimize": 1,  # Basic optimization
                "output_type": "pdfa",  # PDF/A format for better compatibility
                "deskew": True,  # Fix skewed pages
                "language": ["eng"],  # English language
                "tesseract_config": "--psm 1",  # Page segmentation mode
            }

            # Try to add advanced features if requested and available
            if use_advanced:
                try:
                    # Test if unpaper is available
                    import subprocess

                    result = subprocess.run(
                        ["unpaper", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        ocr_options.update(
                            {
                                "clean": True,
                                "remove_background": True,
                            }
                        )
                        print("Advanced OCR features enabled (unpaper found)")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    print("Advanced OCR features disabled (unpaper not available)")

            result = ocrmypdf.ocr(**ocr_options)
            print(f"OCR completed successfully: {output_path}")
            return str(output_path)

        except ocrmypdf.exceptions.PriorOcrFoundError:
            print("PDF already has text layer - no OCR needed")
            return str(self.pdf_path)
        except Exception as e:
            print(f"OCR failed: {e}")
            return None

    def extract_tables(
        self,
        use_ocr: bool = True,
        use_advanced: bool = False,
        tesseract_path: str = None,
    ) -> list[dict[str, Any]]:
        """Extract tables using pdfplumber (works better with OCR'd text)"""
        # Use original PDF if OCR is disabled, otherwise try OCR
        if use_ocr:
            pdf_to_use = self.extract_text_with_ocr(
                force_ocr=True, use_advanced=use_advanced, tesseract_path=tesseract_path
            )
            if not pdf_to_use:
                return []
        else:
            pdf_to_use = str(self.pdf_path)

        tables = []
        try:
            with pdfplumber.open(pdf_to_use) as doc:
                for page_num, page in enumerate(doc.pages):
                    page_tables = page.extract_tables()

                    for table_idx, table in enumerate(page_tables):
                        if table and len(table) > 1:
                            table_data = {
                                "headers": table[0] if table[0] else [],
                                "rows": table[1:] if len(table) > 1 else [],
                                "table_title": f"Table on page {page_num + 1}",
                                "row_count": len(table),
                                "column_count": len(table[0]) if table[0] else 0,
                                "extraction_metadata": {
                                    "confidence_score": 0.9,
                                    "extraction_method": "pdfplumber",
                                    "ocr_used": use_ocr,
                                    "page_number": page_num + 1,
                                    "table_index": table_idx,
                                },
                            }
                            tables.append(table_data)
        except Exception as e:
            print(f"Table extraction failed: {e}")

        return tables

    def extract_statistics(
        self,
        use_ocr: bool = True,
        use_advanced: bool = False,
        tesseract_path: str = None,
    ) -> list[dict[str, Any]]:
        """Extract statistics from OCR'd text"""
        # Use original PDF if OCR is disabled, otherwise try OCR
        if use_ocr:
            pdf_to_use = self.extract_text_with_ocr(
                force_ocr=True, use_advanced=use_advanced, tesseract_path=tesseract_path
            )
            if not pdf_to_use:
                return []
        else:
            pdf_to_use = str(self.pdf_path)

        statistics = []
        try:
            with pdfplumber.open(pdf_to_use) as doc:
                for page_num, page in enumerate(doc.pages):
                    text = page.extract_text()
                    if text:
                        # Extract percentages
                        percentage_pattern = r"(\d+(?:\.\d+)?)\s*%"
                        percentages = re.findall(percentage_pattern, text)

                        for percent in percentages:
                            stat_data = {
                                "statistic_type": "percentage",
                                "statistic_value": float(percent),
                                "statistic_unit": "%",
                                "statistic_label": "Extracted percentage",
                                "context_text": (
                                    text[:200] + "..." if len(text) > 200 else text
                                ),
                                "extraction_metadata": {
                                    "confidence_score": 0.8,
                                    "extraction_method": "regex_pattern",
                                    "ocr_used": use_ocr,
                                    "page_number": page_num + 1,
                                },
                            }
                            statistics.append(stat_data)

                        # Extract large numbers
                        number_pattern = r"\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\b"
                        numbers = re.findall(number_pattern, text)

                        for num_str in numbers:
                            try:
                                num_value = float(num_str.replace(",", ""))
                                if num_value > 100:
                                    stat_data = {
                                        "statistic_type": "number",
                                        "statistic_value": num_value,
                                        "statistic_unit": None,
                                        "statistic_label": "Extracted number",
                                        "context_text": (
                                            text[:200] + "..."
                                            if len(text) > 200
                                            else text
                                        ),
                                        "extraction_metadata": {
                                            "confidence_score": 0.7,
                                            "extraction_method": "regex_pattern",
                                            "ocr_used": use_ocr,
                                            "page_number": page_num + 1,
                                        },
                                    }
                                    statistics.append(stat_data)
                            except ValueError:
                                continue
        except Exception as e:
            print(f"Statistics extraction failed: {e}")

        return statistics

    def extract_all(
        self,
        use_ocr: bool = True,
        use_advanced: bool = False,
        tesseract_path: str = None,
    ) -> dict[str, Any]:
        """Extract all data types with optional OCR"""
        return {
            "tables": self.extract_tables(
                use_ocr=use_ocr,
                use_advanced=use_advanced,
                tesseract_path=tesseract_path,
            ),
            "statistics": self.extract_statistics(
                use_ocr=use_ocr,
                use_advanced=use_advanced,
                tesseract_path=tesseract_path,
            ),
            "ocr_used": use_ocr,
            "advanced_features": use_advanced,
            "input_pdf": str(self.pdf_path),
            "output_directory": str(self.output_dir),
        }


# CLI entry point for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract data from PDF using OCRmyPDF")
    parser.add_argument("pdf", help="Path to input PDF")
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR processing")
    parser.add_argument(
        "--advanced",
        action="store_true",
        help="Try to use advanced OCR features if available",
    )
    parser.add_argument("--tesseract", help="Path to tesseract.exe")
    parser.add_argument("-o", "--output", help="Output JSON file path")

    args = parser.parse_args()

    try:
        extractor = PDFExtractor(args.pdf)
        data = extractor.extract_all(
            use_ocr=not args.no_ocr,
            use_advanced=args.advanced,
            tesseract_path=args.tesseract,
        )

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Results saved to: {args.output}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}")
