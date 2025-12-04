# Last Updated: 2025-12-03

## Purpose
Image validation, format detection, and conversion to data URLs for vLLM multimodal API.

## Key Files
- `processor.py` - ImageProcessor validates images, detects format, enforces size limits
- `converter.py` - ImageConverter converts base64 to data URL format (data:image/jpeg;base64,...)

## Dependencies/Relations
Used by `api/v1/chat.py` for image input processing. Depends on PIL/Pillow, `config.py` settings.
