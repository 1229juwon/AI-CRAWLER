"""YouTube video MP4 download service using yt-dlp."""

import os
from pathlib import Path
from typing import Any

import yt_dlp


class YouTubeDownloadError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class YouTubeDownloadService:
    """Download YouTube videos as MP4 using yt-dlp."""

    def __init__(self, output_dir: str | Path = "downloads") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_ydl_opts(self) -> dict[str, Any]:
        return {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }

    def download(self, video_id: str) -> dict[str, Any]:
        """Download a YouTube video by its video ID.

        Returns dict with keys: video_id, title, file_path, file_size_bytes.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = self._get_ydl_opts()

        downloaded_file: str | None = None
        video_title: str = ""

        def _hook(d: dict[str, Any]) -> None:
            nonlocal downloaded_file, video_title
            if d["status"] == "finished":
                downloaded_file = d["filename"]
                info = d.get("info_dict")
                if info:
                    video_title = info.get("title", "")

        opts["progress_hooks"] = [_hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get("title", "") or video_title

                # If progress hook didn't fire (e.g., file already downloaded),
                # find the file by expected pattern
                if not downloaded_file:
                    expected = str(self.output_dir / f"{video_id}.mp4")
                    if os.path.exists(expected):
                        downloaded_file = expected
                    else:
                        # List files in output dir matching video_id
                        for f in self.output_dir.glob(f"{video_id}.*"):
                            downloaded_file = str(f)
                            break

                if not downloaded_file or not os.path.exists(downloaded_file):
                    raise YouTubeDownloadError(f"Failed to download video: {video_id}")

                file_size = os.path.getsize(downloaded_file)
                return {
                    "video_id": info.get("id", video_id),
                    "title": video_title or info.get("title", ""),
                    "file_path": downloaded_file,
                    "file_size_bytes": file_size,
                }
        except yt_dlp.utils.DownloadError as exc:
            raise YouTubeDownloadError(f"yt-dlp download error for {video_id}: {exc}")