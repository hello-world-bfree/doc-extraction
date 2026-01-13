import argparse
import sys
from pathlib import Path

from ..builders.epub_builder import EpubBuilder
from ..scrapers.configs import ScraperConfig
from ..scrapers.image_scraper import AutoImageScraper, DynamicImageScraper, StaticImageScraper
from ..storage.s3_uploader import S3Config, S3Uploader


def main():
    parser = argparse.ArgumentParser(
        description="Extract images from websites and optionally build EPUB or upload to S3"
    )

    parser.add_argument(
        "url",
        help="URL of the website to scrape images from"
    )

    parser.add_argument(
        "--scraper-type",
        choices=["auto", "static", "dynamic"],
        default="auto",
        help="Type of scraper to use (default: auto)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output EPUB file path (implies --build-epub)"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./images"),
        help="Directory to save scraped images (default: ./images)"
    )

    parser.add_argument(
        "--title",
        default="Image Gallery",
        help="EPUB title (default: Image Gallery)"
    )

    parser.add_argument(
        "--author",
        default="Web Scraper",
        help="EPUB author (default: Web Scraper)"
    )

    parser.add_argument(
        "--min-image-size",
        type=int,
        default=10,
        help="Minimum image size in KB (default: 10)"
    )

    parser.add_argument(
        "--max-images",
        type=int,
        help="Maximum number of images to extract"
    )

    parser.add_argument(
        "--no-epub",
        action="store_true",
        help="Skip EPUB generation, just download images"
    )

    parser.add_argument(
        "--include-svg",
        action="store_true",
        help="Include SVG images"
    )

    parser.add_argument(
        "--no-convert-webp",
        action="store_true",
        help="Don't convert WebP images to PNG"
    )

    parser.add_argument(
        "--min-width",
        type=int,
        default=200,
        help="Minimum image width in pixels (default: 200)"
    )

    parser.add_argument(
        "--min-height",
        type=int,
        default=200,
        help="Minimum image height in pixels (default: 200)"
    )

    parser.add_argument(
        "--no-quality-check",
        action="store_true",
        help="Disable quality filtering (keep all images regardless of size)"
    )

    parser.add_argument(
        "--upload-s3",
        action="store_true",
        help="Upload images to S3 (requires --s3-bucket)"
    )

    parser.add_argument(
        "--s3-bucket",
        help="S3 bucket name (required if --upload-s3)"
    )

    parser.add_argument(
        "--s3-prefix",
        default="images/",
        help="S3 key prefix (default: images/)"
    )

    parser.add_argument(
        "--s3-region",
        default="us-east-1",
        help="S3 region (default: us-east-1)"
    )

    parser.add_argument(
        "--s3-public",
        action="store_true",
        help="Make S3 uploads public (default: private)"
    )

    args = parser.parse_args()

    if args.upload_s3 and not args.s3_bucket:
        print("Error: --s3-bucket is required when using --upload-s3")
        sys.exit(1)

    config = ScraperConfig(
        min_image_size_kb=args.min_image_size,
        max_images=args.max_images,
        include_svg=args.include_svg,
        convert_webp=not args.no_convert_webp,
        output_dir=args.output_dir,
        min_width=args.min_width,
        min_height=args.min_height,
        quality_check=not args.no_quality_check,
    )

    print(f"Scraping images from: {args.url}")
    print(f"Scraper type: {args.scraper_type}")
    print(f"Output directory: {config.output_dir}")

    if args.scraper_type == "auto":
        scraper = AutoImageScraper(args.url, config)
    elif args.scraper_type == "static":
        scraper = StaticImageScraper(args.url, config)
    elif args.scraper_type == "dynamic":
        scraper = DynamicImageScraper(args.url, config)

    images = scraper.extract_images()

    if not images:
        print("No images found!")
        sys.exit(1)

    print(f"\nSuccessfully extracted {len(images)} images")

    if args.upload_s3:
        print(f"\nUploading images to S3 bucket: {args.s3_bucket}")
        s3_config = S3Config(
            bucket_name=args.s3_bucket,
            prefix=args.s3_prefix,
            region=args.s3_region,
            private=not args.s3_public,
        )
        try:
            uploader = S3Uploader(s3_config)
            image_paths = [img.local_path for img in images]
            results = uploader.upload_images(image_paths)
            print(f"Uploaded {len(results)} images to S3")
        except ImportError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Failed to upload images to S3: {e}")
            sys.exit(1)

    if args.output or not args.no_epub:
        output_path = args.output or Path("./output.epub")

        print(f"\nBuilding EPUB: {output_path}")

        try:
            builder = EpubBuilder(title=args.title, author=args.author)

            if images:
                builder.add_cover_image(images[0].local_path)

            builder.add_images(images)

            builder.save(output_path)

            print(f"\n✓ Success!")
            print(f"  - Images extracted: {len(images)}")
            print(f"  - EPUB created: {output_path}")
            if args.upload_s3:
                print(f"  - S3 bucket: {args.s3_bucket}")

        except Exception as e:
            print(f"Error building EPUB: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print(f"\n✓ Images saved to: {config.output_dir}")


if __name__ == "__main__":
    main()
