#!/usr/bin/env python3
"""
html_to_synthetic.py

A utility template script to render local HTML files using Playwright,
extract DOM bounding boxes of target elements (text, headings, buttons, images),
take page screenshots, and compile them into a VLM synthetic training dataset.

Usage:
  1. Install Playwright:
     pip install playwright
     playwright install chromium
  2. Run the script:
     python3 html_to_synthetic.py --html index.html --output html_extracted_dataset
"""

import os
import argparse
import json
from playwright.sync_api import sync_playwright

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert HTML templates into OCR/VLM synthetic training datasets with Playwright."
    )
    parser.add_argument(
        "--html",
        type=str,
        required=True,
        help="Path to the input HTML file (can be a local path or a URL)."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="html_dataset",
        help="Output folder for saving screenshots and annotations."
    )
    parser.add_argument(
        "--selectors",
        type=str,
        default="p, h1, h2, h3, h4, h5, h6, img, button, a, span",
        help="Comma-separated CSS selectors to extract bounding boxes for."
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Viewport width of the browser (default: 1280)."
    )
    parser.add_argument(
        "--height",
        type=int,
        default=800,
        help="Initial viewport height of the browser (default: 800)."
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize coordinates to a [0, 1000] scale."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Resolve target URL / local file path
    target = args.html
    if not target.startswith("http://") and not target.startswith("https://"):
        target = os.path.abspath(target)
        if not os.path.exists(target):
            print(f"Error: Local file '{target}' does not exist.")
            return
        target = f"file://{target}"

    os.makedirs(args.output, exist_ok=True)
    
    selectors_list = [s.strip() for s in args.selectors.split(",")]
    
    print(f"Launching headless browser to render: {target}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set viewport
        context = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1
        )
        page = context.new_page()
        
        # Load page and wait for idle network
        page.goto(target, wait_until="networkidle")
        
        # Get actual document dimensions to capture the whole scrollable page
        dimensions = page.evaluate("""() => {
            return {
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight
            }
        }""")
        
        doc_w = dimensions["width"]
        doc_h = dimensions["height"]
        print(f"Rendered Page size: {doc_w}x{doc_h} pixels")
        
        # Resize viewport to capture full page without scrolling bounds
        page.set_viewport_size({"width": doc_w, "height": doc_h})
        
        # Screenshot full page
        screenshot_filename = "page.png"
        screenshot_path = os.path.join(args.output, screenshot_filename)
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Saved full-page screenshot to '{screenshot_path}'")
        
        # Extract element positions using JS
        # We query all elements matching selectors and return their tags, innerText, and bounding rects
        js_extractor = """
        (selectors) => {
            const elements = [];
            selectors.forEach(sel => {
                const nodes = document.querySelectorAll(sel);
                nodes.forEach(node => {
                    // Check if element is visible and has physical size
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    
                    if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                        // Extract text cleanly, filter out nested children text if needed
                        // For generic container elements (like A/SPAN), take their text.
                        let text = node.innerText || "";
                        if (node.tagName.toLowerCase() === 'img') {
                            text = node.getAttribute('alt') || node.getAttribute('src') || "[image]";
                        }
                        
                        elements.push({
                            tag: node.tagName.toLowerCase(),
                            text: text.trim(),
                            bbox: [rect.left, rect.top, rect.right, rect.bottom]
                        });
                    }
                });
            });
            return elements;
        }
        """
        
        raw_elements = page.evaluate(js_extractor, selectors_list)
        print(f"Extracted {len(raw_elements)} matching elements from DOM.")
        
        # Process bounding boxes
        annotations = []
        for elem in raw_elements:
            x0, y0, x1, y1 = elem["bbox"]
            
            # Format bounding boxes
            if args.normalize:
                # Scale to [0, 1000] based on full document dimensions
                nx0 = max(0, min(1000, int((x0 / doc_w) * 1000)))
                ny0 = max(0, min(1000, int((y0 / doc_h) * 1000)))
                nx1 = max(0, min(1000, int((x1 / doc_w) * 1000)))
                ny1 = max(0, min(1000, int((y1 / doc_h) * 1000)))
                bbox_formatted = [nx0, ny0, nx1, ny1]
            else:
                bbox_formatted = [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]
                
            annotations.append({
                "type": "image" if elem["tag"] == "img" else "text",
                "tag": elem["tag"],
                "text": elem["text"],
                "bbox": bbox_formatted
            })
            
        # Write output metadata JSON
        metadata_filename = "layout.json"
        metadata_path = os.path.join(args.output, metadata_filename)
        
        layout_metadata = {
            "source": target,
            "dimensions": {
                "pixels": [doc_w, doc_h]
            },
            "coordinate_system": "normalized_1000" if args.normalize else "pixel_coordinates",
            "annotations": annotations
        }
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(layout_metadata, f, indent=2, ensure_ascii=False)
        print(f"Saved layout annotations to '{metadata_path}'")
        
        browser.close()
        
    print("Done generating synthetic data from HTML!")

if __name__ == "__main__":
    main()
