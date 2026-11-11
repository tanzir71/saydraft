"""Lightweight IDs for explicitly installed cleanup runtimes."""

RUNTIME_MODELS = {
    "cpu": "llama-cpp-b12110-cpu-x64",
    "vulkan": "llama-cpp-b12110-vulkan-x64",
}


def runtime_model_id(backend):
    try:
        return RUNTIME_MODELS[backend]
    except (KeyError, TypeError) as error:
        raise ValueError("Choose the CPU or Vulkan cleanup runtime") from error
