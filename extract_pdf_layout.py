#!/usr/bin/env python3
import os
import argparse
import json
import fitz  # PyMuPDF
from PIL import Image, ImageDraw

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract high-quality layout and OCR data from PDF files for VLM synthetic training data."
    )
    parser.add_argument(
        "--pdf",
        type=str,
        required=True,
        help="Path to the input PDF file (e.g. pharmarcity.pdf)."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="extracted_dataset",
        help="Output directory to save images and annotations."
    )
    parser.add_argument(
        "--granularity",
        type=str,
        choices=["word", "line", "block"],
        default="word",
        help="Granularity of extracted text bounding boxes (default: word)."
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="DPI for rendering page images. Higher DPI means higher resolution page screenshots (default: 150)."
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="If set, normalizes bounding boxes to a [0, 1000] scale instead of absolute pixel coordinates."
    )
    parser.add_argument(
        "--extract-images",
        action="store_true",
        help="If set, extracts and saves individual images found in the PDF (both raw embedded bytes and visual crops)."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not os.path.exists(args.pdf):
        print(f"Error: PDF file '{args.pdf}' not found.")
        return

    os.makedirs(args.output, exist_ok=True)
    if args.extract_images:
        images_output_dir = os.path.join(args.output, "extracted_images")
        os.makedirs(images_output_dir, exist_ok=True)

    print(f"Opening PDF: {args.pdf}")
    doc = fitz.open(args.pdf)
    print(f"Total pages to process: {len(doc)}")
    
    # Calculate scale factor from DPI (PDF default unit is point = 1/72 inch)
    zoom = args.dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_width = page.rect.width
        page_height = page.rect.height
        
        # 1. Render the clean page image
        pix = page.get_pixmap(matrix=matrix)
        img_w, img_h = pix.width, pix.height
        
        # Save page image
        img_filename = f"page_{page_idx:03d}.png"
        img_path = os.path.join(args.output, img_filename)
        pix.save(img_path)
        
        # 2. Extract layouts
        extracted_elements = []
        
        # Get PyMuPDF dictionary representation of the page
        text_dict = page.get_text("dict")
        
        # We can extract text items based on requested granularity
        if args.granularity == "word":
            # get_text("words") is more robust for single-word coordinate matching
            words = page.get_text("words")
            for w in words:
                x0, y0, x1, y1, text_str, block_no, line_no, word_no = w
                extracted_elements.append({
                    "type": "text",
                    "text": text_str,
                    "bbox_points": [x0, y0, x1, y1],
                    "metadata": {
                        "block_no": block_no,
                        "line_no": line_no,
                        "word_no": word_no
                    }
                })
        else:
            # Parse dict blocks for line or block granularity
            for block in text_dict.get("blocks", []):
                if block["type"] == 0:  # Text block
                    if args.granularity == "block":
                        # Concatenate text from all lines
                        lines_text = []
                        for line in block.get("lines", []):
                            line_text = "".join([span["text"] for span in line.get("spans", [])])
                            lines_text.append(line_text)
                        block_text = "\n".join(lines_text)
                        
                        extracted_elements.append({
                            "type": "text",
                            "text": block_text,
                            "bbox_points": list(block["bbox"]),
                            "metadata": {
                                "block_no": block.get("number", -1)
                            }
                        })
                    elif args.granularity == "line":
                        for line in block.get("lines", []):
                            line_text = "".join([span["text"] for span in line.get("spans", [])])
                            extracted_elements.append({
                                "type": "text",
                                "text": line_text,
                                "bbox_points": list(line["bbox"]),
                                "metadata": {
                                    "block_no": block.get("number", -1)
                                }
                            })
        
        # Extract image blocks (type == 1 in text_dict['blocks'])
        for block in text_dict.get("blocks", []):
            if block["type"] == 1:
                block_no = block.get("number", -1)
                ext = block.get("ext", "png")
                
                # Image block metadata
                img_metadata = {
                    "block_no": block_no,
                    "width": block.get("width"),
                    "height": block.get("height"),
                    "ext": ext
                }
                
                # If extract-images is enabled, save image files
                if args.extract_images:
                    raw_name = f"page_{page_idx:03d}_raw_{block_no}.{ext}"
                    raw_path = os.path.join(images_output_dir, raw_name)
                    
                    # 1. Save raw embedded image bytes
                    raw_bytes = block.get("image")
                    if raw_bytes:
                        with open(raw_path, "wb") as f_img:
                            f_img.write(raw_bytes)
                        img_metadata["image_path_raw"] = os.path.join("extracted_images", raw_name)
                    
                    # 2. Crop visually from rendered image
                    crop_name = f"page_{page_idx:03d}_crop_{block_no}.png"
                    crop_path = os.path.join(images_output_dir, crop_name)
                    
                    # Calculate pixel bounding box for cropping
                    bx0, by0, bx1, by1 = block["bbox"]
                    px0, py0, px1, py1 = bx0 * zoom, by0 * zoom, bx1 * zoom, by1 * zoom
                    # Load page image and crop
                    with Image.open(img_path) as page_img:
                        cropped = page_img.crop((int(px0), int(py0), int(px1), int(py1)))
                        cropped.save(crop_path)
                        img_metadata["image_path_crop"] = os.path.join("extracted_images", crop_name)
                
                extracted_elements.append({
                    "type": "image",
                    "bbox_points": list(block["bbox"]),
                    "metadata": img_metadata
                })
        
        # Helper: convert point coords to desired format
        # [x0, y0, x1, y1]
        def format_bbox(bbox):
            x0, y0, x1, y1 = bbox
            if args.normalize:
                # Normalize to [0, 1000] scale based on page_width and page_height
                nx0 = max(0, min(1000, int((x0 / page_width) * 1000)))
                ny0 = max(0, min(1000, int((y0 / page_height) * 1000)))
                nx1 = max(0, min(1000, int((x1 / page_width) * 1000)))
                ny1 = max(0, min(1000, int((y1 / page_height) * 1000)))
                return [nx0, ny0, nx1, ny1]
            else:
                # Scale to absolute pixel coordinates
                px0 = x0 * zoom
                py0 = y0 * zoom
                px1 = x1 * zoom
                py1 = y1 * zoom
                return [round(px0, 2), round(py0, 2), round(px1, 2), round(py1, 2)]

        # Prepare final JSON list
        annotations = []
        for elem in extracted_elements:
            bbox_formatted = format_bbox(elem["bbox_points"])
            ann = {
                "type": elem["type"],
                "bbox": bbox_formatted,
            }
            if "text" in elem:
                ann["text"] = elem["text"]
            if "metadata" in elem:
                ann["metadata"] = elem["metadata"]
            annotations.append(ann)
            
        # Save annotations JSON
        json_filename = f"layout_{page_idx:03d}.json"
        json_path = os.path.join(args.output, json_filename)
        
        page_metadata = {
            "page_index": page_idx,
            "page_dimensions": {
                "points": [page_width, page_height],
                "pixels": [img_w, img_h]
            },
            "coordinate_system": "normalized_1000" if args.normalize else "pixel_coordinates",
            "annotations": annotations
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(page_metadata, f, indent=2, ensure_ascii=False)

        # 3. Create visual overlay for manual quality check/verification
        # Load the saved image via Pillow
        with Image.open(img_path) as img:
            viz_img = img.copy()
            draw = ImageDraw.Draw(viz_img)
            
            for ann in annotations:
                bbox = ann["bbox"]
                if args.normalize:
                    # Map from [0, 1000] scale back to pixel coordinates for visual drawing
                    x0 = (bbox[0] / 1000.0) * img_w
                    y0 = (bbox[1] / 1000.0) * img_h
                    x1 = (bbox[2] / 1000.0) * img_w
                    y1 = (bbox[3] / 1000.0) * img_h
                else:
                    x0, y0, x1, y1 = bbox
                
                # Colors: green for text, red for image
                color = (46, 204, 113) if ann["type"] == "text" else (231, 76, 60)
                width = 2
                
                draw.rectangle([x0, y0, x1, y1], outline=color, width=width)
                
            viz_filename = f"viz_page_{page_idx:03d}.png"
            viz_path = os.path.join(args.output, viz_filename)
            viz_img.save(viz_path)
            
        print(f"Page {page_idx+1} processed: saved '{img_filename}', '{json_filename}', and layout preview '{viz_filename}'")

    print(f"\nProcessing complete! All files saved in: {args.output}")

if __name__ == "__main__":
    main()
