import pytesseract
from PIL import Image

def ocr_image(image_path: str) -> str:
    """
    OCR for scanned financial documents.
    """
    image = Image.open(image_path)
    return pytesseract.image_to_string(image)
