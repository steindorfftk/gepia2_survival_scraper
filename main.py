from multiprocessing import freeze_support
import tqdm  # pip install tqdm

import logging
from tqdm_multiprocess.logger import setup_logger_tqdm
logger = logging.getLogger(__name__)

from tqdm_multiprocess import TqdmMultiProcessPool  # pip install tqdm-multiprocess

from scraper import Scraper, ScrapingStatus


def worker_fn(scraper, ds_name, worker_pbar, global_pbar):
    for gene_name in scraper.status._args_per_dataset_(ds_name):
        if scraper.query_gene_safe(ds_name, gene_name):
            worker_pbar.update()
            global_pbar.update()


def mp_fn(*a):
    pbar_init, global_pbar = a[-2:]
    scraper, ds_name = a[:-2]
    with pbar_init(
        total=len(scraper.status.genes),
        initial=len(scraper.status.read_genes[ds_name]),
        dynamic_ncols=True
    ) as worker_pbar:
        worker_pbar.set_description(ds_name.upper())

        worker_fn(scraper, ds_name, worker_pbar, global_pbar)
    return ds_name


def err_cb(ds_name):
    logger.error(
        f'An error occurred when processing dataset {ds_name}.'
    )


def suc_cb(ds_name):
    logger.info(
        f'Processing of dataset {ds_name} has finished.'
    )


def main():
    scraper = Scraper(ScrapingStatus())

    setup_logger_tqdm('log.log')
    pool = TqdmMultiProcessPool(process_count=8)

    tqdm_args = dict(
        total=len(scraper.status.datasets) * len(scraper.status.genes),
        initial=sum(map(len, scraper.status.read_genes.values())),
        dynamic_ncols=True
    )

    tasks = [
        (mp_fn, (scraper, ds_name)) for ds_name in scraper.status.datasets
    ]

    with tqdm.tqdm(**tqdm_args) as global_progress:
        global_progress.set_description('Total')

        pool.map(global_progress, tasks, err_cb, suc_cb)


if __name__ == '__main__':
    freeze_support()
    main()
