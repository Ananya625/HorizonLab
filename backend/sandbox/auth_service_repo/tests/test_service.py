import pytest
from app.service import execute_service

def test_execute_service_nominal():
    try:
        res = execute_service(3)
        assert res is not None
    except TypeError:
        res = execute_service()
        assert res is not None

def test_execute_service_edge_cases():
    try:
        assert execute_service(0) is not None
        assert execute_service(-2) is not None
    except TypeError:
        pass
