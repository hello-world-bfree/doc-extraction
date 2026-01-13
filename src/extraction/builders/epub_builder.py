import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ebooklib import epub
from PIL import Image

from ..scrapers.image_scraper import ImageData


class EpubBuilder:
    def __init__(
        self,
        title: str,
        author: str = "Unknown",
        language: str = "en",
        identifier: Optional[str] = None
    ):
        self.book = epub.EpubBook()

        self.book.set_title(title)
        self.book.set_language(language)

        self.book.add_author(author)

        if identifier is None:
            identifier = f"image-epub-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.book.set_identifier(identifier)

        self.chapters: list[epub.EpubHtml] = []
        self.images: list[epub.EpubImage] = []

    def add_cover_image(self, image_path: Path) -> None:
        with open(image_path, 'rb') as f:
            cover_content = f.read()

        self.book.set_cover('cover.jpg', cover_content)

    def add_image(
        self,
        image_data: Union[ImageData, Path],
        caption: Optional[str] = None,
        chapter_title: Optional[str] = None
    ) -> None:
        if isinstance(image_data, Path):
            local_path = image_data
            alt_text = caption
        else:
            local_path = image_data.local_path
            alt_text = caption or image_data.alt_text

        if not local_path.exists():
            print(f"Warning: Image not found: {local_path}")
            return

        mime_type, _ = mimetypes.guess_type(str(local_path))
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'

        with open(local_path, 'rb') as f:
            image_content = f.read()

        epub_image = epub.EpubImage(
            uid=f"image_{len(self.images)}",
            file_name=f"images/{local_path.name}",
            media_type=mime_type,
            content=image_content
        )
        self.book.add_item(epub_image)
        self.images.append(epub_image)

        if chapter_title is None:
            chapter_title = alt_text or f"Image {len(self.chapters) + 1}"

        try:
            with Image.open(local_path) as img:
                width, height = img.size
                aspect_ratio = height / width if width > 0 else 1
                max_width = 100
                computed_height = int(max_width * aspect_ratio)
        except Exception:
            max_width = 100
            computed_height = 100

        html_content = f'''<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{chapter_title}</title>
    <style>
        body {{
            text-align: center;
            margin: 0;
            padding: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}
        .image-container {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            width: 95%;
            max-height: 90vh;
        }}
        img {{
            max-width: 100%;
            max-height: 85vh;
            height: auto;
            width: auto;
            object-fit: contain;
        }}
        .caption {{
            margin-top: 1em;
            padding: 0.5em 1em;
            font-size: 1em;
            font-weight: 500;
            color: #333;
            max-width: 90%;
        }}
    </style>
</head>
<body>
    <div class="image-container">
        <img src="{epub_image.file_name}" alt="{alt_text or ''}" />
    </div>
    {f'<div class="caption">{alt_text}</div>' if alt_text else ''}
</body>
</html>'''

        chapter = epub.EpubHtml(
            title=chapter_title,
            file_name=f"chapter_{len(self.chapters)}.xhtml",
            lang='en'
        )
        chapter.set_content(html_content.encode('utf-8'))
        self.book.add_item(chapter)
        self.chapters.append(chapter)

    def add_images(
        self,
        images: list[Union[ImageData, Path]],
        captions: Optional[list[str]] = None
    ) -> None:
        for idx, image in enumerate(images):
            caption = captions[idx] if captions and idx < len(captions) else None
            self.add_image(image, caption=caption)

    def save(self, output_path: Union[str, Path]) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.book.toc = tuple(self.chapters)

        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        self.book.spine = ['nav'] + self.chapters

        epub_options = {
            'plugins': []
        }

        epub.write_epub(str(output_path), self.book, epub_options)
        print(f"EPUB created successfully: {output_path}")
