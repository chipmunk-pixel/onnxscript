"""Registry for aten functions."""

from __future__ import annotations
import dataclasses

import inspect
from typing import Any, Callable, Optional

import onnxscript


@dataclasses.dataclass
class FunctionWithMeta:
    """Struct for an ONNX function and the associating metadata.

    Attributes:
        name: The registered name (e.g. "aten::add") of the function.
        function: A compiled OnnxFunction or a plain Python function.
        signature: The signature of the function.
    """

    name: str
    function: onnxscript.OnnxFunction | Callable
    signature: inspect.Signature


class OverloadedFunction:
    """Overloaded function."""

    def __init__(self, name: str):
        self.name = name
        self.default: Optional[FunctionWithMeta] = None
        self.overloads: list[FunctionWithMeta] = []

    def set_default(self, func: FunctionWithMeta) -> None:
        """Set the default function."""
        self.default = func

    def add_overload(self, func: FunctionWithMeta) -> None:
        """Add an overload."""
        self.overloads.append(func)


class Registry:
    """Registry for aten functions."""

    def __init__(self):
        # Mapping from registered name to the OverloadedFunction
        self._registry: dict[str, OverloadedFunction] = {}
        # Mapping from function name to the FunctionWithMeta
        self._name_to_function: dict[str, FunctionWithMeta] = {}

    def register(
        self, func: Any, aten_name: str, *, signature: inspect.Signature, overload: bool = False
    ) -> None:
        """Register a function."""
        overloaded_function = self._registry.setdefault(aten_name, OverloadedFunction(aten_name))

        function_with_meta = FunctionWithMeta(aten_name, function=func, signature=signature)
        if overload:
            overloaded_function.add_overload(function_with_meta)
        else:
            overloaded_function.set_default(function_with_meta)
        self._name_to_function[func.name] = function_with_meta

    def __getitem__(self, aten_name) -> OverloadedFunction:
        return self._registry[aten_name]

    def __contains__(self, aten_name) -> bool:
        return aten_name in self._registry

    def __iter__(self):
        return iter(self._registry)

    def __repr__(self):
        return repr(self._registry)

    def get_function_meta_by_name(self, name: str) -> FunctionWithMeta:
        """Get a function by its onnx function name (not the aten name)."""
        return self._name_to_function[name]


# Default registry
default_registry = Registry()


def torch_op(
    aten_name,
    *,
    overload: bool = False,
    registry: Optional[Registry] = None,
    trace_only: bool = False,
) -> Callable[[Callable[..., Any]], onnxscript.OnnxFunction | Callable[..., Any]]:
    """Register a torch op.

    Args:
        aten_name: The name of the aten function. E.g. "aten::add".
        overload: Whether the function is an overload (not default).
        registry: Registry to register the function to. If None, the default registry is used.
        trace_only: Whether the function should only be traced and not compiled.
    """
    if registry is None:
        registry = default_registry

    def wrapper(func: Callable[..., Any]) -> onnxscript.OnnxFunction | Callable[..., Any]:

        # Register the function signature
        signature = inspect.signature(func)

        if trace_only:
            processed_func = func
        else:
            # Compile the function
            custom_opset = onnxscript.values.Opset(domain="onnxscript.atenlib", version=1)
            processed_func = onnxscript.script(opset=custom_opset)(func)

        assert registry is not None
        registry.register(processed_func, aten_name, signature=signature, overload=overload)
        return processed_func

    return wrapper
