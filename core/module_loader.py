import importlib
import pkgutil
import traceback

LOADED_MODULES = {}

def load_modules(package="modules"):
    global LOADED_MODULES

    LOADED_MODULES = {}

    try:
        pkg = importlib.import_module(package)

        for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
            try:
                module = importlib.import_module(
                    f"{package}.{module_name}"
                )

                if hasattr(module, "register"):
                    LOADED_MODULES[module_name] = module.register()

                    print(
                        f"[MODULE] Loaded: {module_name}"
                    )

            except Exception:
                print(
                    f"[MODULE ERROR] {module_name}"
                )
                traceback.print_exc()

    except Exception:
        traceback.print_exc()

    return LOADED_MODULES
