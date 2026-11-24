"""Read trusted local model artifacts, including modules from before relocation."""
import pickle


class ForecastUnpickler(pickle.Unpickler):
    def __init__(self, stream, *, module_aliases):
        super().__init__(stream)
        self._module_aliases = module_aliases

    def find_class(self, module, name):
        for legacy, current in self._module_aliases.items():
            if module == legacy or module.startswith(legacy + "."):
                module = current + module[len(legacy):]
                break
        return super().find_class(module, name)
