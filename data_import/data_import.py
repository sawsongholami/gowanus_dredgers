import pandas as pd
import pathlib as pl
import pdfplumber
import requests

dir_project = pl.Path(__file__).parent.parent.absolute()
dir_data = dir_project / 'data'
dir_wqm_csvs = dir_data / 'wqm_csvs'
dir_wqm_pdfs = dir_data / 'wqm_pdfs'


def get_pdf(url=None, pdf_name=None, url_date=None):
    url_prefix = 'https://gowanussuperfund.com/wp-content/uploads'
    if url is not None:
        url_final = url
    elif pdf_name is not None and url_date is not None:
        url_final = f'{url_prefix}/{url_date}/{pdf_name}'
    else:
        raise ValueError('Must specify either url or both pdf_name and url_date')

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        ),
        "Referer": "https://gowanussuperfund.com/",
    }

    # Send a GET request to download the file
    response = requests.get(url_final, headers=headers)

    # Save the PDF into your PyCharm project directory
    if response.status_code == 200:
        with open(dir_wqm_pdfs / pdf_name, "wb") as file:
            file.write(response.content)
        print("PDF downloaded successfully!")
    else:
        print(f"Failed to download. Status code: {response.status_code}")


def pdf_to_csv(pdf_name, first_page_number, column_name_option=0):
    col_options = {
        0: ['date', 'time',
            'turbidity_ambient', 'turbidity_tb1', 'turbidity_usb',
            'rolling_avg_turbidity_ambient', 'rolling_avg_turbidity_tb1', 'rolling_avg_turbidity_usb',
            'difference_tb1_ambient', 'difference_usb_ambient']
    }
    csv_name = pdf_name.replace('.pdf', '.csv')
    # Open the PDF
    with pdfplumber.open(dir_wqm_pdfs / pdf_name) as pdf:
        first_page = pdf.pages[first_page_number - 1]

        # Extract table as a list of lists
        extracted_table = first_page.extract_table()

        # Convert to DataFrame
        df = pd.DataFrame(extracted_table[2:], columns=col_options[column_name_option])
        df.to_csv(dir_wqm_csvs / csv_name, index=False)


if __name__ == '__main__':
    pdf_name = 'RTA2-WQM-Weekly-Report_Week-098.pdf'
    get_pdf(pdf_name=pdf_name, url_date='2026/05')
    pdf_to_csv(pdf_name=pdf_name, first_page_number=15)
