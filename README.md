# WSS Telegram Bot 🤖

Stay on top of the part time job grind!

> This repository contains a simple script that runs multiple times daily via Github-Actions to scrape NTU's WSS jobs and aggregate them to a Google Sheet before posting them to a Telegram channel.

## Installation 🛠

1. Clone the project and install the dependencies

   ```
   pip install -r requirements.txt
   ```

2. Fill in the environment variables in `.env`

   ```bash
   cp .env.example .env
   ```

3. Obtain a Google Sheet API key

   > Open the Google Sheets API page and click the "Enable" button. This takes you to the API manager page.

   > Select a project using the drop down menu at the top of the page. Create a new project, if you do not already have one.

   > Choose "Credentials" in the left panel.

   > Click "Manage service accounts", then create a service account for the connector. On the Create key step, create and download a key in JSON format.

## Tech Stack

- Selenium
- Github Actions
