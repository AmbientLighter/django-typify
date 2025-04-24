from django_typify.stubgen import generate_stub_lines


def test_generate_stub_lines():
    annotations = {
        "Network": [("rbac_policies", "NetworkRBACPolicy")],
        "Instance": [("ports", "Port")],
    }

    lines = generate_stub_lines(annotations)
    assert "class Network:" in lines
    assert "    rbac_policies: models.Manager['NetworkRBACPolicy']" in lines
