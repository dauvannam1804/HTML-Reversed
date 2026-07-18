#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import shutil
import json
from datasets import load_dataset
from playwright.sync_api import sync_playwright
import threading
from concurrent.futures import ThreadPoolExecutor

class ThreadSafeIter:
    def __init__(self, it):
        self.it = iter(it)
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def __next__(self):
        with self.lock:
            return next(self.it)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Stream HuggingFaceFW/fineweb-2 Vietnamese subset, filter by year, print to PDF, and extract layouts."
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=5,
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
        "--no-extract-images",
        action="store_false",
        dest="extract_images",
        help="Disable extracting and saving individual images found in the PDF."
    )
    parser.add_argument(
        "--no-scroll",
        action="store_true",
        help="Skip scrolling the page to load lazy-loaded elements (faster crawl)."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of concurrent worker threads (default: 2)."
    )
    parser.add_argument(
        "--scroll-step",
        type=int,
        default=1200,
        help="Scroll jump step in pixels (default: 1200)."
    )
    parser.add_argument(
        "--scroll-delay",
        type=int,
        default=30,
        help="Delay in milliseconds between scroll steps (default: 30)."
    )
    return parser.parse_args()

def scroll_to_bottom(page, step=1200, delay=30):
    try:
        page.evaluate(f"""
            async () => {{
                const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                const scrollHeight = document.body.scrollHeight;
                for (let i = 0; i < scrollHeight; i += {step}) {{
                    window.scrollTo(0, i);
                    await delay({delay});
                }}
                window.scrollTo(0, scrollHeight);
                await delay(500);
                window.scrollTo(0, 0);
                await delay(500);
            }}
        """)
    except Exception as e:
        print(f"  [Warning] Scrolling failed: {e}")

def worker_crawl(worker_id, thread_safe_dataset, args, lock, success_counter_ref, total_inspected_ref):
    print(f"Worker {worker_id} started.")
    
    with sync_playwright() as p:
        try:
            try:
                browser = p.chromium.launch(headless=True, channel="chrome")
            except Exception:
                browser = p.chromium.launch(headless=True)
            
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            context.set_default_timeout(30000)
        except Exception as e:
            print(f"Worker {worker_id} [Error] Failed to initialize Playwright: {e}")
            return

        while True:
            with lock:
                if success_counter_ref[0] >= args.num_samples:
                    break

            try:
                item = next(thread_safe_dataset)
            except StopIteration:
                break

            with lock:
                total_inspected_ref[0] += 1

            url = item.get("url")
            date_str = item.get("date")
            doc_id = item.get("id")

            if not url or not date_str:
                continue

            try:
                year = int(date_str[:4])
            except ValueError:
                continue

            if not (args.start_year <= year <= args.end_year):
                continue

            with lock:
                current_target_idx = success_counter_ref[0]
            
            print(f"\n[Worker {worker_id}][Match {current_target_idx + 1}] Found matching page (Year: {year}):")
            print(f"  ID : {doc_id}")
            print(f"  URL: {url}")

            temp_output_dir = os.path.join(args.output, f"temp_{doc_id}")
            if os.path.exists(temp_output_dir):
                shutil.rmtree(temp_output_dir)
            os.makedirs(temp_output_dir, exist_ok=True)

            target_pdf_path = os.path.join(temp_output_dir, "document.pdf")
            page = context.new_page()
            render_success = False

            try:
                print(f"  [Worker {worker_id}] Navigating to URL...")
                page.goto(url, wait_until="load", timeout=30000)
                
                if not args.no_scroll:
                    page.wait_for_timeout(3000)
                    page.emulate_media(media="screen")
                    print(f"  [Worker {worker_id}] Scrolling to trigger lazy-loaded content (step={args.scroll_step}, delay={args.scroll_delay})...")
                    scroll_to_bottom(page, args.scroll_step, args.scroll_delay)
                else:
                    page.emulate_media(media="screen")

                print(f"  [Worker {worker_id}] Printing page to PDF...")
                page.pdf(
                    path=target_pdf_path,
                    format="A4",
                    print_background=True,
                    margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"}
                )

                print(f"  [Worker {worker_id}] Saving page HTML source...")
                html_content = page.content()
                target_html_path = os.path.join(temp_output_dir, "source.html")
                with open(target_html_path, "w", encoding="utf-8") as f_html:
                    f_html.write(html_content)

                render_success = True
            except Exception as e:
                print(f"  [Worker {worker_id}][Warning] Failed to render webpage: {e}")
            finally:
                page.close()

            if not render_success:
                if os.path.exists(temp_output_dir):
                    shutil.rmtree(temp_output_dir)
                continue

            print(f"  [Worker {worker_id}] Running layout extraction pipeline...")
            cmd = [
                sys.executable, "extract_pdf_layout.py",
                "--pdf", target_pdf_path,
                "--output", temp_output_dir,
                "--granularity", args.granularity,
                "--dpi", str(args.dpi)
            ]
            if args.normalize:
                cmd.append("--normalize")
            if not args.extract_images:
                cmd.append("--no-extract-images")

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                with lock:
                    if success_counter_ref[0] < args.num_samples:
                        final_idx = success_counter_ref[0]
                        final_output_dir = os.path.join(args.output, f"doc_{final_idx:03d}")
                        
                        with open(os.path.join(temp_output_dir, "url.txt"), "w", encoding="utf-8") as f_url:
                            f_url.write(url + "\n")
                        
                        if os.path.exists(final_output_dir):
                            shutil.rmtree(final_output_dir)
                        os.rename(temp_output_dir, final_output_dir)
                        
                        print(f"  [Worker {worker_id}][Success] Layout extracted for doc_{final_idx:03d}")
                        success_counter_ref[0] += 1
                    else:
                        if os.path.exists(temp_output_dir):
                            shutil.rmtree(temp_output_dir)
            else:
                print(f"  [Worker {worker_id}][Error] Layout extraction failed for {target_pdf_path}:")
                print(f"  {result.stderr}")
                if os.path.exists(temp_output_dir):
                    shutil.rmtree(temp_output_dir)

        browser.close()
    print(f"Worker {worker_id} finished.")

def main():
    args = parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    print("----------------------------------------------------------------")
    print("FineWeb-2 Vietnamese PDF Crawler & Layout Extraction Pipeline")
    print(f"Target Samples: {args.num_samples}")
    print(f"Filter Years  : {args.start_year} -> {args.end_year}")
    print(f"Output Directory: {args.output}")
    print(f"Workers       : {args.workers}")
    print(f"Scroll Enabled: {not args.no_scroll}")
    if not args.no_scroll:
        print(f"Scroll Step   : {args.scroll_step} px")
        print(f"Scroll Delay  : {args.scroll_delay} ms")
    print("----------------------------------------------------------------\n")
    cache_path = "fineweb_urls_cache.json"
    cached_items = []
    
    if os.path.exists(cache_path):
        print(f"Loading URLs from local cache: '{cache_path}'...")
        try:
            with open(cache_path, "r", encoding="utf-8") as f_cache:
                cached_items = json.load(f_cache)
            print(f"Successfully loaded {len(cached_items)} URLs from cache.")
        except Exception as e:
            print(f"Warning: Failed to load cache: {e}. Rebuilding cache...")
            cached_items = []

    # If cache doesn't exist or has fewer samples than requested, load more from HF
    if len(cached_items) < args.num_samples:
        # If cache is totally empty, we want to pre-populate it with at least 100 samples
        min_target_size = max(100, args.num_samples)
        additional_needed = min_target_size - len(cached_items)
        
        if len(cached_items) == 0:
            print("Cache is empty. Streaming from HuggingFace to pre-filter matching URLs...")
            print(f"This is a one-time operation. Populating cache with {min_target_size} URLs (no browsers are launched)...")
        else:
            print(f"Cache has only {len(cached_items)} URLs, but you requested {args.num_samples} samples.")
            print(f"Streaming from HuggingFace to fetch {additional_needed} more matching URLs...")

        try:
            dataset = load_dataset(
                "HuggingFaceFW/fineweb-2",
                name="vie_Latn",
                split="train",
                streaming=True
            )
            
            existing_ids = {item["id"] for item in cached_items}
            count = 0
            for item in dataset:
                doc_id = item.get("id")
                if doc_id in existing_ids:
                    continue
                url = item.get("url")
                date_str = item.get("date")
                if not url or not date_str:
                    continue
                try:
                    year = int(date_str[:4])
                except ValueError:
                    continue
                if args.start_year <= year <= args.end_year:
                    cached_items.append({
                        "id": doc_id,
                        "url": url,
                        "date": date_str
                    })
                    count += 1
                    if count >= additional_needed:
                        break
            
            with open(cache_path, "w", encoding="utf-8") as f_cache:
                json.dump(cached_items, f_cache, indent=2, ensure_ascii=False)
            print(f"Successfully updated cache with {len(cached_items)} matching URLs in '{cache_path}'.\n")
            
        except Exception as e:
            print(f"Error loading/processing dataset from HuggingFace: {e}")
            if not cached_items:
                return
            else:
                print("Will proceed to crawl using the current cached URLs.")
            
    thread_safe_dataset = ThreadSafeIter(cached_items)
    success_counter_ref = [0]
    total_inspected_ref = [0]
    lock = threading.Lock()
    
    print(f"\nStreaming dataset and processing webpages using {args.workers} workers...")
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for i in range(args.workers):
            futures.append(
                executor.submit(
                    worker_crawl,
                    i,
                    thread_safe_dataset,
                    args,
                    lock,
                    success_counter_ref,
                    total_inspected_ref
                )
            )
        for fut in futures:
            fut.result()
            
    print("\n================================================================")
    print(f"Process finished! Successfully gathered {success_counter_ref[0]} samples.")
    print(f"Total inspected documents: {total_inspected_ref[0]}")
    print(f"Outputs saved in: {args.output}")
    print("================================================================")
    # Force exit to prevent Playwright background threads/processes from hanging on cleanup
    os._exit(0)

if __name__ == "__main__":
    main()
