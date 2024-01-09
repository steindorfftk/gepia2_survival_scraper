import pathlib

from scraping_utils import (
    read_txt_lines,
    read_processed_genes
)


class ScrapingStatus:
    output_root: str
    genes: list[str]
    datasets: list[str]
    read_genes: dict[str, set[str]]

    def __init__(self):
        self._init_output_dir_()
        self.genes = read_txt_lines('genes.txt')
        self.datasets = read_txt_lines('datasets.txt')
        self._init_read_genes_()

    def _init_output_dir_(self) -> pathlib.Path:
        d = pathlib.Path.cwd() / 'output'
        d.mkdir(parents=True, exist_ok=True)
        self.output_root = d

    def _init_read_genes_(self) -> dict[str, set[str]]:
        csv_header = ['Gene', 'PValue', 'HR', 'Worse prognosis']
        self.read_genes = dict()
        for dataset_name in self.datasets:
            output_filename = str(self.output_root / f'{dataset_name}.csv')

            if not pathlib.Path(output_filename).exists():
                with open(output_filename, 'a') as fp:
                    fp.writelines([','.join(csv_header)+'\n'])
            else:
                self.read_genes[dataset_name] = read_processed_genes(
                    output_filename)

    def _args_per_dataset_(self, dataset_name):
        genes_it = iter(self.genes)
        if dataset_name in self.read_genes:
            genes_it = filter(
                lambda x: x not in self.read_genes[dataset_name],
                genes_it)
        return genes_it



    def _args_(self):
        for dataset_name in self.datasets:
            for gene_name in self._args_per_dataset_(dataset_name):
                yield (
                    dataset_name,
                    gene_name
                )
