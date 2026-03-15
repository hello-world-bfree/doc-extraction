def __getattr__(name):
    _exports = {
        "ImageData", "StaticImageScraper", "DynamicImageScraper",
        "AutoImageScraper", "ScraperConfig",
    }
    if name in _exports:
        if name == "ScraperConfig":
            from .configs import ScraperConfig
            return ScraperConfig
        from .image_scraper import (
            ImageData, StaticImageScraper, DynamicImageScraper, AutoImageScraper,
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ImageData",
    "StaticImageScraper",
    "DynamicImageScraper",
    "AutoImageScraper",
    "ScraperConfig",
]
