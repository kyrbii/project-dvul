from models.messages import PlotCodeOutput
from backend.llm import llm_instance


def test_get_llm_instance_with_structured_output_monkeypatched(monkeypatch):
    class DummyLLM:
        def __init__(self, *args, **kwargs):
            self._wrapped = False

        def with_structured_output(self, model):
            self._wrapped = True
            self._model = model
            return self

    monkeypatch.setattr(llm_instance, "ChatOpenAI", DummyLLM)

    inst = llm_instance.get_llm_instance(local=False, model_name="m", api_key="k", structured_output_model=PlotCodeOutput)
    assert isinstance(inst, DummyLLM)
    assert getattr(inst, "_wrapped", False) is True
    assert getattr(inst, "_model", None) is PlotCodeOutput


def test_get_llm_instance_without_with_structured(monkeypatch):
    class DummyLLMNoWrap:
        def __init__(self, *args, **kwargs):
            self.created = True

    monkeypatch.setattr(llm_instance, "ChatOpenAI", DummyLLMNoWrap)

    inst = llm_instance.get_llm_instance(local=False, model_name="m", api_key="k", structured_output_model=PlotCodeOutput)
    assert isinstance(inst, DummyLLMNoWrap)
