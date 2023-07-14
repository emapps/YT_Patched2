"""Downloader Class."""
import re
from typing import Any, List

import requests
from bs4 import BeautifulSoup as bs
from loguru import logger
from selectolax.lexbor import LexborHTMLParser

from src.downloader.download import Downloader
from src.utils import AppNotFound, slugify


class ApkMirror(Downloader):
    """Files downloader."""

    def extract_download_link(self, page: str, app: str) -> None:
        """Function to extract the download link from apkmirror html page.

        :param page: Url of the page
        :param app: Name of the app
        """
        logger.debug(f"Extracting download link from\n{page}")
        parser = LexborHTMLParser(self.config.session.get(page).text)

        resp = self.config.session.get(
            self.config.apk_mirror + parser.css_first("a.accent_bg").attributes["href"]
        )
        parser = LexborHTMLParser(resp.text)

        href = parser.css_first(
            "p.notes:nth-child(3) > span:nth-child(1) > a:nth-child(1)"
        ).attributes["href"]
        self._download(self.config.apk_mirror + href, f"{app}.apk")
        logger.debug("Finished Extracting link and downloading")

    def get_download_page(self, parser: LexborHTMLParser, main_page: str) -> str:
        """Function to get the download page in apk_mirror.

        :param parser: Parser
        :param main_page: Main Download Page in APK mirror(Index)
        :return:
        """
        logger.debug(f"Getting download page from {main_page}")
        apm = parser.css(".apkm-badge")
        sub_url = ""
        for is_apm in apm:
            parent_text = is_apm.parent.parent.text()
            if "APK" in is_apm.text() and (
                "arm64-v8a" in parent_text
                or "universal" in parent_text
                or "noarch" in parent_text
            ):
                parser = is_apm.parent
                sub_url = parser.css_first(".accent_color").attributes["href"]
                break
        if sub_url == "":
            logger.exception(
                f"Unable to find any apk on apkmirror_specific_version on {main_page}"
            )
            raise AppNotFound("Unable to find apk on apkmirror site.")
        download_url = self.config.apk_mirror + sub_url
        return download_url

    def specific_version(self, app: str, version: str) -> None:
        """Function to download the specified version of app from  apkmirror.

        :param app: Name of the application
        :param version: Version of the application to download
        :return: Version of downloaded apk
        """
        logger.debug(f"Trying to download {app},specific version {version}")
        version = version.replace(".", "-")
        main_page = f"{self.config.apk_mirror_version_urls.get(app)}-{version}-release/"
        parser = LexborHTMLParser(
            self.config.session.get(main_page, allow_redirects=True).text
        )
        download_page = self.get_download_page(parser, main_page)
        self.extract_download_link(download_page, app)
        logger.debug(f"Downloaded {app} apk from apkmirror_specific_version")

    def find_apkmirror_version_links(self, app: str) -> List[str]:
        """Find all versions of app from apkmirror."""
        ids = {}
        ids.update(self.patcher.revanced_app_ids)
        ids.update(self.patcher.revanced_extended_app_ids)
        package_name = {i for i in ids if ids[i][0] == app}
        s = requests.session()
        s.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:99.0) Gecko/20100101 Firefox/99.0"
            }
        )
        r = s.get(
            f"https://www.apkmirror.com/?post_type=app_release&searchtype=apk&page=1&s={package_name}"
        )
        soup = bs(r.text, "html.parser")
        app = app.replace("_", "-")
        return list(
            map(
                lambda tag: tag["href"],
                filter(
                    lambda tag: f"{app}" in tag["href"], soup.select("a.downloadLink")
                ),
            )
        )

    def parse_link_version(self, link: str) -> str:
        """Extract version from link."""
        try:
            link = slugify(link)
            # re.search(r"\b\d+(?:-\d+)*\b", link).group(0)
            searched = re.search(r"(\d+(?:-\d+)+)", link)
            if searched:
                return searched.group(0)
            raise AttributeError()
        except AttributeError:
            logger.error("Unable to parse link to get version")
            raise AppNotFound()

    def get_latest_version(self, app: str) -> str:
        """Get latest version of the app."""
        version_links = self.find_apkmirror_version_links(app)
        versions = list(map(self.parse_link_version, version_links))
        max_version = max(versions)
        return max_version

    def latest_version(self, app: str, **kwargs: Any) -> None:
        """Function to download whatever the latest version of app from
        apkmirror.

        :param app: Name of the application
        :return: Version of downloaded apk
        """
        logger.debug(f"Trying to download {app}'s latest version from apkmirror")
        version = self.get_latest_version(app)
        logger.debug(f"Selected {version} to download {app}'s from apkmirror")
        return self.specific_version(app, version)
