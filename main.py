from multiprocessing import freeze_support
from typing import Optional
import psutil


import tqdm  # pip install tqdm
import logging

from scraper import Scraper, ScrapingStatus

from tqdm_multiprocess.logger import setup_logger_tqdm
logger = logging.getLogger(__name__)

from tqdm_multiprocess import TqdmMultiProcessPool  # pip install tqdm-multiprocess


def worker_fn(global_pbar, scraper, ds_name, gene_name):
    if scraper.query_gene_safe(ds_name, gene_name):
        global_pbar.update(ds_name)


def mp_fn(*a):
    global_pbar = a[-1]
    worker_args = a[:-2]
    worker_fn(global_pbar, *worker_args)
    return worker_args


def err_cb(worker_args):
    logger.error(
        f'An error occurred when processing {worker_args = }.'
    )


def suc_cb(worker_args): pass


class MultiTqdm:
    bars: dict[str, tqdm.tqdm]

    def __init__(
        self,
        tqdms_kwargs: list[dict[str]],
        global_bar_id: Optional[str] = None
    ):
        # TODO: make default total bar by summing args
        self.bars = dict()
        for kw in tqdms_kwargs:
            bar_id = kw['desc']
            self.bars[bar_id] = tqdm.tqdm(**kw)
        self.global_bar_id = global_bar_id

    def __enter__(self):
        for bar in self.bars.values():
            bar.__enter__()
        return self

    def __exit__(self, *a):
        for bar in self.bars.values():
            bar.__exit__(*a)

    def update(self, bar_id: Optional[str] = None, **update_kw):
        if bar_id and bar_id in self.bars:
            self.bars[bar_id].update(**update_kw)

        if self.global_bar_id:
            self.bars[self.global_bar_id].update(**update_kw)


def main():
    log_filepath = 'log.log'

    num_proc = psutil.cpu_count() * 4

    status = ScrapingStatus()

    tqdms_kwargs = [dict(
        desc='Total',
        total=len(status.datasets) * len(status.genes),
        initial=sum(map(
            lambda d: len(status.read_genes[d]),
            status.datasets))
    )]
    for ds_name in status.datasets:
        total = len(status.genes)
        done = len(status.read_genes[ds_name])
        if done < total:
            tqdms_kwargs.append(dict(
                desc=ds_name,
                total=total,
                initial=done
            ))
        else:
            logging.info(f'Dataset {ds_name} has already been processed.')  # TODO: fix this message
    tqdms_kwargs = [
        kw | dict(
            dynamic_ncols=True
        ) for kw in tqdms_kwargs
    ]

    scraper = Scraper(status)
    tasks = [
        (mp_fn, (scraper, *a)) for a in scraper.status._args_()
    ]

    setup_logger_tqdm(log_filepath)
    pool = TqdmMultiProcessPool(process_count=num_proc)
    with MultiTqdm(tqdms_kwargs, global_bar_id='Total') as global_progress:
        pool.map(global_progress, tasks, err_cb, suc_cb)


if __name__ == '__main__':
    freeze_support()
    main()
