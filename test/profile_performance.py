from biocypher.create import BioCypherEdge, BioCypherNode
from biocypher.driver import Driver
from biocypher.utils import bcolors
import random
import cProfile, pstats, io
import timeit, pickle


def create_network_by_gen(num_nodes, num_edges, profile=False):
    d = Driver(version=False)

    def node_gen(num_nodes):
        for i in range(num_nodes):
            yield BioCypherNode(i, "test")

    def edge_gen(num_edges):
        for _ in range(num_edges):
            src = random.randint(1, num_nodes)
            tar = random.randint(1, num_nodes)

            yield BioCypherEdge(src, tar, "test")

    node_profile, np_printout = d.add_biocypher_nodes(
        node_gen(num_nodes), profile=profile
    )
    edge_profile, ep_printout = d.add_biocypher_edges_mod(
        edge_gen(num_edges), profile=profile
    )

    if profile:
        delete_test_network()
        d.add_biocypher_nodes(node_gen(num_nodes), profile=False)
        edge_profile_mod, epm_printout = d.add_biocypher_edges_mod(
            edge_gen(num_edges), profile=profile
        )
        return (
            (node_profile, np_printout),
            (edge_profile, ep_printout),
            (edge_profile_mod, epm_printout),
        )

    d.close()


def create_network_by_list(num_nodes, num_edges, mod=False):
    d = Driver(version=False)

    def node_list(num_nodes):
        ls = []
        for i in range(num_nodes):
            ls.append(BioCypherNode(i, "test"))

        return ls

    def edge_list(num_edges):
        ls = []
        for _ in range(num_edges):
            src = random.randint(1, num_nodes)
            tar = random.randint(1, num_nodes)
            ls.append(BioCypherEdge(src, tar, "test"))

        return ls

    d.add_biocypher_nodes(node_list(num_nodes))
    if mod:
        d.add_biocypher_edges_mod(edge_list(num_edges))
    else:
        d.add_biocypher_edges(edge_list(num_edges))

    d.close()


def setup_constraint():
    d = Driver(version=False)
    d.query(
        "CREATE CONSTRAINT test_id "
        "IF NOT EXISTS ON (n:test) "
        "ASSERT n.id IS UNIQUE "
    )
    d.close()


def remove_constraint():
    d = Driver(version=False)
    d.query("DROP CONSTRAINT test_id")
    d.close()


def delete_test_network():
    d = Driver(version=False)
    d.query("MATCH (n)-[:test]-() DETACH DELETE n")
    d.query("MATCH (n:test) DETACH DELETE n")
    d.close()


def create_networks():
    seq = (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000)
    res = dict()

    for n in seq:
        lis = timeit.timeit(
            lambda: create_network_by_list(n, int(n * 1.5)), number=1
        )
        delete_test_network()
        lism = timeit.timeit(
            lambda: create_network_by_list(n, int(n * 1.5), mod=True), number=1
        )
        delete_test_network()

        res.update({"lis%s" % n: lis, "lism%s" % n: lism})

    with open("benchmark.pickle", "wb") as f:
        pickle.dump(res, f)

    print(res)


def visualise_benchmark():
    import matplotlib.pyplot as plt
    import pickle

    with open("benchmark.pickle", "rb") as f:
        res = pickle.load(f)

    x = [key for key in res.keys() if "lism" in key]
    x = [int(e.replace("lism", "")) for e in x]
    lis = [value for key, value in res.items() if "lism" not in key]
    lism = [value for key, value in res.items() if "lism" in key]

    plt.plot(x, lis, marker="o", label="List")
    plt.plot(x, lism, marker="o", label="List (modified)")
    plt.xlabel("Network size (nodes)")
    plt.ylabel("Time (s)")
    plt.legend()
    plt.show()


def profile_neo4j(num_nodes, num_edges):

    np, ep, epm = create_network_by_gen(num_nodes, num_edges, profile=True)
    print("")
    print(f"{bcolors.HEADER}### NODE PROFILE ###{bcolors.ENDC}")
    for p in np[1]:
        print(p)
    print("")
    print(f"{bcolors.HEADER}### EDGE PROFILE ###{bcolors.ENDC}")
    for p in ep[1]:
        print(p)
    print("")
    print(f"{bcolors.HEADER}### MODIFIED EDGE PROFILE ###{bcolors.ENDC}")
    for p in epm[1]:
        print(p)


if __name__ == "__main__":
    python_prof = False
    neo4j_prof = False
    run = False
    viz = True

    # setup
    setup_constraint()

    if python_prof:
        profile = cProfile.Profile()
        profile.enable()

    if run:
        create_networks()

    if python_prof:
        profile.disable()

        s = io.StringIO()
        sortby = pstats.SortKey.CUMULATIVE
        ps = pstats.Stats(profile, stream=s).sort_stats(sortby)
        ps.print_stats()
        # print(s.getvalue())
        filename = "create_network.prof"
        ps.dump_stats(filename)

    if viz:
        visualise_benchmark()

    if neo4j_prof:
        profile_neo4j(num_nodes=10, num_edges=15)
        """
        Eager execution of the apoc.merge.relationships is the primary 
        holdup for this function. More info about Eager here: 
        https://community.neo4j.com/t/cypher-sleuthing-the-eager-operator/10730
        and here:
        https://neo4j.com/docs/cypher-manual/current/execution-plans/operators/#query-plan-eager

        She says: "In order to get around the eager operator, we need to 
        ensure Cypher isn’t worried about conflicting operations. The 
        best way to do this is to divide our query into single 
        operations so that Cypher won’t invoke eager as a safeguard. 
        Let’s profile this as two queries to see that."

        Essentially, I think this means that Neo4j waits for the MERGE
        performed on the source and target nodes before going on to the 
        WITH statement.

        Updated to MERGE the nodes and edges in separate queries in the 
        function `create_biocypher_edges_mod()`; it returns only the 
        results of the edge query, not the node merge.
        """

    # teardown
    delete_test_network()
    remove_constraint()
