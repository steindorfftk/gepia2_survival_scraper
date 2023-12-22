# import asyncio
# import csv
# import time
import json
from multiprocessing import Pool
import requests  # pip install requests
import io
import pathlib
import random

import PyPDF2  # pip install PyPDF2
from seleniumwire import webdriver  # pip install selenium-wire

import logging

logger = logging.getLogger('scraper')
logging_level = logging.DEBUG
logger.setLevel(logging_level)

handler = logging.StreamHandler()
handler.setLevel(logging_level)

handler.setFormatter(
    logging.Formatter("%(name)s;%(asctime)s;%(levelname)s;%(message)s"))
logger.addHandler(handler)

OUTPUT_DIR: str


def read_processed_genes(filepath: str) -> set[str]:
    genes = set()
    with open(filepath) as fp:
        fp.readline()
        for line in fp.readlines():
            gene = line.strip().split(',')[0]
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
    pdf_bytes_str = str(pdf_bytes)
    if pdf_bytes_str.startswith('b\'<!DOCTYPE HTML'):
        return {h: 'NA' for h in ('PValue', 'HR', 'Worse Prognosis')}

    page = PyPDF2.PdfReader(io.BytesIO(pdf_bytes)).pages[0]
    page_content = page.extract_text()

    info = page_content[page_content.find('Logrank'):].split('\n')[:5]
    pval, hr = tuple(map(
        lambda x: float(eval(str(
            x.split('=')[-1].replace('e', '*10e').replace('−', '-')
        ))), info
    ))[:2]

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


def query_gene(
    OUTPUT_DIR, cookies, request_headers: list[str],
    dataset_name: str, gene_name: str
):
    gene_name = gene_name
    logger.debug(f'Starting {gene_name} on {dataset_name}')

    data = payload_from_gene_data(
        dataset=dataset_name, signature=gene_name,
        cutoff_1=67, cutoff_2=33
    )

    # gera PDF no server
    response = requests.post(
        'http://gepia2.cancer-pku.cn/assets/PHP4/survival_zf.php',
        data=data,
        verify=False,
        cookies=cookies,
        headers=request_headers)

    # baixa PDF
    # time.sleep(.1)  # to avoid timeouts
    response_dict = eval(response.content.decode())
    response = requests.get(
        f'http://gepia2.cancer-pku.cn/tmp/{response_dict["outdir"]}',
        cookies=cookies,
        headers=request_headers)

    try:
        pdf_data = read_pdf(response.content)
    except Exception as e:
        logging.error(
            f'Caught exception {e} '+
            f'when running {gene_name} on {dataset_name}. '
            'Ignoring case...')
    info_dict = {'Gene': gene_name} | pdf_data

    logger.debug(f'Finished querying {info_dict["Gene"]} on {dataset_name}')

    output_filepath = str(OUTPUT_DIR / f'{dataset_name}.csv')
    csv_header = list(info_dict.keys())
    with open(output_filepath, '+a') as fp:
        fp.writelines([','.join(
            (str(info_dict[k]) for k in csv_header)
        )+'\n'])
    logger.debug(
        f'Finished writing {info_dict["Gene"]} on ' +
        f'{dataset_name} output file')


def args_iter(
    cookies, headers: list[str],
    datasets: list[str], genes: list[str],
    read_genes: list[str],
    OUTPUT_DIR: str
):
    for dataset_name in datasets:
        if dataset_name in read_genes:
            genes_it = filter(lambda x: x not in read_genes, genes)
        else:
            genes_it = iter(genes)
        for gene_name in genes_it:
            yield (
                OUTPUT_DIR, cookies, headers,
                dataset_name,
                gene_name
            )


def main():
    logger.info('Starting!')

    # setup
    OUTPUT_DIR = pathlib.Path.cwd() / 'output'
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    genes = read_txt_lines('genes.txt')
    datasets = read_txt_lines('datasets.txt')

    cookies = get_cookies()
    with open('request_headers.json') as fp:
        headers = json.load(fp)

    # exec
    # limits = (5, 2)
    # limits = (10, 10)
    # limits = (20, 20)
    limits = (100, 100)
    datasets = random.sample(datasets, min(limits[0], len(datasets)))
    genes = random.sample(genes, min(limits[1], len(genes)))

    # creates output files
    csv_header = ['Gene', 'PValue', 'HR', 'Worse prognosis']
    read_genes: dict[str, set[str]] = {}
    for dataset_name in datasets:
        output_filename = str(OUTPUT_DIR / f'{dataset_name}.csv')

        if not pathlib.Path(output_filename).exists():
            with open(output_filename, 'a') as fp:
                fp.writelines([','.join(csv_header)+'\n'])
                fp.flush()
        else:
            read_genes[dataset_name] = read_processed_genes(output_filename)

    try:
        with Pool() as p:  # TODO: wait for tasks after loop
            p.starmap(
                query_gene,
                args_iter(
                    cookies, headers,
                    datasets, genes, read_genes, OUTPUT_DIR)
            )
            logger.debug("Finished creating tasks")
    except KeyboardInterrupt:
        exit(-1)
    else:
        logger.info('Exiting!')
        exit()


if __name__ == '__main__':
    main()
