import urllib.parse
from time import sleep
from typing import List, Dict

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

from .objects import Scraper


class PeopleSearch(Scraper):
    # People search can be slower to load; increase wait timeout locally
    WAIT_FOR_ELEMENT_TIMEOUT = 10
    def __init__(
        self,
        driver,
        base_url: str = "https://www.linkedin.com/",
        close_on_complete: bool = False,
        scrape: bool = False,
    ):
        super().__init__()
        self.driver = driver
        self.base_url = base_url

        if scrape:
            self.scrape(close_on_complete)

    def scrape(self, close_on_complete: bool = True):
        if self.is_signed_in():
            self.scrape_logged_in(close_on_complete=close_on_complete)
        else:
            raise NotImplementedError("This part is not implemented yet")

    def scrape_people_card_link(self, base_element) -> str:
        # Try multiple ways to locate the profile link within a people result card
        candidate_selectors = [
            'span.entity-result__title-text a.app-aware-link[href*="/in/"]',
            'a.app-aware-link[href*="/in/"]',
            'a[data-test-app-aware-link][href*="/in/"]',
            'a[href*="linkedin.com/in/"]',
        ]
        for selector in candidate_selectors:
            try:
                link = base_element.find_element(By.CSS_SELECTOR, selector)
                href = (link.get_attribute("href") or "").strip()
                if href and "/in/" in href:
                    return href.split("?")[0]
            except Exception:
                continue
        return ""

    def scrape_people_card_details(self, base_element) -> Dict[str, str]:
        profile_url = self.scrape_people_card_link(base_element)

        # Name: prefer profile image alt, fallback to anchor text
        name = ""
        try:
            img = base_element.find_element(
                By.CSS_SELECTOR, "img.presence-entity__image[alt]"
            )
            alt = (img.get_attribute("alt") or "").strip()
            if alt:
                name = alt
        except Exception:
            pass
        if not name:
            try:
                name_anchor = base_element.find_element(
                    By.CSS_SELECTOR, 'a[data-test-app-aware-link][href*="/in/"]'
                )
                name = (name_anchor.text or "").strip()
            except Exception:
                pass

        # Connection degree if visible
        connection = ""
        try:
            connection = base_element.find_element(
                By.CSS_SELECTOR, ".entity-result__badge-text"
            ).text.strip()
        except Exception:
            pass

        # Headline and location heuristics: gather t-14 blocks
        headline = ""
        location = ""
        try:
            blocks = base_element.find_elements(By.CSS_SELECTOR, "div.t-14")
            texts = [b.text.strip() for b in blocks if (b.text or "").strip()]
            # Prefer a block that includes common headline separators or long text
            for t in texts:
                if len(t) > 25 and not headline:
                    headline = t
            # Location tends to be short (<= 40) and not equal to headline
            for t in texts:
                if t != headline and 2 <= len(t) <= 40 and not location:
                    location = t
        except Exception:
            pass

        return {
            "name": name,
            "profile_url": profile_url,
            "headline": headline,
            "location": location,
            "connection": connection,
        }

    def scrape_logged_in(self, close_on_complete: bool = True):
        if close_on_complete:
            self.driver.close()
        return

    def search(self, search_term: str) -> List[str]:
        url = urllib.parse.urljoin(
            self.base_url, "search/results/people/"
        ) + f"?keywords={urllib.parse.quote(search_term)}&refresh=true"
        self.driver.get(url)

        # Allow results to load and trigger additional lazy loads
        for _ in range(4):
            self.scroll_to_bottom()
            sleep(2)

        # Try to ensure at least one result is present; accept multiple possible DOMs
        try:
            try:
                self.wait_for_element_to_load(
                    by=By.CLASS_NAME, name="reusable-search__entity-result-list"
                )
            except TimeoutException:
                self.wait_for_element_to_load(by=By.CLASS_NAME, name="entity-result")
        except TimeoutException:
            # No results visible; return empty list instead of raising a blank error
            return []

        # Collect results using multiple item selectors to handle DOM variants
        result_items = self.driver.find_elements(
            By.CSS_SELECTOR,
            '[data-view-name="search-entity-result-universal-template"], .reusable-search__result-container, .entity-result__item, .entity-result',
        )

        found: List[str] = []
        for people_card in result_items:
            try:
                profile_url = self.scrape_people_card_link(people_card)
                if profile_url:
                    found.append(profile_url)
            except Exception:
                continue

        # Deduplicate while preserving order
        seen = set()
        unique_profiles: List[str] = []
        for href in found:
            if href not in seen:
                seen.add(href)
                unique_profiles.append(href)
        return unique_profiles

    def search_detailed(self, search_term: str) -> List[Dict[str, str]]:
        """Return detailed people results including name, url, headline, location, connection."""
        url = urllib.parse.urljoin(
            self.base_url, "search/results/people/"
        ) + f"?keywords={urllib.parse.quote(search_term)}&refresh=true"
        self.driver.get(url)

        for _ in range(4):
            self.scroll_to_bottom()
            sleep(2)

        try:
            try:
                self.wait_for_element_to_load(
                    by=By.CLASS_NAME, name="reusable-search__entity-result-list"
                )
            except TimeoutException:
                self.wait_for_element_to_load(by=By.CLASS_NAME, name="entity-result")
        except TimeoutException:
            return []

        result_items = self.driver.find_elements(
            By.CSS_SELECTOR,
            '[data-view-name="search-entity-result-universal-template"], .reusable-search__result-container, .entity-result__item, .entity-result',
        )

        detailed: List[Dict[str, str]] = []
        for card in result_items:
            try:
                item = self.scrape_people_card_details(card)
                # Skip headless or empty entries
                if item.get("profile_url") and "/in/" in item["profile_url"]:
                    detailed.append(item)
            except Exception:
                continue
        # Deduplicate by profile_url while preserving order
        seen = set()
        unique: List[Dict[str, str]] = []
        for item in detailed:
            url = item["profile_url"]
            if url not in seen:
                seen.add(url)
                unique.append(item)
        return unique


