
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
