from repository.chatbot_repository import ChatbotRepository
from services.simulation_services import SimulationFeedback


def test_update_session_context_with_simulation_appends_rendered_feedback():
    repository = ChatbotRepository(db=None)
    repository.start_session("Initial briefing")
    repository.messages.append({"role": "assistant", "content": "Ready."})

    messages = repository.update_session_context_with_simulation(
        SimulationFeedback(affected_points=3, average_cooling_c=-1.25)
    )

    content = messages[-1]["content"][0]["text"]
    assert messages[-1]["role"] == "user"
    assert "<briefing-update>" in content
    assert "<<<SIMULATION RESULT>>>" in content
    assert "Affected readings: 3" in content