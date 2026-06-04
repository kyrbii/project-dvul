import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from models.messages import PlotCodeOutput
from backend.llm.plot_agent import get_plot_code, PlotCodeResult

def test_plotting_agent_self_correction():
    # 1. Create a dummy dataframe
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    
    # 2. Mock LLM instances
    mock_llm = MagicMock()
    
    # We will simulate a sequence of two invocations:
    # First invocation: Returns bad code that references a non-existent column "C"
    # Second invocation: Returns corrected code that references "A" and "B"
    bad_output = PlotCodeOutput(
        title="Bad Plot",
        code="import matplotlib.pyplot as plt\nplt.plot(df['C'])\n"
    )
    good_output = PlotCodeOutput(
        title="Good Plot",
        code="import matplotlib.pyplot as plt\nplt.plot(df['A'], df['B'])\n"
    )
    
    # Set the side_effect for invoke
    mock_llm.invoke.side_effect = [bad_output, good_output]
    
    # 3. Patch get_llm_instance to return our mock_llm
    with patch("backend.llm.plot_agent.get_llm_instance", return_value=mock_llm) as mock_get_inst:
        context = {
            "filename": "test.csv",
            "columns": ["A", "B"],
            "preview": df.head(1).to_dict(orient="records")
        }
        
        result: PlotCodeResult = get_plot_code(
            instructions="Plot C",
            context=context,
            model="test-model",
            local=False,
            df=df
        )
        
        # 4. Assertions
        # Verify that get_llm_instance was called
        mock_get_inst.assert_called()
        
        # Verify that mock_llm.invoke was called exactly twice (first failed, second corrected)
        assert mock_llm.invoke.call_count == 2
        
        # Verify result contains the final successful code and SVG data
        assert result.title == "Good Plot"
        assert "df['A']" in result.code
        assert result.svg is not None
        assert result.svg.startswith("<svg") or "svg" in result.svg
        assert result.error is None
        
        # Check the messages that were passed to the second invoke call
        calls = mock_llm.invoke.call_args_list
        second_call_messages = calls[1][0][0] # first arg of second call
        
        # There should be: SystemMessage, HumanMessage(Initial), AIMessage(Bad code), HumanMessage(Error details)
        assert len(second_call_messages) == 4
        assert isinstance(second_call_messages[2], AIMessage)
        assert "plt.plot(df['C'])" in second_call_messages[2].content
        assert isinstance(second_call_messages[3], HumanMessage)
        assert "Sandbox Error" in second_call_messages[3].content
        assert "'C'" in second_call_messages[3].content

if __name__ == "__main__":
    test_plotting_agent_self_correction()
    print("Self-correction test PASSED successfully!")
