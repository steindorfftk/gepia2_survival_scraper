from scraper import Scraper


scraper = Scraper()

args = [
    ('PCPG', 'GRK6'),
]
for a in args:
    scraper.query_gene_safe(*a)
