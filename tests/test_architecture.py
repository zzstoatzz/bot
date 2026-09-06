"""Architecture drift checks protect the public model's source claims."""

from bot.core.architecture import (
    ROOT,
    architecture_model,
    source_inventory,
    specification,
)


def test_model_has_resolvable_connections_and_source_anchors():
    spec = specification()
    ids = {n.id for n in spec.nodes}
    assert len(ids) == len(spec.nodes)
    assert {"semble", "atlas", "memory", "encounters", "journal", "prefect"} <= ids
    occupied = {(n.lane, n.row) for n in spec.nodes}
    assert len(occupied) == len(ids)
    for edge in spec.edges:
        assert edge.source in ids and edge.target in ids
    for node in spec.nodes:
        assert node.sources
        for source in node.sources:
            if source.repo == "bot":
                assert (ROOT / source.path).is_file(), source.path
    model = architecture_model()
    assert all(
        s["evidence"] != "symbol not found"
        for n in model["nodes"]
        for s in n["sources"]
    )


def test_unfinished_reader_is_not_presented_as_running():
    model = architecture_model()
    reader = next(n for n in model["nodes"] if n["id"] == "reader")
    assert reader["status"] == "planned"
    assert all(e["planned"] for e in model["edges"] if e["source"] == "reader")
    assert "not a service health check" in model["basis"]


def test_inventory_is_derived_and_runtime_configuration_is_allowlisted():
    modules = source_inventory()
    agent = next(m for m in modules if m["path"] == "src/bot/agent.py")
    assert "bot.config" in agent["imports"]
    assert any(
        f["name"] == "process_cycle" and f["line"] > 0 for f in agent["functions"]
    )
    model = architecture_model()
    assert "choose-influences" in model["skills"]
    assert "inject_self" in {f["name"] for f in model["prompt_blocks"]}
    assert set(model["configuration"]) == {
        "main_model",
        "policy_model",
        "memory_model",
        "etiquette",
        "prefect_authenticated",
        "semble_writes_configured",
    }
