import os
import gspread
import pandas as pd
import asyncio
import telegram
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")


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


def scrape() -> list[dict]:
    # For Chrome
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_driver = webdriver.Chrome(options=chrome_options)
    chrome_driver.get("https://venus.wis.ntu.edu.sg/PortalServices/ServiceListModule/LaunchService.aspx?type=1&launchSvc=https%3A%2F%2Fvenus%2Ewis%2Entu%2Eedu%2Esg%2FWSS2%2FStudent%2FLogin%2Easpx")

    wait = WebDriverWait(chrome_driver, 60)

    username_input_box = chrome_driver.find_element(
        by=By.NAME, value="UserName")
    username_input_box.send_keys(USERNAME)

    domain_dropdown = Select(
        chrome_driver.find_element(by=By.NAME, value="Domain"))
    domain_dropdown.select_by_value("STUDENT")

    login_button = chrome_driver.find_element(by=By.NAME, value="bOption")
    login_button.click()

    password_input_box = chrome_driver.find_element(by=By.NAME, value="PIN")
    password_input_box.send_keys(PASSWORD)

    login_button = chrome_driver.find_element(by=By.NAME, value="bOption")
    login_button.click()

    # TODO: Account for page login errors

    # Wait until the page loads
    view_assignment_anchor = wait.until(EC.presence_of_element_located(
        (By.XPATH, "/html/body/form/div[3]/div[2]/table/tbody/tr[1]/td[1]/div/div/div/div/table[3]/tbody/tr[2]/td[3]/a")))
    view_assignment_anchor.click()

    jobs = []
    jobs.extend(scrape_jobs(chrome_driver, wait))

    next_anchor = wait.until(EC.presence_of_element_located(
        (By.ID, "ctl00_detail_grdBind__nextPageLink")))
    while not next_anchor.get_attribute("disabled"):
        next_anchor.click()
        jobs.extend(scrape_jobs(chrome_driver, wait))
        next_anchor = wait.until(EC.presence_of_element_located(
            (By.ID, "ctl00_detail_grdBind__nextPageLink")))

    # Close the browser
    chrome_driver.quit()

    return jobs


def scrape_jobs(chrome_driver: webdriver.Chrome, wait: WebDriverWait) -> list[dict]:
    import re
    job_table = wait.until(EC.presence_of_element_located(
        (By.ID, "ctl00_detail_gvAvailableJob")))
    table_rows = job_table.find_elements(by=By.TAG_NAME, value="tr")

    data = []
    for i, row in enumerate(table_rows[1:]):
        try:
            print(row.text)
            td_elements = row.find_elements(by=By.TAG_NAME, value="td")
        except StaleElementReferenceException:
            # Find the row again
            row = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, f"#ctl00_detail_gvAvailableJob > tbody > tr:nth-child({i+2})")))
            print(row.text)
            td_elements = row.find_elements(by=By.TAG_NAME, value="td")

        job_data = [td.text for td in td_elements][2:-1]

        anchor_tag = td_elements[2].find_element(by=By.TAG_NAME, value="a")
        print(f"Anchor: {anchor_tag.text}\n")
        anchor_tag.click()

        # Wait until the new tab finishes loading
        wait.until(EC.number_of_windows_to_be(2))
        chrome_driver.switch_to.window(chrome_driver.window_handles[-1])

        job_type = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblJobType").text
        job_nature = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblJobNature").text
        job_start_date = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblStartDt").text
        job_end_date = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblEndDt").text
        job_hrs_per_week = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblNoHrPerWeek").text
        job_salary = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblSalary").text
        job_skills_required = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblSkills").text
        job_learning_outcome = chrome_driver.find_element(
            by=By.ID, value="ctl00_detail_ucJobMain1_lblLearningOutcome").text

        job_data_dict = {
            "ID": job_data[0],
            "Title": job_data[1],
            "Hiring Department": job_data[2],
            "Contact Person": job_data[3],
            "Contact Email": job_data[4],
            "Posted Date": re.sub(r'(\d{2}/\d{2}/)00(\d{2})', r'\g<1>20\g<2>', job_data[5]),
            "Type": job_type,
            "Nature": job_nature,
            "Start Date": job_start_date,
            "End Date": job_end_date,
            "Hours Per Week": job_hrs_per_week,
            "Salary": job_salary,
            "Skills Required": job_skills_required,
            "Learning Outcome": job_learning_outcome,
            "Status": "Active"
        }
        data.append(job_data_dict)

        # chrome_driver.save_screenshot(f"job_page_screenshot.png")

        # Close the new tab
        chrome_driver.close()

        # Switch back to the original tab
        chrome_driver.switch_to.window(chrome_driver.window_handles[0])

    return data


def process_jobs(old_df, jobs):
    old_ids = set(old_df["ID"])
    new_ids = set(jobs["ID"])

    unlisted = old_ids - new_ids
    new_jobs = new_ids - old_ids

    print("Unlisted jobs:", unlisted)
    print("New jobs:", new_jobs)

    old_df["Status"] = "Active"

    old_df.loc[old_df[old_df["ID"].isin(
        unlisted)].index, "Status"] = "Unlisted"
    new_jobs_df = jobs[jobs["ID"].isin(new_jobs)]

    res_df = pd.concat([old_df, new_jobs_df])
    print(res_df)

    # Convert the 'Date Posted' column to datetime format
    res_df['Date'] = pd.to_datetime(res_df['Posted Date'], format='%d/%m/%Y')

    # Get the date 2 weeks ago
    two_weeks_ago = datetime.now() - timedelta(weeks=2)

    # Select rows where the status is not 'Unlisted' or the date posted is within the last 2 weeks
    res_df = res_df[(res_df['Status'] != 'Unlisted') |
                    (res_df['Date'] > two_weeks_ago)]
    res_df.drop(columns=["Date"], inplace=True)
    print("Dropped stale jobs!")

    return (res_df, new_jobs_df)


async def send_message(message):
    bot = telegram.Bot(token=BOT_TOKEN)
    await bot.sendMessage(chat_id=CHAT_ID, text=message)
    print("Message sent!")


async def main():
    g_sheet = GoogleSheetsConnector("keyfile.json", "WSS Jobs")

    df = pd.DataFrame(g_sheet.get_all_values())
    # Set first row as column names
    df.columns = df.iloc[0]
    df = df.iloc[1:]
    print("Fetched data from Google Sheets successfully!")

    jobs = pd.DataFrame(scrape())
    print("Scraped data successfully!")

    res_df, new_jobs_df = process_jobs(df, jobs)
    print("Processed jobs!")

    g_sheet.set_dataframe(res_df)

    for _, row in new_jobs_df.iterrows():
        message = f"""
Title: {row['Title']}\n
Hiring Department: {row['Hiring Department']}\n
Contact Person: {row['Contact Person']}\n
Contact Email: {row['Contact Email']}\n
Posted Date: {row['Posted Date']}\n
Type: {row['Type']}\n
Nature: \n{row['Nature']}\n
Start Date: {row['Start Date']}\n
End Date: {row['End Date']}\n
Hours Per Week: {row['Hours Per Week']}\n
Salary: {row['Salary']}\n
Skills Required: \n{row['Skills Required']}\n
Learning Outcome: \n{row['Learning Outcome']}\n
        """
        await send_message(message)


if __name__ == '__main__':
    asyncio.run(main())
