import os
import random
import string
import tempfile

import pytest

from biocypher._core import BioCypher
from biocypher._create import BioCypherNode


def get_random_string(length):

    # choose from all lowercase letter
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(length))


def _get_nodes(l: int) -> list:
    nodes = []
    for i in range(l):
        bnp = BioCypherNode(
            node_id=f'p{i+1}',
            node_label='protein',
            preferred_id='uniprot',
            properties={
                'score': 4 / (i + 1),
                'name': 'StringProperty1',
                'taxon': 9606,
                'genes': ['gene1', 'gene2'],
            },
        )
        nodes.append(bnp)
        bnm = BioCypherNode(
            node_id=f'm{i+1}',
            node_label='microRNA',
            preferred_id='mirbase',
            properties={
                'name': 'StringProperty1',
                'taxon': 9606,
            },
        )
        nodes.append(bnm)

    return nodes


# temporary output paths
@pytest.fixture
def path():
    path = os.path.join(
        tempfile.gettempdir(),
        f'biocypher-test-{get_random_string(5)}',
    )
    os.makedirs(path, exist_ok=True)
    return path


@pytest.fixture
def core(path):
    bc = BioCypher()
    bc.output_directory = path
    return bc


def test_biocypher(core):
    assert core.dbms == 'neo4j'
    assert core.offline == True
    assert core.strict_mode == False


def test_write_node_data_from_gen(core, path):
    nodes = _get_nodes(4)

    def node_gen(nodes):
        yield from nodes

    passed = core.write_nodes(node_gen(nodes))

    p_csv = os.path.join(path, 'Protein-part000.csv')
    m_csv = os.path.join(path, 'MicroRNA-part000.csv')

    with open(p_csv) as f:
        pr = f.read()

    with open(m_csv) as f:
        mi = f.read()

    assert passed
    assert "p1;'StringProperty1';4.0;9606;'gene1|gene2';'p1';'uniprot'" in pr
    assert 'BiologicalEntity' in pr
    assert "m1;'StringProperty1';9606;'m1';'mirbase'" in mi
    assert 'ChemicalEntity' in mi
