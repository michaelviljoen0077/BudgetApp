"""
Image processing service for analyzing receipts and bank statements using AI vision.
"""
from typing import Optional, Dict, Any
import io
import base64
from pathlib import Path
from PIL import Image
import pdfplumber


class ImageService:
    """Service for processing images and PDFs using AI vision (no OCR needed)."""
    
    def __init__(self):
        """Initialize image service."""
        pass
    
    def process_document(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Process any document (image or PDF) and prepare it for AI vision.
        
        Args:
            file_bytes: Raw file bytes
            filename: Original filename (to determine type)
            
        Returns:
            Dictionary with:
                - base64_image: Base64 encoded image for AI
                - type: 'image' or 'pdf'
                - pages: Number of pages (for PDFs)
        """
        filename_lower = filename.lower()
        
        # Determine file type
        if filename_lower.endswith('.pdf'):
            # Convert first page of PDF to image
            image_bytes = self._pdf_to_image(file_bytes)
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            result = {
                "base64_image": base64_image,
                "type": "pdf",
                "pages": 1  # For now, just first page
            }
        elif any(filename_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif']):
            # Convert image to base64
            base64_image = base64.b64encode(file_bytes).decode('utf-8')
            
            result = {
                "base64_image": base64_image,
                "type": "image",
                "pages": 1
            }
        else:
            raise ValueError(f"Unsupported file type: {filename}")
        
        return result
    
    def _pdf_to_image(self, pdf_bytes: bytes) -> bytes:
        """Convert first page of PDF to PNG image bytes."""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    raise ValueError("PDF has no pages")
                
                # Get first page as image
                first_page = pdf.pages[0]
                img = first_page.to_image(resolution=150)
                pil_image = img.original
                
                # Convert to PNG bytes
                img_byte_arr = io.BytesIO()
                pil_image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                return img_byte_arr.read()
        except Exception as e:
            raise ValueError(f"Failed to convert PDF to image: {e}")


# Global instance
_image_service = None


def get_image_service() -> ImageService:
    """Get or create the global ImageService instance."""
    global _image_service
    if _image_service is None:
        _image_service = ImageService()
    return _image_service
