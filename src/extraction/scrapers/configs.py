from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ScraperConfig:
    min_image_size_kb: int = 10
    max_images: Optional[int] = None
    include_svg: bool = False
    convert_webp: bool = True
    output_dir: Path = field(default_factory=lambda: Path("./images"))
    timeout: int = 30

    min_width: int = 200
    min_height: int = 200
    quality_check: bool = True

    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    lazy_load_attributes: list[str] = field(default_factory=lambda: [
        "data-src",
        "data-lazy",
        "data-lazy-src",
        "data-original",
        "data-srcset",
    ])

    ignore_patterns: list[str] = field(default_factory=lambda: [
        "favicon",
        "icon",
        "avatar",
        "thumb",
        "sprite",
        "placeholder",
        "loading",
        "1x1",
        "spinner",
    ])
