import io
import json
import pathlib
import traceback

import requests  # pip install requests
import tqdm  # pip install tqdm

import PyPDF2  # pip install PyPDF2
from seleniumwire import webdriver  # pip install selenium-wire


def read_processed_genes(filepath: str) -> set[str]:
    genes = set()
    with open(filepath) as fp:
        fp.readline()  # skip header
        for line in fp.readlines():
            line = line.strip()
            if len(line) > 0:
                gene = line.split(',')[0]
                genes.add(gene)
    return genes


def read_txt_lines(filepath: str) -> list[str]:
    data = []
    with open(filepath) as text:
        for line in text.readlines():
            line = line.strip()
            if len(line) > 0:
                data.append(line)
    return data


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


def get_headers():
    with open('request_headers.json') as fp:
        return json.load(fp)


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


class Scraper:
    OUTPUT_DIR: str

    genes: list[str]
    datasets: list[str]
    read_genes: dict[str, set[str]]

    cookies: dict[str, str]
    request_headers: dict

    def __init__(self):
        self.OUTPUT_DIR = self._init_output_dir_()

        self.genes = read_txt_lines('genes.txt')
        self.datasets = read_txt_lines('datasets.txt')
        self.read_genes = self._init_read_genes_()

        self.cookies = get_cookies()
        self.request_headers = get_headers()

    def _init_output_dir_(self) -> pathlib.Path:
        d = pathlib.Path.cwd() / 'output'
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _init_read_genes_(self) -> dict[str, set[str]]:
        csv_header = ['Gene', 'PValue', 'HR', 'Worse prognosis']
        read_genes: dict[str, set[str]] = {}
        for dataset_name in self.datasets:
            output_filename = str(self.OUTPUT_DIR / f'{dataset_name}.csv')

            if not pathlib.Path(output_filename).exists():
                with open(output_filename, 'a') as fp:
                    fp.writelines([','.join(csv_header)+'\n'])
            else:
                read_genes[dataset_name] = read_processed_genes(
                    output_filename)
        return read_genes

    def query_gene(self, dataset_name: str, gene_name: str):
        data = payload_from_gene_data(
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

        pdf_data = read_pdf(response.content)
        info_dict = {'Gene': gene_name} | pdf_data

        output_filepath = str(
            self.OUTPUT_DIR / f'{dataset_name}.csv')
        csv_header = list(info_dict.keys())
        with open(output_filepath, '+a') as fp:
            fp.writelines([','.join(
                (str(info_dict[k]) for k in csv_header)
            )+'\n'])

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
