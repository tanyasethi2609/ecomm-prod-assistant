import csv
import time
import re
import os
from bs4 import BeautifulSoup # Html parsing
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By # Browser level extraction 
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class FlipkartScraper:
    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def get_top_reviews(self,product_url,count=2):
        """Get the top reviews for a product.
        """
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = uc.Chrome(version_main=142, options=options, use_subprocess=True)

        if not product_url.startswith("http"):
            return "No reviews found"

        reviews = []
        try:
            driver.get(product_url)

            # wait for page body to load
            try:
                WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except TimeoutException:
                print("Timeout waiting for product page to load")

            # try to close known popup button (common flipkart close class), fallback to '✕' xpath
            try:
                close_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button._2KpZ6l._2doB4z"))
                )
                close_btn.click()
            except Exception:
                try:
                    btn = driver.find_element(By.XPATH, "//button[contains(text(), '✕')]")
                    btn.click()
                except Exception:
                    pass

            # scroll to load dynamic content
            for _ in range(4):
                ActionChains(driver).send_keys(Keys.END).perform()
                time.sleep(1)

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # first try a few known review container selectors, otherwise fall back to long text blocks
            review_blocks = soup.select("div._27M-vq, div.col.EPCmJX, div._6K-7Co, div.t-ZTKy, div.qwjRop")
            seen = set()

            for block in review_blocks:
                text = block.get_text(separator=" ", strip=True)
                if text and text not in seen and len(text) > 20:
                    reviews.append(text)
                    seen.add(text)
                if len(reviews) >= count:
                    break

            # fallback: grab large paragraph texts from page
            if len(reviews) < count:
                for p in soup.find_all(["p", "div"]):
                    txt = p.get_text(separator=" ", strip=True)
                    if txt and len(txt) > 80 and txt not in seen:
                        reviews.append(txt)
                        seen.add(txt)
                    if len(reviews) >= count:
                        break

        except Exception as e:
            print(f"Error while fetching top reviews: {e}")
            reviews = []

        driver.quit()
        return " || ".join(reviews) if reviews else "No reviews found"
    
    def scrape_flipkart_products(self, query, max_products=1, review_count=2):
        """Scrape Flipkart products based on a search query.
    """
        print("DEBUG: data_scrapper loaded from:", __file__)

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = uc.Chrome(version_main=142, options=options, use_subprocess=True)

        search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        driver.get(search_url)

        # wait for results container
        try:
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div._1YokD2._3Mn1Gg")))
        except TimeoutException:
            # fallback small wait
            time.sleep(3)

        # try to close popup
        try:
            close_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button._2KpZ6l._2doB4z"))
            )
            close_btn.click()
        except Exception:
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
            except Exception:
                pass

        products = []

        try:
            items = WebDriverWait(driver, 6).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-id]"))
            )
        except TimeoutException:
            items = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")

        items = items[:max_products]
        main_window = driver.current_window_handle

        for item in items:
            title = price = rating = total_reviews = product_link = product_id = "N/A"
            try:
                # get product link from anchor inside item (more reliable than click)
                try:
                    link_el = item.find_element(By.CSS_SELECTOR, "a[href*='/p/']")
                    href = link_el.get_attribute("href")
                    product_link = href if href.startswith("http") else "https://www.flipkart.com" + href
                except Exception:
                    # fallback: click the item and read current URL
                    try:
                        item.find_element(By.CSS_SELECTOR, "a").click()
                        time.sleep(1)
                        product_link = driver.current_url
                    except Exception:
                        raise

                # open product page in new tab to avoid losing search results
                driver.execute_script("window.open(arguments[0]);", product_link)
                WebDriverWait(driver, 6).until(lambda d: len(d.window_handles) > 1)
                driver.switch_to.window(driver.window_handles[-1])

                # wait for title or body
                try:
                    title_el = WebDriverWait(driver, 6).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h1, span.B_NuCI"))
                    )
                    title = title_el.text.strip()
                except Exception:
                    # try header span inside h1
                    try:
                        title = driver.find_element(By.CSS_SELECTOR, "h1>span").text.strip()
                    except Exception:
                        title = "N/A"

                # price: look for first element containing the rupee symbol
                try:
                    price_el = WebDriverWait(driver, 4).until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'₹')]") )
                    )
                    price = price_el.text.strip()
                except Exception:
                    price = "N/A"

                # rating: try a few selectors
                try:
                    rating = driver.find_element(By.CSS_SELECTOR, "div._3LWZlK").text.strip()
                except Exception:
                    try:
                        rating = driver.find_element(By.XPATH, "//span[contains(@id, 'productRating')]").text.strip()
                    except Exception:
                        rating = "N/A"

                # total reviews: try to extract from search item first, then fall back to product page text
                total_reviews = "N/A"
                try:
                    reviews_text = item.find_element(By.CSS_SELECTOR, "span.Wphh3N").text.strip()
                    match = re.search(r"(\d{1,3}(?:,\d{3})*)\s+Reviews", reviews_text)
                    total_reviews = match.group(1) if match else reviews_text
                except Exception:
                    try:
                        # parse product page text for common patterns
                        soup_page = BeautifulSoup(driver.page_source, "html.parser")
                        page_text = soup_page.get_text(" ", strip=True)

                        # Pattern: 'X Ratings & Y Reviews'
                        m = re.search(r"(\d{1,3}(?:,\d{3})*)\s*Ratings\s*&\s*(\d{1,3}(?:,\d{3})*)\s*Reviews", page_text)
                        if m:
                            total_reviews = m.group(2)
                        else:
                            # Pattern: 'Y Reviews'
                            m = re.search(r"(\d{1,3}(?:,\d{3})*)\s+Reviews", page_text)
                            if m:
                                total_reviews = m.group(1)
                            else:
                                # fallback to 'X Ratings' if reviews not present
                                m = re.search(r"(\d{1,3}(?:,\d{3})*)\s+Ratings", page_text)
                                if m:
                                    total_reviews = m.group(1)
                    except Exception:
                        total_reviews = "N/A"

                # attempt to extract product id from url
                try:
                    match = re.findall(r"/p/(itm[0-9A-Za-z]+)", product_link)
                    product_id = match[0] if match else "N/A"
                except Exception:
                    product_id = "N/A"

            except Exception as e:
                print(f"Error occurred while processing item: {e}")
                # try to ensure we are back to main window
                try:
                    driver.switch_to.window(main_window)
                except Exception:
                    pass
                continue

            # collect top reviews
            top_reviews = "No reviews found"
            if "flipkart.com" in product_link and product_link != "N/A":
                top_reviews = self.get_top_reviews(product_link, count=review_count)

            products.append([product_id, title, rating, total_reviews, price, top_reviews])

            # close product tab and switch back
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(main_window)
            except Exception:
                pass

        driver.quit()
        return products
    
    def save_to_csv(self, data, filename="product_reviews.csv"):
        """Save the scraped product reviews to a CSV file."""
        if os.path.isabs(filename):
            path = filename
        elif os.path.dirname(filename):  # filename includes subfolder like 'data/product_reviews.csv'
            path = filename
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            # plain filename like 'output.csv'
            path = os.path.join(self.output_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["product_id", "product_title", "rating", "total_reviews", "price", "top_reviews"])
            writer.writerows(data)
        