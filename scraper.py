import io
import json
import traceback
from typing import Optional

import requests  # pip install requests

import PyPDF2  # pip install PyPDF2
from seleniumwire import webdriver  # pip install selenium-wire


from scraping_status import ScrapingStatus


class Scraper:
    status: ScrapingStatus
    cookies: dict[str, str]
    request_headers: dict

    def __init__(self, status: Optional[ScrapingStatus] = None):
        self.request_headers = self.get_headers()
        self.cookies = self.get_cookies()
        self.status = ScrapingStatus() if status is None else status

    def _write_query_result_(self, dataset_name: str, info_dict: dict):
        output_filepath = str(
            self.status.output_root / f'{dataset_name}.csv')
        csv_header = list(info_dict.keys())
        with open(output_filepath, '+a') as fp:
            fp.writelines([','.join(
                (str(info_dict[k]) for k in csv_header)
            )+'\n'])

    def query_gene(self, dataset_name: str, gene_name: str):
        data = self.payload_from_gene_data(
            dataset=dataset_name, signature=gene_name,
            cutoff_1=67, cutoff_2=33
        )

        # gera PDF no server
        response = requests.post(
            'http://gepia2.cancer-pku.cn/assets/PHP4/survival_zf.php',
            data=data,
            verify=False,
            cookies=self.cookies,
            headers=self.request_headers)

        # baixa PDF
        response_dict = eval(response.content.decode())
        response = requests.get(
            f'http://gepia2.cancer-pku.cn/tmp/{response_dict["outdir"]}',
            cookies=self.cookies,
            headers=self.request_headers)

        pdf_data = self.read_pdf(response.content)
        info_dict = {'Gene': gene_name} | pdf_data

        self._write_query_result_(dataset_name, info_dict)

    def query_gene_safe(self, dataset_name: str, gene_name: str) -> bool:
        # TODO: maybe could be decorated
        try:
            self.query_gene(dataset_name, gene_name)
        except BaseException as e:
            ex = f'{type(e)}: {e}'
            args = (dataset_name, gene_name)
            tb = traceback.format_exc()

            msg = '\n'.join((
                f'Args {args} => {ex}.',
                f'{tb}'
            ))
            print(msg)  # TODO: logging.error
            return False
        else:
            return True

    @staticmethod
    def get_cookies():
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--log-level=OFF')

        driver = webdriver.Chrome(
            options=chrome_options,
            seleniumwire_options={
                'suppress_connection_errors': False,
                'service_log_path': 'NUL'
            }
        )

        driver.get('http://gepia2.cancer-pku.cn/#survival')
        cookies = requests.cookies.RequestsCookieJar()

        for cookie in driver.get_cookies():
            cookies.set(
                cookie['name'], cookie['value'],
                domain=cookie['domain'], path=cookie['path'])
        driver.close()

        return cookies

    @staticmethod
    def get_headers():
        with open('request_headers.json') as fp:
            return json.load(fp)

    @staticmethod
    def payload_from_gene_data(
        dataset: list[str], signature: str,
        cutoff_1: float, cutoff_2: float
    ) -> dict[str, str]:
        return {
            'methodoption': 'os',
            'dataset': dataset,
            'signature': signature,
            'highcol': '#ff0000',
            'lowcol': '#0000ff',
            'groupcutoff1': str(cutoff_1),
            'groupcutoff2': str(cutoff_2),
            'axisunit': 'month',
            'ifhr': 'hr',
            'ifconf': 'conf',
            'signature_norm': '',
            'is_sub': 'false',
            'subtype': '',
        }

    @staticmethod
    def read_pdf(pdf_bytes: bytes) -> dict[str, float | str]:
        return_keys = ('PValue', 'HR', 'Worse Prognosis')
        empty_return = {h: 'NA' for h in return_keys}

        pdf_bytes_str = str(pdf_bytes)
        if pdf_bytes_str.startswith('b\'<!DOCTYPE HTML'):
            return empty_return

        page = PyPDF2.PdfReader(io.BytesIO(pdf_bytes)).pages[0]
        page_content = page.extract_text()
        info = tuple(
            page_content[page_content.find('Logrank'):].split('\n')[:2])

        eval_str: tuple[str] = tuple(map(
            lambda x: x.split('=')[-1].replace(
                'e', '*10e').replace('−', '-'),
            info
        ))
        if any(map(lambda x: x == 'NaN', eval_str)):
            return empty_return

        pval, hr = tuple(map(
            lambda s: float(eval(s)), eval_str
        ))

        prognosis = 'NA'
        if (pval < .05):
            if (hr >= 1.):
                prognosis = 'High'
            else:
                prognosis = 'Low'

        return {
            'PValue': pval,
            'HR': hr,
            'Worse prognosis': prognosis
        }
