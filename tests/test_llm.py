def test_llm_returns_response(mocker):
    mocker.patch(
        "backend.llm.service.get_llm_response",
        return_value=(
            {"filename": "test.csv", "dataframe": None},
            {"bot_message": "Die Daten zeigen..."}
        )
    )
    from backend.llm.service import get_llm_response
    chat_store, response = get_llm_response({}, "Analysiere die Daten")
    assert response["bot_message"] is not None

def test_llm_empty_message(mocker):
    mocker.patch(
        "backend.llm.service.get_llm_response",
        return_value=(
            {"filename": "test.csv", "dataframe": None},
            {"bot_message": ""}
        )
    )
    from backend.llm.service import get_llm_response
    chat_store, response = get_llm_response({}, "")
    assert response["bot_message"] == ""