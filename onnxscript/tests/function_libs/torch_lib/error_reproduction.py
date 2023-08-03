from __future__ import annotations

import pathlib
import platform
import sys
import time
import traceback
from typing import Any, Mapping

import numpy as np
import onnx
import onnxruntime as ort
import torch

_REPRODUCTION_TEMPLATE = '''\
import google.protobuf.text_format
import numpy as np
from numpy import array, float16, float32, float64, int32, int64
import onnx
import onnxruntime as ort

# Run n times
N = 1

onnx_model_text = """
{onnx_model_text}
"""

ort_inputs = {ort_inputs}

# Set up the inference session
session_options = ort.SessionOptions()
session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
onnx_model = onnx.ModelProto()
google.protobuf.text_format.Parse(onnx_model_text, onnx_model)

# Uncomment this line to save the model to a file for examination
# onnx.save_model(onnx_model, "{short_test_name}.onnx")

onnx.checker.check_model(onnx_model)
session = ort.InferenceSession(onnx_model.SerializeToString(), session_options, providers=("CPUExecutionProvider",))

# Run the model
for _ in range(N):
    ort_outputs = session.run(None, ort_inputs)
'''

_ISSUE_MARKDOWN_TEMPLATE = """
### Summary

ONNX Runtime raises `{error_text}` when executing test `{test_name}` in ONNX Script `TorchLib`.

To recreate this report, use

```bash
CREATE_REPRODUCTION_REPORT=1 python -m pytest onnxscript/tests/function_libs/torch_lib/ops_test.py -k {short_test_name}
```

### To reproduce

```python
{reproduction_code}
```

### Full error stack

```
{error_stack}
```

### Environment

```
{sys_info}
```
"""


def create_reproduction_report(
    test_name: str,
    onnx_model: onnx.ModelProto,
    ort_inputs: Mapping[str, Any],
    error: Exception,
) -> None:
    onnx_model_text = str(onnx_model)
    with np.printoptions(threshold=sys.maxsize):
        ort_inputs = dict(ort_inputs.items())
        input_text = str(ort_inputs)
    error_text = str(error)
    error_stack = error_text + "\n" + "".join(traceback.format_tb(error.__traceback__))
    sys_info = f"""\
OS: {platform.platform()}
Python version: {sys.version}
onnx=={onnx.__version__}
onnxruntime=={ort.__version__}
numpy=={np.__version__}
torch=={torch.__version__}
"""
    short_test_name = test_name.split(".")[-1]
    reproduction_code = _REPRODUCTION_TEMPLATE.format(
        onnx_model_text=onnx_model_text,
        ort_inputs=input_text,
        short_test_name=short_test_name,
    )

    markdown = _ISSUE_MARKDOWN_TEMPLATE.format(
        error_text=error_text,
        test_name=test_name,
        short_test_name=short_test_name,
        reproduction_code=reproduction_code,
        error_stack=error_stack,
        sys_info=sys_info,
    )

    # Turn test name into a valid file name
    markdown_file_name = f'{test_name.split(".")[-1].replace("/", "-").replace(":", "-")}-{str(time.time()).replace(".", "_")}.md'
    reports_dir = pathlib.Path("error_reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    with open(reports_dir / markdown_file_name, "w", encoding="utf-8") as f:
        f.write(markdown)
