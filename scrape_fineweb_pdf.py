#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import shutil
from datasets import load_dataset
from playwright.sync_api import sync_playwright

def parse_args():
    parser = argparse.ArgumentParser(
        description="Stream HuggingFaceFW/fineweb-2 Vietnamese subset, filter by year, print to PDF, and extract layouts."
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=20,
        help="Number of successfully processed webpages to collect."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output_dataset/fineweb_samples",
        help="Output directory to save the structured dataset."
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2021,
        help="Start year of crawled date to filter (inclusive)."
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2026,
        help="End year of crawled date to filter (inclusive)."
    )
    # Passed to extract_pdf_layout.py
    parser.add_argument(
        "--granularity",
        type=str,
        choices=["word", "line", "block"],
        default="word",
        help="Granularity of extracted text bounding boxes (passed to extraction script)."
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="DPI for rendering page images in layout extraction."
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize bounding boxes to a [0, 1000] scale in layout extraction."
    )
    parser.add_argument(
        "--extract-images",
        action="store_true",
        help="Extract and save individual images found in the PDF."
    )
    return parser.parse_args()

def scroll_to_bottom(page):
    try:
        page.evaluate("""
            async () => {
                const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                const scrollHeight = document.body.scrollHeight;
                for (let i = 0; i < scrollHeight; i += 400) {
                    window.scrollTo(0, i);
                    await delay(100);
                }
                window.scrollTo(0, scrollHeight);
                await delay(500);
                window.scrollTo(0, 0);
                await delay(500);
            }
        """)
    except Exception as e:
        print(f"  [Warning] Scrolling failed: {e}")

def main():
    args = parse_args()
    
    # 1. Setup directories
    os.makedirs(args.output, exist_ok=True)
    
    print("----------------------------------------------------------------")
    print("FineWeb-2 Vietnamese PDF Crawler & Layout Extraction Pipeline")
    print(f"Target Samples: {args.num_samples}")
    print(f"Filter Years  : {args.start_year} -> {args.end_year}")
    print(f"Output Directory: {args.output}")
    print("----------------------------------------------------------------\n")
    
    # 2. Start Playwright
    print("Initializing Playwright...")
    with sync_playwright() as p:
        # Try to launch using system Chrome to avoid dependency issues
        try:
            print("Attempting to launch Playwright using system Chrome...")
            browser = p.chromium.launch(headless=True, channel="chrome")
        except Exception as e:
            print(f"Could not launch with system Chrome: {e}")
            print("Falling back to default Playwright Chromium browser...")
            browser = p.chromium.launch(headless=True)
            
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.set_default_timeout(30000)  # 30 seconds timeout
        
        # 3. Stream HuggingFaceFW/fineweb-2 (subset vie_Latn)
        print("Loading dataset 'HuggingFaceFW/fineweb-2' (subset: vie_Latn, streaming: True)...")
        try:
            dataset = load_dataset(
                "HuggingFaceFW/fineweb-2",
                name="vie_Latn",
                split="train",
                streaming=True
            )
        except Exception as e:
            print(f"Error loading dataset: {e}")
            browser.close()
            return
            
        success_count = 0
        total_inspected = 0
        
        print("\nStreaming dataset and processing webpages...")
        for item in dataset:
            total_inspected += 1
            url = item.get("url")
            date_str = item.get("date")
            doc_id = item.get("id")
            
            if not url or not date_str:
                continue
                
            # Filter by crawl/page date year
            try:
                year = int(date_str[:4])
            except ValueError:
                continue
                
            if not (args.start_year <= year <= args.end_year):
                continue
                
            print(f"\n[Match {success_count + 1}] Found matching page (Year: {year}):")
            print(f"  ID : {doc_id}")
            print(f"  URL: {url}")
            
            # 4. Create target directory first
            doc_output_dir = os.path.join(args.output, f"doc_{success_count:03d}")
            os.makedirs(doc_output_dir, exist_ok=True)
            target_pdf_path = os.path.join(doc_output_dir, "document.pdf")
            
            # 5. Try rendering the webpage to PDF using Playwright directly into the folder
            page = context.new_page()
            render_success = False
            try:
                print(f"  Navigating to URL...")
                page.goto(url, wait_until="load", timeout=30000)
                # Wait a bit for dynamic content/scripts to load fully
                page.wait_for_timeout(3000)
                
                # Emulate screen media to prevent @media print stylesheet hiding elements
                page.emulate_media(media="screen")
                
                # Scroll to bottom to trigger lazy loading of images/content
                print(f"  Scrolling to trigger lazy-loaded content...")
                scroll_to_bottom(page)
                
                print(f"  Printing page to PDF...")
                page.pdf(
                    path=target_pdf_path,
                    format="A4",
                    print_background=True,
                    margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"}
                )
                render_success = True
            except Exception as e:
                print(f"  [Warning] Failed to render webpage: {e}")
            finally:
                page.close()
                
            if not render_success:
                # Clean up directory since rendering failed
                if os.path.exists(doc_output_dir):
                    shutil.rmtree(doc_output_dir)
                continue
                
            # 6. Run the layout extraction pipeline on the printed PDF
            print(f"  Running layout extraction pipeline...")
            cmd = [
                sys.executable, "extract_pdf_layout.py",
                "--pdf", target_pdf_path,
                "--output", doc_output_dir,
                "--granularity", args.granularity,
                "--dpi", str(args.dpi)
            ]
            if args.normalize:
                cmd.append("--normalize")
            if args.extract_images:
                cmd.append("--extract-images")
                
            # Run extraction as subprocess
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"  [Success] Layout extracted for doc_{success_count:03d}")
                # Save the source URL to a text file
                with open(os.path.join(doc_output_dir, "url.txt"), "w", encoding="utf-8") as f_url:
                    f_url.write(url + "\n")
                success_count += 1
            else:
                print(f"  [Error] Layout extraction failed for {target_pdf_path}:")
                print(f"  {result.stderr}")
                # Remove the directory since extraction failed
                shutil.rmtree(doc_output_dir)
                
            if success_count >= args.num_samples:
                break
                
        print("\n================================================================")
        print(f"Process finished! Successfully gathered {success_count} samples.")
        print(f"Total inspected documents: {total_inspected}")
        print(f"Outputs saved in: {args.output}")
        print("================================================================")
        
        browser.close()

if __name__ == "__main__":
    main()
