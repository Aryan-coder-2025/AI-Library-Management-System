import pytest
from app.services.copilot_agent import tool_visualize_3d_concept, execute_librarian_agent_rag
from app.models import User
from app.schemas import EnhancedCopilotResponse

def test_tool_visualize_3d_concept_neural_network():
    res = tool_visualize_3d_concept("neural network", title="Test Neural Net")
    assert res["status"] == "success"
    assert res["concept_type"] == "neural_network"
    assert "Neural" in res["title"]

def test_tool_visualize_3d_concept_transformer():
    res = tool_visualize_3d_concept("transformer multi-head attention")
    assert res["status"] == "success"
    assert res["concept_type"] == "transformer_architecture"
    assert "Transformer" in res["title"]

def test_tool_visualize_3d_concept_distributed_cluster():
    res = tool_visualize_3d_concept("distributed raft cluster")
    assert res["status"] == "success"
    assert res["concept_type"] == "distributed_cluster"
    assert "Raft" in res["title"]

def test_tool_visualize_3d_concept_quantum_bloch():
    res = tool_visualize_3d_concept("quantum bloch sphere")
    assert res["status"] == "success"
    assert res["concept_type"] == "quantum_bloch"
    assert "Bloch" in res["title"]

def test_tool_visualize_3d_concept_molecule():
    res = tool_visualize_3d_concept("benzene molecule structure")
    assert res["status"] == "success"
    assert res["concept_type"] == "molecule"
    assert "Benzene" in res["title"]

def test_execute_librarian_agent_rag_3d_routing(db):
    test_user = User(
        id=999,
        email="test_student@university.edu",
        full_name="Alice Student",
        role="student",
        is_active=True,
    )
    resp: EnhancedCopilotResponse = execute_librarian_agent_rag(
        db=db,
        query="visualize a 3D neural network for me",
        current_user=test_user,
    )
    assert resp.concept_3d is not None
    assert resp.concept_3d["concept_type"] == "neural_network"
    assert "3d" in resp.answer.lower()

def test_execute_librarian_agent_rag_concept_without_3d_request(db):
    test_user = User(
        id=999,
        email="test_student@university.edu",
        full_name="Alice Student",
        role="student",
        is_active=True,
    )
    resp: EnhancedCopilotResponse = execute_librarian_agent_rag(
        db=db,
        query="explain Transformers and multi-head attention",
        current_user=test_user,
    )
    # Strictly ensures no 3D model unless ordered by user!
    assert resp.concept_3d is None
    assert "transformer" in resp.answer.lower()
    assert any("3D" in f for f in resp.suggested_followups)
