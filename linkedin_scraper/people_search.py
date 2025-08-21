import urllib.parse
from time import sleep
from typing import List

from selenium.webdriver.common.by import By

from .objects import Scraper


class PeopleSearch(Scraper):
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

    def scrape_people_card(self, base_element) -> str:
        title_span = self.wait_for_element_to_load(
            by=By.CLASS_NAME, name="entity-result__title-text", base=base_element
        )
        people_link = self.wait_for_element_to_load(
            by=By.CLASS_NAME, name="app-aware-link", base=title_span
        )
        href = people_link.get_attribute("href") or ""
        return href.split("?")[0]

    def scrape_logged_in(self, close_on_complete: bool = True):
        if close_on_complete:
            self.driver.close()
        return

    def search(self, search_term: str) -> List[str]:
        url = urllib.parse.urljoin(
            self.base_url, "search/results/people/"
        ) + f"?keywords={urllib.parse.quote(search_term)}&refresh=true"
        self.driver.get(url)
        self.scroll_to_bottom()
        sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)

        people_list_class_name = "entity-result"
        self.wait_for_element_to_load(by=By.CLASS_NAME, name=people_list_class_name)

        for pct in (0.3, 0.6, 1):
            self.scroll_class_name_element_to_page_percent(
                people_list_class_name, pct
            )
            sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)

        people_profiles: List[str] = []
        result_items = self.wait_for_all_elements_to_load(
            by=By.CLASS_NAME, name="entity-result__item"
        )
        for people_card in result_items:
            try:
                profile_url = self.scrape_people_card(people_card)
                if profile_url:
                    people_profiles.append(profile_url)
            except Exception:
                continue
        return people_profiles


