import os
import random
import argparse
import gspread
import pandas as pd
import asyncio
import telegram
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, ElementClickInterceptedException
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
# PASSWORD = os.getenv("PASSWORD")
PASSWORD = "milesG0@t904"


class GoogleSheetsConnector:
    def __init__(self, keyfile_path, sheet_name):
        if not os.path.isfile(keyfile_path):
            raise Exception("Invalid keyfile path")
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(
            keyfile_path)
        self.client = gspread.authorize(self.creds)
        self.sheet = self.client.open(sheet_name).sheet1

    def get_all_values(self):
        return self.sheet.get_all_values()

    def get_column_values(self, col):
        return self.sheet.col_values(col)

    def get_row_values(self, row):
        return self.sheet.row_values(row)

    def update_cell(self, row, col, value):
        self.sheet.update_cell(row, col, value)

    def set_dataframe(self, df):
        set_with_dataframe(self.sheet, df)


class JobScraper:
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait, google_sheet, debug=False):
        self.driver = driver
        self.wait = wait
        self.google_sheet = google_sheet
        self.debug = debug

    def login(self, username, password) -> None:
        # Code to login
        self.driver.get(
            "https://apps.ntu.edu.sg/WSSClaims_Student/OpenAssignments")

        # Wait for SSO
        self.wait.until(EC.url_contains("https://loginfs.ntu.edu.sg/"))
        self.wait.until(EC.presence_of_element_located((By.NAME, "UserName")))

        username_input_box = self.driver.find_element(
            by=By.NAME, value="UserName")
        username_input_box.send_keys("student\\" + username)

        password_input_box = self.driver.find_element(
            by=By.NAME, value="Password")
        password_input_box.send_keys(password)

        login_button = self.driver.find_element(by=By.ID, value="submitButton")
        login_button.click()

    def navigate_to_jobs_page_and_scrape(self) -> list[dict]:
        # Code to navigate to jobs page
        self.wait.until(EC.url_contains(
            "https://apps.ntu.edu.sg/WSSClaims_Student/OpenAssignments"))
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        jobs = []
        jobs.extend(self.scrape_jobs())

        next_anchor = self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "button[aria-label='go to next page']")))
        has_next = next_anchor.get_attribute("disabled")
        while not has_next:
            try:
                next_anchor.click()
                jobs.extend(self.scrape_jobs())
                next_anchor = self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button[aria-label='go to next page']")))
                has_next = next_anchor.get_attribute("disabled")
            except StaleElementReferenceException:
                next_anchor = self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button[aria-label='go to next page']")))
                next_anchor.click()
                jobs.extend(self.scrape_jobs())
                next_anchor = self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button[aria-label='go to next page']")))
                has_next = next_anchor.get_attribute("disabled")

        # Close the browser
        self.driver.quit()

        return jobs

    def scrape_jobs(self) -> list[dict]:
        import json

        start = self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "span[data-testid='Pagination.RecordNumberFrom']"))).text
        end = self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "span[data-testid='Pagination.RecordNumberTo']"))).text
        print(f"Scraping jobs from {start} to {end}")

        try:
            table_rows = self.wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "table > tbody > .table-row")))
            print(f"Number of jobs: {len(table_rows)}")
        except NoSuchElementException as e:
            self.driver.save_screenshot("no_jobs_error_screenshot.png")
            print("No jobs found!")
            raise RuntimeError("No jobs found!")

        data = []
        for i, row in enumerate(table_rows):
            print(f"\nJob {i+1}:")

            if i + 1 == (int(end) - int(start) + 2):
                break

            time.sleep(random.randint(0, 3))
            try:
                print(f"Getting row...")
                td_elements = row.find_elements(by=By.TAG_NAME, value="td")
            except StaleElementReferenceException:
                # Find the row again
                row = self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f"table > tbody > tr:nth-child({i+1})")))
                td_elements = row.find_elements(by=By.TAG_NAME, value="td")

            try:
                print(f"Getting anchor tag...")
                anchor_tag = td_elements[0].find_element(
                    by=By.TAG_NAME, value="a")
                self.wait.until(EC.element_to_be_clickable(anchor_tag))
                print(f"Anchor: {anchor_tag.text}\n")
                anchor_tag.click()
            except StaleElementReferenceException:
                # Find the anchor tag again
                anchor_tag = self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f"table > tbody > tr:nth-child({i+1}) > td:nth-child(1) > a")))
                anchor_tag.click()
            except ElementClickInterceptedException:
                # Find the anchor tag again
                anchor_tag = self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f"table > tbody > tr:nth-child({i+1}) > td:nth-child(1) > a")))
                self.driver.execute_script("arguments[0].click();", anchor_tag)

            try:
                # Wait until the new page finishes loading
                self.wait.until(EC.url_contains(
                    "https://apps.ntu.edu.sg/WSSClaims_Student/ApplyAssignment"))
                self.wait.until(EC.presence_of_element_located(
                    (By.ID, "b1-MainContent")))
            except Exception:
                self.driver.save_screenshot(
                    "page_not_load_error_screenshot.png")
                raise RuntimeError("New page did not load!")

            job_data_dict = {
                "Assignment Number": None,
                "Type": None,
                "Category": None,
                "Contact Person": None,
                "Contact Email": None,
                "Supervisor": None,
                "Max Applicants": None,
                "Start Date": None,
                "End Date": None,
                "Hours Per Week": None,
                "Allowance": None,
                "Nature of Assignment": None,
                "Skills Requirement": None,
                "Learning Outcome": None,
                "Department": None,
                "Status": "Active"
            }

            # \$b12 > div:nth-child(1)
            for element in self.driver.find_elements(by=By.CSS_SELECTOR, value="#\$b12 > div"):
                time.sleep(random.randint(1, 3))
                # find label in element with html attribute data-label
                label = element.find_element(
                    by=By.CSS_SELECTOR, value="label[data-label]").text.strip()

                if label.endswith(":"):
                    label = label[:-1]
                if label.endswith("(S$/hour)"):
                    label = label[:-9].strip()

                if label not in job_data_dict:
                    print(f"Skipping {label}")
                    continue

                value = element.find_element(
                    by=By.CSS_SELECTOR, value="span[data-expression]").text.strip()
                job_data_dict[label] = value

            print(json.dumps(job_data_dict, indent=4))

            data.append(job_data_dict)
            self.driver.back()
            time.sleep(random.randint(1, 3))

        return data

    def process_jobs(self, old_df: pd.DataFrame, jobs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Code to process jobs
        old_ids = set(old_df["Assignment Number"])
        new_ids = set(jobs["Assignment Number"])

        unlisted = old_ids - new_ids
        new_jobs = new_ids - old_ids

        print("Unlisted jobs:", unlisted)
        print("New jobs:", new_jobs)

        old_df["Status"] = "Active"

        old_df.loc[old_df[old_df["Assignment Number"].isin(
            unlisted)].index, "Status"] = "Unlisted"
        new_jobs_df = jobs[jobs["Assignment Number"].isin(new_jobs)]

        res_df = pd.concat([old_df, new_jobs_df])
        print(res_df)

        # Convert the 'Date Posted' column to datetime format
        res_df['Date'] = pd.to_datetime(
            res_df['Start Date'], format="%d %b %Y")

        # Get the date 2 weeks ago
        two_weeks_ago = datetime.now() - timedelta(weeks=2)

        # Select rows where the status is not 'Unlisted' or the date posted is within the last 2 weeks
        res_df = res_df[(res_df['Status'] != 'Unlisted') |
                        (res_df['Date'] > two_weeks_ago)]
        res_df.drop(columns=["Date"], inplace=True)
        print("Dropped stale jobs!")

        return (res_df, new_jobs_df)

    async def send_message(self, message) -> None:
        # Code to send message
        bot = telegram.Bot(token=BOT_TOKEN)
        await bot.sendMessage(chat_id=CHAT_ID, text=message)
        print("Message sent!")

    async def run(self) -> None:
        df = pd.DataFrame(self.google_sheet.get_all_values())
        # Set first row as column names
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        print("Fetched data from Google Sheets successfully!")

        try:
            self.login(USERNAME, PASSWORD)
            start = time.time()
            jobs = pd.DataFrame(self.navigate_to_jobs_page_and_scrape())
            print(f"{len(jobs)} jobs scraped in {time.time() - start:.2f} seconds!")
            print("Scraped data successfully!")
        except RuntimeError as e:
            print(e)
            await self.send_message("An error occurred while scraping the jobs 😭")
            return

        res_df, new_jobs_df = self.process_jobs(df, jobs)
        print("Processed jobs!")
        print(res_df)
        print(new_jobs_df)

        if self.debug:
            return

        self.google_sheet.set_dataframe(res_df)

        if new_jobs_df.empty:
            await self.send_message("No new jobs found at this time 🤷‍♂️")
            return

        for _, row in new_jobs_df.iterrows():
            message = f"""
Assignment Number: {row['Assignment Number']}\n
Category: {row['Category']}\n
Hiring Department: {row['Department']}\n
Contact Person: {row['Contact Person']}\n
Contact Email: {row['Contact Email']}\n
Max Applicants: {row['Max Applicants']}\n
Type: {row['Type']}\n
Nature: \n{row['Nature of Assignment']}\n
Start Date: {row['Start Date']}\n
End Date: {row['End Date']}\n
Hours Per Week: {row['Hours Per Week']}\n
Salary: {row['Allowance']}\n
Skills Required: \n{row['Skills Requirement']}\n
Learning Outcome: \n{row['Learning Outcome']}\n
            """
            await self.send_message(message)
            time.sleep(3)


async def main():
    parser = argparse.ArgumentParser(description='Job Scraper')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Enable debug mode')
    args = parser.parse_args()

    chrome_options = ChromeOptions()
    if not args.debug:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 120)
    google_sheet = GoogleSheetsConnector("keyfile.json", "WSS Jobs")

    scraper = JobScraper(driver, wait, google_sheet, args.debug)
    await scraper.run()


if __name__ == '__main__':
    asyncio.run(main())
