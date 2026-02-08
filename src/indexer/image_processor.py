"""画像処理・説明生成"""

import base64
import hashlib
import mimetypes
from pathlib import Path

import httpx
from openai import OpenAI

from src.config.settings import get_settings
from src.notion.models import ImageInfo


class ImageProcessor:
    """画像のダウンロードと説明生成を行う"""

    def __init__(self):
        self.settings = get_settings()
        self.storage_dir = self.settings.image_storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.openai_client = OpenAI(api_key=self.settings.openai_api_key)

    def process_image(self, image: ImageInfo) -> ImageInfo:
        """画像をダウンロードして説明を生成"""
        if not image.url:
            return image

        # ダウンロード
        local_path = self._download_image(image.url)
        if not local_path:
            return image

        image.local_path = str(local_path)

        # 説明生成
        description = self._generate_description(local_path, image.caption)
        image.description = description

        return image

    def _download_image(self, url: str) -> Path | None:
        """画像をダウンロードしてローカルに保存"""
        try:
            # URLからハッシュを生成してファイル名に使用
            url_hash = hashlib.md5(url.encode()).hexdigest()[:16]

            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()

                # Content-Typeから拡張子を推定
                content_type = response.headers.get("content-type", "image/png")
                ext = mimetypes.guess_extension(content_type.split(";")[0]) or ".png"

                filename = f"{url_hash}{ext}"
                local_path = self.storage_dir / filename

                local_path.write_bytes(response.content)
                return local_path

        except Exception as e:
            print(f"画像ダウンロードエラー: {url} - {e}")
            return None

    def _generate_description(self, image_path: Path, caption: str | None) -> str:
        """GPT-4oを使って画像の説明を生成"""
        try:
            # 画像をbase64エンコード
            image_data = image_path.read_bytes()
            base64_image = base64.b64encode(image_data).decode("utf-8")

            # MIMEタイプを推定
            mime_type, _ = mimetypes.guess_type(str(image_path))
            mime_type = mime_type or "image/png"

            prompt = "この画像の内容を日本語で詳しく説明してください。図表やグラフの場合は、その内容や重要なポイントも含めて説明してください。"
            if caption:
                prompt += f"\n\nキャプション: {caption}"

            response = self.openai_client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            print(f"画像説明生成エラー: {image_path} - {e}")
            return caption or ""
