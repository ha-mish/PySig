import json
from urllib.request import Request, urlopen

import pytest


pytestmark = pytest.mark.ui


def test_model_api_returns_json(studio_server):
    with urlopen(studio_server["url"] + "/api/model") as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert "model" in payload
    assert "summary" in payload


def test_validate_api_reports_missing_arm(studio_server):
    body = json.dumps(
        {
            "model": {
                "intersections": [{"id": "I1", "arms": []}],
                "lanes": [
                    {"id": "L1", "intersection_id": "I1", "arm_id": "MISSING"}
                ],
            }
        }
    ).encode("utf-8")
    request = Request(
        studio_server["url"] + "/api/validate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert payload["valid"] is False
    assert "missing arm" in payload["errors"][0].lower()
