from multiprocessing import Pool
from scraper import Scraper


if __name__ == '__main__':
    scraper = Scraper()

    total_queries = len(scraper.datasets) * len(scraper.genes)
    done_queries = sum(map(len, scraper.read_genes.values()))
    done_queries_perc = 100 * done_queries / total_queries
    print(f'Done {done_queries}/{total_queries} ({done_queries_perc:.2f}%) queries')

    with Pool() as pool:
        pool.starmap(
            func=scraper.query_gene_safe,
            iterable=scraper._map_args_iter_())
