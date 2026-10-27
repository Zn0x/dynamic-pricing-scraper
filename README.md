# 📈 Dynamic Pricing Scraper & Analytics Pipeline

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Headless%20RPA-red?style=for-the-badge&logo=playwright&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Wrangling-darkgreen?style=for-the-badge&logo=pandas&logoColor=white)
![Google Cloud](https://img.shields.io/badge/Google%20Sheets-API-yellow?style=for-the-badge&logo=google-sheets&logoColor=white)

An automated data extraction and dynamic repricing pipeline built for web platforms. The bot manages unattended session lifecycles, solves multi-factor authentication (2FA) via IMAP token parsing, interacts with complex dynamic data tables via DOM manipulation, and leverages Pandas for data transformation, type casting, and cloud persistence.

---

## ⚡ Architecture & Features

- **Automated MFA/2FA Resolution:** Listens over SSL to incoming IMAP mail alerts and extracts one-time security codes using regex token matching.
- **Dynamic DOM Column Filtering:** Manipulates PrimeFaces/JSF enterprise UI table togglers in real time, unchecking redundant metrics and isolating relevant pricing variables.
- **Data Transformation Pipeline:**
  - Cleans, parses, and normalizes date/time records.
  - Sorts historical records chronologically.
  - Casts string numerals to native floating-point types for calculation accuracy.
- **Cloud Database Synchronization:** Streams transformed tabular records into Google Sheets using Service Account credentials.

---

## 🛠️ Tech Stack

- **Language:** Python
- **Automation:** Playwright
- **Data Analysis:** Pandas, OpenPyXL
- **Protocols & Integrations:** `imaplib`, `gspread` (Google Sheets API)

---

## 🚀 Setup & Execution

### 1. Installation
```bash
git clone [https://github.com/Zn0x/dynamic-pricing-scraper.git](https://github.com/Zn0x/dynamic-pricing-scraper.git)
cd dynamic-pricing-scraper
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

### 2. Enviroment

cp .env.example .env

### 3. Run pipeline

python main.py

---

### 6. Subirlo limpio a tu repositorio

En tu terminal, adentro de la carpeta de este proyecto:

```bash
# Verificar que tu email sea el personal:
git config user.email

# Iniciar y commitear limpio:
git init
git add .
git commit -m "feat: initial release of dynamic pricing scraper"
git branch -M main
git remote add origin https://github.com/Zn0x/dynamic-pricing-scraper.git
git push -u origin main